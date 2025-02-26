#!/bin/bash

set -e

/usr/sbin/mysqld --user=mysql &

redis-server &

exec "$@"
