from search import SearchViewWithExtraFilters
from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^$', SearchViewWithExtraFilters(), name='search'),
)
