from binder.monkeypatch import before, after, patch

from haystack.backends.whoosh_backend import WhooshSearchBackend
def build_schema_with_debugging(original_function, self, fields):
    """
    print "build_schema fields = %s" % fields
    from haystack import connections
    
    unified = connections[self.connection_alias].get_unified_index()
    print "indexes = %s" % unified.indexes
    #        self.content_field_name, self.schema = self.build_schema(connections[self.connection_alias].get_unified_index().all_searchfields())
    print "collect_indexes = %s" % unified.collect_indexes()

    print "apps = %s" % settings.INSTALLED_APPS

    import inspect
    
    try:
        from django.utils import importlib
    except ImportError:
        from haystack.utils import importlib

    search_index_module = importlib.import_module("documents.search_indexes")
    for item_name, item in inspect.getmembers(search_index_module, inspect.isclass):
        print "%s: %s" % (item_name,
            getattr(item, 'haystack_use_for_indexing', False))

        if getattr(item, 'haystack_use_for_indexing', False):
            # We've got an index. Check if we should be ignoring it.
            class_path = "documents.search_indexes.%s" % (item_name)

            print "excluded_index %s = %s" % (class_path,
                class_path in unified.excluded_indexes)
            print "excluded_indexes_id %s = %s" % (str(item_name),
                unified.excluded_indexes_ids.get(item_name) == id(item))
    """
    from django.conf import settings
    print "build_schema: settings = %s" % settings
    print "build_schema: INSTALLED_APPS = %s" % settings.INSTALLED_APPS
    # import pdb; pdb.set_trace()
    return original_function(self, fields)
# patch(WhooshSearchBackend, 'build_schema', build_schema_with_debugging)

from haystack.utils.loading import UnifiedIndex
def build_with_debugging(original_function, self, indexes=None):
    print "UnifiedIndex build(%s)" % indexes
    import traceback
    traceback.print_stack()
    original_function(self, indexes)
    print "UnifiedIndex built: indexes = %s" % self.indexes
# patch(UnifiedIndex, 'build', build_with_debugging)

def collect_indexes_with_debugging(original_function, self):
    from django.conf import settings
    print "collect_indexes: settings = %s" % settings
    print "collect_indexes: INSTALLED_APPS = %s" % settings.INSTALLED_APPS
    # import pdb; pdb.set_trace()

    from haystack import connections
    from django.utils.module_loading import module_has_submodule
    import inspect
    
    try:
        from django.utils import importlib
    except ImportError:
        from haystack.utils import importlib

    for app in settings.INSTALLED_APPS:
        print "collect_indexes: trying %s" % app
        mod = importlib.import_module(app)

        try:
            search_index_module = importlib.import_module("%s.search_indexes" % app)
        except ImportError:
            if module_has_submodule(mod, 'search_indexes'):
                raise

            continue

        for item_name, item in inspect.getmembers(search_index_module, inspect.isclass):
            print "collect_indexes: %s: %s" % (item_name,
                getattr(item, 'haystack_use_for_indexing', False))
            if getattr(item, 'haystack_use_for_indexing', False):
                # We've got an index. Check if we should be ignoring it.
                class_path = "%s.search_indexes.%s" % (app, item_name)

                print "excluded_index %s = %s" % (class_path,
                    class_path in self.excluded_indexes)
                print "excluded_indexes_id %s = %s" % (str(item_name),
                    self.excluded_indexes_ids.get(item_name) == id(item))

                if class_path in self.excluded_indexes or self.excluded_indexes_ids.get(item_name) == id(item):
                    self.excluded_indexes_ids[str(item_name)] = id(item)
                    continue

    return original_function(self)
# patch(UnifiedIndex, 'collect_indexes', collect_indexes_with_debugging)

from south.management.commands.syncdb import Command as SouthSyncdbCommand
# @after(SouthSyncdbCommand, 'handle_noargs')
def haystack_reset_after_syncdb(self, migrate_all=False, **options):
    """
    Work around https://github.com/toastdriven/django-haystack/issues/495 and
    http://south.aeracode.org/ticket/1023 by resetting the UnifiedIndex
    after South's syncdb has run.
    """

    from haystack import connections
    for conn in connections.all():
        conn.get_unified_index().teardown_indexes()
        conn.get_unified_index().reset()
        conn.get_unified_index().setup_indexes()

@before(SouthSyncdbCommand, 'handle_noargs')
def haystack_init_before_syncdb(self, migrate_all=False, **options):
    """
    Alternative workaround, that initialises Haystack first, so that
    fixtures can be indexed.
    """
    # breakpoint()
    from haystack import connections
    for conn in connections.all():
        conn.get_unified_index().setup_indexes()

# from haystack.indexes import SearchIndex
# before(SearchIndex, 'update_object')(breakpoint)

# from haystack.indexes import RealTimeSearchIndex
# before(RealTimeSearchIndex, '_setup_save')(breakpoint)

# from django.forms.forms import BoundField
# before(BoundField, 'value')(breakpoint)

from haystack.management.commands.update_index import Command as UpdateCommand
@before(UpdateCommand, 'handle')
def dont_die_on_missing_files_in_update_index(self, *items, **options):
    def replacement_prepare_text(original_function, self, document):
        try:
            return original_function(self, document)
        except IOError as e: # missing file, cannot index
            return e
    from documents.search_indexes import DocumentIndex
    patch(DocumentIndex, 'prepare_text', replacement_prepare_text)
