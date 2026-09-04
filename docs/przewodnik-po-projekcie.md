# Jak czytać ten projekt

Przewodnik po **całym** projekcie Django, nie po samym wyszukiwaniu. Kolejność
jest taka, żeby każdy plik wyjaśniał się przez poprzedni — od wejścia procesu
do szablonu, który renderuje odpowiedź.

Dokumenty w `docs/`, żeby się nie pogubić:

| plik                                                     | odpowiada na pytanie                                                                |
| -------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| **ten plik**                                             | jak czytać cały projekt Django, od zera                                             |
| [`przewodnik-po-zmianach.md`](przewodnik-po-zmianach.md) | w jakiej kolejności czytać zmiany z sesji o wyszukiwaniu i jak je pociąć na commity |
| [`search.md`](search.md)                                 | dlaczego wyszukiwanie jest zrobione tak, a nie inaczej (pomiary, decyzje)           |
| [`nowa-aplikacja.md`](nowa-aplikacja.md)                 | jak założyć nową aplikację i po co jest `app_template/`                             |

Ten plik zaczyna się od zera i nie zakłada znajomości Django.

- [Mapa: gdzie co leży](#mapa-gdzie-co-lezy)
- [Etap 0 — jak w ogóle uruchomić](#etap-0)
- [Etap 1 — ścieżka żądania](#etap-1)
- [Etap 2 — warstwa danych](#etap-2)
- [Etap 3 — widoki](#etap-3)
- [Etap 4 — szablony](#etap-4)
- [Etap 5 — formularze i POST](#etap-5)
- [Etap 6 — poza HTML](#etap-6)
- [Etap 7 — wyszukiwanie](#etap-7)
- [Etap 8 — testy](#etap-8)
- [Co zauważysz po drodze](#co-zauwazysz)
- [Ćwiczenia sprawdzające](#cwiczenia)

---

<a id="mapa-gdzie-co-lezy"></a>

## Mapa: gdzie co leży

Katalog projektu Django nazywa się tak samo jak repozytorium, ale dzieli je
`src/` — warto to zapamiętać, bo nazwa wraca w dwóch miejscach:

```
sylwanspot/                  <- katalog repozytorium (tu jest docker-compose.yml)
├── docker-compose.yml       usługi: db, web_migrate, web_run
├── Dockerfile               obraz aplikacji (python:3.12-slim + uv, wielostopniowy)
├── postgres/                obraz bazy (PostgreSQL + polski Hunspell)
├── do.sh                    skróty do docker compose
├── pyproject.toml           zależności + konfiguracja pytest/ruff/mypy
├── uv.lock                  zamknięte wersje wszystkich zależności
├── .python-version          3.12
├── .pre-commit-config.yaml
├── .dockerignore
├── manage.py
├── docs/
└── src/                     <- kod (instalowany edytowalnie)
    ├── sylwanspot/          <- pakiet konfiguracyjny projektu
    │   ├── settings.py
    │   ├── settings_typecheck.py  atrapy POSTGRES_* dla mypy
    │   ├── urls.py          root URLconf
    │   ├── wsgi.py / asgi.py
    │   └── __init__.py
    └── blog/                <- jedyna aplikacja z kodem
        ├── models.py        Post, Comment, PublishedManager
        ├── views.py         4 widoki funkcyjne + 1 klasowy
        ├── urls.py          URLconf aplikacji (namespace "blog")
        ├── forms.py         3 formularze
        ├── admin.py         panel administracyjny
        ├── apps.py          konfiguracja aplikacji + rejestracja sygnałów
        ├── search.py        logika wyszukiwania (FTS + fallback)
        ├── signals.py       utrzymanie search_vector
        ├── feeds.py         kanał RSS
        ├── sitemaps.py      sitemap.xml
        ├── tests/          pakiet testów, plik na moduł źródłowy
        ├── migrations/      0001–0006
        ├── templatetags/
        │   └── blog_tags.py własne tagi i filtry szablonów
        ├── templates/blog/  szablony HTML
        ├── static/css/
        └── management/commands/
```

Zasada, którą warto zapamiętać: **katalog projektu** (`src/sylwanspot/`)
trzyma konfigurację i nie zawiera logiki. **Aplikacja** (`blog/`) zawiera całą
logikę. Django pozwala mieć wiele aplikacji w jednym projekcie; tutaj jest
jedna.

---

<a id="etap-0"></a>

## Etap 0 — jak w ogóle uruchomić

Zacznij od tego, bo każdy kolejny etap warto móc od razu sprawdzić w
przeglądarce.

**Czytaj:** `docker-compose.yml` → `Dockerfile` → `do.sh`

Trzy usługi, z czego dwie to warianty tej samej:

| usługa        | rola                                                          |
| ------------- | ------------------------------------------------------------- |
| `db`          | PostgreSQL 16.2 z polskim słownikiem (build z `./postgres`)   |
| `web_migrate` | `<<: *web` + `manage.py migrate`, czeka na `db` healthy       |
| `web_run`     | `<<: *web` + `runserver 0.0.0.0:8000`, czeka na `web_migrate` |

Wspólną część obu — obraz, `working_dir`, wolumen `.:/app`, zmienne
środowiskowe, sieć — trzyma jeden blok `x-web: &web` **nad** `services:`.
To nie usługa, tylko fragment do ponownego użycia: compose ignoruje klucze
najwyższego poziomu zaczynające się od `x-`, a `<<: *web` w każdej z usług
wkleja jego zawartość. Gdyby ta wspólna definicja była zwykłą usługą (a
potomkowie sięgali po nią przez `extends:`), `docker compose up` startowałby
ją jak każdą inną — czyli drugi, niepotrzebny `runserver` obok `web_run`.

To jest cały mechanizm startu: `web_run` nie wstanie, dopóki migracje się nie
wykonają, a te nie wystartują, dopóki healthcheck bazy nie przejdzie.

```bash
docker compose up            # albo: ./do.sh start
```

Testy uruchamiasz przez `./do.sh test` (pod spodem `pytest` w kontenerze
`web_run`). **`manage.py test` nie zadziała** — testy są napisane pod pytesta,
więc unittestowy discovery Django znajdzie zero przypadków i wypisze
`NO TESTS RAN` zamiast błędu. Szczegóły: [Etap 8](#etap-8).

Jakość kodu ma trzy komendy, wszystkie w kontenerze:

```bash
./do.sh lint        # ruff check
./do.sh format      # ruff format
./do.sh typecheck   # mypy
```

Te same narzędzia chodzą z `pre-commit`. Hooki instaluje się raz —
`uv run pre-commit install` — a potem uruchamiają się same przy każdym
`git commit`; całe repo naraz sprawdza `uv run pre-commit run --all-files`.
mypy działa też poza kontenerem (`uv run mypy`) dzięki
`src/sylwanspot/settings_typecheck.py` — patrz komentarz w tym pliku.

Zależności dodaje się na hoście: `uv add <paczka>`, potem `./do.sh build`.

`ruff format` celowo pomija dwie rzeczy: ten przewodnik (przykłady w nim
używają wyrównanych w kolumnie komentarzy końcowych, które formatter zbiłby do
jednej spacji) oraz migracje w `blog/migrations/` (są generowane przez Django
albo, jak `0005`, pisane ręcznie w surowym SQL-u — przeformatowanie byłoby
edycją, na którą nie ma zgody). Linter mimo to sprawdza migracje normalnie —
w `per-file-ignores` wyciszone są w nich tylko `E501` i `I001` (projektowo,
dla całego repo, wyciszony jest jeszcze `RUF012` — więc obowiązuje i tutaj).

Dwie rzeczy warte odnotowania w `docker-compose.yml`: `target: dev` wybiera
etap obrazu z narzędziami deweloperskimi, a wolumen `.:/app` montuje repo do
kontenera — dlatego `runserver` przeładowuje się po każdej edycji pliku i nie
musisz przebudowywać obrazu, żeby zobaczyć zmianę w kodzie. Pakiety
`sylwanspot` i `blog` są importowalne bez ręcznego ustawiania ścieżek importu,
bo `uv sync` instaluje projekt edytowalnie ze `src/`. Samo środowisko leży w
`/opt/venv`, **poza** `/app` — inaczej bind mount by je przykrył.

---

<a id="etap-1"></a>

## Etap 1 — ścieżka żądania

Ta sekwencja jest sercem Django. Przeczytaj cztery pliki po kolei i będziesz
rozumiał 80% frameworka.

### 1.1 `manage.py`

Trzy linie, które mają znaczenie: ustawia `DJANGO_SETTINGS_MODULE` na
`sylwanspot.settings` i przekazuje `sys.argv` do `execute_from_command_line`.
To wszystko — `manage.py` to tylko launcher komend. Każde `manage.py cokolwiek`
przechodzi tędy.

### 1.2 `src/sylwanspot/settings.py`

Konfiguracja całego projektu. Przy pierwszym czytaniu skup się na czterech
miejscach, resztę pomiń:

- **`INSTALLED_APPS`** — co jest włączone. Zwróć uwagę na
  `django.contrib.postgres` (potrzebne dla `SearchVectorField` i `GinIndex`),
  `taggit` (biblioteka zewnętrzna do tagów) oraz `blog.apps.BlogConfig` —
  wskazanie _konkretnej klasy konfiguracyjnej_, nie samej nazwy aplikacji. To
  ma znaczenie w etapie 2.
- **`TEMPLATES`** → `"APP_DIRS": True` — dlatego szablony leżą w
  `blog/templates/`, a nie w katalogu globalnym.
- **`DATABASES`** — `django.db.backends.postgresql`, wartości przez
  `python-decouple` (`config("POSTGRES_DB")`), czyli ze zmiennych środowiskowych
  ustawionych w `docker-compose.yml`.
- **`MIDDLEWARE`** — lista przetwarzająca _każde_ żądanie po kolei. Tu żyje
  ochrona CSRF, sesje i uwierzytelnianie.

### 1.3 `src/sylwanspot/urls.py` — root URLconf

Punkt wejścia routingu. Trzy wpisy: panel admina, `include('blog.urls')` pod
prefiksem `blog/` oraz `sitemap.xml`.

Kluczowa rzecz: `include(..., namespace='blog')` w połączeniu z
`app_name = "blog"` w `blog/urls.py` daje przestrzeń nazw. Dlatego wszędzie w
szablonach widzisz `{% url "blog:post_detail" %}`, a nie `{% url "post_detail" %}`.

### 1.4 `blog/urls.py` — URLconf aplikacji

Siedem tras. Przeczytaj je jako spis treści całej aplikacji — każda wskazuje
na widok, do którego przejdziesz w etapie 3:

```python
""                                          -> PostListView        (lista)
"tag/<slug:tag_slug>/"                      -> PostListView        (lista po tagu)
"<int:year>/<int:month>/<int:day>/<slug:post>/" -> post_detail
"<int:post_id>/share/"                      -> post_share
"<int:post_id>/comment/"                    -> post_comment
"feed/"                                     -> LatestPostsFeed
"search/"                                   -> post_search
```

`<int:...>` i `<slug:...>` to _konwertery ścieżki_ — Django waliduje typ i
przekazuje go do widoku jako argument nazwany. Zauważ, że `post_detail` bierze
aż cztery segmenty: data plus slug. Dlaczego, wyjaśni się w etapie 2 przy
`unique_for_date`.

> **Pełna ścieżka żądania:** przeglądarka → `wsgi.py` → MIDDLEWARE → root
> URLconf → `blog/urls.py` → widok → model (SQL) → szablon → HttpResponse →
> MIDDLEWARE w drugą stronę → przeglądarka.

---

<a id="etap-2"></a>

## Etap 2 — warstwa danych

### 2.1 `blog/models.py`

Najważniejszy plik w projekcie. Dwa modele i jeden manager.

**`Post`** — przeczytaj pole po polu, a potem zatrzymaj się na czterech
rzeczach:

- **`class Status(models.TextChoices)`** — enum wewnątrz modelu. Django tworzy
  z tego `choices` dla pola i daje dostęp przez `Post.Status.PUBLISHED`.
  W bazie siedzi dwuznakowe `"DF"` / `"PB"`.
- **`slug = models.SlugField(unique_for_date="publish")`** — unikalność slugu
  _w obrębie dnia publikacji_, nie globalnie. To dlatego URL ma w sobie datę:
  dwa posty mogą mieć slug `nowy-post`, jeśli opublikowano je innego dnia.
- **`author = models.ForeignKey(settings.AUTH_USER_MODEL, related_name="blog_posts")`**
  — relacja do wbudowanego modelu użytkownika. `related_name` tworzy odwrotną
  relację: `user.blog_posts.all()`.
- **`tags = TaggableManager()`** — z biblioteki django-taggit. Nie jest to
  zwykłe `ManyToManyField`: tagi trzymane są w tabelach `taggit_tag` i
  `taggit_taggeditem` przez _generic foreign key_, czyli jedna tabela obsługuje
  tagi dla dowolnego modelu. To komplikacja, która wraca w etapie 7.

**`PublishedManager`** — własny manager nadpisujący `get_queryset()`, żeby
filtrować po statusie. Efekt jest taki:

```python
Post.objects.all()      # wszystkie posty, także szkice
Post.published.all()    # tylko opublikowane
```

Zwróć uwagę, że `objects = models.Manager()` jest zadeklarowany **jawnie**.
Gdyby go nie było, Django uznałby `published` za domyślny manager i admin
przestałby pokazywać szkice.

**`class Meta`** — `ordering` (domyślne sortowanie każdego zapytania) oraz
`indexes`. Ta lista wraca w etapie 7.

**`Comment`** — prostszy: `ForeignKey` do `Post` z `related_name="comments"`,
dlatego w widoku piszesz `post.comments.filter(active=True)`, a nie
`Comment.objects.filter(post=post)`.

**`get_absolute_url()`** — konwencja Django. Model sam wie, jak zbudować swój
URL przez `reverse()`. Dlatego szablony robią `{{ post.get_absolute_url }}` i
nie muszą znać struktury adresów.

### 2.2 `blog/migrations/`

Historia schematu bazy, plik po pliku. Przeczytaj tylko nazwy i po jednej
operacji z każdego — nie ma potrzeby czytać ich w całości:

| migracja                  | co robi                                         |
| ------------------------- | ----------------------------------------------- |
| `0001_initial`            | tworzy `Post`                                   |
| `0002_alter_post_slug`    | dodaje `unique_for_date`                        |
| `0003_comment`            | tworzy `Comment`                                |
| `0004_post_tags`          | podłącza taggit                                 |
| `0005_polish_fts`         | polska konfiguracja FTS + `pg_trgm`             |
| `0006_post_search_vector` | kolumna `search_vector` + indeks GIN + backfill |

Model to _deklaracja stanu docelowego_; migracje to _kroki dojścia_. Django
generuje je z różnicy między modelem a ostatnią migracją:

```bash
docker compose exec web_run python /app/manage.py makemigrations blog --check --dry-run
# "No changes detected" = model i migracje są spójne
```

`0005` i `0006` są nietypowe, bo zawierają surowy SQL (`RunSQL`) — to wyjątek,
nie norma. Uzasadnienie jest w [`docs/search.md`](search.md).

### 2.3 `blog/admin.py`

Najkrótsza droga do zobaczenia własnych danych. `@admin.register(Post)` plus
klasa `ModelAdmin` z deklaracjami — `list_display`, `list_filter`,
`prepopulated_fields` (slug generowany z tytułu w locie w JS), `raw_id_fields`
(pole autora jako ID, nie rozwijana lista z wszystkimi userami).

```bash
docker compose exec web_run python /app/manage.py createsuperuser
# potem http://localhost:8000/admin/
```

Warto tam wejść już teraz i dodać post z tagami — będziesz miał na czym
testować kolejne etapy.

---

<a id="etap-3"></a>

## Etap 3 — widoki

`blog/views.py`. Pięć widoków — cztery funkcyjne i jeden klasowy — i to
zderzenie dwóch stylów jest właśnie najciekawszą rzeczą w tym pliku.

### 3.1 `post_detail` — widok funkcyjny, wzorzec podstawowy

Zacznij od tego. Struktura każdego widoku funkcyjnego w Django:

```python
def post_detail(request, year, month, day, post):   # argumenty z URLconf
    post = get_object_or_404(...)                   # pobierz albo 404
    comments = post.comments.filter(active=True)    # dane powiązane
    form = CommentForm()                            # pusty formularz
    similar_posts = ...                             # logika dodatkowa
    return render(request, "szablon.html", {...})   # szablon + kontekst
```

Zwróć uwagę na `similar_posts` — to najbardziej pouczające trzy linie w całym
pliku:

```python
post_tags_ids = post.tags.values_list("id", flat=True)
similar_posts = Post.published.filter(tags__in=post_tags_ids).exclude(id=post.id)
similar_posts = similar_posts.annotate(same_tags=Count("tags")).order_by("-same_tags", "-publish")[:4]
```

Trzy mechanizmy ORM w jednym: `filter(tags__in=...)` (przejście przez relację
podwójnym podkreśleniem), `annotate(Count(...))` (agregat policzony przez bazę
i dostępny jako atrybut obiektu) oraz `[:4]` (`LIMIT` w SQL, nie cięcie listy
w Pythonie). QuerySety są **leniwe** — żaden SQL nie leci, dopóki szablon nie
zacznie iterować.

### 3.2 `PostListView` — widok klasowy

Ten sam problem, inne podejście. `ListView` dostarcza gotowo paginację i
pobranie listy; ty nadpisujesz tylko punkty zaczepienia:

- `get_queryset()` — dodaje filtrowanie po tagu, jeśli w URL był `tag_slug`
- `get_context_data()` — wkłada `tag` do kontekstu szablonu
- `paginate_by = 3` — z tego bierze się `page_obj` w szablonie

Porównaj to z zakomentowaną funkcją `post_list` **bezpośrednio nad klasą** —
została w pliku celowo albo przez zapomnienie, ale jako materiał do nauki jest
świetna: robi dokładnie to samo ręcznie, z pełną obsługą `Paginator`,
`PageNotAnInteger` i `EmptyPage`. Przeczytaj obie wersje obok siebie; to
najlepsza ilustracja, co widok klasowy właściwie dla ciebie robi.

> Uwaga na zakomentowanej wersji: `return render(...)` jest wewnątrz bloku
> `except EmptyPage`, więc gdyby ją odkomentować, zwracałaby `None` dla
> normalnego żądania. Kolejny powód, dla którego klasowa wersja wygrała.

### 3.3 Pozostałe

`post_share` i `post_comment` to etap 5. `post_search` to etap 7.

---

<a id="etap-4"></a>

## Etap 4 — szablony

`blog/templates/`. Czytaj w tej kolejności, bo dziedziczenie idzie od
najbardziej ogólnego.

### 4.1 `blog/base.html` — szkielet

Definiuje bloki, które wypełniają wszystkie inne szablony:
`{% block title %}`, `{% block content %}`, plus `meta_description` i
`meta_keywords`. Poza tym cały sidebar — i tu jest ciekawostka: sidebar
wywołuje **własne tagi szablonów**, więc dane dociąga sam, bez pomocy widoku:

```django
Na blogu znajdziesz {% total_posts %} wpisów.
{% show_latest_posts 3 %}
{% get_most_commented_posts as most_commented_posts %}
```

Dlatego żaden widok nie musi przekazywać danych do sidebara. Cena: te
zapytania lecą przy **każdym** renderowaniu strony.

### 4.2 `blog/templatetags/blog_tags.py` — tu mieszkają te tagi

Cztery rzeczy, trzy różne rodzaje rejestracji — dobry przekrój możliwości:

| nazwa                      | typ             | zwraca                                       |
| -------------------------- | --------------- | -------------------------------------------- |
| `total_posts`              | `simple_tag`    | liczbę                                       |
| `show_latest_posts`        | `inclusion_tag` | wyrenderowany podszablon `latest_posts.html` |
| `get_most_commented_posts` | `simple_tag`    | QuerySet (używany z `as ...`)                |
| `markdown`                 | `filter`        | HTML z markdowna, przez `mark_safe`          |
| `pluralize_pl`             | `filter`        | poprawną polską formę liczby mnogiej         |

Dwie rzeczy do zauważenia. Po pierwsze, plik musi leżeć w katalogu
`templatetags/` z `__init__.py` — inaczej `{% load blog_tags %}` nie zadziała.
Po drugie, filtr `markdown` używa `mark_safe`, czyli **wyłącza auto-escaping**.
Jest to bezpieczne dokładnie tak długo, jak długo treść postów piszą wyłącznie
zaufani autorzy przez admina.

### 4.3 Szablony konkretne

- `blog/post/list.html` — `{% extends %}`, pętla po `posts`, linki do tagów
  przez `{% url "blog:post_list_by_tag" tag.slug %}`, na końcu
  `{% include "pagination.html" with page=page_obj %}`
- `pagination.html` — reużywalny fragment, dostaje `page` jako parametr
- `blog/post/detail.html` — post, podobne posty, licznik komentarzy
  (`pluralize_pl`), lista komentarzy, `{% include %}` formularza
- `blog/post/includes/comment_form.html` — sam formularz; konwencja `includes/`
  dla fragmentów nierenderowanych samodzielnie

Zwróć uwagę na `{% empty %}` w pętlach `{% for %}` — to gałąź dla pustej
kolekcji, czystsza niż osobne `{% if %}`.

---

<a id="etap-5"></a>

## Etap 5 — formularze i POST

### 5.1 `blog/forms.py`

Trzy formularze, dwa różne rodzaje bazowe:

- **`EmailPostForm(forms.Form)`** — formularz _niezwiązany_ z modelem. Pola
  deklarujesz ręcznie, dane nigdzie nie są zapisywane, tylko wysyłane mailem.
- **`CommentForm(forms.ModelForm)`** — formularz _z modelu_. `Meta.model` i
  `Meta.fields` wystarczają, żeby Django wygenerował pola, walidację i metodę
  `save()`.
- **`SearchForm(forms.Form)`** — jedno pole, etap 7.

### 5.2 `post_share` — wzorzec GET/POST w jednym widoku

Kanoniczny kształt, który zobaczysz w każdym projekcie Django:

```python
if request.method == "POST":
    form = EmailPostForm(request.POST)   # formularz związany z danymi
    if form.is_valid():                  # walidacja
        cd = form.cleaned_data           # dane po walidacji i konwersji typów
        send_mail(...)
        sent = True
else:
    form = EmailPostForm()               # pusty formularz dla GET
return render(...)                        # jedna ścieżka wyjścia
```

`cleaned_data` to nie to samo co `request.POST` — zawiera wartości po
walidacji i konwersji na typy Pythona.

### 5.3 `post_comment` — i realny błąd do znalezienia

Ten widok ma dekorator `@require_POST` (odrzuca GET) i zapisuje komentarz
przez `form.save(commit=False)`, żeby dopiąć `comment.post = post` przed
zapisem. Wzorzec `commit=False` warto zapamiętać.

Ale **przeczytaj go uważnie do końca**: gdy `form.is_valid()` zwróci `False`,
funkcja nie ma żadnego `return`. Zwraca `None`, a Django podnosi wtedy
`ValueError`. Sprawdzone na żywo:

```
POST z pustym e-mailem i treścią  -> HTTP 500 (ValueError)
POST z poprawnymi danymi          -> HTTP 200 "Komentarz został dodany"
```

To błąd sprzed tej sesji i **nie został naprawiony** — nie mieściło się w
zakresie zadania o wyszukiwaniu. Jeśli szukasz pierwszego samodzielnego
zadania w tym repo, to jest bardzo dobry kandydat: wystarczy `return render(...)`
z niepoprawnym formularzem poza blokiem `if`, żeby użytkownik zobaczył błędy
walidacji zamiast strony 500.

---

<a id="etap-6"></a>

## Etap 6 — poza HTML

Dwa krótkie pliki pokazujące, że widok nie musi zwracać strony.

- **`blog/feeds.py`** — `LatestPostsFeed(Feed)` z `django.contrib.syndication`.
  Metody `items()`, `item_title()`, `item_description()`, `item_pubdate()`
  wystarczają, żeby Django wygenerował RSS. Podłączony w `blog/urls.py` jako
  `LatestPostsFeed()` — instancja, nie klasa. Sprawdź:
  `curl -s localhost:8000/blog/feed/ | head -3`

  W wygenerowanym XML zobaczysz `<language>en-us</language>` przy polskiej
  treści — to najbardziej dotykalny skutek `LANGUAGE_CODE = "en-us"`
  z etapu 1.2 i dobry punkt wyjścia, jeśli kiedyś zabierzesz się za lokalizację.

- **`blog/sitemaps.py`** — `PostSitemap(Sitemap)` z `items()` i `lastmod()`.
  Podłączony w **root** URLconf, nie w aplikacji, bo `sitemap.xml` musi być w
  korzeniu domeny. Wymaga `django.contrib.sites` i `SITE_ID = 1`
  w `settings.py`. Sprawdź: `curl -s localhost:8000/sitemap.xml`

Oba używają `Post.published` — czyli szkice nie wyciekają ani do RSS, ani do
sitemapy. To ta sama jedna linia w managerze chroni trzy różne wyjścia.

---

<a id="etap-7"></a>

## Etap 7 — wyszukiwanie

Ostatnie, bo dotyka wszystkich poprzednich warstw naraz i jest jedynym
miejscem, gdzie projekt wychodzi poza standardowe Django w stronę
specyficznych możliwości PostgreSQL.

Kolejność czytania: `search.py` → `signals.py` → `apps.py` → `views.post_search`
→ `templates/blog/post/search.html` → `management/commands/rebuild_search_vectors.py`.

Trzy rzeczy warte zauważenia z perspektywy _frameworka_, niezależnie od samego
FTS:

1. **`apps.py` + `signals.py` — sygnały.** `BlogConfig.ready()` importuje
   `signals`, co rejestruje odbiorniki. To jedyne poprawne miejsce na taki
   import — w momencie `ready()` rejestr modeli jest już gotowy. Teraz wracasz
   do etapu 1 i rozumiesz, dlaczego `INSTALLED_APPS` wskazuje
   `blog.apps.BlogConfig`, a nie samo `"blog"`.
2. **`management/commands/` — własna komenda.** Klasa `Command(BaseCommand)`
   z metodą `handle()` w pliku o tej nazwie i Django samo dodaje
   `manage.py rebuild_search_vectors`. Wymaga `__init__.py` w `management/`
   i `management/commands/`.
3. **`search.py` — logika poza widokiem.** Widok ma 20 linii i deleguje.
   To dlatego wyszukiwanie da się przetestować bez klienta HTTP.

Uzasadnienia decyzji, pomiary i znane ograniczenia:
[`docs/search.md`](search.md). Infrastruktura bazy:
[`postgres/README.md`](../postgres/README.md).

---

<a id="etap-8"></a>

## Etap 8 — testy

**Czytaj:** `pyproject.toml` (sekcja `[tool.pytest.ini_options]`) →
`src/blog/tests/conftest.py` → dowolny `src/blog/tests/test_*.py`

```bash
./do.sh test                                            # całość
./do.sh test src/blog/tests/test_search.py              # jeden plik
./do.sh test src/blog/tests/test_search.py -k fuzzy     # jedna grupa przypadków
./do.sh test --create-db                                # po EDYCJI istniejącej migracji
```

### 8.1 Dlaczego pytest, a nie `manage.py test`

Runner Django wymaga klas dziedziczących po `TestCase`; pytest przyjmuje zwykłe
funkcje i daje dwie rzeczy, które przy rosnącej liczbie testów robią różnicę:
`@pytest.mark.parametrize` zamiast pętli z `subTest` (każdy przypadek to
osobna, nazwana pozycja w raporcie) oraz fixture'y wstrzykiwane po nazwie
zamiast dziedziczonych metod pomocniczych.

Konsekwencja: **`manage.py test` nie znajdzie tych testów.** Wypisze
`Found 0 test(s)` i `NO TESTS RAN` — nie błąd, więc łatwo tego nie zauważyć.
Jedyną obsługiwaną komendą jest `./do.sh test`.

Konfiguracja pytesta siedzi w `pyproject.toml`, w sekcji
`[tool.pytest.ini_options]` — tam są `DJANGO_SETTINGS_MODULE`, `testpaths` i
`--reuse-db`. Pakiety znajduje się bez `pythonpath`, bo `uv sync` instaluje
projekt edytowalnie ze `src/`.

`--reuse-db` znaczy „nie kasuj bazy testowej po przebiegu". Django i tak puszcza
na niej `migrate`, więc **nowe migracje są podchwytywane normalnie** — oszczędza
się na tym, że migracja 0005 (budowa słownika hunspell) nie wykonuje się od nowa
za każdym razem. Realna różnica na tym projekcie: ~1.9 s wobec ~0.9 s.

Kiedy trzeba `--create-db`: gdy zmienisz **migrację już zapisaną jako
zastosowana**. `migrate` porównuje nazwy z tabelą `django_migrations` i pomija
te, które tam są — nie zagląda w ich treść. Baza zostaje ze starym schematem.
Ta sama pułapka dotyczy usunięcia, przenumerowania i zsquashowania migracji.

Objaw jest jednoznaczny — nagle sypie się kilkanaście niepowiązanych testów:

```
psycopg.errors.UndefinedColumn: column "lead" of relation "blog_post" does not exist
```

Na tym projekcie najbardziej realny scenariusz to poprawka w SQL-u migracji
0005: dopisujesz słownik do konfiguracji `polish`, testy przy `--reuse-db`
nadal chodzą po starej konfiguracji i **przechodzą** — co jest groźniejsze niż
błąd, bo wygląda jak sukces.

### 8.2 Podział na pliki

Jeden plik na moduł źródłowy — dzięki temu odpowiedź na pytanie „gdzie dopisać
test do `search.py`" jest mechaniczna, a nie uznaniowa.

| plik                      | co pokrywa                                                                |
| ------------------------- | ------------------------------------------------------------------------- |
| `test_postgres_setup.py`  | konfiguracja `polish`, hunspell, stop-słowa, `pg_trgm`                    |
| `test_search.py`          | `search_posts()` — co znajduje, w jakiej kolejności, ile zapytań kosztuje |
| `test_search_indexing.py` | `signals.py` + `rebuild_search_vectors` — co ląduje w `search_vector`     |
| `test_views.py`           | wyrenderowany HTML: widok wyszukiwania i licznik komentarzy               |
| `test_templatetags.py`    | `pluralize_pl` — czysta funkcja, bez bazy                                 |

Dwa pliki pomocnicze:

- **`conftest.py`** — fixture'y współdzielone: `author` i fabryka `make_post`.
  Pytest wstrzykuje je po nazwie argumentu, bez importu. Trafia tu wyłącznie
  to, czego używa więcej niż jeden moduł; pomocnik jednego modułu zostaje
  w tym module (patrz `vector_of` w `test_search_indexing.py`).
- **`assertions.py`** — pytest-django nie eksportuje asercji Django, a
  `assertContains(..., html=True)` porównuje HTML semantycznie, nie bajt po
  bajcie. Cztery linie, które podpinają je jako zwykłe funkcje.

Rozdzielenie `test_postgres_setup.py` od reszty jest celowe: te testy nie
sprawdzają Twojego kodu, tylko środowisko. Gdy kontener `db` wstanie ze starego
obrazu, mają krzyknąć one — zamiast kilkunastu testów wyszukiwania
z niezrozumiałym komunikatem.

### 8.3 Kiedy dzielić dalej

Gdy plik przekroczy ~300–400 linii albo pojawi się w nim druga wyraźna oś
tematyczna. Najbliższy kandydat to `test_views.py`: przy testach `post_share`
(wysyłka maila), `post_comment` i paginacji stanie się pakietem
`tests/views/` z plikiem na widok. Nie wcześniej — pusty plik założony
„na zapas" to tylko jedno miejsce więcej do sprawdzenia.

---

<a id="co-zauwazysz"></a>

## Co zauważysz po drodze

Rzeczy, które wyglądają na błąd albo niedokończenie — żeby nie zastanawiać się,
czy czegoś nie rozumiesz.

**Realne problemy, nienaprawione:**

- `post_comment` zwraca `None` przy niepoprawnym formularzu → HTTP 500.
  Opisane w etapie 5.
- `SECRET_KEY` jest w `settings.py` na sztywno, `DEBUG = True`,
  `ALLOWED_HOSTS = []`. Poprawne dla dev, blokujące dla produkcji.
- Hasło do SMTP jest wpisane w `docker-compose.yml` jako placeholder z iksów.
  Zanim wstawisz tam prawdziwe, przenieś je do pliku `.env` (ten plik już
  raz z repo usunięto — patrz `git log`).

**Świadome lub nieszkodliwe:**

- `LANGUAGE_CODE = "en-us"` i `TIME_ZONE = "UTC"` przy polskiej treści. To nie
  przypadek, że ma to znaczenie — z tego wynika, dlaczego liczba mnoga wymaga
  własnego filtru, a nie `ngettext` (etap 4.2).
- Zakomentowana funkcja `post_list` w `views.py` — zostawiona, świetna do nauki
  (etap 3.2).
- Klasa `Postadmin` (małe „a") obok `CommentAdmin`. Kosmetyka.
- Brak `CLAUDE.md`. Jeśli będziesz często wracał do tego repo z Claude Code,
  warto go dodać przez `/init`.

---

<a id="cwiczenia"></a>

## Ćwiczenia sprawdzające

Jeśli umiesz odpowiedzieć bez zaglądania, przeczytałeś ze zrozumieniem.

1. Dlaczego URL posta zawiera datę, a nie tylko slug?
2. Czym różni się `Post.objects` od `Post.published` i dlaczego oba są
   zadeklarowane jawnie?
3. Skąd sidebar bierze liczbę postów, jeśli żaden widok mu jej nie przekazuje?
4. Dlaczego `INSTALLED_APPS` wskazuje `blog.apps.BlogConfig`, a nie `"blog"`?
5. W którym momencie wykonuje się SQL dla `similar_posts` w `post_detail`?
6. Co się stanie, gdy wyślesz formularz komentarza z pustym e-mailem?
7. Dlaczego `sitemap.xml` jest w root URLconf, a `feed/` w URLconf aplikacji?
8. Dlaczego tagi nie mogły trafić do indeksu funkcyjnego w etapie 7?

Odpowiedzi: 1 → `unique_for_date="publish"` (2.1); 2 → jawny `objects`
zapobiega temu, by `published` został managerem domyślnym (2.1); 3 → własny
tag `{% total_posts %}` (4.1–4.2); 4 → `ready()` rejestruje sygnały (7);
5 → dopiero gdy szablon zacznie iterować (3.1); 6 → HTTP 500, `ValueError` (5.3);
7 → musi być w korzeniu domeny (6); 8 → leżą w innej tabeli, a indeks funkcyjny
widzi tylko własny wiersz ([`docs/search.md`](search.md)).
