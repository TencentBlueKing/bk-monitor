#!/bin/bash

export LC_ALL=C
export LANG=C

if [ "$(dirname ${BASH_SOURCE})" != "." ];then
    cd ${BASH_SOURCE%/*}
fi

source ./parse_yaml.sh
create_variables etc/env.yaml

_status_linux_proc () {
    local proc="$1"
    local pids
    local __pids=()

    pids=$(ps xao pid,ppid,command | awk -v PROG="./$proc" '$3 == PROG { print $1 }')
    for pid in ${pids[@]} ; do
        abs_path=$(readlink -f /proc/$pid/exe)
        if [ "${abs_path%/$proc*}" == "${PWD}" ] ; then
            __pids=(${__pids} ${pid})
        fi
    done
    pids=(${__pids[@]})

    echo -n ${pids[@]}

    [ ${#pids[@]} -ne 0 ]
}


_stop () {
    kill -9 $(_status_linux_proc $1) 2>/dev/null
}

_status () {
    _status_linux_proc $1
}

plugin_id="{{ plugin_id }}"

echo "stop ${plugin_id} ..."
_stop "${plugin_id}"

if ! _status "${plugin_id}"; then
    echo "Done"
    exit 0
else
    echo "Fail"
    exit 1
fi
