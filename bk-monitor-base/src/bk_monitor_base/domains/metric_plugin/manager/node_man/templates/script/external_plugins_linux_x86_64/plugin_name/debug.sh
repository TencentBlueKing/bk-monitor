#!/bin/bash

export LC_ALL=C
export LANG=C

source ./parse_yaml.sh
create_variables etc/env.yaml

mkdir -p $BK_PLUGIN_PID_PATH

${GSE_AGENT_HOME}/plugins/bin/bkmonitorbeat -c etc/bkmonitorbeat_debug.yaml