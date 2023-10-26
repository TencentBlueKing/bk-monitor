#!/usr/bin/env bash
source ${CTRL_DIR}/config.env
a=""
for ip in ${BKMONITOR_INFLUXDB_PROXY_IP[@]}
do
a=${a}"$ip""\n"
done
echo -e ${a}