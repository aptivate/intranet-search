from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Run (test) a search query against the Whoosh index'
    args = '[index_dir] query'

    def handle(self, *args, **options):
        from whoosh.index import open_dir
        from settings import HAYSTACK_CONNECTIONS
        
        if len(args) == 1:
            path = HAYSTACK_CONNECTIONS['default']['PATH']
            query_str = args[0]
        elif len(args) == 1:
            path = args[0]
            query_str = args[1]
        else:
            raise CommandError("Command accepts only one or two arguments")
        
        from django.utils.encoding import force_unicode
        query_str = force_unicode(query_str)
        
        ix = open_dir(path)
        
        with ix.searcher() as searcher:
            from whoosh.qparser import QueryParser
            parser = QueryParser("text", ix.schema)
            query = parser.parse(query_str)
            results = searcher.search(query, limit=100)
            
            if len(results) == 0:
                self.stdout.write('no results\n')
            else:
                for i, r in enumerate(results):
                    docnum = results.docnum(i)
                    deleted = searcher.reader().is_deleted(docnum)

                    if deleted:
                        deleted_str = "deleted"
                    else:
                        deleted_str = "alive"
                    
                    self.stdout.write('result %d [%s] = %s\n' %
                        (i, deleted_str, r))
                
                self.stdout.write('\n%d results\n' % len(results))
