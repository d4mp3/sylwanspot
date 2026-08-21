"""Blog search: PostgreSQL Full Text Search with a pg_trgm fuzzy fallback.

    query
      -> PostgreSQL FTS (websearch_to_tsquery over the stored search_vector)
      -> ts_rank_cd ranking, weighted title/tags/body
      -> results ordered by relevance
    no FTS hits
      -> pg_trgm strict_word_similarity on the title (typos, missing diacritics)

Everything runs inside PostgreSQL; there is no external search engine. The
reasoning behind each choice here -- and the measurements behind the numbers --
is in docs/search.md.
"""

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramStrictWordSimilarity,
)
from django.db.models import F, TextField, Value

from .models import Post

#: Text search configuration created by migration blog/0005_polish_fts.
#: Backed by the Polish Hunspell dictionary shipped in postgres/Dockerfile.
SEARCH_CONFIG = "polish"

#: Field weights baked into Post.search_vector. PostgreSQL's default rank
#: multipliers are A=1.0, B=0.4, C=0.2, D=0.1, so a title hit outranks a tag
#: hit, which outranks a body hit.
SEARCH_WEIGHTS = (
    ("title", "A"),
    ("tags", "B"),
    ("body", "C"),
)

#: pg_trgm strict_word_similarity cut-off for the fuzzy fallback.
#:
#: strict_word_similarity() is used rather than word_similarity() because it
#: only considers extents that align with word boundaries. Measured against
#: this blog's titles:
#:
#:   signal   0.615  "postgress"      -> "Pierwsze kroki z PostgreSQL"
#:            0.615  "kubernets"      -> "Kubernetes dla początkujących"
#:            0.538  "wdrazanie"      -> "Wdrażanie Django w Dockerze"
#:            0.429  "poczatkujacych" -> "Kubernetes dla początkujących"
#:            0.417  "poscik"         -> "Pościk post"
#:   noise    0.333  "poscik"         -> "markdown post"     (matches "post")
#:            0.176  "gotowanie"      -> "Wdrażanie ..."      (shared suffix)
#:            0.071  "kot"            -> "Kubernetes ..."
#:
#: 0.4 sits in the gap. Plain word_similarity() has no such gap -- it scores
#: both "poczatkujacych" and the bogus "poscik"/"post" pair at 0.429, because
#: a short target word inflates the score.
#:
#: Known limitation: letter transpositions ("djnago", "pyhton") score ~0.27,
#: below the noise floor, so trigrams cannot recover them at any safe
#: threshold. Fixing that class would need edit distance (fuzzystrmatch), and
#: unaccenting would be better served by the `unaccent` extension than by
#: trigram luck -- both deliberately out of scope here.
TRIGRAM_THRESHOLD = 0.4


def build_post_search_vector(*, title, tags, body):
    """The canonical weighted tsvector expression for a post.

    Takes plain strings rather than field names so it can be used inside an
    UPDATE (which cannot join to the tags table).
    """
    # Note: tsvector `||` shifts the right operand's positions past the left
    # one's, so lexeme positions run contiguously across the three fields.
    # A phrase query can therefore, in principle, match the last word of the
    # title together with the first tag. Accepted: it is a rare and harmless
    # false positive, and the alternative (padding the text with filler tokens
    # to create a position gap) pollutes the index for no real gain.
    parts = {"title": title, "tags": tags, "body": body}
    vector = None
    for field, weight in SEARCH_WEIGHTS:
        piece = SearchVector(
            Value(parts[field] or "", output_field=TextField()),
            weight=weight,
            config=SEARCH_CONFIG,
        )
        vector = piece if vector is None else vector + piece
    return vector


def search_posts(query, queryset=None):
    """Return (results, mode) for a user query.

    ``mode`` is "fts" when Full Text Search matched, "fuzzy" when the trigram
    fallback was used, and "empty" when neither found anything. The fallback
    only runs if FTS came back empty, so the common case is a single query.
    """
    queryset = Post.published.all() if queryset is None else queryset
    query = (query or "").strip()
    if not query:
        return [], "empty"

    results = list(_full_text_search(queryset, query))
    if results:
        return results, "fts"

    results = list(_fuzzy_search(queryset, query))
    return (results, "fuzzy") if results else ([], "empty")


def _full_text_search(queryset, query):
    """Rank matches of the stored tsvector against a websearch tsquery.

    ``websearch_to_tsquery`` is used because it never raises on arbitrary user
    input and understands quoted phrases, ``or`` and leading ``-`` for
    exclusion. The ``@@`` match is the filter (it is what the GIN index on
    search_vector serves); ts_rank_cd only orders. There is deliberately no
    rank threshold: the old `rank__gte=0.3` discarded every body-only match
    (~0.12 against ~0.67 for a title hit). See docs/search.md.
    """
    search_query = SearchQuery(query, config=SEARCH_CONFIG, search_type="websearch")
    return (
        queryset.filter(search_vector=search_query)
        .annotate(
            rank=SearchRank(F("search_vector"), search_query, cover_density=True),
        )
        .order_by("-rank", "-publish")
    )


def _fuzzy_search(queryset, query):
    """Typo-tolerant fallback over titles only.

    Deliberately not run over ``body``: trigram similarity against a long
    article is both expensive and meaningless. Titles (and, through FTS, tags)
    are where misspelled proper nouns and technology names live.
    """
    return (
        queryset.annotate(similarity=TrigramStrictWordSimilarity(query, "title"))
        .filter(similarity__gte=TRIGRAM_THRESHOLD)
        .order_by("-similarity", "-publish")
    )
