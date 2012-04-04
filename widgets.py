from django.forms import widgets

class CheckboxesWithCustomHtmlName(widgets.CheckboxSelectMultiple):
    def __init__(self, attrs=None, choices=(), html_name=None):
        super(CheckboxesWithCustomHtmlName, self).__init__(attrs=attrs,
            choices=choices)
        self.html_name = html_name
        
    def render(self, name, value, attrs=None, choices=()):
        if self.html_name:
            name = self.html_name

        return super(CheckboxesWithCustomHtmlName, self).render(name, value,
            attrs, choices)

    def value_from_datadict(self, data, files, name):
        if self.html_name:
            name = self.html_name

        v = super(CheckboxesWithCustomHtmlName, self).value_from_datadict(data,
            files, name)
        # print "SelectMultiple.value_from_datadict(%s, %s, %s, %s) = %s" % (
        #     self, data, files, name, v)
        return v

class SelectMultipleWithJquery(widgets.SelectMultiple):
    def __init__(self, attrs=None, choices=(), html_name=None):
        super(SelectMultipleWithJquery, self).__init__(attrs=attrs,
            choices=choices)
        self.html_name = html_name
        
    def render(self, name, value, attrs=None, choices=()):
        if self.html_name:
            name = self.html_name

        if attrs is None:
            attrs = {}
        
        html_attrs = {'class': 'multiselect-jquery'}
        html_attrs.update(attrs)

        return super(SelectMultipleWithJquery, self).render(name, value,
            attrs=html_attrs, choices=choices)

    def value_from_datadict(self, data, files, name):
        if self.html_name:
            name = self.html_name

        v = super(SelectMultipleWithJquery, self).value_from_datadict(data,
            files, name)
        # print "SelectMultiple.value_from_datadict(%s, %s, %s, %s) = %s" % (
        #     self, data, files, name, v)
        return v
