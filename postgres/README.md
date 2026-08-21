# PostgreSQL image with Polish Full Text Search

`postgres:16.2` has no `polish` text search configuration — PostgreSQL ships
snowball stemmers for a dozen languages, but Polish is not among them. This
directory builds an image that adds the Polish **Hunspell** dictionary, which
the `blog` app then wires into a `polish` configuration.

## Split of responsibilities

| Concern | Owner | Changing it requires |
| --- | --- | --- |
| `polish.affix`, `polish.dict`, `polish.stop` on disk | `postgres/Dockerfile` | image rebuild + container recreate |
| `TEXT SEARCH DICTIONARY` / `CONFIGURATION` in the database | Django migration `blog/0005_polish_fts` | `manage.py migrate` |
| `pg_trgm` extension | same migration (`TrigramExtension`) | `manage.py migrate` |
| `Post.search_vector` column, GIN index, backfill | Django migration `blog/0006_post_search_vector` | `manage.py migrate` |

The SQL deliberately lives in a migration rather than in
`/docker-entrypoint-initdb.d/`. That hook only fires when the data directory is
empty, so it would skip both the existing `postgres_data` volume and every
database Django creates for the test suite (those come from `CREATE DATABASE`,
not `initdb`).

## Deploying to an existing database

No volume is destroyed and there is no `docker compose down -v`:

```bash
docker compose build db          # bake the dictionary files into the image
docker compose up -d db          # recreate the container, volume untouched
docker compose run --rm web_migrate   # create the SQL objects + backfill
```

`blog/0005_polish_fts` is idempotent, so re-running it against a database that
already has the objects is a no-op.

## Verifying

```bash
docker compose exec -T db psql -U postgres -d postgres -f - < postgres/verify-polish-search.sql
```

The same assertions run as tests in `src/blog/tests/test_postgres_setup.py`
(`./do.sh test src/blog/tests/test_postgres_setup.py`).

## Notes on the dictionary files

* Debian's `hunspell-pl` ships `pl_PL.aff` / `pl_PL.dic` in **ISO-8859-2**.
  PostgreSQL requires files under `$SHAREDIR/tsearch_data` to be UTF-8, so the
  Dockerfile transcodes them with `iconv` and rewrites the `SET` header.
* `DictFile = polish` / `AffFile = polish` resolve to `polish.dict` /
  `polish.affix`, hence the rename.
* The target directory comes from `pg_config --sharedir` rather than a
  hardcoded `/usr/share/postgresql/16`, so a base-image bump cannot silently
  put the files somewhere the server does not look.
* `polish.stop` is ours — PostgreSQL has no Polish stop word list. For an
  ispell/Hunspell dictionary the stop list is matched against the *normalised*
  lexeme, so it contains base forms.
* Hunspell is a spell-checker, not a stemmer: for an ambiguous token it emits
  every base form it can justify. `to_tsvector('polish', 'kot koty kota kotem')`
  yields `'kot':1,2,3,4 'kota':1,2,3 'kotem':4 'koty':2`. All four inflected
  forms are reachable through `kot`, which is what matters for recall; the extra
  lexemes cost a little index size and can occasionally over-match.
* First use of the dictionary in a backend loads the whole word list into that
  session's memory (tens of MB). It is cached per connection, so persistent
  connections amortise it.
