from django.core.management.base import NoArgsCommand, CommandError

from whoosh.filedb.filestore import FileStorage

class Command(NoArgsCommand):
    help = 'Dump the contents of the Whoosh search index'

    def handle_noargs(self, **options):
        # from settings import HAYSTACK_CONNECTIONS
        # storage = FileStorage(HAYSTACK_CONNECTIONS['default']['PATH'])
        storage = FileStorage('/dev/shm/whoosh/')
        
        ix = storage.open_index('SPELL')
        
        with ix.reader() as r:
            for id in r.all_doc_ids():
                print r.stored_fields(id)
