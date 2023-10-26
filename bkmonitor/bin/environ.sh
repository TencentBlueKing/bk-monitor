#!/bin/bash


ENVIRONMENT="development"

if [ 0"$BKAPP_DEPLOY_PLATFORM" = "0" ]; then
    PLATFORM="tencent"
else
    PLATFORM="$BKAPP_DEPLOY_PLATFORM"
fi

export DJANGO_CONF_MODULE="conf.worker.${ENVIRONMENT}.${PLATFORM}"
