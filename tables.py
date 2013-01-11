from django.contrib.admin.views.main import EMPTY_CHANGELIST_VALUE
from django.utils.safestring import mark_safe

import django_tables2 as tables

from binder.models import IntranetUser, Program
from documents.models import DocumentType

class SearchTable(tables.Table):
    title = tables.Column(verbose_name="Title")
    author_names = tables.Column(verbose_name="Authors")
    uploader = tables.Column(verbose_name="Uploaded By")
    created = tables.Column(verbose_name="Date Added")
    programs = tables.Column(verbose_name="Programs")
    document_type = tables.Column(verbose_name="Document Type")
    # score = tables.Column(verbose_name="Score")
    
    def render_title(self, value, record):
        if not record:
            return EMPTY_CHANGELIST_VALUE
        return mark_safe("<a href='%s'>%s</a>" % (record.object.get_absolute_url(),
            value))

    def render_author_names(self, value):
        if not value:
            return EMPTY_CHANGELIST_VALUE
        return ', '.join(value)
    
    def render_programs(self, value):
        if not value:
            return EMPTY_CHANGELIST_VALUE
        programs = Program.objects.in_bulk(value)
        return ', '.join([programs[long(i)].name for i in value])
    
    def render_document_type(self, value):
        if not value:
            return EMPTY_CHANGELIST_VALUE
        return DocumentType.objects.get(id=value).name
    
    class Meta:
        attrs = {'class': 'paleblue'}
        sortable = False

class UserSearchTable(tables.Table):
    title = tables.Column(verbose_name="Name")
    job_title = tables.Column(verbose_name="Job Title")
    logged_in = tables.Column(verbose_name="Logged In")

    def render_title(self, value, record):
        return mark_safe("<a href='%s'>%s</a>" % (record.object.get_absolute_url(),
            value))
        
    def render_logged_in(self, record):
        return "Yes" if record.object.is_logged_in() else "No"

    class Meta:
        attrs = {'class': 'paleblue'}
        sortable = False
