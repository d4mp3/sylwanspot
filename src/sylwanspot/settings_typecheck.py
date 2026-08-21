"""Settings używane wyłącznie przez mypy (wtyczkę django-stubs).

Wtyczka importuje settings, żeby zbudować rejestr modeli. Prawdziwe settings są
fail-fast -- brak POSTGRES_* albo EMAIL_*/DEFAULT_FROM_EMAIL to
UndefinedValueError (nie ma pliku .env na hoście). Tu zasiewamy atrapy przed
importem: decouple czyta os.environ przed .env, więc te wartości wygrywają.
`setdefault`, nie przypisanie, żeby w kontenerze wygrały wartości prawdziwe.
Nic się nie łączy z bazą, mypy tylko czyta typy.
"""

import os

os.environ.setdefault("POSTGRES_DB", "typecheck")
os.environ.setdefault("POSTGRES_USER", "typecheck")
os.environ.setdefault("POSTGRES_PASSWORD", "typecheck")
os.environ.setdefault("POSTGRES_HOST", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("EMAIL_HOST_USER", "typecheck")
os.environ.setdefault("EMAIL_HOST_PASSWORD", "typecheck")
os.environ.setdefault("DEFAULT_FROM_EMAIL", "typecheck@example.com")

from sylwanspot.settings import *  # noqa: F403
