from views import SearchViewWithExtraFilters, DocumentListView
from django.conf.urls import patterns, url

urlpatterns = patterns('',
    url(r'^$', SearchViewWithExtraFilters(), name='search'),
    url(r'^documents', DocumentListView(), name='document_list')
)
