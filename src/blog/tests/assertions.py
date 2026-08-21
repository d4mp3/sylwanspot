"""Django's response assertions, usable from plain pytest functions.

pytest-django provides the ``client`` fixture but not the assertion helpers
that go with it, and ``assertContains(..., html=True)`` compares markup
semantically rather than byte-for-byte -- worth keeping wherever the rendered
HTML is what's under test. SimpleTestCase carries them as instance methods, so
bind them once from an instance that never runs a test.
"""

from django.test import SimpleTestCase

_case = SimpleTestCase()

assert_contains = _case.assertContains
