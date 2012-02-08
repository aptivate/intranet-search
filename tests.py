"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""

from django.core.urlresolvers import reverse
from django.test import TestCase
from django.template import Context

import settings

from binder.test_utils import AptivateEnhancedTestCase

class SearchTest(AptivateEnhancedTestCase):
    pass