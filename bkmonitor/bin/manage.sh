#!/bin/bash
SCRIPT_DIR=`dirname $0`
cd $SCRIPT_DIR && cd .. || exit 1

source bin/environ.sh

############
# MainLoop #
############

echo "[ INFO ] DJANGO_CONF_MODULE: \"$DJANGO_CONF_MODULE\"" >&2

${PYTHON_BIN:-python} manage.py $@
