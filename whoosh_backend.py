from collections import defaultdict

from haystack.backends import whoosh_backend as original_backend
from haystack.backends import BaseEngine

from whoosh import analysis, fields, highlight, query, scoring
from whoosh.reading import TermNotFound
from whoosh.support.levenshtein import distance
from whoosh.writing import AsyncWriter

def CUSTOM_MERGE_SMALL(writer, segments):
    """This policy merges small segments, where "small" is defined using a
    fixed number of documents. Unlike whoosh.filedb.filewriting.MERGE_SMALL,
    this one does nothing unless there's more than one segment to merge.
    """

    from whoosh.filedb.filereading import SegmentReader
    unchanged_segments = []
    segments_to_merge = []

    for segment in segments:
        if segment.doc_count_all() < 10000:
            segments_to_merge.append(segment)
        else:
            unchanged_segments.append(segment)
    
    if len(segments_to_merge) > 1:
        for segment in segments_to_merge:
            with SegmentReader(writer.storage, writer.schema, segment) as reader:
                writer.add_reader(reader)
    else:
        # don't bother merging a single segment
        unchanged_segments.extend(segments_to_merge)
    
    return unchanged_segments

class WriterWithFasterSpellingUpdate(AsyncWriter):
    def __init__(self, spelling_storage, spelling_checker, spelling_fields,
        index, delay=0.25, writerargs=None):
        
        super(WriterWithFasterSpellingUpdate, self).__init__(index, delay,
            writerargs)
        self.spelling_storage = spelling_storage
        self.spelling_checker = spelling_checker
        self.spelling_fields  = spelling_fields
        
    def update_document(self, **doc):
        # remove every word previously found in the document from the
        # spelling index
        
        from haystack.constants import ID
        
        super(WriterWithFasterSpellingUpdate, self).update_document(**doc)

        document_schema = self.index.schema
        for fieldname in self.spelling_fields:
            field = document_schema[fieldname]
            
            """
            def generate_words():
                for w, freq, weight, valuestring in field.index(doc[fieldname]):
                    yield w
            """

            if fieldname in doc:
                words = [w for w, freq, weight, valuestring 
                    in field.index(doc[fieldname])]
                
                self.spelling_checker.add_words(words)

class CustomWhooshBackend(original_backend.WhooshSearchBackend):
    silently_fail = False
    
    def setup(self):
        super(CustomWhooshBackend, self).setup()
        self.spelling_fields = (self.content_field_name, 'job_title')

    def get_writer(self, index):
        return WriterWithFasterSpellingUpdate(self.storage, 
            self.get_spell_checker(), self.spelling_fields, index)
    
    """
    def update(self, index, iterable, commit=True):
        import pdb; pdb.set_trace();
        super(CustomWhooshBackend, self).update(index, iterable, commit)
    """

    def update_spelling(self):
        pass
        """
        import pdb; pdb.set_trace()
        sp = self.get_spell_checker()
        sp.add_field(self.index, self.content_field_name)
        sp.add_field(self.index, 'job_title')
        """
        
    def search(self, query_string, sort_by=None, start_offset=0, end_offset=None,
               fields='', highlight=False, facets=None, date_facets=None, query_facets=None,
               narrow_queries=None, spelling_query=None, within=None,
               dwithin=None, distance_point=None, models=None,
               limit_to_registered_models=None, result_class=None, **kwargs):
        
        # needed to initialise self.parser, and will be called anyway
        # by superclass search() method if not already done, so no harm
        # in doing it here.
        self.setup()
        
        from binder.monkeypatch import before
        @before(self.parser, 'parse')
        def log_final_query_string(final_query_string):
            import logging
            logger = logging.getLogger(__name__)
            logger.debug(final_query_string)
            
        #import logging
        #logger = logging.getLogger(__name__)
        #logger.debug(query_string)
        
        return super(CustomWhooshBackend, self).search(query_string, sort_by,
            start_offset, end_offset, fields, highlight, facets, date_facets,
            query_facets, narrow_queries, spelling_query, within, dwithin,
            distance_point, models, limit_to_registered_models, result_class,
            **kwargs)
    
    def create_spelling_suggestion(self, query_string):
        if not self.setup_complete:
            self.setup()
        # import pdb; pdb.set_trace()
        return super(CustomWhooshBackend, self).create_spelling_suggestion(query_string)
    
    def _process_results(self, raw_page, highlight=False, query_string='',
        spelling_query=None, result_class=None):
        """
        Turn off the automatic call to create_spelling_suggestion(), as
        it's wasteful and wrong for all but the simplest queries.
        
        If the caller wants a search suggestion, they'll have to ask for it
        by calling CustomWhooshSearchQuery.get_spelling_suggestion(), which
        Haystack does if you call SearchQuerySet.spelling_suggestion().
        """
        old_include_spelling = self.include_spelling
        self.include_spelling = False
        
        result = super(CustomWhooshBackend, self)._process_results(raw_page,
            highlight, query_string, spelling_query, result_class)
        
        self.include_spelling = old_include_spelling
        return result

    def schema_field_for_haystack_field(self, field_name, field_class):
        """
        Override to disable stemming on TEXT fields.
        """
        
        schema_field = super(CustomWhooshBackend,
            self).schema_field_for_haystack_field(field_name, field_class)
        from whoosh.fields import TEXT
        
        if isinstance(schema_field, TEXT):
            return TEXT(stored=True, field_boost=field_class.boost)
        else:
            return schema_field

