"""Smoke tests for the database this suite runs against.

Nothing here asserts anything about application code -- these check that the
container provides the `polish` text search configuration (created by migration
0005) and pg_trgm. When they fail, the db container is probably running an image
built before postgres/Dockerfile, and fixing that first saves debugging the
dozen search tests that fail as a consequence.
"""

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def scalar(sql, params=None):
    with connection.cursor() as cursor:
        cursor.execute(sql, params or [])
        row = cursor.fetchone()
    return row[0] if row else None


def test_configuration_exists():
    assert (
        scalar("SELECT cfgname FROM pg_ts_config WHERE cfgname = 'polish'") == "polish"
    )


@pytest.mark.parametrize("form", ["kot", "koty", "kota", "kotem"])
def test_hunspell_normalises_polish_inflection(form):
    # Hunspell emits every base form it can justify for an ambiguous token, so
    # assert that 'kot' is reachable from each inflected form rather than
    # asserting an exact tsvector.
    assert scalar(
        "SELECT to_tsvector('polish', %s) @@ to_tsquery('polish', 'kot')", [form]
    ), f"{form!r} should be indexed under the lexeme 'kot'"


def test_unknown_words_fall_through_to_simple():
    # Without `simple` as the terminal dictionary, technology names would be
    # dropped from the index entirely.
    assert (
        scalar("SELECT dictionary::text FROM ts_debug('polish', 'Kubernetes')")
        == "simple"
    )


def test_stop_words_are_removed():
    assert scalar("SELECT to_tsvector('polish', 'i w na oraz')::text") == ""


def test_pg_trgm_is_installed():
    assert scalar("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'") is not None
