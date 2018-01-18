from views import SearchViewWithExtraFilters, DocumentListView
from django.conf.urls import url

urlpatterns = (
    url(r'^$', SearchViewWithExtraFilters(), name='search'),
    url(r'^documents', DocumentListView(), name='document_list')
)
