#!/usr/bin/env bash
source ${CTRL_DIR}/config.env
a=""
for ip in ${INFLUXDB_IP[@]}
do
a=${a}"$ip""\n"
done
echo -e ${a}