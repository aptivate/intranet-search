"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.template import Context

import settings

from binder.test_utils import AptivateEnhancedTestCase
from binder.models import IntranetUser
from search import SearchViewWithExtraFilters, SearchTable

class SearchTest(AptivateEnhancedTestCase):
    fixtures = ['test_permissions', 'test_users']

    def setUp(self):
        super(SearchTest, self).setUp()
        self.john = IntranetUser.objects.get(username='john')
        self.ringo = IntranetUser.objects.get(username='ringo')
        self.login(self.john)

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
        self.assertEqual(1, len(results), "unexpected results in list: %s" %
            results)
        result = results[0]
        self.assertEqual("binder.intranetuser.%s" % self.john.id, result.id)
        self.assertEqual(self.john.full_name, result.title)
        # Free text search for program e.g. 'seeds' and have program people
        # in results without having to apply drop down filter.
        self.assertEqual(self.john.program.name, result.program)
        self.assertEqual(reverse('admin:binder_intranetuser_readonly',
            args=[self.john.id]), result.object.get_absolute_url())
    
    def test_search_model_field_widget_uses_jquery(self):
        response = self.client.get(reverse('search'))
        form = response.context['form']
        from search import SelectMultipleWithJquery
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
            {'q': 'ringo', 'id_models[]': 'binder.intranetuser'})
        table = response.context['results_table']
        
        from search import UserSearchTable
        self.assertIsInstance(table, UserSearchTable)
        
        queryset = table.data.queryset
        results = list(queryset)
        self.assertEqual(1, len(results), "unexpected results in list: %s" %
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
        
        self.assertEquals("No", table.page.object_list.next()["logged_in"])

        # john is logged in, so the column should show Yes instead of No
        response = self.client.get(reverse('search'),
            {'q': 'john', 'id_models[]': 'binder.intranetuser'})
        table = response.context['results_table']
        self.assertEquals("Yes", table.page.object_list.next()["logged_in"])

    def test_can_search_for_all_users(self):
        response = self.client.get(reverse('search'),
            {'id_models[]': 'binder.intranetuser'})
        self.assertIn('results_table', response.context, response)

    def test_can_find_people_by_program(self):
        response = self.client.get(reverse('search'),
            {'q': self.john.program.name})
        table = response.context['results_table']
        results = list(table.data.queryset)
        self.assertEqual(1, len(results), "unexpected results in list: %s" %
            results)
        self.assertEqual(self.john, results[0].object)
