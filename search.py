from django.contrib.admin.templatetags import admin_list
 
from django import forms
from django.db import models as fields
from django.forms import widgets
from django.shortcuts import render_to_response
from django.utils.safestring import mark_safe

from haystack import connections, connection_router
from haystack.backends import SQ, BaseSearchQuery
from haystack.constants import DEFAULT_ALIAS 
from haystack.fields import CharField
from haystack.forms import ModelSearchForm
from haystack.models import SearchResult
from haystack.query import SearchQuerySet, AutoQuery
from haystack.views import SearchView

from binder.models import Program, IntranetUser
from documents.models import DocumentType

import django_tables2 as tables

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
        
        for param_name, param_value in kwargs.iteritems():
            dj = BaseSearchQuery()
        
            if param_name == 'content': 
                # print "fields = %s" % self.fields
                
                for field_name, field_object in self.fields.iteritems():
                    if isinstance(field_object, CharField):
                        this_query = {field_name: param_value}
                        dj.add_filter(SQ(**this_query), use_or=True)
            
                # result = self.__and__(dj)
                self.query.combine(dj, SQ.AND)

            elif getattr(param_value, '__iter__'):
                for possible_value in param_value:
                    this_query = {param_name: possible_value}
                    dj.add_filter(SQ(**this_query), use_or=True)

                self.query.combine(dj, SQ.AND)
            
            else:
                self.query.add_filter(SQ({param_name: param_value}))
        
        # print "exit filter: new query = %s" % self.query
        return self
    
class CheckboxesWithCustomHtmlName(widgets.CheckboxSelectMultiple):
    def __init__(self, attrs=None, choices=(), html_name=None):
        super(CheckboxesWithCustomHtmlName, self).__init__(attrs=attrs,
            choices=choices)
        self.html_name = html_name
        
    def render(self, name, value, attrs=None, choices=()):
        if self.html_name:
            name = self.html_name

        return super(CheckboxesWithCustomHtmlName, self).render(name, value,
            attrs, choices)

    def value_from_datadict(self, data, files, name):
        if self.html_name:
            name = self.html_name

        v = super(CheckboxesWithCustomHtmlName, self).value_from_datadict(data,
            files, name)
        # print "SelectMultiple.value_from_datadict(%s, %s, %s, %s) = %s" % (
        #     self, data, files, name, v)
        return v

class SelectMultipleWithJquery(widgets.SelectMultiple):
    def __init__(self, attrs=None, choices=(), html_name=None):
        super(SelectMultipleWithJquery, self).__init__(attrs=attrs,
            choices=choices)
        self.html_name = html_name
        
    def render(self, name, value, attrs=None, choices=()):
        if self.html_name:
            name = self.html_name

        if attrs is None:
            attrs = {}
        
        html_attrs = {'class': 'multiselect-jquery'}
        html_attrs.update(attrs)

        return super(SelectMultipleWithJquery, self).render(name, value,
            attrs=html_attrs, choices=choices)

    def value_from_datadict(self, data, files, name):
        if self.html_name:
            name = self.html_name

        v = super(SelectMultipleWithJquery, self).value_from_datadict(data,
            files, name)
        # print "SelectMultiple.value_from_datadict(%s, %s, %s, %s) = %s" % (
        #     self, data, files, name, v)
        return v

class SearchFormWithAllFields(ModelSearchForm):
    programs = forms.MultipleChoiceField(
        choices=[(p.id, p.name) for p in Program.objects.all()],
        widget=SelectMultipleWithJquery(html_name='id_programs[]'), 
        required=False)

    document_types = forms.MultipleChoiceField(
        choices=[(t.id, t.name) for t in DocumentType.objects.all()],
        widget=SelectMultipleWithJquery(html_name='id_document_types[]'), 
        required=False)
    
    def __init__(self, *args, **kwargs):
        # print "SearchFormWithAllFields %s initialised with %s, %s" % (
        #     object.__str__(self), args, kwargs)
        if 'searchqueryset' not in kwargs:
            kwargs['searchqueryset'] = SearchQuerySetWithAllFields()
        
        super(SearchFormWithAllFields, self).__init__(*args, **kwargs)
        
    def search(self):
        # print "search starting in %s" % object.__str__(self)
        
        if not self.is_valid():
            # print "invalid form: %s, %s" % (self.is_bound, self.errors)
            return None
        
        kwargs = {}

        if self.cleaned_data.get('q'):
            kwargs['content'] = self.cleaned_data.get('q')

        if self.cleaned_data.get('programs'):
            kwargs['programs'] = self.cleaned_data.get('programs')
        
        if self.cleaned_data.get('document_types'):
            kwargs['document_type'] = self.cleaned_data.get('document_types')
            
        if not kwargs and not self.cleaned_data.get('models'):
            # print "no search"
            return None
    
        sqs = self.searchqueryset.auto_query_custom(**kwargs)
        sqs = sqs.models(*self.get_models())
        
        self.count = sqs.count()
        if self.load_all:
            sqs = sqs.load_all()
            
        return sqs

