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