class CustomWhooshSearchQuery(original_backend.WhooshSearchQuery):
    def get_spelling_suggestion(self, query):
        """
        preferred_query is not optional to catch accidental calls to this
        function without it. Results are no longer calculated during the
        query, so calling this is more expensive than it used to be, and
        should only be done if really desired.
        
        Pass the real query string entered by the user for best results,
        since the result will need to look like what they entered, or they
        won't understand it.
        """
        return self.backend.create_spelling_suggestion(query)

class CustomWhooshEngine(BaseEngine):
    backend = CustomWhooshBackend
    query = CustomWhooshSearchQuery

class FixedWhooshSearchBackend(CustomWhooshBackend):
    # Whoosh does actually support ordering by multiple fields. What it doesn't
    # support is reverse ordering on some fields but not all of them.
    #
    # It also supports facets, so add support for them here.

    def search(self, query_string, sort_by=None, start_offset=0, end_offset=None,
               fields='', highlight=False, facets=None, date_facets=None, query_facets=None,
               narrow_queries=None, spelling_query=None, within=None,
               dwithin=None, distance_point=None, models=None,
               limit_to_registered_models=None, result_class=None, **kwargs):
        if not self.setup_complete:
            self.setup()

        # A zero length query should return no results.
        if len(query_string) == 0:
            return {
                'results': [],
                'hits': 0,
            }

        try:
            from django.utils.encoding import force_text
        except ImportError:
            from django.utils.encoding import force_unicode as force_text

        query_string = force_text(query_string)

        # A one-character query (non-wildcard) gets nabbed by a stopwords
        # filter and should yield zero results.
        if len(query_string) <= 1 and query_string != u'*':
            return {
                'results': [],
                'hits': 0,
            }

        reverse = False

        if sort_by is not None:
            # Determine if we need to reverse the results and if Whoosh can
            # handle what it's being asked to sort by. Reversing is an
            # all-or-nothing action, unfortunately.
            sort_by_list = []
            reverse_counter = 0

            for order_by in sort_by:
                if order_by.startswith('-'):
                    reverse_counter += 1

            if reverse_counter != 0 and reverse_counter != len(sort_by):
                raise SearchBackendError("Whoosh does not handle reverse sorting "
                    "by some fields and not others.")

            for order_by in sort_by:
                if order_by.startswith('-'):
                    sort_by_list.append(order_by[1:])
                else:
                    sort_by_list.append(order_by)

            sort_by = sort_by_list
            reverse = (reverse_counter > 0)

        if date_facets is not None:
            warnings.warn("Whoosh does not handle date faceting.", Warning, stacklevel=2)

        if query_facets is not None:
            warnings.warn("Whoosh does not handle query faceting.", Warning, stacklevel=2)

        narrowed_results = None
        self.index = self.index.refresh()

        if limit_to_registered_models is None:
            from django.conf import settings
            limit_to_registered_models = getattr(settings, 'HAYSTACK_LIMIT_TO_REGISTERED_MODELS', True)

        if models and len(models):
            model_choices = sorted(['%s.%s' % (model._meta.app_label, model._meta.module_name) for model in models])
        elif limit_to_registered_models:
            # Using narrow queries, limit the results to only models handled
            # with the current routers.
            model_choices = self.build_models_list()
        else:
            model_choices = []

        if len(model_choices) > 0:
            if narrow_queries is None:
                narrow_queries = set()

            from haystack.constants import ID, DJANGO_CT, DJANGO_ID
            narrow_queries.add(' OR '.join(['%s:%s' % (DJANGO_CT, rm) for rm in model_choices]))

        narrow_searcher = None

        if narrow_queries is not None:
            # Potentially expensive? I don't see another way to do it in Whoosh...
            narrow_searcher = self.index.searcher()

            for nq in narrow_queries:
                recent_narrowed_results = narrow_searcher.search(self.parser.parse(force_text(nq)))

                if len(recent_narrowed_results) <= 0:
                    return {
                        'results': [],
                        'hits': 0,
                    }

                if narrowed_results:
                    narrowed_results.filter(recent_narrowed_results)
                else:
                   narrowed_results = recent_narrowed_results

        self.index = self.index.refresh()

        if self.index.doc_count():
            searcher = self.index.searcher()
            parsed_query = self.parser.parse(query_string)

            # In the event of an invalid/stopworded query, recover gracefully.
            if parsed_query is None:
                return {
                    'results': [],
                    'hits': 0,
                }

            page_num, page_length = self.calculate_page(start_offset, end_offset)

            search_kwargs = {
                'pagelen': page_length,
                'sortedby': sort_by,
                'reverse': reverse,
            }

            if facets is not None:
                search_kwargs['groupedby'] = []
                for facet_fieldname, extra_options in facets.items():
                    search_kwargs['groupedby'].append(facet_fieldname)

            # Handle the case where the results have been narrowed.
            if narrowed_results is not None:
                search_kwargs['filter'] = narrowed_results

            try:
                raw_page = searcher.search_page(
                    parsed_query,
                    page_num,
                    **search_kwargs
                )
            except ValueError:
                if not self.silently_fail:
                    raise

                return {
                    'results': [],
                    'hits': 0,
                    'spelling_suggestion': None,
                }

            # Because as of Whoosh 2.5.1, it will return the wrong page of
            # results if you request something too high. :(
            if raw_page.pagenum < page_num:
                return {
                    'results': [],
                    'hits': 0,
                    'spelling_suggestion': None,
                }

            results = self._process_results(raw_page, highlight=highlight, query_string=query_string, spelling_query=spelling_query, result_class=result_class, facets=facets)
            searcher.close()

            if hasattr(narrow_searcher, 'close'):
                narrow_searcher.close()

            return results
        else:
            if self.include_spelling:
                if spelling_query:
                    spelling_suggestion = self.create_spelling_suggestion(spelling_query)
                else:
                    spelling_suggestion = self.create_spelling_suggestion(query_string)
            else:
                spelling_suggestion = None

            return {
                'results': [],
                'hits': 0,
                'spelling_suggestion': spelling_suggestion,
            }

    def _process_results(self, raw_page, highlight=False, query_string='',
        spelling_query=None, result_class=None, facets=None):

        results = super(FixedWhooshSearchBackend, self)._process_results(raw_page,
            highlight, query_string, spelling_query, result_class)

        facets_out = {
            'fields': {},
            'dates': {},
            'queries': {},
        }

        for facet_fieldname, extra_options in facets.items():
            facet_results = raw_page.results.groups(facet_fieldname)
            facet_term_counts = []
            for term, term_results in facet_results.iteritems():
                facet_term_counts.append((term, len(term_results)))
            facets_out['fields'][facet_fieldname] = facet_term_counts

        results['facets'] = facets_out
        return results

class FixedWhooshEngine(BaseEngine):
    backend = FixedWhooshSearchBackend
    query = CustomWhooshSearchQuery

