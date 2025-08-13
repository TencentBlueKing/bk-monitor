#!/bin/bash
#         USAGE: ./get_top_proc_cpu.sh <cpu|mem> <number>
#
#   DESCRIPTION: 输出系统当前占用资源（cpu、内存）最多的TopN进程

fields="pcpu,pmem,comm"

usage() {
    cat <<'EOF'
    get_top_proc_in_oneline.sh <cpu|mem> <number of top proc>
EOF
    exit 1
}

join() {
    local IFS="$1"
    shift; echo "$*"
}

if (( $# < 1 )) || (( $# > 2 )) ; then
    usage
fi

case $1 in
    cpu) sort_field=pcpu ;;
    mem) sort_field=rss ;;
    *) usage ;;
esac

if [[ $# -eq 2 ]]; then
    top_n=$2
else
    top_n=6
fi

return_cpu=$(ps -eo "$fields" --sort=-"$sort_field" | head -$(( top_n + 1 )) | awk 'NR==1 { gsub(/%/,"") } {printf "%s \n", $0 }')

echo "${return_cpu}"
