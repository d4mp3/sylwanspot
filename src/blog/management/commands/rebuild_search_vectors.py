"""Rebuild Post.search_vector for every post.

Needed after changing the weighting scheme in blog.search.SEARCH_WEIGHTS,
after changing the `polish` text search configuration, or to repair rows that
were written by a path that bypassed the signals (bulk_create, raw SQL,
loaddata).
"""

from django.core.management.base import BaseCommand

from blog.models import Post


class Command(BaseCommand):
    help = "Recompute the Full Text Search vector for all blog posts."

    def add_arguments(self, parser):
        parser.add_argument(
            "--only-missing",
            action="store_true",
            help="Only rebuild posts whose search_vector is NULL.",
        )

    def handle(self, *args, **options):
        posts = Post.objects.all()
        if options["only_missing"]:
            posts = posts.filter(search_vector__isnull=True)

        count = 0
        # prefetch_related keeps this at 2 reads + 1 write per chunk instead of
        # a tags query per post.
        #
        # The ignore below is a stubs limitation, not a real problem:
        # django-taggit ships no type information (no py.typed), so
        # `Post.tags` reaches mypy as Any and the django plugin cannot see
        # that a TaggableManager is prefetchable. It is -- this is taggit's
        # own documented idiom and it works at runtime. Silenced on this one
        # line rather than for the module, so any other error here still
        # surfaces.
        for post in posts.prefetch_related("tags").iterator(  # type: ignore[misc]
            chunk_size=200
        ):
            post.update_search_vector()
            count += 1

        if options["verbosity"]:
            self.stdout.write(
                self.style.SUCCESS(f"Rebuilt search_vector for {count} post(s).")
            )
