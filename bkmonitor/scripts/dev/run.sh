#!/bin/bash

mkdir -p /app/logs/ /app/run/

cd /app/code/

pip install -r requirements.txt -i https://mirrors.tencent.com/pypi/simple

supervisord -n -c /app/etc/supervisord.conf
