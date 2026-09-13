#!/bin/sh
# Package add-ons as .ankiaddon files in dist/, named after the add-on rather
# than its folder, so someone can download one file and double-click it.
#
#   ./build.sh subject_spread     one add-on
#   ./build.sh                    all of them
set -e
cd "$(dirname "$0")"
mkdir -p dist

build() {
    name="$1"
    [ -f "$name/__init__.py" ] || { echo "no such add-on: $name" >&2; exit 1; }
    # Friendly filename from the manifest's display name; the folder Anki
    # installs into comes from manifest "package", not from this filename.
    pretty=$(python3 -c "
import json,re,sys
n=json.load(open('$name/manifest.json'))['name']
print(re.sub(r'[^a-z0-9]+','-',n.lower()).strip('-'))
" 2>/dev/null || echo "$name")
    out="dist/$pretty.ankiaddon"
    rm -f "$out"
    ( cd "$name" && zip -q -r "../$out" . \
        -x '*.DS_Store' '*__pycache__*' 'meta.json' 'user_files/*' 'README.md' )
    echo "built $out"
}

if [ $# -gt 0 ]; then build "$1"; else
    for d in */; do
        [ "${d%/}" = "dist" ] && continue
        [ -f "${d}__init__.py" ] && build "${d%/}"
    done
fi
