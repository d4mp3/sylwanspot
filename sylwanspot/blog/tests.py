from django.contrib.auth.models import User
from django.db import connection
from django.test import TestCase
from django.urls import reverse

from .models import Comment, Post
from .search import TRIGRAM_THRESHOLD, search_posts
from .templatetags.blog_tags import pluralize_pl


class PolishTextSearchConfigTests(TestCase):
    """The `polish` configuration is created by migration 0005, so it must be
    present in the test database too. If these fail, the db container is
    probably running an image built before postgres/Dockerfile."""

    def _scalar(self, sql, params=None):
        with connection.cursor() as cursor:
            cursor.execute(sql, params or [])
            row = cursor.fetchone()
        return row[0] if row else None

    def test_configuration_exists(self):
        self.assertEqual(
            self._scalar("SELECT cfgname FROM pg_ts_config WHERE cfgname = 'polish'"),
            "polish",
        )

    def test_hunspell_normalises_polish_inflection(self):
        # Hunspell emits every base form it can justify for an ambiguous token,
        # so assert that 'kot' is reachable from each inflected form rather
        # than asserting an exact tsvector.
        for form in ("kot", "koty", "kota", "kotem"):
            with self.subTest(form=form):
                self.assertTrue(
                    self._scalar(
                        "SELECT to_tsvector('polish', %s) @@ to_tsquery('polish', 'kot')",
                        [form],
                    ),
                    f"{form!r} should be indexed under the lexeme 'kot'",
                )

    def test_unknown_words_fall_through_to_simple(self):
        # Without `simple` as the terminal dictionary, technology names would
        # be dropped from the index entirely.
        self.assertEqual(
            self._scalar("SELECT dictionary::text FROM ts_debug('polish', 'Kubernetes')"),
            "simple",
        )

    def test_stop_words_are_removed(self):
        self.assertEqual(
            self._scalar("SELECT to_tsvector('polish', 'i w na oraz')::text"),
            "",
        )

    def test_pg_trgm_is_installed(self):
        self.assertIsNotNone(
            self._scalar("SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm'")
        )


class SearchVectorMaintenanceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user("autor")

    def _make(self, **kwargs):
        defaults = {
            "title": "Wdrażanie Django w Dockerze",
            "slug": "wdrazanie-django",
            "author": self.author,
            "body": "Konfiguracja kontenerów dla aplikacji internetowej.",
            "status": Post.Status.PUBLISHED,
        }
        return Post.objects.create(**{**defaults, **kwargs})

    def _vector(self, post):
        with connection.cursor() as cursor:
            cursor.execute("SELECT search_vector::text FROM blog_post WHERE id = %s", [post.pk])
            return cursor.fetchone()[0]

    def test_vector_is_populated_on_save(self):
        post = self._make()
        self.assertIn("django", self._vector(post))

    def test_vector_reflects_edits(self):
        post = self._make()
        post.title = "Kubernetes od zera"
        post.save()
        vector = self._vector(post)
        self.assertIn("kubernetes", vector)
        self.assertNotIn("django", vector)

    def test_vector_includes_tags(self):
        post = self._make(body="Treść bez nazw technologii.")
        post.tags.add("devops")
        self.assertIn("devops", self._vector(post))
        # ...and searching by a tag name alone finds the post.
        results, mode = search_posts("devops")
        self.assertEqual(mode, "fts")
        self.assertEqual([p.pk for p in results], [post.pk])

    def test_removing_a_tag_removes_it_from_the_vector(self):
        post = self._make()
        post.tags.add("devops")
        post.tags.remove("devops")
        self.assertNotIn("devops", self._vector(post))

    def test_field_weights_are_applied(self):
        vector = self._vector(self._make())
        # title -> A, body -> C
        self.assertIn("'django':2A", vector)
        self.assertIn("C", vector.split("'django':2A")[1])

    def test_rebuild_command_matches_the_signal_path(self):
        from django.core.management import call_command

        post = self._make()
        post.tags.add("docker")
        expected = self._vector(post)

        Post.objects.update(search_vector=None)
        call_command("rebuild_search_vectors", verbosity=0)
        self.assertEqual(self._vector(post), expected)


class SearchBehaviourTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user("autor")

    def _make(self, title, body, slug, tags=(), status=Post.Status.PUBLISHED):
        post = Post.objects.create(
            title=title, slug=slug, author=self.author, body=body, status=status
        )
        if tags:
            post.tags.add(*tags)
        return post

    def test_body_only_matches_are_returned(self):
        """The regression this whole change is about.

        With the old `rank__gte=0.3` filter a body-only match scored ~0.12 and
        was silently dropped, so a post could discuss Django at length and
        still be unfindable unless the word was in its title.
        """
        title_hit = self._make("Django od podstaw", "Cokolwiek.", "django-od-podstaw")
        body_hit = self._make(
            "Notatki z konferencji",
            "Najciekawszy był wykład o Django i jego ekosystemie.",
            "notatki",
        )

        results, mode = search_posts("django")
        self.assertEqual(mode, "fts")
        # Both found, and the title hit ranks first.
        self.assertEqual([p.pk for p in results], [title_hit.pk, body_hit.pk])
        self.assertGreater(results[0].rank, results[1].rank)

    def test_inflected_query_matches_inflected_text(self):
        post = self._make("Zdjęcia kotów", "Galeria z psami.", "zdjecia-kotow")
        for query in ("kot", "koty", "kotem"):
            with self.subTest(query=query):
                results, mode = search_posts(query)
                self.assertEqual(mode, "fts")
                self.assertEqual([p.pk for p in results], [post.pk])

    def test_drafts_are_excluded(self):
        self._make("Szkic o Django", "Treść.", "szkic", status=Post.Status.DRAFT)
        results, mode = search_posts("django")
        self.assertEqual((results, mode), ([], "empty"))

    def test_websearch_operators(self):
        a = self._make("Docker Compose w praktyce", "Konfiguracja.", "compose")
        self._make("Docker Swarm w praktyce", "Konfiguracja.", "swarm")

        results, _ = search_posts('"docker compose"')
        self.assertEqual([p.pk for p in results], [a.pk])

        results, _ = search_posts("docker -swarm")
        self.assertEqual([p.pk for p in results], [a.pk])

    def test_malformed_query_does_not_raise(self):
        self._make("Cokolwiek", "Treść.", "cokolwiek")
        for query in ("&&& |||", "!(:*", "  ", "'"):
            with self.subTest(query=query):
                results, mode = search_posts(query)
                self.assertEqual(mode, "empty")
                self.assertEqual(results, [])

    def test_fuzzy_fallback_recovers_a_typo(self):
        post = self._make("Kubernetes dla początkujących", "Treść.", "k8s")
        results, mode = search_posts("kubernets")
        self.assertEqual(mode, "fuzzy")
        self.assertEqual([p.pk for p in results], [post.pk])

    def test_fuzzy_fallback_recovers_missing_diacritics(self):
        post = self._make("Kubernetes dla początkujących", "Treść.", "k8s")
        results, mode = search_posts("poczatkujacych")
        self.assertEqual(mode, "fuzzy")
        self.assertEqual([p.pk for p in results], [post.pk])

    def test_fuzzy_fallback_does_not_run_when_fts_succeeds(self):
        self._make("Kubernetes dla początkujących", "Treść.", "k8s")
        # The successful path costs exactly one query: the fallback must not be
        # executed speculatively alongside it.
        with self.assertNumQueries(1):
            _, mode = search_posts("kubernetes")
        self.assertEqual(mode, "fts")

    def test_fallback_costs_one_extra_query_only_when_fts_is_empty(self):
        self._make("Kubernetes dla początkujących", "Treść.", "k8s")
        with self.assertNumQueries(2):
            _, mode = search_posts("kubernets")
        self.assertEqual(mode, "fuzzy")

    def test_blank_query_does_not_hit_the_database(self):
        with self.assertNumQueries(0):
            self.assertEqual(search_posts("   "), ([], "empty"))

    def test_unrelated_query_returns_nothing(self):
        self._make("Wdrażanie Django w Dockerze", "Treść.", "django")
        # "gotowanie" shares a Polish suffix with "Wdrażanie" and nothing else;
        # strict_word_similarity scores it ~0.18, well under the threshold.
        results, mode = search_posts("gotowanie")
        self.assertEqual((results, mode), ([], "empty"))

    def test_fuzzy_fallback_does_not_match_a_short_common_word(self):
        """Regression from real data.

        With plain word_similarity, the query "poscik" scored 0.429 against any
        title merely containing "post" -- the same score as the genuine
        diacritic-free hit "poczatkujacych" -> "początkujących". Switching to
        strict_word_similarity (word-boundary aligned) drops the bogus pair to
        0.333 while the real one stays at 0.429.
        """
        wanted = self._make("Pościk post", "Treść.", "poscik-post")
        self._make("markdown post", "Treść.", "markdown-post")
        self._make("Another post", "Treść.", "another-post")

        results, mode = search_posts("poscik")
        self.assertEqual(mode, "fuzzy")
        self.assertEqual([p.pk for p in results], [wanted.pk])

    def test_transpositions_are_a_known_gap(self):
        """Documents a limitation rather than asserting a wish.

        Trigrams score "djnago" ~0.27 against a title containing "Django" --
        lower than unrelated words scoring on shared Polish suffixes. No safe
        threshold recovers transpositions; that would need edit distance.
        """
        self._make("Wdrażanie Django w Dockerze", "Treść.", "django")
        results, mode = search_posts("djnago")
        self.assertEqual((results, mode), ([], "empty"))
        self.assertLess(0.28, TRIGRAM_THRESHOLD)


class SearchViewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user("autor")

    def _make_posts(self, count):
        for n in range(count):
            Post.objects.create(
                title=f"Django odcinek {n}",
                slug=f"django-{n}",
                author=self.author,
                body="Treść wpisu.",
                status=Post.Status.PUBLISHED,
            )

    def test_form_is_shown_without_a_query(self):
        response = self.client.get(reverse("blog:post_search"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Szukaj postów")

    def test_result_count_uses_the_correct_polish_form(self):
        # 1 -> "wynik", 2 -> "wyniki", 5 -> "wyników": the three cases the old
        # `{{ total|pluralize }}` could not express.
        for count, expected in ((1, "Znaleziono 1 wynik"),
                                (2, "Znaleziono 2 wyniki"),
                                (5, "Znaleziono 5 wyników")):
            with self.subTest(count=count):
                Post.objects.all().delete()
                self._make_posts(count)
                response = self.client.get(reverse("blog:post_search"), {"query": "django"})
                self.assertContains(response, expected, html=False)

    def test_no_results_message(self):
        response = self.client.get(reverse("blog:post_search"), {"query": "zupełnie-nic"})
        self.assertContains(response, "Brak wyników")

    def test_blank_query_is_rejected_by_the_form(self):
        response = self.client.get(reverse("blog:post_search"), {"query": "   "})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["total_results"], 0)


class PostDetailPluralTests(TestCase):
    """The comment counter used a hand-rolled {% if %} chain that listed 2/3/4
    literally, so it printed "22 komentarzy" instead of "22 komentarze" -- wrong
    for 51 of the first 200 counts. pluralize_pl replaces it."""

    @classmethod
    def setUpTestData(cls):
        cls.author = User.objects.create_user("autor")
        cls.post = Post.objects.create(
            title="Wpis z komentarzami",
            slug="wpis-z-komentarzami",
            author=cls.author,
            body="Treść.",
            status=Post.Status.PUBLISHED,
        )

    def _get(self):
        return self.client.get(self.post.get_absolute_url())

    def _add_comments(self, count):
        Comment.objects.bulk_create(
            Comment(post=self.post, name=f"Gość {n}", email="a@b.pl", body="Treść.")
            for n in range(count)
        )

    def test_counts_use_the_correct_polish_form(self):
        for count, expected in ((1, "1 komentarz"),
                                (2, "2 komentarze"),
                                (5, "5 komentarzy"),
                                # The cases the old {% if %} chain got wrong:
                                (22, "22 komentarze"),
                                (25, "25 komentarzy")):
            with self.subTest(count=count):
                Comment.objects.all().delete()
                self._add_comments(count)
                self.assertContains(self._get(), f"<h2>{expected}</h2>", html=True)

    def test_zero_comments(self):
        self.assertContains(self._get(), "<h2>0 komentarzy</h2>", html=True)


class PluralizePlTests(TestCase):
    """Polish needs three forms; Django's `pluralize` only knows two."""

    def test_singular(self):
        self.assertEqual(pluralize_pl(1, "wynik,wyniki,wyników"), "wynik")

    def test_few_form(self):
        for n in (2, 3, 4, 22, 23, 24, 102, 1002):
            with self.subTest(n=n):
                self.assertEqual(pluralize_pl(n, "wynik,wyniki,wyników"), "wyniki")

    def test_many_form(self):
        for n in (0, 5, 6, 10, 11, 12, 13, 14, 15, 19, 20, 21, 25, 100, 111, 112):
            with self.subTest(n=n):
                self.assertEqual(pluralize_pl(n, "wynik,wyniki,wyników"), "wyników")

    def test_teens_use_the_many_form(self):
        # The trap: 12, 13, 14 end in 2/3/4 but take "wyników", not "wyniki".
        for n in (12, 13, 14, 112, 113, 114):
            with self.subTest(n=n):
                self.assertEqual(pluralize_pl(n, "wynik,wyniki,wyników"), "wyników")

    def test_matches_django_polish_locale_rule(self):
        # Cross-check against gettext's plural formula for `pl`.
        def gettext_pl(n):
            return 0 if n == 1 else (1 if n % 10 >= 2 and n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20) else 2)

        words = ("wynik", "wyniki", "wyników")
        for n in range(0, 500):
            with self.subTest(n=n):
                self.assertEqual(pluralize_pl(n, ",".join(words)), words[gettext_pl(n)])

    def test_malformed_input_degrades_quietly(self):
        self.assertEqual(pluralize_pl(1, "wynik,wyniki"), "")
        self.assertEqual(pluralize_pl("abc", "wynik,wyniki,wyników"), "")
        self.assertEqual(pluralize_pl(None, "wynik,wyniki,wyników"), "")
