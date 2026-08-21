"""Polish needs three plural forms; Django's `pluralize` only knows two.

Pure functions, so nothing here touches the database -- these run even with the
db container down.
"""

import pytest

from blog.templatetags.blog_tags import pluralize_pl

FORMS = "wynik,wyniki,wyników"


def test_singular():
    assert pluralize_pl(1, FORMS) == "wynik"


@pytest.mark.parametrize("n", [2, 3, 4, 22, 23, 24, 102, 1002])
def test_few_form(n):
    assert pluralize_pl(n, FORMS) == "wyniki"


@pytest.mark.parametrize(
    "n", [0, 5, 6, 10, 11, 12, 13, 14, 15, 19, 20, 21, 25, 100, 111, 112]
)
def test_many_form(n):
    assert pluralize_pl(n, FORMS) == "wyników"


@pytest.mark.parametrize("n", [12, 13, 14, 112, 113, 114])
def test_teens_use_the_many_form(n):
    # The trap: 12, 13, 14 end in 2/3/4 but take "wyników", not "wyniki".
    assert pluralize_pl(n, FORMS) == "wyników"


def test_matches_django_polish_locale_rule():
    # Cross-check against gettext's plural formula for `pl`. Left as a loop
    # rather than parametrised: the assertion is about the whole range, and 500
    # entries would drown every other case in the report.
    def gettext_pl(n):
        return (
            0
            if n == 1
            else (
                1
                if n % 10 >= 2 and n % 10 <= 4 and (n % 100 < 10 or n % 100 >= 20)
                else 2
            )
        )

    words = ("wynik", "wyniki", "wyników")
    for n in range(0, 500):
        assert pluralize_pl(n, ",".join(words)) == words[gettext_pl(n)], f"n = {n}"


@pytest.mark.parametrize(
    "value, forms",
    [
        (1, "wynik,wyniki"),  # too few forms
        ("abc", FORMS),  # not a number
        (None, FORMS),
    ],
)
def test_malformed_input_degrades_quietly(value, forms):
    assert pluralize_pl(value, forms) == ""
