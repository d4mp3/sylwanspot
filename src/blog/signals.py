"""Keep Post.search_vector in sync with the fields it indexes.

The vector is written inside the same transaction as the content change, not
via transaction.on_commit(). That makes the derived column atomic with its
source: a rolled-back edit rolls back the vector too, and there is no window
in which a committed post carries a stale vector. Reading the tags back mid
transaction is safe -- a transaction sees its own uncommitted writes.
"""

from django.db.models.signals import m2m_changed, post_save
from django.dispatch import receiver
from taggit.models import TaggedItem

from .models import Post


@receiver(post_save, sender=Post, dispatch_uid="blog.refresh_search_vector_on_save")
def refresh_search_vector_on_save(sender, instance, **kwargs):
    # update_search_vector() uses queryset.update(), which does not emit
    # post_save, so this cannot recurse.
    instance.update_search_vector()


@receiver(
    m2m_changed, sender=TaggedItem, dispatch_uid="blog.refresh_search_vector_on_tags"
)
def refresh_search_vector_on_tag_change(sender, instance, action, **kwargs):
    # django-taggit sends m2m_changed with sender=TaggedItem for every tagged
    # model, so filter on the instance. Only the post_* actions matter -- the
    # pre_* ones fire before the rows change. A save() that also changes tags
    # therefore writes the vector twice; the second write is the correct one
    # and the cost is one extra UPDATE on an edit, which a blog can afford.
    if action in ("post_add", "post_remove", "post_clear") and isinstance(
        instance, Post
    ):
        instance.update_search_vector()
