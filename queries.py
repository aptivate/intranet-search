from haystack import connections, connection_router
from haystack.backends import SQ, BaseSearchQuery
from haystack.constants import DEFAULT_ALIAS 
from haystack.fields import CharField
from haystack.query import SearchQuerySet, AutoQuery

haystack = connections[DEFAULT_ALIAS].get_unified_index()
all_fields = haystack.all_searchfields()
# print "unified index = %s" % haystack

class SearchQuerySetWithAllFields(SearchQuerySet):
    def __init__(self, site=None, query=None, fields=None, meta=None):
        SearchQuerySet.__init__(self, site, query)
        
        if fields is None:
            """
            from haystack import connections, connection_router
            from haystack.constants import DEFAULT_ALIAS 
            index = connections[DEFAULT_ALIAS].get_unified_index()
            """
            fields = all_fields
        
        self.fields = fields
        # import pdb; pdb.set_trace()

        # print "sqs init (%s): meta = %s" % (self, meta)
        # import traceback
        # traceback.print_stack()
        
        # self.query.set_result_class(SearchResultWithExtraFields)
        
    def auto_query_custom(self, **kwargs):
        """
        Performs a best guess constructing the search query.

        This method is somewhat naive but works well enough for the simple,
        common cases.
        """
        return self.filter(**kwargs)
    
    def filter(self, **kwargs):
        # print "enter filter: old query = %s" % self.query
        clone = self._clone()
        
        for param_name, param_value in kwargs.iteritems():
            new_condition = BaseSearchQuery()
        
            if param_name == 'content': 
                # print "fields = %s" % self.fields
                
                for field_name, field_object in self.fields.iteritems():
                    if isinstance(field_object, CharField):
                        this_query = {field_name: param_value}
                        new_condition.add_filter(SQ(**this_query), use_or=True)
            
                # result = self.__and__(dj)
                clone.query.combine(new_condition, SQ.AND)

            elif getattr(param_value, '__iter__', None):
                for possible_value in param_value:
                    this_query = {param_name: possible_value}
                    new_condition.add_filter(SQ(**this_query), use_or=True)

                clone.query.combine(new_condition, SQ.AND)
            
            else:
                this_query = {param_name: param_value}
                clone.query.add_filter(SQ(**this_query))
        
        # print "exit filter: new query = %s" % self.query
        return clone
