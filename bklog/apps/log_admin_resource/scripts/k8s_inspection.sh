#!/bin/sh
# Resource-owned fixed read-only probe. It intentionally accepts no arguments.

set -u

if [ "$#" -ne 0 ]; then
    exit 64
fi

PROTOCOL="bklog.collector.k8s_inspection.probe.v1"
PROBE_VERSION="137707084.1"
MAX_CONFIG_BYTES=524288
MAX_CHILD_CONFIG_BYTES=65536
MAX_REGISTRAR_BYTES=524288
MAX_SAMPLE_BYTES=65536
MAX_COLLECTOR_FILE_LOG_BYTES=1048576
MAX_CHILD_CONFIGS=20
MAX_SOURCES=50

safe_field() {
    printf '%s' "$1" | tr '\t\r\n' '___'
}

emit_kv() {
    key=$(safe_field "$1")
    value=$(safe_field "${2-}")
    printf 'BKLOG_KV\t%s\t%s\n' "$key" "$value"
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
    printf 'BKLOG_STREAM\t%s\t%s\t%s\t%s\t%s\n' \
        "$(safe_field "$blob_name")" "$(safe_field "$blob_path")" "$returned" "$total" "$truncated"
    printf 'BKLOG_B64\t%s\t' "$(safe_field "$blob_name")"
    dd if="$blob_path" bs=1 count="$returned" 2>/dev/null | base64 | tr -d '\r\n'
    printf '\n'
    printf 'BKLOG_END_STREAM\t%s\n' "$(safe_field "$blob_name")"
}

emit_tail_blob() {
    blob_name=$1
    blob_path=$2
    maximum=$3
    if [ ! -r "$blob_path" ] || [ ! -f "$blob_path" ] || [ -L "$blob_path" ]; then
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
    printf 'BKLOG_STREAM\t%s\t%s\t%s\t%s\t%s\n' \
        "$(safe_field "$blob_name")" "$(safe_field "$blob_path")" "$returned" "$total" "$truncated"
    printf 'BKLOG_B64\t%s\t' "$(safe_field "$blob_name")"
    tail -c "$returned" "$blob_path" 2>/dev/null | base64 | tr -d '\r\n'
    printf '\n'
    printf 'BKLOG_END_STREAM\t%s\n' "$(safe_field "$blob_name")"
}

emit_registrar_stream() {
    stream_name=$1
    registrar_path=$2
    printf 'BKLOG_STREAM\t%s\t%s\t%s\t%s\t%s\n' \
        "$(safe_field "$stream_name")" "$(safe_field "$registrar_path")" \
        "$MAX_REGISTRAR_BYTES" "$MAX_REGISTRAR_BYTES" "unknown"
    if ! command -v base64 >/dev/null 2>&1; then
        emit_kv "${stream_name}.unavailable" "base64_missing"
        printf 'BKLOG_END_STREAM\t%s\n' "$(safe_field "$stream_name")"
        return
    fi
    printf 'BKLOG_B64\t%s\t' "$(safe_field "$stream_name")"
    strings -n 4 -- "$registrar_path" 2>/dev/null | dd bs=1 count="$MAX_REGISTRAR_BYTES" 2>/dev/null | \
        base64 | tr -d '\r\n'
    printf '\n'
    printf 'BKLOG_END_STREAM\t%s\n' "$(safe_field "$stream_name")"
}

