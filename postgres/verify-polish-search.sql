-- Verify the Polish Full Text Search setup.
--
--   docker compose exec -T db psql -U postgres -d postgres \
--       -f - < postgres/verify-polish-search.sql
--
-- Not run automatically anywhere; this is the diagnostic you reach for when
-- search behaves oddly. The equivalent assertions live in blog/tests.py.

\pset border 2

\echo '== 1. Dictionary files present in $SHAREDIR/tsearch_data =='
-- Fails with "could not open dictionary file" if the db image predates
-- postgres/Dockerfile. Nothing below will work in that case.
SELECT dictname, dictinitoption
  FROM pg_ts_dict
 WHERE dictname = 'polish_hunspell';

\echo '== 2. Configuration exists =='
SELECT cfgname FROM pg_ts_config WHERE cfgname = 'polish';

\echo '== 3. Token type -> dictionary mapping (hunspell first, simple last) =='
SELECT t.alias AS token_type, d.dictname, m.mapseqno
  FROM pg_ts_config c
  JOIN pg_ts_config_map m ON m.mapcfg = c.oid
  JOIN pg_ts_dict d ON d.oid = m.mapdict
  JOIN pg_catalog.ts_token_type((SELECT cfgparser FROM pg_ts_config WHERE cfgname='polish')) t
       ON t.tokid = m.maptokentype
 WHERE c.cfgname = 'polish'
   AND t.alias IN ('asciiword','asciihword','hword_asciipart','word','hword','hword_part')
 ORDER BY t.alias, m.mapseqno;

\echo '== 4. Inflection is normalised: all four forms must yield lexeme "kot" =='
-- Expect: 'kot':1,2,3,4 'kota':1,2,3 'kotem':4 'koty':2
-- The extra lexemes are correct. Hunspell is a spell-checker, not a stemmer:
-- for an ambiguous form it emits every base form it can justify ("kota" is
-- both the genitive of "kot" and a lemma in its own right). What matters is
-- that 'kot' appears at all four positions, so any inflected query matches.
SELECT to_tsvector('polish', 'kot koty kota kotem');

\echo '== 5. ts_debug: which dictionary handled the token =='
SELECT * FROM ts_debug('polish', 'koty');

\echo '== 6. Words absent from the Polish dictionary fall through to simple =='
-- Expect dictionary = simple for Django/Kubernetes, polish_hunspell for
-- wdrażanie -> wdrażać. This is why `WITH polish_hunspell, simple` matters:
-- with hunspell alone, every technology name would be dropped from the index.
SELECT token, dictionary, lexemes FROM ts_debug('polish', 'Django Kubernetes wdrażanie');

\echo '== 7. Stop words are removed =='
-- Expect no lexemes for "w" and "i".
SELECT to_tsvector('polish', 'Programowanie w Pythonie i testowanie kodu');

\echo '== 8. Query side: websearch_to_tsquery, and inflected matching =='
SELECT websearch_to_tsquery('polish', 'django docker')            AS implicit_and,
       websearch_to_tsquery('polish', '"docker compose" -swarm')   AS phrase_and_negation,
       websearch_to_tsquery('polish', 'django or flask')           AS explicit_or,
       websearch_to_tsquery('polish', '& | ! ( ) :* <->')          AS garbage_does_not_raise;

SELECT to_tsvector('polish', 'Zdjęcia kotów i psów')
       @@ websearch_to_tsquery('polish', 'kot') AS singular_query_matches_plural_text;

\echo '== 9. pg_trgm available for the fuzzy fallback =='
SELECT extversion AS pg_trgm_version FROM pg_extension WHERE extname = 'pg_trgm';

-- blog.search uses strict_word_similarity (word-boundary aligned) with a
-- threshold of 0.4. Expect every SIGNAL row above 0.4 and every noise row
-- below it. The transposition rows document a real limitation: trigrams score
-- them ~0.27, *below* the noise floor, so no threshold recovers that class.
SELECT kind, typo, title,
       round(strict_word_similarity(typo, title)::numeric, 3) AS strict_ws,
       round(word_similarity(typo, title)::numeric, 3)        AS plain_ws
  FROM (VALUES
     ('SIGNAL typo',          'postgress',      'Pierwsze kroki z PostgreSQL'),
     ('SIGNAL typo',          'kubernets',      'Kubernetes dla początkujących'),
     ('SIGNAL no diacritics', 'wdrazanie',      'Wdrażanie Django w Dockerze'),
     ('SIGNAL no diacritics', 'poczatkujacych', 'Kubernetes dla początkujących'),
     ('SIGNAL transposition', 'djnago',         'Wdrażanie Django w Dockerze'),
     ('noise short word',     'poscik',         'markdown post'),
     ('noise shared suffix',  'gotowanie',      'Wdrażanie Django w Dockerze'),
     ('noise',                'kot',            'Kubernetes dla początkujących')
  ) v(kind, typo, title)
 ORDER BY strict_ws DESC;
-- The plain_ws column shows why strict_ws was chosen: plain word_similarity
-- scores the real 'poczatkujacych' hit and the bogus 'poscik'/'post' pair
-- identically (0.429), leaving no threshold that separates them.

\echo '== 10. The GIN index is usable for the @@ predicate =='
-- On a table this small PostgreSQL will still choose a sequential scan; that
-- is correct, not a bug. Force it off to prove the index can serve the query.
SET enable_seqscan = off;
EXPLAIN (COSTS OFF)
SELECT id FROM blog_post
 WHERE search_vector @@ websearch_to_tsquery('polish', 'django');
RESET enable_seqscan;

\echo '== 11. No post is missing its search vector =='
SELECT count(*) AS posts_with_null_search_vector
  FROM blog_post WHERE search_vector IS NULL;