class QuickSearchForm(SearchFormWithAllFields):
    def __init__(self, *args, **kwargs):
        super(QuickSearchForm, self).__init__(*args, **kwargs)
        
        # reduce set of choices
        self.fields['models'].widget = \
            CheckboxesWithCustomHtmlName(html_name='id_models[]')
        from django.utils.text import capfirst
        from haystack.constants import DEFAULT_ALIAS
        using = DEFAULT_ALIAS
        choices = [("%s.%s" % (m._meta.app_label, m._meta.module_name),
            capfirst(unicode(m._meta.verbose_name_plural)))
            for m in connections[using].get_unified_index().get_indexed_models()
            if m == IntranetUser]
        self.fields['models'].choices = sorted(choices, key=lambda x: x[1])

class SearchFormWithJqueryLists(SearchFormWithAllFields):
    def __init__(self, *args, **kwargs):
        super(SearchFormWithJqueryLists, self).__init__(*args, **kwargs)
        
        # override the one created by the ModelSearchForm constructor
        # to use a jquery drop-down box instead
        self.fields['models'].widget = \
            SelectMultipleWithJquery(html_name='id_models[]')
        self.fields['models'].widget.choices = self.fields['models'].choices

from django.contrib.admin.views.main import ChangeList
class SearchList(ChangeList):
    def url_for_result(self, result):
        return result.object.get_absolute_url()

from django.contrib.admin.views.main import EMPTY_CHANGELIST_VALUE

class SearchTable(tables.Table):
    title = tables.Column(verbose_name="Title")
    authors = tables.Column(verbose_name="Authors")
    uploader = tables.Column(verbose_name="Uploaded By")
    created = tables.Column(verbose_name="Date Added")
    programs = tables.Column(verbose_name="Programs")
    document_type = tables.Column(verbose_name="Document Type")
    score = tables.Column(verbose_name="Score")
    
    def render_title(self, value, record):
        # print "record = %s (%s)" % (record, dir(record))
        return mark_safe("<a href='%s'>%s</a>" % (record.object.get_absolute_url(),
            value))

    def render_authors(self, value):
        if not value:
            return EMPTY_CHANGELIST_VALUE
        users = IntranetUser.objects.in_bulk(value)
        return ', '.join([users[long(i)].full_name for i in value])
    
    def render_programs(self, value):
        programs = Program.objects.in_bulk(value)
        return ', '.join([programs[long(i)].name for i in value])
    
    def render_document_type(self, value):
        if not value:
            return EMPTY_CHANGELIST_VALUE
        return DocumentType.objects.get(id=value).name
    
    class Meta:
        attrs = {'class': 'paleblue'}

class UserSearchTable(tables.Table):
    title = tables.Column(verbose_name="Name")
    job_title = tables.Column(verbose_name="Job Title")
    logged_in = tables.Column(verbose_name="Logged In")

    def render_title(self, value, record):
        return mark_safe("<a href='%s'>%s</a>" % (record.object.get_absolute_url(),
            value))
        
    def render_logged_in(self, record):
        return "Yes" if record.object.is_logged_in() else "No"

    class Meta:
        attrs = {'class': 'paleblue'}

from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator

class SuggestionForm(forms.Form):
    suggestion = forms.CharField(widget=widgets.HiddenInput,
        required=False)

class SearchViewWithExtraFilters(SearchView):
    prefix = 'results_'
    page_field = 'page'
    sort_by_field = 'sort'

    from django.template import RequestContext
    
    def __init__(self, template=None, load_all=True, 
        form_class=SearchFormWithJqueryLists,
        searchqueryset=None, context_class=RequestContext,
        results_per_page=None):
        
        super(SearchViewWithExtraFilters, self).__init__(template, load_all,
            form_class, searchqueryset, context_class, results_per_page)

    """
    def get_results(self):
        import pdb; pdb.set_trace()
        return super(SearchViewWithExtraFilters, self).get_results()
    """
     
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
