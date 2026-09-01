#!/bin/sh
# Package one add-on as <name>.ankiaddon, installable through
# Tools > Add-ons > Install from file.
#
#   ./build.sh day_off
#
# With no argument, builds every add-on in the repository.
set -e
cd "$(dirname "$0")"

build() {
    name="$1"
    [ -f "$name/__init__.py" ] || { echo "no such add-on: $name" >&2; exit 1; }
    rm -f "$name.ankiaddon"
    ( cd "$name" && zip -q -r "../$name.ankiaddon" . \
        -x '*.DS_Store' '*__pycache__*' 'meta.json' 'user_files/*' 'README.md' )
    echo "built $name.ankiaddon"
}

if [ $# -gt 0 ]; then
    build "$1"
else
    for d in */; do
        [ -f "${d}__init__.py" ] && build "${d%/}"
    done
fi
