from search import SearchViewWithExtraFilters, DocumentListView
from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url(r'^$', SearchViewWithExtraFilters(), name='search'),
    url(r'^documents', DocumentListView(), name='document_list')
)
