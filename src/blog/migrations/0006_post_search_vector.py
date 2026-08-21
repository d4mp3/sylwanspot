"""Add the stored, weighted search vector plus its GIN index.

Chosen over a functional GIN index on to_tsvector(...) because the vector
includes tag names, which live in taggit_taggeditem/taggit_tag. An expression
index can only reference columns of its own row, so tags could never be part
of a functional index -- and dropping them would lose the most precise signal
a blog post has after its title.
"""

from django.contrib.postgres.indexes import GinIndex
import django.contrib.postgres.search
from django.db import migrations


# Mirrors blog.search.build_post_search_vector. Kept as frozen SQL (rather
# than importing app code, which migrations must not depend on) and executed
# as one statement so the backfill is a single pass over the table.
BACKFILL = """
UPDATE blog_post p
   SET search_vector =
           setweight(to_tsvector('polish', coalesce(p.title, '')), 'A')
        || setweight(to_tsvector('polish', coalesce((
               SELECT string_agg(t.name, ' ')
                 FROM taggit_taggeditem ti
                 JOIN taggit_tag t ON t.id = ti.tag_id
                 JOIN django_content_type ct ON ct.id = ti.content_type_id
                WHERE ct.app_label = 'blog'
                  AND ct.model = 'post'
                  AND ti.object_id = p.id
           ), '')), 'B')
        || setweight(to_tsvector('polish', coalesce(p.body, '')), 'C');
"""

# Reverse only clears the derived column; no source data is touched. The
# AddField reversal drops the column anyway, so this is belt-and-braces.
CLEAR = "UPDATE blog_post SET search_vector = NULL;"


class Migration(migrations.Migration):

    dependencies = [
        ("blog", "0005_polish_fts"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="search_vector",
            field=django.contrib.postgres.search.SearchVectorField(editable=False, null=True),
        ),
        migrations.AddIndex(
            model_name="post",
            index=GinIndex(fields=["search_vector"], name="blog_post_search_vector_gin"),
        ),
        migrations.RunSQL(sql=BACKFILL, reverse_sql=CLEAR),
    ]
