from django.core.management.base import NoArgsCommand, CommandError

from whoosh.filedb.filestore import FileStorage

class Command(NoArgsCommand):
    help = 'Show the effects of sorting on search result scores'

    def handle_noargs(self, **options):
        from settings import HAYSTACK_CONNECTIONS
        storage = FileStorage(HAYSTACK_CONNECTIONS['default']['PATH'])
        # storage = FileStorage('/dev/shm/whoosh/')
        
        ix = storage.open_index('MAIN')
        
        with ix.searcher() as s:
            from whoosh.qparser import QueryParser
            qp = QueryParser("content", schema=ix.schema)

            q = qp.parse(u"((title:whee OR text:whee OR notes:whee OR program:whee OR job_title:whee) AND document_type:5 AND (programs:1 OR programs:2))")
            results = s.search(q)
            for i, r in enumerate(results):
                print "%d: (%s) %s" % (i, r['id'], r['title'])

            q = qp.parse(u"((title:whee OR text:whee OR notes:whee OR program:whee OR job_title:whee) AND document_type:5 AND (programs:1 OR programs:2))")
            results = s.search(q, sortedby='-created')
            for i, r in enumerate(results):
                print "%d: (%s) %s" % (i, r['id'], r['title'])
