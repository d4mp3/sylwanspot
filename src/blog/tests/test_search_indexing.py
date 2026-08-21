"""Post.search_vector is a derived column, and these cover the machinery that
keeps it in step with title, tags and body: the receivers in blog.signals and
the `rebuild_search_vectors` management command.

What a query then *finds* lives in test_search.py; this file only cares that
the right lexemes, with the right weights, end up in the row.
"""

import pytest
from django.core.management import call_command
from django.db import connection

from blog.models import Post
from blog.search import search_posts

pytestmark = pytest.mark.django_db


def vector_of(post):
    """The stored tsvector as text, read straight from the row.

    Deliberately bypasses the ORM: the point is to see what Postgres actually
    holds, not what Django thinks it wrote.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT search_vector::text FROM blog_post WHERE id = %s", [post.pk])
        return cursor.fetchone()[0]


def test_vector_is_populated_on_save(make_post):
    assert "django" in vector_of(make_post())


def test_vector_reflects_edits(make_post):
    post = make_post()
    post.title = "Kubernetes od zera"
    post.save()

    vector = vector_of(post)
    assert "kubernetes" in vector
    assert "django" not in vector


def test_vector_includes_tags(make_post):
    post = make_post(body="Treść bez nazw technologii.", tags=["devops"])
    assert "devops" in vector_of(post)
    # ...and searching by a tag name alone finds the post.
    results, mode = search_posts("devops")
    assert mode == "fts"
    assert [p.pk for p in results] == [post.pk]


def test_removing_a_tag_removes_it_from_the_vector(make_post):
    post = make_post(tags=["devops"])
    post.tags.remove("devops")
    assert "devops" not in vector_of(post)


def test_field_weights_are_applied(make_post):
    vector = vector_of(make_post())
    # title -> A, body -> C
    assert "'django':2A" in vector
    assert "C" in vector.split("'django':2A")[1]


def test_rebuild_command_matches_the_signal_path(make_post):
    post = make_post(tags=["docker"])
    expected = vector_of(post)

    Post.objects.update(search_vector=None)
    call_command("rebuild_search_vectors", verbosity=0)
    assert vector_of(post) == expected
