"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.core.handlers.wsgi import WSGIRequest
from django.core.urlresolvers import reverse
from django.forms import widgets

from haystack.constants import DEFAULT_ALIAS

from binder.test_utils import AptivateEnhancedTestCase
from binder.models import IntranetUser

from forms import SuggestionForm
from tables import SearchTable

class SearchTest(AptivateEnhancedTestCase):
    fixtures = ['test_programs', 'test_permissions', 'test_users']

    def setUp(self):
        super(SearchTest, self).setUp()
        self.john = IntranetUser.objects.get(username='john')
        self.ringo = IntranetUser.objects.get(username='ringo')
        self.ken = IntranetUser.objects.get(username='ken')
        self.smith = IntranetUser.objects.get(username='smith')
        self.login(self.john)
        from haystack import connections
        self.unified = connections[DEFAULT_ALIAS].get_unified_index()

    def test_cannot_search_without_login(self):
        """
        from django.http import HttpResponseRedirect
        from binder.monkeypatch import before, breakpoint
        before(HttpResponseRedirect, '__init__')(breakpoint)
        """
        self.client.logout()
        response = self.client.get(reverse('search'),
            {'id_models[]': 'binder.intranetuser'}, follow=True)
        self.assertTemplateUsed(response, 'admin/login.html',
            'anonymous users should be required to log in before searching: ' +
            '%s' % response)
        
    def test_search_indexes_people(self):
        response = self.client.get(reverse('search'), {'q': 'john'})
        table = response.context['results_table']
        self.assertIsInstance(table, SearchTable)
        queryset = table.data.queryset
        results = list(queryset)
        self.assertEqual(2, len(results), "unexpected results in list: %s" %
            results)
        result = results[0]
        self.assertEqual("binder.intranetuser.%s" % self.john.id, result.id)
        self.assertEqual(self.john.full_name, result.title)
        # Free text search for program e.g. 'seeds' and have program people
        # in results without having to apply drop down filter.
        self.assertEqual(self.john.program.name, result.program)
        self.assertEqual(reverse('admin:binder_intranetuser_readonly',
            args=[self.john.id]), result.object.get_absolute_url())

    """
    def test_quick_search_form_uses_select_widget(self):
        response = self.client.get(reverse('front_page'))
        form = response.context['search']['form']
        models_field = form.fields['models']

        from django.forms.widgets import Select
        self.assertIsInstance(models_field, Select)
        self.assertSequenceEqual(models_field.choices,
            models_field.widget.choices)
    """
    
    def test_search_model_field_widget_uses_jquery(self):
        response = self.client.get(reverse('search'))
        form = self.assertInDict('form', response.context)
        
        from widgets import SelectMultipleWithJquery
        self.assertIsInstance(form.fields['models'].widget,
            SelectMultipleWithJquery)
        self.assertSequenceEqual(form.fields['models'].choices,
            form.fields['models'].widget.choices)

    def test_search_for_people_uses_different_results_table(self):
        """
        Re: kanban card: Add 'People' tick box in top right...
        list with names as hyperlinks to profile page and job title and
        logged in 'status' (separate story)
        """
        response = self.client.get(reverse('search'),
            {'q': 'john', 'id_models[]': 'binder.intranetuser'})
        table = response.context['results_table']
        
        from tables import UserSearchTable
        self.assertIsInstance(table, UserSearchTable)
        
        queryset = table.data.queryset
        results = list(queryset)
        self.assertEqual(2, len(results), "unexpected results in list: %s" %
            results)
        
        columns = table.base_columns.items()
        # list with names as hyperlinks to profile page and job title 
        # and logged in 'status'
        self.assertEqual('title', columns[0][0])
        self.assertEqual('Name', columns[0][1].verbose_name)
        self.assertEqual('job_title', columns[1][0])
        self.assertEqual('Job Title', columns[1][1].verbose_name)
        self.assertEqual('logged_in', columns[2][0])
        self.assertEqual('Logged In', columns[2][1].verbose_name)
        
        self.assertEquals("Yes", table.page.object_list.next()["logged_in"])

        # john is logged in, so the column should show Yes instead of No
        response = self.client.get(reverse('search'),
            {'q': 'starr', 'id_models[]': 'binder.intranetuser'})
        table = response.context['results_table']
        self.assertEquals("No", table.page.object_list.next()["logged_in"])

    def test_can_search_for_all_users(self):
        response = self.client.get(reverse('search'),
            {'id_models[]': 'binder.intranetuser'})
        self.assertIn('results_table', response.context, response)

    def test_can_find_people_by_program(self):
        response = self.client.get(reverse('search'),
            {'q': self.john.program.name}, follow=True)
        # only one result, so should be redirected to readonly view page
        self.assertIsInstance(response.real_request, WSGIRequest)
        url = response.real_request.build_absolute_uri(self.john.get_absolute_url())
        self.assertSequenceEqual([(url, 302)], response.redirect_chain)

    def test_quick_search_form_has_a_search_type_dropdown(self):
        response = self.client.get(reverse('search'),
            {'q': 'john'}, follow=True)
        form = response.context['search']['form']
        field = form.fields['models']
        
        from django.forms import fields
        self.assertIsInstance(field, fields.MultipleChoiceField)
        
        from widgets import SelectMultipleWithJquery
        self.assertIsInstance(field.widget, SelectMultipleWithJquery)
        
        response = self.client.get(reverse('search'),
            {'q': 'john', 'id_models[]': 'binder.intranetuser'})

        table = response.context['results_table']
        queryset = table.data.queryset
        self.assertItemsEqual((IntranetUser,), queryset.query.models)
        
        # check that the correct models are selected too
        quick_search_form = response.context['search']['form']
        self.assertTrue(quick_search_form.is_valid())
        self.assertItemsEqual(('binder.intranetuser',), 
            quick_search_form.cleaned_data.get('models'))
        
        advanced_search_form = response.context['form']
        self.assertItemsEqual(('binder.intranetuser',), 
            advanced_search_form.cleaned_data.get('models'))

    def test_spelling_suggestions(self):
        """
        This test relies on the monkeypatch to change the minimum
        n-gram size of the SpellingChecker to 2, otherwise it won't
        find any matches.
        """
        
        response = self.client.get(reverse('search'),
            {'q': 'rnigo'}, follow=True)
        sf = response.context['suggestform']
        self.assertIsInstance(sf, SuggestionForm)
        self.assertEqual('ringo', sf['suggestion'].value())
        self.assertIsInstance(sf['suggestion'].field.widget,
            widgets.HiddenInput)

        # check that stemming is not done on words ending in "er"
        response = self.client.get(reverse('search'),
            {'q': 'shearre'}, follow=True)
        self.assertEqual('shearer', 
            response.context['suggestform']['suggestion'].value())

        # check that the job title field is indexed, and stemming is not
        # done on words ending in "er" for spelling queries
        # from binder.monkeypatch import before, breakpoint
        # from whoosh_backend import CustomWhooshBackend
        # before(CustomWhooshBackend, 'create_spelling_suggestion')(breakpoint)
        
        response = self.client.get(reverse('search'),
            {'q': 'songwritr'}, follow=True)
        self.assertIn('suggestion', response.context,
            'unexpected response: %s' % response)
        self.assertEqual('songwriter', 
            response.context['suggestform']['suggestion'].value())

    def test_notes_field_for_user(self):
        index = self.unified.get_index(IntranetUser)
        
        from haystack.fields import CharField
        self.assertIsInstance(index.fields['notes'], CharField)
        self.assertEqual('notes', index.fields['notes'].model_attr)
        
        response = self.client.get(reverse('search'),
            {'q': "Yoko"}, follow=True)

        # only one result, so should be redirected to readonly view page
        self.assertIsInstance(response.real_request, WSGIRequest)
        url = response.real_request.build_absolute_uri(self.john.get_absolute_url())
        self.assertSequenceEqual([(url, 302)], response.redirect_chain)
        
    def test_update_document_removes_old_from_spelling(self):
        index = self.unified.get_index(IntranetUser)
        backend = index._get_backend(DEFAULT_ALIAS)
        
        from whoosh_backend import CustomWhooshBackend
        self.assertIsInstance(backend, CustomWhooshBackend)

        self.assertEqual('kenneth', backend.create_spelling_suggestion('Kenneth'))
        self.assertEqual('starr', # not "barbie"!
            backend.create_spelling_suggestion('Barbie'))

        self.ken.full_name = "Barbie"
        self.ken.save()
        
        self.assertEqual('lennon', # not "kenneth"!
            backend.create_spelling_suggestion('Kenneth'))
        self.assertEqual('barbie', backend.create_spelling_suggestion('Barbie'))
