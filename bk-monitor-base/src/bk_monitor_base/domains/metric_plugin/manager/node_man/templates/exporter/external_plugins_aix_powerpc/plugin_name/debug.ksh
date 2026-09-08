#!/bin/ksh

export LC_ALL=C
export LANG=C

. ./parse_yaml.ksh
create_variables etc/env.yaml

./start.ksh && ${GSE_AGENT_HOME}/plugins/bin/bkmonitorbeat -c etc/bkmonitorbeat_debug.yaml
