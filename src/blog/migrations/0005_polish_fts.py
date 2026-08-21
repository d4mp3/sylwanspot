"""Create the Polish text search configuration and enable pg_trgm.

Why this lives in a migration rather than in /docker-entrypoint-initdb.d:
the entrypoint hook only runs when the data directory is empty, so it would
skip both the existing postgres_data volume and every database Django creates
for the test suite (those come from CREATE DATABASE, not initdb). A migration
covers dev, CI and production from one place.

The Hunspell *files* are not created here -- they are installed into
$SHAREDIR/tsearch_data by postgres/Dockerfile. If this migration fails with
"could not open dictionary file", the database is running an image built
before that Dockerfile existed; rebuild it (see postgres/README.md).
"""

from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations

# Idempotent: safe to re-run against a database that already has the objects,
# which matters because the same SQL may already have been applied by hand on
# a long-lived volume.
CREATE_POLISH_FTS = """
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
          FROM pg_ts_dict d
          JOIN pg_namespace n ON n.oid = d.dictnamespace
         WHERE d.dictname = 'polish_hunspell' AND n.nspname = 'public'
    ) THEN
        CREATE TEXT SEARCH DICTIONARY public.polish_hunspell (
            TEMPLATE  = ispell,
            DictFile  = polish,
            AffFile   = polish,
            StopWords = polish
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1
          FROM pg_ts_config c
          JOIN pg_namespace n ON n.oid = c.cfgnamespace
         WHERE c.cfgname = 'polish' AND n.nspname = 'public'
    ) THEN
        CREATE TEXT SEARCH CONFIGURATION public.polish (COPY = simple);
    END IF;
END
$$;

-- COPY = simple already provides a mapping for every token type, so ALTER
-- MAPPING FOR always has something to replace and is itself idempotent.
-- Dictionary order matters: polish_hunspell first (it normalises Polish
-- inflection and drops stop words), then simple as the terminal fallback so
-- words absent from the Polish dictionary -- django, docker, kubernetes --
-- are still indexed, lowercased and unchanged.
ALTER TEXT SEARCH CONFIGURATION public.polish
    ALTER MAPPING FOR asciiword, asciihword, hword_asciipart,
                      word, hword, hword_part
    WITH polish_hunspell, simple;
"""

# Reverse is data-safe: it only drops the two catalog objects, and only if
# nothing depends on them. RESTRICT (the default) makes the drop fail rather
# than cascade into a column that still uses the configuration.
DROP_POLISH_FTS = """
DROP TEXT SEARCH CONFIGURATION IF EXISTS public.polish;
DROP TEXT SEARCH DICTIONARY IF EXISTS public.polish_hunspell;
"""


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0004_post_tags"),
    ]

    operations = [
        # Supplies similarity()/word_similarity() for the fuzzy fallback.
        TrigramExtension(),
        migrations.RunSQL(
            sql=CREATE_POLISH_FTS,
            reverse_sql=DROP_POLISH_FTS,
        ),
    ]
