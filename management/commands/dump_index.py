from django.core.management.base import BaseCommand, CommandError

class Command(BaseCommand):
    help = 'Dump the contents of the Whoosh search index'
    args = '[index_dir]'

    def handle(self, *args, **options):
        from whoosh.index import open_dir
        from settings import HAYSTACK_CONNECTIONS
        
        if len(args) == 0:
            path = HAYSTACK_CONNECTIONS['default']['PATH']
        elif len(args) == 1:
            path = args[0] 
        else:
            raise CommandError("Command accepts only one, optional argument")
        
        ix = open_dir(path)
        
        with ix.reader() as reader:
            for field_and_term in reader.all_terms():
                self.stdout.write('posting %s = %s\n' %
                    (field_and_term, list(reader.postings(*field_and_term).all_items())))
        
        with ix.searcher() as searcher:
            results = searcher.documents()
            for i, r in enumerate(results):
                deleted = searcher.reader().is_deleted(i)
                
                if deleted:
                    deleted_str = "deleted"
                else:
                    deleted_str = "alive"
                
                self.stdout.write('result %d [%s] = %s\n' %
                    (i, deleted_str, r))
