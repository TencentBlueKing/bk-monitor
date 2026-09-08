#!/bin/bash

export LC_ALL=C
export LANG=C

source ./parse_yaml.sh
create_variables etc/env.yaml
pid=$(cat ${BK_PLUGIN_PID_PATH})
kill -9 ${pid} 2>/dev/null 1>&1
exit 0
