#!/bin/sh
# Emit metadata and a bounded, base64-encoded filename stream. The Worker decodes
# names before applying the public evidence schema and path redaction rules.
set -eu
export LC_ALL=C TZ=UTC0
operation=$1
path=$2
case "$path" in /*) ;; *) exit 64 ;; esac
# Keep errors structured and never copy a diagnostic containing a source path
# to the public evidence. GNU stat semantics are required for these fields.
format='%d %i %f %s %Y %Z|%y|%z'
if ! stat -Lc "$format" / >/dev/null 2>&1; then
    printf 'ERROR stat_tool_unavailable\n'
    exit 0
fi
fail_stat() {
    case "$1" in
        *': No such file or directory') reason=source_path_not_found ;;
        *': Permission denied') reason=source_permission_denied ;;
        *': Not a directory') reason=source_not_directory ;;
        *) reason=source_stat_failed ;;
    esac
    printf 'ERROR %s\n' "$reason"
    exit 0
}
metadata() {
    value=$(stat "$1" "$format" -- "$2" 2>&1) || fail_stat "$value"
    printf '%s\n' "$value"
}
enter_directory() {
    cd -P -- "$1" 2>/dev/null && return
    # stat reports the lookup error even when sh only reports "can't cd".
    message=$(stat -Lc %f -- "$1" 2>&1) || fail_stat "$message"
    if [ ! -d "$1" ]; then fail_stat ': Not a directory'; fi
    if [ ! -x "$1" ]; then fail_stat ': Permission denied'; fi
    fail_stat ''
}
precision=ns
if [ "$operation" = list ]; then
    # Old Workers consume one opaque token, using their selected Python's
    # stat precision. With no interpreter, only shell follow-ups are possible.
    for py in /usr/bin/python3 /usr/bin/python /usr/local/bin/python3; do
        [ -x "$py" ] || continue
        precision=$(cd / && "$py" -E -S -c 'import os; print("ns" if hasattr(os.stat("."), "st_mtime_ns") else "float")')
        break
    done
fi
printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%S.%6NZ)" "$precision"
if [ "${3:-}" = guarded ]; then
    # Address the entry relative to the same directory that supplied its guard.
    parent=${path%/*}
    enter_directory "${parent:-/}"
    metadata -Lc .
    path=./${path##*/}
fi
case "$operation" in
    stat)
        metadata -Lc "$path"
        ;;
    list)
        enter_directory "$path"
        metadata -Lc .
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
