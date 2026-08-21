"""Coverage of the views' rendered output.

These go through the URLconf and the templates on purpose: the Polish plural
forms they assert are produced in the templates, not in Python, so a unit test
of pluralize_pl alone would not catch a template that forgot to call it.

When this file outgrows a single screenful per view, split it into a
tests/views/ package with one module per view rather than letting it sprawl.
"""

import pytest
from django.urls import reverse

from blog.models import Comment

from .assertions import assert_contains

pytestmark = pytest.mark.django_db


class TestSearchView:
    @pytest.fixture
    def make_posts(self, make_post):
        def _make(count):
            return [
                make_post(
                    title=f"Django odcinek {n}",
                    body="Treść wpisu.",
                    slug=f"django-{n}",
                )
                for n in range(count)
            ]

        return _make

    def test_form_is_shown_without_a_query(self, client):
        response = client.get(reverse("blog:post_search"))
        assert response.status_code == 200
        assert_contains(response, "Szukaj postów")

    @pytest.mark.parametrize(
        "count, expected",
        [
            (1, "Znaleziono 1 wynik"),
            (2, "Znaleziono 2 wyniki"),
            (5, "Znaleziono 5 wyników"),
        ],
    )
    def test_result_count_uses_the_correct_polish_form(self, client, make_posts, count, expected):
        # 1 -> "wynik", 2 -> "wyniki", 5 -> "wyników": the three cases the old
        # `{{ total|pluralize }}` could not express.
        make_posts(count)

        response = client.get(reverse("blog:post_search"), {"query": "django"})
        assert_contains(response, expected, html=False)

    def test_no_results_message(self, client):
        response = client.get(reverse("blog:post_search"), {"query": "zupełnie-nic"})
        assert_contains(response, "Brak wyników")

    def test_blank_query_is_rejected_by_the_form(self, client):
        response = client.get(reverse("blog:post_search"), {"query": "   "})
        assert response.status_code == 200
        assert response.context["total_results"] == 0


class TestPostDetailCommentCount:
    """The comment counter used a hand-rolled {% if %} chain that listed 2/3/4
    literally, so it printed "22 komentarzy" instead of "22 komentarze" --
    wrong for 51 of the first 200 counts. pluralize_pl replaces it."""

    @pytest.fixture
    def post(self, make_post):
        return make_post(
            title="Wpis z komentarzami",
            body="Treść.",
            slug="wpis-z-komentarzami",
        )

    @staticmethod
    def add_comments(post, count):
        Comment.objects.bulk_create(
            Comment(post=post, name=f"Gość {n}", email="a@b.pl", body="Treść.")
            for n in range(count)
        )

    @pytest.mark.parametrize(
        "count, expected",
        [
            (1, "1 komentarz"),
            (2, "2 komentarze"),
            (5, "5 komentarzy"),
            # The cases the old {% if %} chain got wrong:
            (22, "22 komentarze"),
            (25, "25 komentarzy"),
        ],
    )
    def test_counts_use_the_correct_polish_form(self, client, post, count, expected):
        self.add_comments(post, count)

        response = client.get(post.get_absolute_url())
        assert_contains(response, f"<h2>{expected}</h2>", html=True)

    def test_zero_comments(self, client, post):
        response = client.get(post.get_absolute_url())
        assert_contains(response, "<h2>0 komentarzy</h2>", html=True)
