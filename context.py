# extensions to django.core.context_processors

import search

def additions(request):
    return {
        'search': {
            'form': search.QuickSearchForm(request.GET),
        },
    }
