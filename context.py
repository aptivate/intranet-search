# extensions to django.core.context_processors

from forms import QuickSearchForm

def additions(request):
    return {
        'search': {
            'form': QuickSearchForm(request.GET),
        },
    }
