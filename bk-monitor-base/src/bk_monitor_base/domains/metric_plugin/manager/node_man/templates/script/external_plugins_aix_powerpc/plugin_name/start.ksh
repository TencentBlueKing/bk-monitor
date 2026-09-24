#!/bin/ksh

export LC_ALL=C
export LANG=C

cd `dirname $0`
. ./parse_yaml.ksh
create_variables etc/env.yaml

./{{ collector_json.aix.filename }} ${BK_CMD_ARGS}
