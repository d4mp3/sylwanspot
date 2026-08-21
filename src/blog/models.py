from django.conf import settings
from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.urls import reverse
from django.utils import timezone
from taggit.managers import TaggableManager


class PublishedManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(status=Post.Status.PUBLISHED)


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = "DF", "Draft"
        PUBLISHED = "PB", "Published"

    title = models.CharField(max_length=250)
    slug = models.SlugField(max_length=250, unique_for_date="publish")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="blog_posts")
    body = models.TextField()
    publish = models.DateTimeField(default=timezone.now)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    status = models.CharField(
        max_length=2,
        choices=Status,
        default=Status.DRAFT,
    )
    # Pre-computed, weighted tsvector over title + tags + body. Maintained by
    # blog.signals (see blog.search.build_post_search_vector for the formula)
    # and rebuildable with `manage.py rebuild_search_vectors`. Storing it means
    # a search never has to run to_tsvector() over the whole table.
    search_vector = SearchVectorField(null=True, editable=False)

    objects = models.Manager()
    published = PublishedManager()
    tags = TaggableManager()

    class Meta:
        ordering = ("-publish",)
        indexes = [
            models.Index(fields=["-publish"]),
            GinIndex(fields=["search_vector"], name="blog_post_search_vector_gin"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("blog:post_detail", args=[self.publish.year, self.publish.month, self.publish.day, self.slug])

    def tags_text(self):
        """Tag names as a single string, for indexing purposes."""
        return " ".join(self.tags.values_list("name", flat=True))

    def update_search_vector(self):
        """Recompute and store this post's search_vector.

        Uses .update() rather than .save() so it never recurses through
        post_save and never clobbers concurrent edits to other fields.
        """
        from .search import build_post_search_vector

        Post.objects.filter(pk=self.pk).update(
            search_vector=build_post_search_vector(
                title=self.title,
                tags=self.tags_text(),
                body=self.body,
            )
        )


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    name = models.CharField(max_length=80)
    email = models.EmailField()
    body = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["created"]
        indexes = [
            models.Index(fields=["created"]),
        ]

    def __str__(self):
        return f"Comment by {self.name} on {self.post}"
