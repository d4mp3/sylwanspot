# Jak zakładać nową aplikację

Krótka notatka o `app_template/` w katalogu repozytorium: po co powstał, jak z
niego korzystać i co zrobić po wygenerowaniu aplikacji.

- [Komenda](#komenda)
- [Co dalej, po wygenerowaniu](#co-dalej)
- [Po co szablon istnieje](#po-co)
- [Dlaczego `django-admin` z wnętrza `src/`](#dlaczego-django-admin)
- [Co jest w szablonie](#co-jest-w-szablonie)
- [Jak rozwijać szablon](#jak-rozwijac)

---

<a id="komenda"></a>

## Komenda

```bash
./do.sh startapp account
```

Powstaje `src/account/`. To wszystko, co trzeba pamiętać — `do.sh` dokłada
katalog roboczy i `--template`. Bez wrappera, na hoście, jest to:

```bash
cd src && uv run django-admin startapp account --template=../app_template
```

Ten drugi wariant działa **bez zmiennych środowiskowych** i bez działającego
kontenera, bo `startapp` jest komendą szablonową: nie importuje settings i nie
dotyka bazy. Przydaje się, gdy `docker compose` nie stoi. Ma też tę zaletę, że
pliki należą do Ciebie, a nie do `root` (kontener `dev` działa jako root).

---

<a id="co-dalej"></a>

## Co dalej, po wygenerowaniu

Szablon nie potrafi zmodyfikować plików spoza nowej aplikacji, więc trzy rzeczy
zostają do zrobienia ręcznie:

1. **`INSTALLED_APPS`** w `src/sylwanspot/settings.py` — dopisz `AppConfig`, nie
   samą nazwę pakietu, spójnie z resztą:

   ```python
   INSTALLED_APPS = [
       "account.apps.AccountConfig",
       ...
   ]
   ```

2. **Root URLconf** w `src/sylwanspot/urls.py` — jeśli aplikacja ma widoki:

   ```python
   path("account/", include("account.urls")),
   ```

3. **Migracje** — dopiero gdy powstanie pierwszy model:
   `./do.sh makemigrations account`, potem `./do.sh migrate`.

Czego **nie** trzeba robić: kasować nieużywanych importów ani przenosić
`tests.py` do pakietu. Szablon nie generuje ani jednego, ani drugiego.

---

<a id="po-co"></a>

## Po co szablon istnieje

Wbudowany szablon Django nie zna konwencji tego projektu i za każdym razem
zostawia te same trzy rzeczy do posprzątania:

**1. Cztery błędy `F401` na wejściu.** Django generuje pliki-zaślepki z
importem „na przyszłość": `from django.db import models` w `models.py`,
`from django.contrib import admin` w `admin.py`, `from django.shortcuts import
render` w `views.py`, `from django.test import TestCase` w `tests.py`. Żaden nie
jest użyty, a `ruff` ma włączoną regułę `F` — więc `ruff check` zwraca 4 błędy.
Hook w `.pre-commit-config.yaml` działa z `--fix`, czyli przy pierwszej próbie
commita sam wytnie te importy i **przerwie commit** z powodu zmodyfikowanych
plików. Nasze zaślepki nie importują niczego; import dopisujesz razem z
pierwszym użyciem.

**2. `tests.py`, którego nikt nie uruchamia.** `pyproject.toml` ma
`python_files = ["test_*.py"]`, więc pytest **nie zbiera** pliku o nazwie
`tests.py` — testy w nim wyglądają na napisane, a nie wykonują się nigdy. Do
tego `exclude` w `[tool.hatch.build.targets.wheel]` to `src/*/tests/**`, czyli
`tests.py` (plik, nie katalog) trafiłby do koła produkcyjnego. Konwencja
projektu, ta z `src/blog/tests/`, to pakiet z plikiem `test_*.py` na moduł
źródłowy — i to generuje szablon.

**3. Podwójne cudzysłowy i formatowanie.** Django generuje kod z pojedynczymi
cudzysłowami, `ruff format` zmienia je na podwójne. Kolejna zmiana pliku pod
ręką hooka. Szablon jest już sformatowany zgodnie z `ruff format`.

Efekt: aplikacja z `./do.sh startapp` przechodzi `ruff check`, `ruff format
--check` i `mypy` bez jednej poprawki.

---

<a id="dlaczego-django-admin"></a>

## Dlaczego `django-admin` z wnętrza `src/`

Naturalny odruch to zostać w katalogu repozytorium i podać Django katalog
docelowy: `python manage.py startapp account src/account`. To nie działa, i
warto wiedzieć dlaczego, bo błąd wygląda na niezrozumiały:

```
CommandError: 'account' conflicts with the name of an existing Python module
```

Django waliduje nazwę aplikacji przez `find_spec(name)`
(`django/core/management/templates.py`). Katalog `src/` jest na `sys.path` — bo
projekt jest zainstalowany edytowalnie — a pusty katalog `src/account/`, który
musiałeś utworzyć wcześniej (Django wymaga, by katalog docelowy istniał), jest
z punktu widzenia Pythona poprawnym **namespace package**. `find_spec` go
znajduje i uznaje za kolizję nazw.

Uruchomienie z wnętrza `src/` **bez** argumentu z katalogiem docelowym odwraca
kolejność: Django samo tworzy katalog, i robi to *po* walidacji nazwy. Nie ma
pustego katalogu w momencie sprawdzania, więc nie ma kolizji. Żadnych obejść w
`manage.py`.

---

<a id="co-jest-w-szablonie"></a>

## Co jest w szablonie

```
app_template/
├── __init__.py-tpl
├── apps.py-tpl              AppConfig z poprawną nazwą klasy i default_auto_field
├── models.py-tpl            komentarz, zero importów
├── admin.py-tpl             komentarz ze wskazaniem wzoru w blog/admin.py
├── views.py-tpl             komentarz
├── urls.py-tpl              app_name + otypowana pusta lista urlpatterns
├── migrations/
│   └── __init__.py-tpl
└── tests/
    └── __init__.py-tpl      pakiet, nie tests.py
```

Świadomie **nie** ma tu `forms.py`, `templates/`, `static/`, `signals.py` ani
`templatetags/`. `blog` ma je wszystkie, ale żaden nie jest potrzebny w każdej
aplikacji, a puste pliki mylą — dodawaj je wtedy, gdy naprawdę wchodzą do gry.
Wygenerowanego `urls.py` też nie ma obowiązku zostawiać: skasuj, jeśli
aplikacja nie ma widoków.

Adnotacja w `urls.py` nie jest ozdobą. `urlpatterns = []` bez typu to przy
`check_untyped_defs = true` błąd mypy `Need type annotation for urlpatterns`,
czyli znowu przerwany commit.

---

<a id="jak-rozwijac"></a>

## Jak rozwijać szablon

Mechanizm jest w Django, nie w tym projekcie, i ma kilka reguł, o które łatwo
się potknąć:

- **Rozszerzenie `.py-tpl`** jest obowiązkowe dla plików z kodem. Django zmienia
  je na `.py` przy kopiowaniu. Dzięki temu pliki szablonu nie są prawidłowym
  Pythonem — i nie muszą być: `ruff` i `mypy` ich nie widzą (`files = ["src",
  "manage.py"]`), a Python ich nie kompiluje.
- **Renderowane są tylko pliki, które po zmianie nazwy kończą się na `.py`.**
  Reszta jest kopiowana bajt w bajt — łącznie z plikami, których byś tam nie
  chciał. Dlatego ta notatka leży w `docs/`, a nie w `app_template/README.md`:
  README wylądowałby w każdej nowej aplikacji.
- **Zmienne w treści**: `{{ app_name }}` (np. `probe_app`) i
  `{{ camel_case_app_name }}` (`ProbeApp` — podkreślenia wypadają, człony idą z
  wielkiej litery). Dostępne są też `{{ django_version }}` i
  `{{ docs_version }}`.
- **Nazwy plików i katalogów** nie używają `{{ }}`. Django podmienia w nich
  dosłowny ciąg `app_name`, więc katalog `app_template/templates/app_name/`
  utworzy `src/account/templates/account/`. Git nie śledzi pustych katalogów,
  więc taki katalog potrzebuje pliku w środku — a ten plik znajdzie się w każdej
  nowej aplikacji.
- **Katalogi z kropką na początku i `__pycache__`** są pomijane.
- Treść jest renderowana **silnikiem szablonów Django**, więc literalne `{{`
  albo `{%` w kodzie zostanie zinterpretowane. Jeśli kiedyś dodasz do szablonu
  plik HTML, pamiętaj o `{% verbatim %}` albo o innym rozszerzeniu.

Po każdej zmianie w `app_template/` warto zrobić przebieg kontrolny — szablonu
nie sprawdza żaden hook:

```bash
cd src && uv run django-admin startapp probe_app --template=../app_template
cd .. && uv run ruff check src/probe_app && uv run ruff format --check src/probe_app && uv run mypy
rm -rf src/probe_app
```
