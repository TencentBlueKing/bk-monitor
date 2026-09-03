#!/bin/sh
# Resource-owned fixed read-only probe. It accepts only server-controlled typed arguments.

set -u
LC_ALL=C
export LC_ALL

if [ "$#" -ne 3 ]; then
    exit 64
fi
TARGET_DATA_ID=$1
INCLUDE_SOURCE_SAMPLE=$2
TARGET_CONFIG_HINTS=$3
case "$TARGET_DATA_ID" in
    ''|*[!0-9]*|0) exit 64 ;;
esac
case "$INCLUDE_SOURCE_SAMPLE" in
    0|1) ;;
    *) exit 64 ;;
esac
case "$TARGET_CONFIG_HINTS" in
    -) ;;
    ''|*[!A-Za-z0-9_.,-]*) exit 64 ;;
esac
if [ "${#TARGET_CONFIG_HINTS}" -gt 4096 ]; then
    exit 64
fi
target_config_hint_count=$(printf '%s' "$TARGET_CONFIG_HINTS" | tr ',' '\n' | awk '$0 != "-" && NF {count++} END {print count+0}')
if [ "$target_config_hint_count" -gt 20 ]; then
    exit 64
fi

PROTOCOL="bklog.collector.inspection.probe.v1"
PROBE_VERSION="137865321.1"
# Stay below BK-JOB/GSE's 5 MiB atomic script-task log limit.
OUTPUT_BUDGET_BYTES=4194304
OUTPUT_FINAL_RESERVE_BYTES=4096
MAX_CONFIG_BYTES=524288
MAX_CHILD_CONFIG_BYTES=65536
MAX_REGISTRAR_BYTES=524288
MAX_SAMPLE_BYTES=65536
MAX_COLLECTOR_FILE_LOG_BYTES=1048576
MAX_CHILD_CONFIG_SCAN=1000
MAX_MATCHED_CHILD_CONFIGS=5
MAX_SOURCES=50
output_used_bytes=0
content_kv_count=0
stream_count=0
output_budget_exhausted=false

safe_field() {
    printf '%s' "$1" | tr '\t\r\n' '___'
}

