#!/bin/bash

export LC_ALL=C
export LANG=C

cd `dirname $0`
source ./parse_yaml.sh
create_variables etc/env.yaml

$PYTHON_PATH main.py $DATADOG_CHECK_NAME -c etc/conf.yaml --log-path $BK_PLUGIN_LOG_PATH
