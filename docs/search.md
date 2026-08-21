# Blog search design

PostgreSQL is the only search engine. No Elasticsearch/OpenSearch/Meilisearch/
Typesense — see [When to outgrow this](#when-to-outgrow-this).

```
query
  ↓  websearch_to_tsquery('polish', …)
PostgreSQL Full Text Search   ← GIN index on Post.search_vector
  ↓  ts_rank_cd, weighted title/tags/body
results ordered by relevance
  ↓  (only if FTS returned nothing)
pg_trgm strict_word_similarity on titles
  ↓
typo-tolerant guesses
```

Implementation: [`blog/search.py`](../src/blog/search.py). Database
infrastructure: [`postgres/README.md`](../postgres/README.md).

## Decisions

### The `rank >= 0.3` threshold was removed, not lowered

This was the actual bug. PostgreSQL's default rank multipliers are
A=1.0, B=0.4, C=0.2, D=0.1, so on this corpus:

| match location | weight | `ts_rank` |
| --- | --- | --- |
| title | A | ~0.67 |
| body only | C | ~0.12 |

`rank >= 0.3` therefore kept **title hits only**. A post that discussed Django
at length in its body but not in its title was unfindable. Measured on a
20 000-row table: the old query returned 20 rows where the correct one returns
59 — 39 body matches silently dropped.

The fix is to separate *matching* from *ranking*:

* `search_vector @@ query` is the filter — a boolean predicate, and the thing
  the GIN index can serve.
* `ts_rank_cd` only orders.

No score threshold at all. A document either contains the query terms or it
does not; there is no meaningful absolute rank below which a genuine match
becomes noise, and any constant picked here would be tuned to one corpus size.
Regression test: `SearchBehaviourTests.test_body_only_matches_are_returned`.

### `SearchVectorField` over a functional GIN index

Tags decided it. Tag names live in `taggit_taggeditem` / `taggit_tag`, and an
expression index can only reference columns of its own row — so tags could
never be part of a functional index, and dropping them would lose the most
precise signal a post has after its title.

The column is maintained by `post_save` + `m2m_changed` receivers in
[`blog/signals.py`](../src/blog/signals.py), which write it *inside* the
same transaction as the content change (not via `transaction.on_commit`), so
the derived column is atomic with its source. `manage.py rebuild_search_vectors`
repairs rows written by paths that bypass signals (`bulk_create`, raw SQL,
`loaddata`) and is what you run after changing `SEARCH_WEIGHTS`.

Measured at 20 000 rows, `EXPLAIN ANALYZE`:

| approach | plan | time |
| --- | --- | --- |
| `to_tsvector()` per row + rank filter | Parallel Seq Scan | **25 589 ms** |
| `@@` on stored vector | Bitmap Index Scan on GIN | **0.168 ms** |

### Field weights: title A, tags B, body C

The real model has `title`, `body` and taggit `tags` — there is no
`description`/`summary`/`excerpt`, and none was added just to fill a scheme.
Tags sit at B rather than A because a tag is a coarser signal than a title: an
article *titled* "Docker" is more about Docker than one merely *tagged*
`docker`.

### `search_type="websearch"`

Right choice here. `websearch_to_tsquery` needs PostgreSQL ≥ 11 (we run 16.2)
and Django ≥ 2.2 (we run 5.2), so there is no compatibility obstacle. It gives
users quoted phrases, `-` for exclusion and `or`, and — the property that
matters most for a public search box — it **never raises** on malformed input.
`&&& |||` yields an empty query and a "no results" page instead of a 500.
Verified in `test_malformed_query_does_not_raise` and
`test_websearch_operators`.

Caveat: the `or` operator is the English word, so a Polish user writing `lub`
gets it treated as a search term. Acceptable; the alternative (`plain`) drops
phrase and negation support entirely.

### `cover_density=True`

Kept. `ts_rank_cd` rewards query terms appearing close together, which is what
you want for article search. Measured with the query `docker compose` against
two posts, one with the words adjacent and one with them ~150 words apart:

| document | `ts_rank` | `ts_rank_cd` |
| --- | --- | --- |
| words adjacent | 0.1982 | 0.2000 |
| words far apart | 0.0000 | 0.0007 |

Both orderings agree; `ts_rank_cd` states the proximity difference explicitly
instead of collapsing the distant document to zero. It needs positional
information in the tsvector, which `to_tsvector` provides and nothing here
strips.

### Trigrams are a fallback, and `strict_word_similarity` not `word_similarity`

The fallback runs only when FTS returned zero rows, so the successful path
costs one query and the fuzzy path two — asserted with `assertNumQueries` in
`test_fuzzy_fallback_does_not_run_when_fts_succeeds`.

It scores `title` only. Trigram similarity against a full article body is both
expensive and meaningless — a long document matches everything a little.

`strict_word_similarity` (word-boundary aligned) beat plain `word_similarity`
on real data:

| | query → title | `strict_ws` | `word_similarity` |
| --- | --- | --- | --- |
| signal | `postgress` → "…PostgreSQL" | 0.615 | 0.800 |
| signal | `kubernets` → "Kubernetes…" | 0.615 | 0.800 |
| signal | `wdrazanie` → "Wdrażanie…" | 0.538 | 0.538 |
| signal | `poczatkujacych` → "…początkujących" | 0.429 | 0.429 |
| **noise** | `poscik` → "markdown post" | **0.333** | **0.429** |
| noise | `gotowanie` → "Wdrażanie…" | 0.176 | 0.300 |
| noise | `kot` → "Kubernetes…" | 0.071 | 0.250 |

Plain `word_similarity` scores a genuine diacritic-free hit and a bogus
`poscik`/`post` pair *identically* at 0.429 — a short target word inflates it,
so no threshold separates them. `strict_word_similarity` opens a gap, and
`TRIGRAM_THRESHOLD = 0.4` sits in it.

**Known gap:** letter transpositions (`djnago`, `pyhton`) score ~0.27 — below
the noise floor. Trigrams cannot recover that class at any safe threshold; it
would need edit distance (`fuzzystrmatch`). Likewise, diacritic-free queries
work here by trigram luck; the `unaccent` extension would do it properly. Both
deliberately out of scope. Documented in
`test_transpositions_are_a_known_gap`.

### Polish plural forms in the template

Polish has three: `1 wynik`, `2 wyniki`, `5 wyników`. Django's built-in
`pluralize` only encodes the two-form English rule, and `ngettext` would not
help either — `LANGUAGE_CODE` is `en-us`, so the active locale applies English
plural rules regardless of the strings passed. Hence the `pluralize_pl` filter
in `blog/templatetags/blog_tags.py`, which implements gettext's `pl` formula
and is cross-checked against it for n ∈ [0, 500) in `PluralizePlTests`.

## When to outgrow this

Revisit an external engine only on a real need: a very large document count,
serious autocomplete, faceting, complex synonym sets, multilingual indexing at
scale, or a requirement for a separate search cluster. None applies to a blog
of this size.
