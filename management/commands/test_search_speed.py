from django.core.management.base import NoArgsCommand, CommandError

from whoosh.filedb.filestore import FileStorage

def run_search(query):
    from settings import HAYSTACK_CONNECTIONS
    storage = FileStorage(HAYSTACK_CONNECTIONS['default']['PATH'])
    # storage = FileStorage('/dev/shm/whoosh/')
    
    ix = storage.open_index('MAIN')
    
    with ix.searcher() as s:
        from whoosh.qparser import QueryParser
        qp = QueryParser("text", schema=ix.schema)

        q = qp.parse(query)
        results = s.search(q)
        for i, r in enumerate(results):
            result = "%d: (%s) %s" % (i, r['id'], r['title']) # ignored


class Command(NoArgsCommand):
    help = 'Test searching using Haystack and Whoosh'

    def time(self, python_code):
        import timeit
        time = timeit.Timer(python_code, "from %s import run_search" % __name__).timeit(number=5)
        print "%s = %s" % (python_code, time)
         
    def handle_noargs(self, **options):
        self.time('run_search(u"django_ct:documents.document")')
        self.time('run_search(u"(*)")')
        self.time('run_search(u"(*) AND (django_ct:documents.document)")')
        self.time('run_search(u"text:foo")')
        self.time('run_search(u"(text:foo) AND (django_ct:documents.document)")')

        