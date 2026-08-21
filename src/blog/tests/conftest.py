"""Fixtures shared by more than one test module.

A helper used by exactly one module lives next to that module instead; keeping
this file small is what stops it turning into a second, invisible test suite.
"""

import pytest
from django.contrib.auth.models import User

from blog.models import Post


@pytest.fixture
def author(db):
    return User.objects.create_user("autor")


@pytest.fixture
def make_post(author):
    """Factory for posts, published by default.

    A factory rather than a single fixture instance because the ranking and
    fuzzy-fallback tests need several posts in one database, each with its own
    title and body.
    """

    def _make(
        title="Wdrażanie Django w Dockerze",
        body="Konfiguracja kontenerów dla aplikacji internetowej.",
        slug="wdrazanie-django",
        tags=(),
        status=Post.Status.PUBLISHED,
        **kwargs,
    ):
        post = Post.objects.create(
            title=title, slug=slug, author=author, body=body, status=status, **kwargs
        )
        if tags:
            post.tags.add(*tags)
        return post

    return _make
