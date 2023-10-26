#!/bin/bash

SCRIPT_DIR=`dirname $0`
cd $SCRIPT_DIR && cd .. || exit 1

source bin/environ.sh

export DJANGO_SETTINGS_MODULE=settings
export C_FORCE_ROOT=true


