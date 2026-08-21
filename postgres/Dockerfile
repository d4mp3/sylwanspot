FROM postgres:16.2

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends hunspell-pl; \
    tsearch_data="$(pg_config --sharedir)/tsearch_data"; \
    test -d "$tsearch_data"; \
    iconv -f ISO-8859-2 -t UTF-8 /usr/share/hunspell/pl_PL.aff \
        | sed '1s/^SET .*/SET UTF-8/' > "$tsearch_data/polish.affix"; \
    iconv -f ISO-8859-2 -t UTF-8 /usr/share/hunspell/pl_PL.dic \
        > "$tsearch_data/polish.dict"; \
    apt-get purge -y --auto-remove hunspell-pl; \
    rm -rf /var/lib/apt/lists/*; \
    chmod 644 "$tsearch_data/polish.affix" "$tsearch_data/polish.dict"; \
    head -1 "$tsearch_data/polish.affix"; \
    ls -l "$tsearch_data/polish.affix" "$tsearch_data/polish.dict"

# PostgreSQL ships no Polish stop word list, so we provide one. Referenced as
# `StopWords = polish` by the polish_hunspell dictionary.
COPY polish.stop /tmp/polish.stop
RUN set -eux; \
    tsearch_data="$(pg_config --sharedir)/tsearch_data"; \
    mv /tmp/polish.stop "$tsearch_data/polish.stop"; \
    chmod 644 "$tsearch_data/polish.stop"
