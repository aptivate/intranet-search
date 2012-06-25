from collections import defaultdict

from haystack.backends import whoosh_backend as original_backend
from haystack.backends import BaseEngine

from whoosh import analysis, fields, highlight, query, scoring
from whoosh.reading import TermNotFound
from whoosh.spelling import SpellChecker
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

# Based on the "Old, obsolete spell checker - DO NOT USE" from Whoosh
# by Matt Chaput. See http://bitbucket.org/mchaput/whoosh/issue/224
# for rationale.

class SpellCheckerWithIncrementalUpdates(SpellChecker):
    """
    This feature is obsolete, apparently.
    """

    def __init__(self, storage, document_reader, spelling_fields,
            indexname="SPELL", booststart=2.0, boostend=1.0, mingram=3, 
            maxgram=4, minscore=0.5):
        super(SpellCheckerWithIncrementalUpdates, self).__init__(storage,
            indexname, booststart, boostend, mingram, maxgram,
            minscore)
        self.document_reader = document_reader
        self.spelling_fields = spelling_fields

    def _schema(self):
        # Creates a schema given this object's mingram and maxgram attributes.

        from whoosh.fields import Schema, FieldType, ID, STORED
        from whoosh.formats import Frequency
        from whoosh.analysis import SimpleAnalyzer

        idtype = ID()
        freqtype = FieldType(Frequency(), SimpleAnalyzer())

        fls = [("word", STORED)]
        for size in xrange(self.mingram, self.maxgram + 1):
            fls.extend([("start%s" % size, idtype),
                        ("end%s" % size, idtype),
                        ("gram%s" % size, freqtype)])

        return Schema(**dict(fls))

    def suggestions_and_scores(self, text, weighting=None):
        raise NotImplementedError()

    def suggestions(self, text, weighting=None):
        if weighting is None:
            weighting = scoring.TF_IDF()

        grams = defaultdict(list)
        for size in xrange(self.mingram, self.maxgram + 1):
            key = "gram%s" % size
            nga = analysis.NgramAnalyzer(size)
            for t in nga(text):
                grams[key].append(t.text)

        queries = []
        for size in xrange(self.mingram, min(self.maxgram + 1, len(text))):
            key = "gram%s" % size
            gramlist = grams[key]
            queries.append(query.Term("start%s" % size, gramlist[0],
                                      boost=self.booststart))
            queries.append(query.Term("end%s" % size, gramlist[-1],
                                      boost=self.boostend))
            for gram in gramlist:
                queries.append(query.Term(key, gram))

        q = query.Or(queries)
        ix = self.index()
        s = ix.searcher(weighting=weighting)
        try:
            result = s.search(q, limit=None)
            return [(fs["word"], result.score(i))
                for i, fs in enumerate(result)]
        finally:
            s.close()

    def suggest(self, text, number=3, usescores=False):
        suggestions = self.suggestions(text)

        if usescores:
            def keyfn(a):
                return 0 - (1 / distance(text, a[0])) * a[1]
            
            def generate_word_score_tuples(suggestions):
                for word, spelling_score in suggestions:
                    for field in self.spelling_fields:
                        if (field, word) in self.document_reader:
                            yield (word, 
                                self.document_reader.term_info(field, word).score,
                                spelling_score)
                            continue
            
            suggestions = list(generate_word_score_tuples(suggestions))
        else:
            def keyfn(a):
                return distance(text, a[0])

            def filter_out_dead_words(suggestions):
                for word, spelling_score in suggestions:
                    for field in self.spelling_fields:
                        if (field, word) in self.document_reader:
                            yield (word, None, spelling_score)
                            continue
            
            suggestions = list(filter_out_dead_words(suggestions))
        
        suggestions.sort(key=keyfn)
        
        return [word for word, document_score_or_none, spelling_score
            in suggestions[:number]
            if spelling_score >= self.minscore]

    def add_field(self, ix, fieldname):
        raise NotImplementedError()
        """
        with ix.reader() as document_index:
            with self.index().reader() as spelling_reader:
                with self.index().writer() as spelling_writer:
                    for word, terminfo in document_index.iter_field(fieldname):
                        try:
                            terminfo = spelling_reader.term_info(fieldname, word)
                        except TermNotFound:
                            self.add_word(word, spelling_writer)
        """
        
    def add_words(self, words):
        with self.index().reader() as spelling_reader:
            # with AsyncWriter(self.index()) as spelling_writer:
            # deliberately don't use "with", so we control the commit mergetype
            spelling_writer = AsyncWriter(self.index())

            for word in words:
                try:
                    spelling_reader.term_info('word', word)
                except TermNotFound:
                    self.add_word(word, spelling_writer)

            # import pdb; pdb.set_trace()
            spelling_writer.commit(mergetype=CUSTOM_MERGE_SMALL)   
            # spelling_writer.close()  

    def add_word(self, word, writer):
        fields = {"word": word}
        for size in xrange(self.mingram, self.maxgram + 1):
            nga = analysis.NgramAnalyzer(size)
            gramlist = [t.text for t in nga(word)]
            if len(gramlist) > 0:
                fields["start%s" % size] = gramlist[0]
                fields["end%s" % size] = gramlist[-1]
                fields["gram%s" % size] = " ".join(gramlist)
        # import pdb; pdb.set_trace()
        writer.add_document(**fields)

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
    
    def get_spell_checker(self):
        return SpellCheckerWithIncrementalUpdates(self.storage,
            self.index.reader(), self.spelling_fields, mingram=2)

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
        import logging
        logger = logging.getLogger(__name__)
        logger.debug(query_string)
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
