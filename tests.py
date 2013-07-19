from django.core.handlers.wsgi import WSGIRequest
from django.core.urlresolvers import reverse
from django.forms import widgets

from haystack.constants import DEFAULT_ALIAS

from binder.test_utils import AptivateEnhancedTestCase
from search import SearchTable, SuggestionForm

from forms import SuggestionForm, SearchFormWithAllFields
from tables import SearchTable

class SearchTestBase(AptivateEnhancedTestCase):
    def _pre_setup(self):
        """
        We need to change the Haystack configuration before fixtures are
        loaded, otherwise they end up in the developer's index and not the
        temporary test index, which is bad for both developers and tests.
        
        This is an internal interface and its use is not recommended.
        """

        super(SearchTestBase, self)._pre_setup()

        from haystack.constants import DEFAULT_ALIAS
        from django.conf import settings
        settings.HAYSTACK_CONNECTIONS[DEFAULT_ALIAS]['PATH'] = '/dev/shm/whoosh'
        settings.HAYSTACK_CONNECTIONS[DEFAULT_ALIAS]['SILENTLY_FAIL'] = False
        # settings.HAYSTACK_CONNECTIONS[DEFAULT_ALIAS]['STORAGE'] = 'ram'

        from haystack import connections
        self.search_conn = connections[DEFAULT_ALIAS]
        # self.search_conn.get_backend().use_file_storage = False
        # self.search_conn.get_backend().setup()
        self.backend = self.search_conn.get_backend()
        self.backend.delete_index()

    def setUp(self):
        super(SearchTestBase, self).setUp()
        self.unified_index = self.search_conn.get_unified_index()
        
