#!/bin/sh
# Emit metadata and a bounded, base64-encoded filename stream. The Worker decodes
# names before applying the public evidence schema and path redaction rules.
set -eu
export LC_ALL=C TZ=UTC0
operation=$1
path=$2
case "$path" in /*) ;; *) exit 64 ;; esac
if [ "${3:-}" = guarded ]; then
    # Address the entry relative to the same directory that supplied its guard.
    parent=${path%/*}
    cd -P -- "${parent:-/}"
    stat -Lc '%d %i %f %s %Y %Z|%y|%z' .
    path=./${path##*/}
fi
case "$operation" in
    stat)
        if ! stat -Lc '%d %i %f %s %Y %Z|%y|%z' -- "$path"; then
            printf 'stat_unavailable\n'
            exit 0
        fi
        ;;
    list)
        cd -P -- "$path"
        stat -Lc '%d %i %f %s %Y %Z|%y|%z' .
        # A trailing empty record signals normal completion. Keep one byte
        # beyond the budget to distinguish truncation from producer failure.
        { find . -mindepth 1 -maxdepth 1 -print0 && printf '\000'; } |
            head -c 65537 | base64
        ;;
    readlink)
        before=$(stat -c '%d %i %f %s %Y %Z|%y|%z' -- "$path")
        printf '%s\n' "$before"
        # The empty record distinguishes a failed readlink from a short target.
        { readlink -n -- "$path" && printf '\000'; } | base64
        after=$(stat -c '%d %i %f %s %Y %Z|%y|%z' -- "$path")
        [ "$before" = "$after" ] || exit 1
        ;;
    *) exit 64 ;;
esac

# Pod exec keeps stdin open after sending the script.
exit 0