emit_kv() {
    key=$(safe_field "$1")
    value=$(safe_field "${2-}")
    line=$(printf 'BKLOG_KV\t%s\t%s' "$key" "$value")
    line_size=$((${#line} + 1))
    if [ "$((output_used_bytes + line_size + OUTPUT_FINAL_RESERVE_BYTES))" -gt "$OUTPUT_BUDGET_BYTES" ]; then
        output_budget_exhausted=true
        return 1
    fi
    printf '%s\n' "$line"
    output_used_bytes=$((output_used_bytes + line_size))
    content_kv_count=$((content_kv_count + 1))
}

emit_manifest_kv() {
    key=$(safe_field "$1")
    value=$(safe_field "${2-}")
    line=$(printf 'BKLOG_KV\t%s\t%s' "$key" "$value")
    line_size=$((${#line} + 1))
    if [ "$((output_used_bytes + line_size))" -gt "$OUTPUT_BUDGET_BYTES" ]; then
        return 1
    fi
    printf '%s\n' "$line"
    output_used_bytes=$((output_used_bytes + line_size))
}

decoded_base64_size() {
    encoded_value=$1
    if [ -z "$encoded_value" ]; then
        printf '0'
        return
    fi
    printf '%s' "$encoded_value" | base64 -d 2>/dev/null | wc -c | tr -d ' '
}

emit_encoded_stream() {
    stream_name_value=$(safe_field "$1")
    stream_path_value=$(safe_field "$2")
    stream_returned=$3
    stream_total=$4
    stream_truncated=$5
    stream_encoded=$6
    stream_encoded_size=${#stream_encoded}
    stream_header=$(printf 'BKLOG_STREAM\t%s\t%s\t%s\t%s\t%s\t%s' \
        "$stream_name_value" "$stream_path_value" "$stream_returned" "$stream_total" \
        "$stream_truncated" "$stream_encoded_size")
    stream_payload=$(printf 'BKLOG_B64\t%s\t%s' "$stream_name_value" "$stream_encoded")
    stream_end=$(printf 'BKLOG_END_STREAM\t%s' "$stream_name_value")
    stream_output_size=$((${#stream_header} + ${#stream_payload} + ${#stream_end} + 3))
    if [ "$((output_used_bytes + stream_output_size + OUTPUT_FINAL_RESERVE_BYTES))" -gt "$OUTPUT_BUDGET_BYTES" ]; then
        output_budget_exhausted=true
        emit_kv "${stream_name_value}.unavailable" "output_budget_exhausted" || true
        return 1
    fi
    printf '%s\n%s\n%s\n' "$stream_header" "$stream_payload" "$stream_end"
    output_used_bytes=$((output_used_bytes + stream_output_size))
    stream_count=$((stream_count + 1))
}

emit_blob() {
    blob_name=$1
    blob_path=$2
    maximum=$3
    if [ ! -r "$blob_path" ]; then
        emit_kv "${blob_name}.unavailable" "true"
        return
    fi
    if ! command -v base64 >/dev/null 2>&1; then
        emit_kv "${blob_name}.unavailable" "base64_missing"
        return
    fi
    if command -v sha256sum >/dev/null 2>&1; then
        emit_kv "${blob_name}.sha256" "$(sha256sum -- "$blob_path" 2>/dev/null | awk '{print $1}')"
    fi
    total=$(wc -c < "$blob_path" 2>/dev/null | tr -d ' ')
    case "$total" in
        ''|*[!0-9]*) total=0 ;;
    esac
    emit_kv "${blob_name}.mtime_epoch" "$(stat -Lc '%Y' "$blob_path" 2>/dev/null)"
    returned=$total
    truncated=false
    if [ "$returned" -gt "$maximum" ]; then
        returned=$maximum
        truncated=true
    fi
    encoded=$(dd if="$blob_path" bs=1 count="$returned" 2>/dev/null | base64 | tr -d '\r\n')
    actual_returned=$(decoded_base64_size "$encoded")
    emit_encoded_stream "$blob_name" "$blob_path" "$actual_returned" "$total" "$truncated" "$encoded" || true
}

emit_tail_blob() {
    blob_name=$1
    blob_path=$2
    maximum=$3
    if [ ! -r "$blob_path" ] || [ ! -f "$blob_path" ]; then
        emit_kv "${blob_name}.unavailable" "true"
        return
    fi
    if ! command -v base64 >/dev/null 2>&1; then
        emit_kv "${blob_name}.unavailable" "base64_missing"
        return
    fi
    total=$(wc -c < "$blob_path" 2>/dev/null | tr -d ' ')
    case "$total" in
        ''|*[!0-9]*) total=0 ;;
    esac
    returned=$total
    truncated=false
    if [ "$returned" -gt "$maximum" ]; then
        returned=$maximum
        truncated=true
    fi
    encoded=$(tail -c "$returned" "$blob_path" 2>/dev/null | base64 | tr -d '\r\n')
    actual_returned=$(decoded_base64_size "$encoded")
    emit_encoded_stream "$blob_name" "$blob_path" "$actual_returned" "$total" "$truncated" "$encoded" || true
}

registrar_filter_keys=""
registrar_filter_separator='
'

# Keys stay deliberately loose (source path, resolved path and both basenames) because
# the server still matches registrar states on path plus inode and device. Filtering the
# probe side on the full path alone would turn a server-side path mismatch into missing
# evidence, which is harder to diagnose than a mismatch.
add_registrar_filter_key() {
    candidate=$1
    [ -n "$candidate" ] || return 0
    case "$registrar_filter_separator$registrar_filter_keys$registrar_filter_separator" in
        *"$registrar_filter_separator$candidate$registrar_filter_separator"*) return 0 ;;
    esac
    if [ -n "$registrar_filter_keys" ]; then
        registrar_filter_keys="$registrar_filter_keys$registrar_filter_separator$candidate"
    else
        registrar_filter_keys=$candidate
    fi
}

emit_registrar_stream() {
    stream_name=$1
    registrar_path=$2
    if ! command -v base64 >/dev/null 2>&1; then
        emit_kv "${stream_name}.unavailable" "base64_missing"
        return
    fi
    registrar_total_lines=$(strings -n 4 -- "$registrar_path" 2>/dev/null | wc -l | tr -d ' ')
    case "$registrar_total_lines" in
        ''|*[!0-9]*) registrar_total_lines=0 ;;
    esac
    registrar_filter_key_count=0
    if [ -n "$registrar_filter_keys" ]; then
        registrar_filter_key_count=$(printf '%s\n' "$registrar_filter_keys" | wc -l | tr -d ' ')
    fi
    registrar_filtered=false
    registrar_filtered_lines=$registrar_total_lines
    encoded=""
    if [ "$registrar_filter_key_count" -gt 0 ] && command -v grep >/dev/null 2>&1; then
        registrar_filtered=true
        # grep -F reads the pattern operand as one fixed string per line.
        registrar_filtered_content=$(strings -n 4 -- "$registrar_path" 2>/dev/null | \
            grep -F "$registrar_filter_keys" 2>/dev/null)
        if [ -n "$registrar_filtered_content" ]; then
            registrar_filtered_lines=$(printf '%s\n' "$registrar_filtered_content" | wc -l | tr -d ' ')
            encoded=$(printf '%s\n' "$registrar_filtered_content" | \
                dd bs=1 count="$MAX_REGISTRAR_BYTES" 2>/dev/null | base64 | tr -d '\r\n')
        else
            registrar_filtered_lines=0
        fi
    else
        encoded=$(strings -n 4 -- "$registrar_path" 2>/dev/null | \
            dd bs=1 count="$MAX_REGISTRAR_BYTES" 2>/dev/null | base64 | tr -d '\r\n')
    fi
    emit_kv "${stream_name}.total_line_count" "$registrar_total_lines"
    emit_kv "${stream_name}.filtered" "$registrar_filtered"
    emit_kv "${stream_name}.filter_key_count" "$registrar_filter_key_count"
    emit_kv "${stream_name}.filtered_line_count" "$registrar_filtered_lines"
    actual_returned=$(decoded_base64_size "$encoded")
    registrar_truncated=false
    if [ "$actual_returned" -ge "$MAX_REGISTRAR_BYTES" ]; then
        registrar_truncated=true
    fi
    emit_encoded_stream "$stream_name" "$registrar_path" "$actual_returned" \
        "$actual_returned" "$registrar_truncated" "$encoded" || true
}

emit_sample_stream() {
    stream_name=$1
    source_path=$2
    if ! command -v base64 >/dev/null 2>&1; then
        emit_kv "${stream_name}.unavailable" "base64_missing"
        return
    fi
    total=$(wc -c < "$source_path" 2>/dev/null | tr -d ' ')
    case "$total" in
        ''|*[!0-9]*) total=0 ;;
    esac
    encoded=$(tail -c "$MAX_SAMPLE_BYTES" "$source_path" 2>/dev/null | base64 | tr -d '\r\n')
    actual_returned=$(decoded_base64_size "$encoded")
    sample_truncated=false
    if [ "$total" -gt "$actual_returned" ]; then
        sample_truncated=true
    fi
    emit_encoded_stream "$stream_name" "$source_path" "$actual_returned" \
        "$total" "$sample_truncated" "$encoded" || true
}

config_value() {
    key=$1
    file=$2
    awk -v wanted="$key" '
        {
            line=$0
            parsed_key=line
            sub(":.*$", "", parsed_key)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", parsed_key)
        }
        parsed_key == wanted {
            sub("^[^:]*:[[:space:]]*", "", line)
            gsub(/^[[:space:]\047\"]+|[[:space:]\047\"]+$/, "", line)
            print line
            exit
        }
    ' "$file" 2>/dev/null
}

nested_config_value() {
    parent=$1
    child=$2
    file=$3
    awk -v wanted_parent="$parent" -v wanted_child="$child" '
        /^[^[:space:]]/ {
            line=$0
            parsed_key=line
            sub(":.*$", "", parsed_key)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", parsed_key)
            inside=(parsed_key == wanted_parent)
            next
        }
        inside {
            line=$0
            parsed_key=line
            sub(":.*$", "", parsed_key)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", parsed_key)
            if (parsed_key == wanted_child) {
                sub("^[^:]*:[[:space:]]*", "", line)
                gsub(/^[[:space:]\047\"]+|[[:space:]\047\"]+$/, "", line)
                print line
                exit
            }
        }
    ' "$file" 2>/dev/null
}

duration_seconds() {
    printf '%s\n' "$1" | awk '
        {
            value=$0
            gsub(/[[:space:]\047\"]/, "", value)
            if (value ~ /^[0-9.]+ms$/) { sub(/ms$/, "", value); print value / 1000; exit }
            if (value ~ /^[0-9.]+s$/) { sub(/s$/, "", value); print value; exit }
            if (value ~ /^[0-9.]+m$/) { sub(/m$/, "", value); print value * 60; exit }
            if (value ~ /^[0-9.]+h$/) { sub(/h$/, "", value); print value * 3600; exit }
            if (value ~ /^[0-9.]+$/) { print value; exit }
            print 0
        }
    '
}

process_pid=""
sidecar_pid=""
main_config=""
main_config_source="process_argument"
main_config_candidate_count=0
for proc_dir in /proc/[0-9]*; do
    [ -r "$proc_dir/cmdline" ] || continue
    argv=$(tr '\000' '\n' < "$proc_dir/cmdline" 2>/dev/null)
    first=$(printf '%s\n' "$argv" | sed -n '1p')
    case "$first" in
        /bin/bkunifylogbeat|*/bkunifylogbeat)
            process_pid=${proc_dir##*/}
            previous=""
            while IFS= read -r argument; do
                if [ "$previous" = "-c" ]; then
                    main_config=$argument
                    break
                fi
                previous=$argument
            done <<EOF
$argv
EOF
            break
            ;;
    esac
done

for proc_dir in /proc/[0-9]*; do
    [ -r "$proc_dir/cmdline" ] || continue
    first=$(tr '\000' '\n' < "$proc_dir/cmdline" 2>/dev/null | sed -n '1p')
    case "$first" in
        /bk-log-sidecar|*/bk-log-sidecar)
            sidecar_pid=${proc_dir##*/}
            break
            ;;
    esac
done

process_cwd=""
process_binary_path=""
if [ -n "$process_pid" ]; then
    process_cwd=$(readlink "/proc/$process_pid/cwd" 2>/dev/null)
    process_binary_path=$(readlink "/proc/$process_pid/exe" 2>/dev/null)
fi

if [ -n "$main_config" ]; then
    case "$main_config" in
        /*) ;;
        *)
            relative_main_config=""
            if [ -n "$process_cwd" ] && [ -r "$process_cwd/$main_config" ]; then
                relative_main_config="$process_cwd/$main_config"
                main_config_source="process_argument_relative_cwd"
            elif [ -n "$process_binary_path" ]; then
                process_binary_dir=${process_binary_path%/*}
                if [ -r "$process_binary_dir/$main_config" ]; then
                    relative_main_config="$process_binary_dir/$main_config"
                    main_config_source="process_argument_relative_binary"
                fi
            fi
            main_config=$relative_main_config
            ;;
    esac
fi

if [ -n "$main_config" ] && [ -r "$main_config" ]; then
    canonical_main_config=$(readlink -f "$main_config" 2>/dev/null)
    [ -n "$canonical_main_config" ] && main_config=$canonical_main_config
    main_config_candidate_count=1
else
    main_config=""
    main_config_source="bounded_fallback_discovery"
    for candidate in \
        /usr/local/gse*/plugins/etc/bkunifylogbeat.conf \
        /opt/gse*/plugins/etc/bkunifylogbeat.conf \
        /data/etc/bkunifylogbeat.conf
    do
        [ -r "$candidate" ] || continue
        main_config_candidate_count=$((main_config_candidate_count + 1))
        [ -n "$main_config" ] || main_config=$candidate
    done
fi
[ -n "$main_config" ] || main_config="/data/etc/bkunifylogbeat.conf"
emit_kv "protocol" "$PROTOCOL"
emit_kv "probe_version" "$PROBE_VERSION"
emit_kv "target_data_id" "$TARGET_DATA_ID"
emit_kv "include_source_sample" "$INCLUDE_SOURCE_SAMPLE"
emit_kv "process_pid" "$process_pid"
emit_kv "sidecar_pid" "$sidecar_pid"
emit_kv "main_config_path" "$main_config"
emit_kv "main_config_source" "$main_config_source"
emit_kv "main_config_candidate_count" "$main_config_candidate_count"

if [ -z "$process_pid" ]; then
    emit_kv "process_missing" "true"
fi
if [ -z "$sidecar_pid" ]; then
    emit_kv "sidecar_process_missing" "true"
fi

emit_blob "main_config" "$main_config" "$MAX_CONFIG_BYTES"

path_data=$(config_value "path.data" "$main_config")
path_logs=$(config_value "path.logs" "$main_config")
path_pid=$(config_value "path.pid" "$main_config")
emit_kv "path_data" "$path_data"
emit_kv "path_logs" "$path_logs"
emit_kv "path_pid" "$path_pid"
emit_kv "page_size" "$(getconf PAGESIZE 2>/dev/null || printf '4096')"
emit_kv "clock_ticks_per_second" "$(getconf CLK_TCK 2>/dev/null || printf '100')"
emit_kv "cpu_count" "$(getconf _NPROCESSORS_ONLN 2>/dev/null || printf '1')"

multi_config_rows=$(awk '
    /^[^[:space:]]/ {
        if ($0 ~ /^bkunifylogbeat[.]multi_config[[:space:]]*:/) { inside=1; next }
        if (inside) { exit }
    }
    inside && /^[[:space:]]*-[[:space:]]*path[[:space:]]*:/ {
        line=$0; sub("^[^:]*:[[:space:]]*", "", line); gsub(/[\047\"]/, "", line); print line "\t*.conf"; next
    }
    inside && /^[[:space:]]*path[[:space:]]*:/ {
        line=$0; sub("^[^:]*:[[:space:]]*", "", line); gsub(/[\047\"]/, "", line); current=line; next
    }
    inside && /^[[:space:]]*file_pattern[[:space:]]*:/ {
        line=$0; sub("^[^:]*:[[:space:]]*", "", line); gsub(/[\047\"]/, "", line); print current "\t" line
    }
' "$main_config" 2>/dev/null)

if [ -z "$multi_config_rows" ] && [ -d "/data/etc/bkunifylogbeat" ]; then
    multi_config_rows="/data/etc/bkunifylogbeat\t*.conf"
    emit_kv "multi_config_fallback" "true"
fi

tab=$(printf '\t')
hinted_child_paths=$(printf '%s\n' "$TARGET_CONFIG_HINTS" | tr ',' '\n' | while IFS= read -r hint; do
    [ -n "$hint" ] && [ "$hint" != "-" ] || continue
    printf '%b\n' "$multi_config_rows" | while IFS="$tab" read -r directory pattern; do
        [ -d "$directory" ] || continue
        [ "${directory#/}" != "$directory" ] || continue
        find -H "$directory" -maxdepth 1 \( -type f -o -type l \) \
            -name "${pattern:-*.conf}" \
            \( -name "$hint" -o -name "*_$hint" -o -name "$hint.conf" -o -name "${hint}_*.conf" \
            -o -name "*${hint}.conf" -o -name "*${hint}_*.conf" \) \
            -print 2>/dev/null
    done
done)
target_config_hint_path_count=$(printf '%s\n' "$hinted_child_paths" | awk 'NF {count++} END {print count+0}')

if [ "$target_config_hint_count" -gt 0 ]; then
    all_child_paths=$(printf '%s\n' "$hinted_child_paths" | awk 'NF && !seen[$0]++')
else
    all_child_paths=$(
        printf '%b\n' "$multi_config_rows" | while IFS="$tab" read -r directory pattern; do
            [ -d "$directory" ] || continue
            [ "${directory#/}" != "$directory" ] || continue
            find -H "$directory" -maxdepth 1 \( -type f -o -type l \) -name "${pattern:-*.conf}" 2>/dev/null
        done | awk -v limit="$((MAX_CHILD_CONFIG_SCAN + 1))" '
        NF && !seen[$0]++ {print; count++; if (count >= limit) exit}
        '
    )
fi

discovered_child_count=$(printf '%s\n' "$all_child_paths" | awk 'NF {count++} END {print count+0}')
case "$discovered_child_count" in ''|*[!0-9]*) discovered_child_count=0 ;; esac
child_config_scan_truncated=false
if [ "$discovered_child_count" -gt "$MAX_CHILD_CONFIG_SCAN" ]; then
    child_config_scan_truncated=true
fi
scan_paths=$(printf '%s\n' "$all_child_paths" | sed -n "1,${MAX_CHILD_CONFIG_SCAN}p")
child_config_scanned_count=$(printf '%s\n' "$scan_paths" | awk 'NF {count++} END {print count+0}')
case "$child_config_scanned_count" in ''|*[!0-9]*) child_config_scanned_count=0 ;; esac
emit_kv "child_config_scan_limit" "$MAX_CHILD_CONFIG_SCAN"
emit_kv "child_config_scanned_count" "$child_config_scanned_count"
emit_kv "child_config_scan_truncated" "$child_config_scan_truncated"
emit_kv "child_config_hint_count" "$target_config_hint_count"
emit_kv "child_config_hint_path_count" "$target_config_hint_path_count"

matching_child_paths=$(while IFS= read -r child_path; do
    [ -n "$child_path" ] || continue
    awk -v wanted="$TARGET_DATA_ID" '
        {
            line=$0
            sub(/[[:space:]]+#.*$/, "", line)
            key=line
            sub(/:.*/, "", key)
            gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
            sub(/^-[[:space:]]*/, "", key)
            if (key == "dataid" || key == "data_id" || key == "dataId") {
                sub(/^[^:]*:[[:space:]]*/, "", line)
                gsub(/^[[:space:]\047\"]+|[[:space:]\047\"]+$/, "", line)
                if (line == wanted) found=1
            }
        }
        END {exit found ? 0 : 1}
    ' "$child_path" 2>/dev/null && printf '%s\n' "$child_path"
done <<EOF
$scan_paths
EOF
)
child_config_match_count=$(printf '%s\n' "$matching_child_paths" | awk 'NF {count++} END {print count+0}')
case "$child_config_match_count" in ''|*[!0-9]*) child_config_match_count=0 ;; esac
child_config_match_limit_exceeded=false
if [ "$child_config_match_count" -gt "$MAX_MATCHED_CHILD_CONFIGS" ]; then
    child_config_match_limit_exceeded=true
    emit_kv "child_config_limit_exceeded" "true"
fi
child_paths=$(printf '%s\n' "$matching_child_paths" | sed -n "1,${MAX_MATCHED_CHILD_CONFIGS}p")
child_count=$(printf '%s\n' "$child_paths" | awk 'NF {count++} END {print count+0}')
case "$child_count" in ''|*[!0-9]*) child_count=0 ;; esac
emit_kv "child_config_match_count" "$child_config_match_count"
emit_kv "child_config_match_limit_exceeded" "$child_config_match_limit_exceeded"
emit_kv "child_config_count" "$child_count"

child_index=0
source_patterns=""
while IFS= read -r child_path && [ "$child_index" -lt "$MAX_MATCHED_CHILD_CONFIGS" ]; do
    [ -n "$child_path" ] || continue
    case "$child_path" in
        *"$tab"*) continue ;;
    esac
    emit_blob "child_config.$child_index" "$child_path" "$MAX_CHILD_CONFIG_BYTES"
    extracted_patterns=$(awk '
        /^[[:space:]]*paths[[:space:]]*:[[:space:]]*\[/ {
            line=$0
            sub("^[^[]*\\[", "", line)
            sub("\\].*$", "", line)
            count=split(line, values, ",")
            for (idx=1; idx<=count; idx++) {
                value=values[idx]
                gsub(/^[[:space:]\047\"]+|[[:space:]\047\"]+$/, "", value)
                if (value ~ /^\//) print value
            }
            inside=0
            next
        }
        /^[[:space:]]*paths[[:space:]]*:/ { inside=1; next }
        inside && /^[[:space:]]*-[[:space:]]*/ {
            line=$0
            sub("^[[:space:]]*-[[:space:]]*", "", line)
            gsub(/^[\047\"]|[\047\"]$/, "", line)
            if (line ~ /^\//) print line
            next
        }
        inside && $0 !~ /^[[:space:]]/ { inside=0 }
    ' "$child_path" 2>/dev/null)
    if [ -n "$extracted_patterns" ]; then
        source_patterns="$source_patterns
$extracted_patterns"
    fi
    child_index=$((child_index + 1))
done <<EOF
$child_paths
EOF

source_patterns=$(printf '%s\n' "$source_patterns" | awk 'NF' | sort -u | sed -n "1,$((MAX_SOURCES + 1))p")
source_pattern_count=$(printf '%s\n' "$source_patterns" | awk 'NF {count++} END {print count+0}')
case "$source_pattern_count" in ''|*[!0-9]*) source_pattern_count=0 ;; esac
emit_kv "source_pattern_count" "$source_pattern_count"
if [ "$source_pattern_count" -gt "$MAX_SOURCES" ]; then
    emit_kv "source_narrowing_required" "true"
fi

snapshot_one_process() {
    phase=$1
    role=$2
    pid=$3
    prefix="$phase.$role"
    if [ -z "$pid" ] || [ ! -r "/proc/$pid/stat" ]; then
        emit_kv "$prefix.unavailable" "true"
        return
    fi
    stat_row=$(cat "/proc/$pid/stat" 2>/dev/null)
    cpu_ticks=$(printf '%s\n' "$stat_row" | awk '{print $14+$15}')
    start_ticks=$(printf '%s\n' "$stat_row" | awk '{print $22}')
    rss_pages=$(printf '%s\n' "$stat_row" | awk '{print $24}')
    fd_count=$(find "/proc/$pid/fd" -mindepth 1 -maxdepth 1 2>/dev/null | wc -l | tr -d ' ')
    read_bytes=$(awk '/^read_bytes:/ {print $2}' "/proc/$pid/io" 2>/dev/null)
    write_bytes=$(awk '/^write_bytes:/ {print $2}' "/proc/$pid/io" 2>/dev/null)
    threads=$(awk '/^Threads:/ {print $2}' "/proc/$pid/status" 2>/dev/null)
    pss_kib=$(awk '/^Pss:/ {print $2}' "/proc/$pid/smaps_rollup" 2>/dev/null)
    fd_soft_limit=$(awk '/^Max open files/ {print $(NF-2)}' "/proc/$pid/limits" 2>/dev/null)
    fd_hard_limit=$(awk '/^Max open files/ {print $(NF-1)}' "/proc/$pid/limits" 2>/dev/null)
    fd_socket=0
    fd_pipe=0
    fd_anon=0
    fd_deleted=0
    fd_other=0
    fd_inspected=0
    for fd_path in /proc/$pid/fd/*; do
        [ -e "$fd_path" ] || continue
        [ "$fd_inspected" -lt 4096 ] || break
        fd_target=$(readlink "$fd_path" 2>/dev/null)
        case "$fd_target" in
            socket:*) fd_socket=$((fd_socket + 1)) ;;
            pipe:*) fd_pipe=$((fd_pipe + 1)) ;;
            anon_inode:*) fd_anon=$((fd_anon + 1)) ;;
            *) fd_other=$((fd_other + 1)) ;;
        esac
        case "$fd_target" in *' (deleted)') fd_deleted=$((fd_deleted + 1)) ;; esac
        fd_inspected=$((fd_inspected + 1))
    done
    emit_kv "$prefix.process_pid" "$pid"
    emit_kv "$prefix.binary_path" "$(readlink "/proc/$pid/exe" 2>/dev/null)"
    emit_kv "$prefix.cpu_ticks" "$cpu_ticks"
    emit_kv "$prefix.start_ticks" "$start_ticks"
    emit_kv "$prefix.rss_pages" "$rss_pages"
    emit_kv "$prefix.fd_count" "$fd_count"
    emit_kv "$prefix.read_bytes" "$read_bytes"
    emit_kv "$prefix.write_bytes" "$write_bytes"
    emit_kv "$prefix.threads" "$threads"
    emit_kv "$prefix.pss_kib" "$pss_kib"
    emit_kv "$prefix.fd_soft_limit" "$fd_soft_limit"
    emit_kv "$prefix.fd_hard_limit" "$fd_hard_limit"
    emit_kv "$prefix.fd_inspected" "$fd_inspected"
    emit_kv "$prefix.fd_socket" "$fd_socket"
    emit_kv "$prefix.fd_pipe" "$fd_pipe"
    emit_kv "$prefix.fd_anon" "$fd_anon"
    emit_kv "$prefix.fd_other" "$fd_other"
    emit_kv "$prefix.fd_deleted" "$fd_deleted"
    if [ "$fd_count" -gt "$fd_inspected" ]; then
        emit_kv "$prefix.fd_classification_truncated" "true"
    fi
    if [ -r "/proc/$pid/cgroup" ]; then
        emit_blob "$prefix.cgroup" "/proc/$pid/cgroup" 65536
        cgroup_v2_path=$(awk -F: '$1 == "0" && $2 == "" {print $3; exit}' "/proc/$pid/cgroup" 2>/dev/null)
        case "$cgroup_v2_path" in
            /*)
                case "$cgroup_v2_path" in
                    *'..'*) ;;
                    *)
                        cgroup_v2_root="/sys/fs/cgroup/${cgroup_v2_path#/}"
                        for metric in memory.current memory.max pids.current pids.max; do
                            if [ -r "$cgroup_v2_root/$metric" ]; then
                                emit_kv "$prefix.cgroup.$metric" "$(dd if="$cgroup_v2_root/$metric" bs=1 count=65536 2>/dev/null)"
                            fi
                        done
                        if [ -r "$cgroup_v2_root/cpu.stat" ]; then
                            for cpu_metric in usage_usec user_usec system_usec nr_periods nr_throttled throttled_usec; do
                                emit_kv "$prefix.cgroup.cpu.stat.$cpu_metric" "$(awk -v key="$cpu_metric" '$1 == key {print $2; exit}' "$cgroup_v2_root/cpu.stat" 2>/dev/null)"
                            done
                        fi
                        ;;
                esac
                ;;
        esac
    fi
}

snapshot_processes() {
    phase=$1
    snapshot_one_process "$phase" "collector" "$process_pid"
    snapshot_one_process "$phase" "sidecar" "$sidecar_pid"
}

snapshot_sources() {
    phase=$1
    index=0
    source_limit_exceeded=false
    while IFS= read -r pattern; do
        case "$pattern" in
            /*) ;;
            *) continue ;;
        esac
        for source_path in $pattern; do
            [ -e "$source_path" ] || continue
            if [ "$index" -ge "$MAX_SOURCES" ]; then
                source_limit_exceeded=true
                break
            fi
            metadata=$(stat -Lc '%d %i %s %Y' "$source_path" 2>/dev/null)
            [ -n "$metadata" ] || continue
            device=$(printf '%s\n' "$metadata" | awk '{print $1}')
            inode=$(printf '%s\n' "$metadata" | awk '{print $2}')
            size_bytes=$(printf '%s\n' "$metadata" | awk '{print $3}')
            mtime_epoch=$(printf '%s\n' "$metadata" | awk '{print $4}')
            resolved_path=$(readlink -f "$source_path" 2>/dev/null)
            emit_kv "$phase.source.$index.pattern" "$pattern"
            emit_kv "$phase.source.$index.path" "$source_path"
            emit_kv "$phase.source.$index.resolved_path" "$resolved_path"
            add_registrar_filter_key "$source_path"
            add_registrar_filter_key "$resolved_path"
            add_registrar_filter_key "${source_path##*/}"
            add_registrar_filter_key "${resolved_path##*/}"
            if [ -L "$source_path" ]; then
                emit_kv "$phase.source.$index.symlink" "true"
            fi
            emit_kv "$phase.source.$index.device" "$device"
            emit_kv "$phase.source.$index.inode" "$inode"
            emit_kv "$phase.source.$index.size_bytes" "$size_bytes"
            emit_kv "$phase.source.$index.mtime_epoch" "$mtime_epoch"
            if [ "$phase" = "second" ] && [ "$INCLUDE_SOURCE_SAMPLE" = "1" ] && [ -f "$source_path" ]; then
                emit_sample_stream "$phase.source.$index.sample" "$source_path"
            fi
            index=$((index + 1))
        done
    done <<EOF
$source_patterns
EOF
    emit_kv "$phase.source_count" "$index"
    if [ "$source_limit_exceeded" = "true" ]; then
        emit_kv "source_narrowing_required" "true"
    fi
}

snapshot_registrar() {
    phase=$1
    if [ -z "$path_data" ]; then
        emit_kv "$phase.registrar_unavailable" "path_data_missing"
        return
    fi
    registrar_path="$path_data/bkunifylogbeat.bkpipe.db"
    emit_kv "registrar_path" "$registrar_path"
    if ! command -v strings >/dev/null 2>&1; then
        emit_kv "$phase.registrar_unavailable" "strings_missing"
        return
    fi
    if [ ! -r "$registrar_path" ]; then
        emit_kv "$phase.registrar_unavailable" "registrar_unreadable"
        return
    fi
    emit_registrar_stream "$phase.registrar_strings" "$registrar_path"
}

snapshot_processes "first"
snapshot_sources "first"
snapshot_registrar "first"

flush=$(duration_seconds "$(nested_config_value 'bkunifylogbeat.registry' 'flush' "$main_config")")
scan=0
max_backoff=0
multiline=0
while IFS= read -r child_path; do
    current=$(duration_seconds "$(config_value 'scan_frequency' "$child_path")")
    scan=$(awk -v left="$scan" -v right="$current" 'BEGIN {if (left > right) print left; else print right}')
    current=$(duration_seconds "$(config_value 'max_backoff' "$child_path")")
    max_backoff=$(awk -v left="$max_backoff" -v right="$current" 'BEGIN {if (left > right) print left; else print right}')
    current=$(duration_seconds "$(config_value 'timeout' "$child_path")")
    multiline=$(awk -v left="$multiline" -v right="$current" 'BEGIN {if (left > right) print left; else print right}')
done <<EOF
$child_paths
EOF
required=$(awk -v flush="$flush" -v scan="$scan" -v backoff="$max_backoff" -v multiline="$multiline" '
    BEGIN { value=flush*2; if (scan>value) value=scan; if (backoff>value) value=backoff; if (multiline>value) value=multiline; print value+2 }
')
observation=$(awk -v value="$required" 'BEGIN {if (value<5) print 5; else if (value>30) print 30; else print int(value+0.999)}')
emit_kv "observation_required_seconds" "$required"
emit_kv "observation_seconds" "$observation"
if awk -v value="$required" 'BEGIN {exit !(value>30)}'; then
    emit_kv "insufficient_observation_window" "true"
fi
sleep "$observation"

snapshot_processes "second"
snapshot_registrar "second"
snapshot_sources "second"

collector_file_log_count=0
case "$path_logs" in
    /*)
        if [ -d "$path_logs" ]; then
            collector_file_logs=$(find -H "$path_logs" -maxdepth 1 \( -type f -o -type l \) \( \
                -name 'bkunifylogbeat' -o -name 'bkunifylogbeat.[0-9]*' -o \
                -name 'bkunifylogbeat.err*' -o -name 'bkunifylogbeat.error*' -o \
                -name 'bkunifylogbeat-error*.log*' -o -name '*.log' -o -name '*.log.*' \
            \) 2>/dev/null | sort | tail -n 2)
            while IFS= read -r collector_file_log && [ "$collector_file_log_count" -lt 2 ]; do
                [ -n "$collector_file_log" ] || continue
                emit_tail_blob "collector_file_log.$collector_file_log_count" "$collector_file_log" "$((MAX_COLLECTOR_FILE_LOG_BYTES / 2))"
                collector_file_log_count=$((collector_file_log_count + 1))
            done <<EOF
$collector_file_logs
EOF
        fi
        ;;
esac
emit_kv "collector_file_log_count" "$collector_file_log_count"

emit_manifest_kv "manifest_kv_count" "$content_kv_count" || exit 70
emit_manifest_kv "manifest_stream_count" "$stream_count" || exit 70
emit_manifest_kv "output_budget_bytes" "$OUTPUT_BUDGET_BYTES" || exit 70
emit_manifest_kv "output_budget_exhausted" "$output_budget_exhausted" || exit 70
emit_manifest_kv "completed" "true" || exit 70
exit 0