class SearchTest(SearchTestBase):
    fixtures = ['test_programs', 'test_permissions', 'test_users',
                'test_documenttypes']

    def setUp(self):
        super(SearchTest, self).setUp()
        self.john = IntranetUser.objects.get(username='john')
        self.ringo = IntranetUser.objects.get(username='ringo')
        self.ken = IntranetUser.objects.get(username='ken')
        self.smith = IntranetUser.objects.get(username='smith')
        self.login(self.john)
        from haystack import connections

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
        
    def assert_search_results(self, response, expected_results):
        table = response.context['results_table']
        self.assertIsInstance(table, SearchTable)
        self.assertFalse(table._meta.sortable, "Table sorting is disabled " +
            "as it appears not to work properly")

        columns = table.base_columns.items()
        self.assertNotIn('score', [c[0] for c in columns],
            "Score column is disabled on request")

        queryset = table.data.queryset
        actual_results = list(queryset)
        self.assertEqual(len(expected_results), len(actual_results),
            "unexpected results in list: %s" % actual_results)

        for expected, actual in zip(expected_results, actual_results):
            self.assertEqual("binder.intranetuser.%s" % expected.id, actual.id)
            self.assertEqual(expected.full_name, actual.title)

            # Free text search for program e.g. 'seeds' and have program people
            # in results without having to apply drop down filter.
            if expected.program is None:
                self.assertIsNone(actual.program)
            else:
                self.assertEqual(expected.program.name, actual.program)

            self.assertEqual(reverse('admin:binder_intranetuser_readonly',
                args=[expected.id]), actual.object.get_absolute_url())

    def test_search_indexes_people(self):
        response = self.client.get(reverse('search'), {'q': 'john'})
        self.assert_search_results(response, [self.john, self.smith])

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
        self.assertFalse(table._meta.sortable, "Table sorting is disabled " +
            "as it appears not to work properly")
        
        queryset = table.data.queryset
        results = list(queryset)
        self.assertEqual(1, len(results), "unexpected results in list: %s" %
            results)
        self.assertEqual(self.john.id, results[0].pk)
        
        columns = table.base_columns.items()
        # list with names as hyperlinks to profile page and job title 
        # and logged in 'status'
        self.assertEqual('title', columns[0][0])
        self.assertEqual('Name', columns[0][1].verbose_name)
        self.assertEqual('job_title', columns[1][0])
        self.assertEqual('Job Title', columns[1][1].verbose_name)
        self.assertEqual('logged_in', columns[2][0])
        self.assertEqual('Logged In', columns[2][1].verbose_name)
        
        # john is logged in, so the column should show Yes instead of No
        import pdb; pdb.set_trace()
        self.assertEquals("Yes", table.page.object_list.next()["logged_in"])

        # now try Kenneth, who is not logged in
        response = self.client.get(reverse('search'),
            {'q': 'starr', 'id_models[]': 'binder.intranetuser'})
        table = response.context['results_table']
        results = list(table.page.object_list)
        self.assertEqual(1, len(results), "unexpected results in list: %s" %
            results)
        self.assertEqual(self.kenneth.full_name, results[0]["title"])
        self.assertEquals("No", results[0]["logged_in"])

    def test_can_search_for_all_users(self):
        response = self.client.get(reverse('search'),
            {'id_models[]': 'binder.intranetuser'})
        self.assertIn('results_table', response.context, response)

    def test_can_find_people_by_program(self):
        response = self.client.get(reverse('search'),
            {'q': self.john.program.name}, follow=True)
        self.assert_search_results(response, [self.john])

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

    def test_no_suggestions_without_query(self):
        response = self.client.get(reverse('search'), {'q': ''}, follow=True)
        self.assertNotIn('suggestform', response.context)

    def test_spelling_suggestions(self):
        """
        This test relies on the monkeypatch to change the minimum
        n-gram size of the SpellingChecker to 2, otherwise it won't
        find any matches.
        """

        response = self.client.get(reverse('search'), {'q': 'ringo'})
        self.assertNotIn('suggestform', response.context,
            "Should be no suggestion when the suggestion is the same " +
            "as the actual search")
        
        response = self.client.get(reverse('search'), {'q': 'rnigo'})
        suggestform = self.assertInDict('suggestform', response.context)
        self.assertIsInstance(suggestform, SuggestionForm)
        self.assertEqual('ringo', suggestform['suggestion'].value())
        self.assertIsInstance(suggestform['suggestion'].field.widget,
            widgets.HiddenInput)

        # check that stemming is not done on words ending in "er"
        response = self.client.get(reverse('search'), {'q': 'shearre'})
        suggestform = self.assertInDict('suggestform', response.context)
        self.assertEqual('shearer', suggestform['suggestion'].value())

        # check that the job title field is indexed, and stemming is not
        # done on words ending in "er" for spelling queries
        # from binder.monkeypatch import before, breakpoint
        # from whoosh_backend import CustomWhooshBackend
        # before(CustomWhooshBackend, 'create_spelling_suggestion')(breakpoint)
        
        response = self.client.get(reverse('search'), {'q': 'songwritr'})
        suggestform = self.assertInDict('suggestform', response.context)
        self.assertEqual('songwriter', suggestform['suggestion'].value())

    def test_notes_field_for_user(self):
        index = self.unified_index.get_index(IntranetUser)
        
        from haystack.fields import CharField
        self.assertIsInstance(index.fields['notes'], CharField)
        self.assertEqual('notes', index.fields['notes'].model_attr)
        
        response = self.client.get(reverse('search'),
            {'q': "Yoko"}, follow=True)
        self.assert_search_results(response, [self.john])
        
    def test_update_document_removes_old_from_spelling(self):
        from whoosh_backend import CustomWhooshBackend
        self.assertIsInstance(self.backend, CustomWhooshBackend)

        self.assertEqual('kenneth', self.backend.create_spelling_suggestion('Kenneth'))
        self.assertEqual('starr', # not "barbie"!
            self.backend.create_spelling_suggestion('Barbie'))

        self.ken.full_name = "Barbie"
        self.ken.save()
        
        self.assertEqual('lennon', # not "kenneth"!
            self.backend.create_spelling_suggestion('Kenneth'))
        self.assertEqual('barbie', self.backend.create_spelling_suggestion('Barbie'))

    """
    def test_search_with_no_results_does_not_crash(self):
        for model, index in self.unified.indexes.iteritems():
            from django.contrib.auth.models import User
            if issubclass(model, User):
                # don't delete the current user, or we'll be logged out
                model.objects.exclude(id=self.current_user.id).delete()
            else:
                model.objects.all().delete()
        
        # list all documents
        response = self.client.get(reverse('search'),
            {'q': '', 'id_models[]': 'documents.document'}, follow=True) 
        form = self.assertIn('form', response.context)
        self.assertEquals(0, form.count)
        table = self.assertIn('results_table', response.context,
            "Should be a results table on this page:\n\n%s" % response.content) 
        queryset = table.data.queryset
        results = list(queryset)
        self.assertEqual(0, len(results), "unexpected results in list: %s" %
            results)
    """

    def test_program_choices_are_updated_for_each_instance(self):
        programs = Program.objects.values_list('id', 'name')
        search_form = SearchFormWithAllFields()
        choices = search_form['programs'].field.choices
        self.assertItemsEqual(choices, programs)

        Program.objects.all()[0].delete()
        new_programs = Program.objects.values_list('id', 'name')
        search_form = SearchFormWithAllFields()
        choices = search_form['programs'].field.choices
        self.assertItemsEqual(choices, new_programs)

    def test_document_type_choices_are_updated_live_not_loaded_at_startup(self):
        doc_types = DocumentType.objects.values_list('id', 'name')
        search_form = SearchFormWithAllFields()
        choices = search_form['document_types'].field.choices
        self.assertItemsEqual(choices, doc_types)

        DocumentType.objects.all()[0].delete()
        new_doc_types = DocumentType.objects.values_list('id', 'name')
        search_form = SearchFormWithAllFields()
        choices = search_form['document_types'].field.choices
        self.assertItemsEqual(choices, new_doc_types)

    def test_searchqueryset_slice_does_not_return_None_entries_for_deleted_objects(self):
        """
        https://github.com/toastdriven/django-haystack/issues/602
        """

        response = self.client.get(reverse('search'),
            {'id_models[]': 'binder.intranetuser', 'q': 'ringo'})
        self.assertEqual(response.status_code, 200)
        table, queryset = self.assert_search_results_table_get_queryset(response)
        self.assertItemsEqual([self.ringo.pk], [r.pk for r in queryset[0:200]],
            "Missing or unexpected search results")

        # temporarily disable model delete signal handler, to leave
        # an entry in the search index pointing to a nonexistent model
        from binder import configurable 
        usi = self.unified_index.get_index(configurable.UserModel)
        from django.db.models import signals
        signals.post_delete.disconnect(usi.remove_object, sender=usi.get_model())
        self.ringo.delete()
        signals.post_delete.connect(usi.remove_object, sender=usi.get_model())

        response = self.client.get(reverse('search'),
            {'id_models[]': 'binder.intranetuser', 'q': 'ringo'})
        self.assertEqual(response.status_code, 200)
        table, queryset = self.assert_search_results_table_get_queryset(response)
        self.assertItemsEqual([], queryset[0:200],
            "Missing or unexpected search results")

