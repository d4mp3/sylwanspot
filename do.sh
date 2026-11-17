#!/bin/bash

COLUMNS="`tput cols`"
LINES="`tput lines`"
BOLD=$(tput bold)
NORMAL=$(tput sgr0)

COMPOSE_FILES="-f docker-compose.yml"

DOCKER_COMPOSE="docker compose ${COMPOSE_FILES}"

_requires() {
    service="$1"
    $DOCKER_COMPOSE ps -q $service &> /dev/null
    if [[ "$?" == 1 ]]; then
        echo "'$service' service is not running. Please run \`start\` first."
        exit 1
    fi
}

build() {
    $DOCKER_COMPOSE build --force-rm "${@:3}"
}

compose() {
    $DOCKER_COMPOSE "$@"
}

start() {
    $DOCKER_COMPOSE up "$@"
}

stop() {
    $DOCKER_COMPOSE down "$@"
}

shell() {
    _requires web_run
    exec -w /app web_run /bin/bash
}

migrate() {
    _requires web_run
    exec -w /app web_run python manage.py migrate "$@"
}

makemigrations() {
    _requires web_run
    exec -w /app web_run python manage.py makemigrations "$@"
}

startapp() {
    _requires web_run
    exec -w /app/src web_run django-admin startapp --template=../app_template "$@"
}

check() {
    _requires web_run
    exec -w /app web_run python manage.py check
}

lint() {
    _requires web_run
    exec -w /app web_run ruff check "$@"
}

format() {
    _requires web_run
    exec -w /app web_run ruff format "$@"
}

typecheck() {
    _requires web_run
    exec -w /app web_run mypy "$@"
}

test() {
    _requires web_run
    exec -w /app web_run python -m pytest "$@"
}

exec() {
    $DOCKER_COMPOSE exec -u "$(id -u):$(id -g)" -e HOME=/tmp -e COLUMNS -e LINES "$@"
}

_usage() {
    cat <<USAGE
Convenience wrapper around docker compose.

Usage:

    ${BOLD}build${NORMAL} [<arg>]

        Builds all the images (or the ones specified).


    ${BOLD}exec${NORMAL} [<arg>]

        Execute a command in a container

    ${BOLD}compose${NORMAL}

        Minimal wrapper around docker-compose, just ensures the correct config files are loaded.

    ${BOLD}migrate${NORMAL} [<arg>]

        Apply any unapplied django migrations

    ${BOLD}makemigrations${NORMAL} [<arg>]

        Create a new Django migration, using the given args

    ${BOLD}startapp${NORMAL} <name>

        Create a new Django app under src/, e.g. \`./do.sh startapp account\`.
        Remember to add its AppConfig to INSTALLED_APPS afterwards.

    ${BOLD}check${NORMAL}

        Validate django settings

    ${BOLD}lint${NORMAL} [<arg>]

        Run ruff over the codebase. Extra args are passed through, e.g.
        \`./do.sh lint --fix\`.

    ${BOLD}format${NORMAL} [<arg>]

        Reformat the codebase with ruff format.

    ${BOLD}typecheck${NORMAL} [<arg>]

        Run mypy over the codebase.

    ${BOLD}test${NORMAL} [<arg>]

        Run the test suite with pytest. Extra args are passed through, e.g.
        \`./do.sh test src/blog/tests/test_search.py -k fuzzy\`.


    ${BOLD}shell${NORMAL}

        Opens a bash terminal in web_run

    ${BOLD}start${NORMAL} [<arg>]

        Start the django server (and dependent services)
        You can pass \`-d\` for running detached.

    ${BOLD}stop${NORMAL} [<arg>]

        Stop the django server (and dependent services)

USAGE
}

if [ "$1" == "" ]; then
    _usage
fi

$*