emit_sample_stream() {
    stream_name=$1
    source_path=$2
    printf 'BKLOG_STREAM\t%s\t%s\t%s\t%s\t%s\n' \
        "$(safe_field "$stream_name")" "$(safe_field "$source_path")" \
        "$MAX_SAMPLE_BYTES" "$MAX_SAMPLE_BYTES" "unknown"
    if ! command -v base64 >/dev/null 2>&1; then
        emit_kv "${stream_name}.unavailable" "base64_missing"
        printf 'BKLOG_END_STREAM\t%s\n' "$(safe_field "$stream_name")"
        return
    fi
    printf 'BKLOG_B64\t%s\t' "$(safe_field "$stream_name")"
    tail -c "$MAX_SAMPLE_BYTES" "$source_path" 2>/dev/null | base64 | tr -d '\r\n'
    printf '\n'
    printf 'BKLOG_END_STREAM\t%s\n' "$(safe_field "$stream_name")"
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

[ -n "$main_config" ] || main_config="/data/etc/bkunifylogbeat.conf"
emit_kv "protocol" "$PROTOCOL"
emit_kv "probe_version" "$PROBE_VERSION"
emit_kv "process_pid" "$process_pid"
emit_kv "sidecar_pid" "$sidecar_pid"
emit_kv "main_config_path" "$main_config"

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
child_paths=$(printf '%b\n' "$multi_config_rows" | while IFS="$tab" read -r directory pattern; do
    [ -d "$directory" ] || continue
    [ "${directory#/}" != "$directory" ] || continue
    find "$directory" -maxdepth 1 -type f -name "${pattern:-*.conf}" 2>/dev/null
done | sed -n "1,$((MAX_CHILD_CONFIGS + 1))p")

child_count=$(printf '%s\n' "$child_paths" | awk 'NF {count++} END {print count+0}')
case "$child_count" in ''|*[!0-9]*) child_count=0 ;; esac
if [ "$child_count" -gt "$MAX_CHILD_CONFIGS" ]; then
    emit_kv "child_config_limit_exceeded" "true"
    child_count=$MAX_CHILD_CONFIGS
fi
emit_kv "child_config_count" "$child_count"

child_index=0
source_patterns=""
while IFS= read -r child_path && [ "$child_index" -lt "$MAX_CHILD_CONFIGS" ]; do
    [ -n "$child_path" ] || continue
    case "$child_path" in
        *'\t'*|*'\r'*|*'\n'*) continue ;;
    esac
    emit_blob "child_config.$child_index" "$child_path" "$MAX_CHILD_CONFIG_BYTES"
    extracted_patterns=$(awk '
        /^[[:space:]]*paths[[:space:]]*:[[:space:]]*\[/ {
            line=$0
            sub("^[^[]*\\[", "", line)
            sub("\\].*$", "", line)
            count=split(line, values, ",")
            for (index=1; index<=count; index++) {
                value=values[index]
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
    while IFS= read -r pattern && [ "$index" -lt "$MAX_SOURCES" ]; do
        case "$pattern" in
            /*) ;;
            *) continue ;;
        esac
        for source_path in $pattern; do
            [ "$index" -lt "$MAX_SOURCES" ] || break
            [ -e "$source_path" ] || continue
            metadata=$(stat -Lc '%d %i %s %Y' "$source_path" 2>/dev/null)
            [ -n "$metadata" ] || continue
            device=$(printf '%s\n' "$metadata" | awk '{print $1}')
            inode=$(printf '%s\n' "$metadata" | awk '{print $2}')
            size_bytes=$(printf '%s\n' "$metadata" | awk '{print $3}')
            mtime_epoch=$(printf '%s\n' "$metadata" | awk '{print $4}')
            emit_kv "$phase.source.$index.pattern" "$pattern"
            emit_kv "$phase.source.$index.path" "$source_path"
            emit_kv "$phase.source.$index.resolved_path" "$(readlink -f "$source_path" 2>/dev/null)"
            if [ -L "$source_path" ]; then
                emit_kv "$phase.source.$index.symlink" "true"
            fi
            emit_kv "$phase.source.$index.device" "$device"
            emit_kv "$phase.source.$index.inode" "$inode"
            emit_kv "$phase.source.$index.size_bytes" "$size_bytes"
            emit_kv "$phase.source.$index.mtime_epoch" "$mtime_epoch"
            if [ "$phase" = "second" ] && [ -f "$source_path" ]; then
                emit_sample_stream "$phase.source.$index.sample" "$source_path"
            fi
            index=$((index + 1))
        done
    done <<EOF
$source_patterns
EOF
    emit_kv "$phase.source_count" "$index"
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
snapshot_sources "second"
snapshot_registrar "second"

collector_file_log_count=0
case "$path_logs" in
    /*)
        if [ -d "$path_logs" ]; then
            collector_file_logs=$(find "$path_logs" -maxdepth 1 -type f \( -name '*.log' -o -name '*.log.*' \) 2>/dev/null | sort | tail -n 2)
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

emit_kv "completed" "true"
exit 0
