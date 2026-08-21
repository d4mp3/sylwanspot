import markdown
from django import template
from django.db.models import Count
from django.utils.safestring import mark_safe

from ..models import Post

register = template.Library()


@register.simple_tag
def total_posts():
    return Post.published.count()


@register.inclusion_tag("blog/post/latest_posts.html")
def show_latest_posts(count=5):
    latest_posts = Post.published.order_by("-publish")[:count]
    return {"latest_posts": latest_posts}


@register.simple_tag
def get_most_commented_posts(count=5):
    return Post.published.annotate(total_comments=Count("comments")).order_by("-total_comments")[:count]


@register.filter(name="markdown")
def markdown_format(text):
    return mark_safe(markdown.markdown(text))


#: Polish has three plural forms. The rule below is the CLDR/gettext plural
#: formula Django ships for the `pl` locale:
#:     n == 1                                          -> form 0  (1 wynik)
#:     n % 10 in 2..4 and n % 100 not in 10..21        -> form 1  (2 wyniki)
#:     otherwise                                       -> form 2  (5 wyników)
#: Django's built-in `pluralize` filter only knows the two-form English rule,
#: which is why "1 wyników"/"22 wyników" came out wrong. Using gettext's
#: ngettext is not an option here either: LANGUAGE_CODE is "en-us", so the
#: active locale would apply the English rule regardless of the strings given.
@register.filter(name="pluralize_pl")
def pluralize_pl(value, forms_):
    """Pick the Polish plural form for ``value``.

    Usage:
        {{ n }} {{ n|pluralize_pl:"wynik,wyniki,wyników" }}

    ``forms_`` is a comma-separated singular,few,many triple. Returns an empty
    string if the argument is malformed or the value is not a number, so a
    template typo degrades gracefully instead of raising.
    """
    parts = [form.strip() for form in str(forms_).split(",")]
    if len(parts) != 3:
        return ""
    singular, few, many = parts

    try:
        n = abs(int(value))
    except (TypeError, ValueError):
        return ""

    if n == 1:
        return singular
    if 2 <= n % 10 <= 4 and not 10 <= n % 100 <= 21:
        return few
    return many
