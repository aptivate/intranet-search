from django.core.management.base import NoArgsCommand, CommandError

from whoosh.filedb.filestore import FileStorage

class Command(NoArgsCommand):
    help = 'Test searching using Haystack and Whoosh'

    def handle_noargs(self, **options):
        from settings import HAYSTACK_CONNECTIONS
        storage = FileStorage(HAYSTACK_CONNECTIONS['default']['PATH'])
        # storage = FileStorage('/dev/shm/whoosh/')
        
        ix = storage.open_index('MAIN')
        
        with ix.searcher() as s:
            from whoosh.qparser import QueryParser
            qp = QueryParser("text", schema=ix.schema)

            q = qp.parse(u"(*) AND (django_ct:documents.document)")
            results = s.search(q)
            for i, r in enumerate(results):
                print "%d: (%s) %s" % (i, r['id'], r['title'])
