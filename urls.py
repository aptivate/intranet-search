from search import SearchViewWithExtraFilters
from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url(r'^$', SearchViewWithExtraFilters(), name='search'),
)
