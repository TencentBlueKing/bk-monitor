#!/bin/bash

SCRIPT_DIR=`dirname $0`
cd $SCRIPT_DIR && cd .. || exit 1

source bin/environ.sh


API_DJANGO_CONF_MODULE=`echo $DJANGO_CONF_MODULE|sed 's/worker/api/'`
export DJANGO_CONF_MODULE=${API_DJANGO_CONF_MODULE}

${PYTHON_BIN:-python} manage.py $@
