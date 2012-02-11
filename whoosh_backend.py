from haystack.backends import whoosh_backend as original_backend
from haystack.backends import BaseEngine
from whoosh.spelling import SpellChecker

class CustomWhooshBackend(original_backend.WhooshSearchBackend):
    def get_spell_checker(self):
        return SpellChecker(self.storage, mingram=2)

    def update_spelling(self):
        # import pdb; pdb.set_trace()
        sp = self.get_spell_checker()
        sp.add_field(self.index, self.content_field_name)
        sp.add_field(self.index, 'job_title')
    
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
