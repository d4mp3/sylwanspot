"""Behaviour of blog.search.search_posts(): what a query finds, in what order,
which mode it reports back, and how many database round-trips it costs.

The tsvector these queries run against is built elsewhere -- see
test_search_indexing.py.
"""

import pytest

from blog.models import Post
from blog.search import TRIGRAM_THRESHOLD, search_posts

pytestmark = pytest.mark.django_db


def test_body_only_matches_are_returned(make_post):
    """The regression this whole change is about.

    With the old `rank__gte=0.3` filter a body-only match scored ~0.12 and was
    silently dropped, so a post could discuss Django at length and still be
    unfindable unless the word was in its title.
    """
    title_hit = make_post("Django od podstaw", "Cokolwiek.", "django-od-podstaw")
    body_hit = make_post(
        "Notatki z konferencji",
        "Najciekawszy był wykład o Django i jego ekosystemie.",
        "notatki",
    )

    results, mode = search_posts("django")
    assert mode == "fts"
    # Both found, and the title hit ranks first.
    assert [p.pk for p in results] == [title_hit.pk, body_hit.pk]
    assert results[0].rank > results[1].rank


@pytest.mark.parametrize("query", ["kot", "koty", "kotem"])
def test_inflected_query_matches_inflected_text(make_post, query):
    post = make_post("Zdjęcia kotów", "Galeria z psami.", "zdjecia-kotow")

    results, mode = search_posts(query)
    assert mode == "fts"
    assert [p.pk for p in results] == [post.pk]


def test_drafts_are_excluded(make_post):
    make_post("Szkic o Django", "Treść.", "szkic", status=Post.Status.DRAFT)
    assert search_posts("django") == ([], "empty")


def test_websearch_operators(make_post):
    a = make_post("Docker Compose w praktyce", "Konfiguracja.", "compose")
    make_post("Docker Swarm w praktyce", "Konfiguracja.", "swarm")

    results, _ = search_posts('"docker compose"')
    assert [p.pk for p in results] == [a.pk]

    results, _ = search_posts("docker -swarm")
    assert [p.pk for p in results] == [a.pk]


@pytest.mark.parametrize("query", ["&&& |||", "!(:*", "  ", "'"])
def test_malformed_query_does_not_raise(make_post, query):
    make_post("Cokolwiek", "Treść.", "cokolwiek")
    assert search_posts(query) == ([], "empty")


def test_fuzzy_fallback_recovers_a_typo(make_post):
    post = make_post("Kubernetes dla początkujących", "Treść.", "k8s")

    results, mode = search_posts("kubernets")
    assert mode == "fuzzy"
    assert [p.pk for p in results] == [post.pk]


def test_fuzzy_fallback_recovers_missing_diacritics(make_post):
    post = make_post("Kubernetes dla początkujących", "Treść.", "k8s")

    results, mode = search_posts("poczatkujacych")
    assert mode == "fuzzy"
    assert [p.pk for p in results] == [post.pk]


def test_fuzzy_fallback_does_not_run_when_fts_succeeds(make_post, django_assert_num_queries):
    make_post("Kubernetes dla początkujących", "Treść.", "k8s")
    # The successful path costs exactly one query: the fallback must not be
    # executed speculatively alongside it.
    with django_assert_num_queries(1):
        _, mode = search_posts("kubernetes")
    assert mode == "fts"


def test_fallback_costs_one_extra_query_only_when_fts_is_empty(make_post, django_assert_num_queries):
    make_post("Kubernetes dla początkujących", "Treść.", "k8s")
    with django_assert_num_queries(2):
        _, mode = search_posts("kubernets")
    assert mode == "fuzzy"


def test_blank_query_does_not_hit_the_database(django_assert_num_queries):
    with django_assert_num_queries(0):
        assert search_posts("   ") == ([], "empty")


def test_unrelated_query_returns_nothing(make_post):
    make_post("Wdrażanie Django w Dockerze", "Treść.", "django")
    # "gotowanie" shares a Polish suffix with "Wdrażanie" and nothing else;
    # strict_word_similarity scores it ~0.18, well under the threshold.
    assert search_posts("gotowanie") == ([], "empty")


def test_fuzzy_fallback_does_not_match_a_short_common_word(make_post):
    """Regression from real data.

    With plain word_similarity, the query "poscik" scored 0.429 against any
    title merely containing "post" -- the same score as the genuine
    diacritic-free hit "poczatkujacych" -> "początkujących". Switching to
    strict_word_similarity (word-boundary aligned) drops the bogus pair to
    0.333 while the real one stays at 0.429.
    """
    wanted = make_post("Pościk post", "Treść.", "poscik-post")
    make_post("markdown post", "Treść.", "markdown-post")
    make_post("Another post", "Treść.", "another-post")

    results, mode = search_posts("poscik")
    assert mode == "fuzzy"
    assert [p.pk for p in results] == [wanted.pk]


def test_transpositions_are_a_known_gap(make_post):
    """Documents a limitation rather than asserting a wish.

    Trigrams score "djnago" ~0.27 against a title containing "Django" -- lower
    than unrelated words scoring on shared Polish suffixes. No safe threshold
    recovers transpositions; that would need edit distance.
    """
    make_post("Wdrażanie Django w Dockerze", "Treść.", "django")

    assert search_posts("djnago") == ([], "empty")
    assert TRIGRAM_THRESHOLD > 0.28
