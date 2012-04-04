from django.contrib.auth.decorators import login_required
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.decorators import method_decorator

from haystack.views import SearchView

from forms import SearchFormWithJqueryLists, SuggestionForm
from tables import UserSearchTable, SearchTable

class SearchViewWithExtraFilters(SearchView):
    prefix = 'results_'
    page_field = 'page'
    sort_by_field = 'sort'

    def __init__(self, template=None, load_all=True, 
        form_class=SearchFormWithJqueryLists, searchqueryset=None, 
        context_class=RequestContext, results_per_page=None):
        
        super(SearchViewWithExtraFilters, self).__init__(template, load_all,
            form_class, searchqueryset, context_class, results_per_page)

    def get_results(self):
        return super(SearchViewWithExtraFilters, self).get_results()
     
    def create_response(self):
        if self.results is None:
            return render_to_response(self.template, dict(form=self.form),
                context_instance=self.context_class(self.request))
        elif self.form.count == 1:
            # If only one result, go straight to profile page
            results = list(self.results)
            from django.shortcuts import redirect
            return redirect(results[0].object)
        else:
            return super(SearchViewWithExtraFilters, self).create_response() 

    def extra_context(self):
        sort_by = self.request.GET.get(self.prefix + self.sort_by_field,
            'score')
        
        if sort_by == 'score':
            sort_by = None
            # this is how we tell haystack to "sort by relevance"?
        
        models = self.form.cleaned_data['models']
        if len(models) == 1 and models[0] == 'binder.intranetuser':
            table_class = UserSearchTable
        else:
            table_class = SearchTable
    
        results_table = table_class(self.results, prefix=self.prefix,
            page_field=self.page_field, order_by=sort_by)
        current_page = self.request.GET.get(results_table.prefixed_page_field, 1)
        results_table.paginate(page=current_page)
        
        context = {
            'is_real_search': (self.form.is_valid() and
                len(self.form.cleaned_data) > 0),
            'count': getattr(self.form, 'count', None),
            'results_table': results_table,
            'request': self.request,
            # 'result_headers': list(admin_list.result_headers(self)),
        }

        context['suggestform'] = SuggestionForm(data={'suggestion': self.form.get_suggestion()})
        
        return context

    # https://docs.djangoproject.com/en/dev/topics/class-based-views/
    __call__ = method_decorator(login_required)(SearchView.__call__)

class DocumentListView(SearchViewWithExtraFilters):
    """
    This is a SearchView with a tweak: it pre-selects the Documents model
    for restricted searches, which means that it returns all documents
    when there is no query, instead of an empty list.
    
    This feels like it should be in the documents module, not here.
    But there are good reasons to put it here:
    
    * It uses the search index to list the documents and retrieve
    the fields, and it has a search form on the page, so it's not
    easy to implement in the documents module, and would introduce
    a cross-module dependency there.
    
    * Despite the name it doesn't actually depend on the Document
    model in any way, so it doesn't introduce a cross-module dependency
    if placed here.
    
    * It could be useful in other applications, at least as an example,
    so I'm reluctant to make it a custom view hidden away in a client's
    private intranet code.
    """
    
    prefix = 'results_'
    page_field = 'page'
    sort_by_field = 'sort'

    def build_form(self, form_kwargs=None):
        data = None
        kwargs = {
            'load_all': self.load_all,
        }
        if form_kwargs:
            kwargs.update(form_kwargs)

        data = {'id_models[]': ['documents.document']}
        
        if len(self.request.GET):
            data.update(self.request.GET)

        if self.searchqueryset is not None:
            kwargs['searchqueryset'] = self.searchqueryset

        return self.form_class(data, **kwargs)