from documents.tests import DocumentTestMixin
class DocumentSearchTests(SearchTestBase, DocumentTestMixin):
    fixtures = ['test_programs', 'test_permissions', 'test_users',
                'test_documenttypes']

    def setUp(self):
        super(DocumentSearchTests, self).setUp()
        self.john = IntranetUser.objects.get(username='john')
        self.ringo = IntranetUser.objects.get(username='ringo')
        self.login(self.john)
        from documents.models import Document
        self.index = self.unified_index.get_index(Document) 

    def test_create_document_indexes_program_properly(self):
        self.assert_create_document_by_post(title='boink')

        # did it save?
        from documents.models import Document
        doc = Document.objects.get()
        self.assertEqual('boink', doc.title)

        program = Program.objects.all()[0]
        self.assertItemsEqual([program], doc.programs.all())
        
        with self.backend.index.searcher() as searcher:
            from haystack.constants import ID, DJANGO_CT, DJANGO_ID
            kwargs = {
                DJANGO_CT: u"%s.%s" % (doc._meta.app_label, doc._meta.module_name),
                DJANGO_ID: u"%s" % doc.pk,
                }
            results = list(searcher.documents(**kwargs))
            self.assertEqual(1, len(results), "expected only one result, " +
                "but found: %s" % results)
            result = results[0]
            from django.utils.encoding import force_unicode
            self.assertEqual(force_unicode(program.id), result['programs'])
        
    def test_search_results_show_external_authors_field(self):
        self.assert_create_document_by_post(
            title='boink',
            authors=[self.john.id, self.ringo.id],
            external_authors="Pee Wee Herman")

        # did it save?
        from documents.models import Document
        doc = Document.objects.get()
        self.assertEqual('boink', doc.title)

        response = self.client.get(reverse('search'), {'q': 'boink'})
        table = response.context['results_table']
        self.assertIsInstance(table, SearchTable)

        columns = table.base_columns.items()
        self.assertIn('author_names', [c[0] for c in columns],
            "Can't find author_names column in table")

        queryset = table.data.queryset
        from haystack.query import SearchQuerySet
        self.assertIsInstance(queryset, SearchQuerySet,
            "Table should be generated from a SearchQuerySet, not a " +
            "normal QuerySet, otherwise the Haystack index is not being used")
        
        row = list(queryset)[0]
        self.assertItemsEqual([self.john.full_name, self.ringo.full_name,
            "Pee Wee Herman"], row.author_names,
            "Authors rendered in search results table, but not as expected")

    def test_word_2003_document_indexing(self):
        doc = Document()
        self.assign_fixture_to_filefield('word_2003.doc', doc.file) 
        
        self.assertEquals("Lorem ipsum dolor sit amet, consectetur " +
            "adipiscing elit.\n\n\nPraesent pharetra urna eu arcu blandit " +
            "nec pretium odio fermentum. Sed in orci quis risus interdum " +
            "lacinia ut eu nisl.\n\n", self.index.prepare_text(doc))

    def test_word_2007_document_indexing(self):
        doc = Document()
        self.assign_fixture_to_filefield('word_2007.docx', doc.file) 
        
        self.assertEquals("Lorem ipsum dolor sit amet, consectetur " +
            "adipiscing elit.\n\nPraesent pharetra urna eu arcu blandit " +
            "nec pretium odio fermentum. Sed in orci quis risus interdum " +
            "lacinia ut eu nisl.\n", self.index.prepare_text(doc))

    def test_word_2007_unicode(self):
        doc = Document()
        self.assign_fixture_to_filefield('smartquote-bullet.docx', doc.file) 
        from django.utils.encoding import force_unicode
        self.assertEquals(u'\u2019\n\u2022\t\n',
            force_unicode(self.index.prepare_text(doc)))

    def test_excel_2003_indexing(self):
        doc = Document()
        self.assign_fixture_to_filefield('excel_2003.xls', doc.file) 
        
        self.assertEquals("Sheet1\n\tLorem ipsum dolor sit amet, " +
            "consectetur adipiscing elit.\t\tPraesent pharetra urna eu " +
            "arcu blandit nec pretium odio fermentum.\n\tSed in orci " +
            "quis risus interdum lacinia ut eu nisl.\n\t\tSed facilisis " +
            "nibh eu diam tincidunt pellentesque semper nulla auctor.\n" +
            "\n\nSheet2\n\t\n\n\nSheet3\n\t\n\n\n",
            self.index.prepare_text(doc))

    def test_excel_2007_indexing(self):
        doc = Document()
        self.assign_fixture_to_filefield('excel_2007.xlsx', doc.file) 
        
        self.assertEquals("Sheet1\n\tLorem ipsum dolor sit amet, " +
            "consectetur adipiscing elit.\tPraesent pharetra urna eu " +
            "arcu blandit nec pretium odio fermentum.\n\tSed in orci " +
            "quis risus interdum lacinia ut eu nisl.\n\tSed facilisis " +
            "nibh eu diam tincidunt pellentesque semper nulla auctor." +
            "\n\n&\"Times New Roman,Regular\"&12&A\t\n\n" +
            "&\"Times New Roman,Regular\"&12Page &P\t\n\n\nSheet2\n\n" +
            "&\"Times New Roman,Regular\"&12&A\t\n\n" +
            "&\"Times New Roman,Regular\"&12Page &P\t\n\n\nSheet3\n\n" +
            "&\"Times New Roman,Regular\"&12&A\t\n\n" +
            "&\"Times New Roman,Regular\"&12Page &P\t\n\n\n",
            self.index.prepare_text(doc))

    def test_powerpoint_2003_indexing(self):
        doc = Document()
        self.assign_fixture_to_filefield('powerpoint_2003.ppt', doc.file) 
        
        self.assertEquals("Lorem Ipsum\n" +
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n" +
            "Praesent pharetra urna eu arcu blandit nec pretium odio " +
            "fermentum.\n" +
            "Sed in orci quis risus interdum lacinia ut eu nisl.\n\n\n\n\n",
            self.index.prepare_text(doc))

    def test_powerpoint_2007_indexing(self):
        doc = Document()
        self.assign_fixture_to_filefield('powerpoint_2007.pptx', doc.file) 
        
        self.assertEquals("Lorem Ipsum\n" +
            "Lorem ipsum dolor sit amet, consectetur adipiscing elit.\n" +
            "Praesent pharetra urna eu arcu blandit nec pretium odio " +
            "fermentum.\n" +
            "Sed in orci quis risus interdum lacinia ut eu nisl.\n",
            self.index.prepare_text(doc))

    def test_pdf_indexing(self):
        doc = Document()
        self.assign_fixture_to_filefield('word_pdf.pdf', doc.file) 
        
        self.assertEquals("\nLorem ipsum dolor sit amet, consectetur " +
            "adipiscing elit.\nPraesent pharetra urna eu arcu blandit " +
            "nec pretium odio fermentum. Sed in orci quis risus interdum " +
            "lacinia ut eu nisl.\n\n\n", self.index.prepare_text(doc))

