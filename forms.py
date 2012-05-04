from django import forms
from django.forms.widgets import HiddenInput 

from haystack.forms import ModelSearchForm

from binder.models import Program
from documents.models import DocumentType

from widgets import SelectMultipleWithJquery
from queries import SearchQuerySetWithAllFields

class SearchFormWithAllFields(ModelSearchForm):
    programs = forms.MultipleChoiceField(
        widget=SelectMultipleWithJquery(html_name='id_programs[]'), 
        required=False)

    document_types = forms.MultipleChoiceField(
        widget=SelectMultipleWithJquery(html_name='id_document_types[]'), 
        required=False)
    
    def __init__(self, *args, **kwargs):
        # print "SearchFormWithAllFields %s initialised with %s, %s" % (
        #     object.__str__(self), args, kwargs)
        if 'searchqueryset' not in kwargs:
            kwargs['searchqueryset'] = SearchQuerySetWithAllFields()
        
        super(SearchFormWithAllFields, self).__init__(*args, **kwargs)
        self.fields['programs'].choices = Program.objects.values_list('id',
                'name')

        self.fields['document_types'].choices = (DocumentType.objects.
                values_list('id', 'name'))
        
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
        
        self.fields['models'].widget = \
            SelectMultipleWithJquery(html_name='id_models[]',
                choices=self.fields['models'].choices)

class SearchFormWithJqueryLists(SearchFormWithAllFields):
    def __init__(self, *args, **kwargs):
        super(SearchFormWithJqueryLists, self).__init__(*args, **kwargs)
        
        # override the one created by the ModelSearchForm constructor
        # to use a jquery drop-down box instead
        self.fields['models'].widget = \
            SelectMultipleWithJquery(html_name='id_models[]',
                choices=self.fields['models'].choices)

class SuggestionForm(forms.Form):
    suggestion = forms.CharField(widget=HiddenInput, required=False)
