#!/bin/bash
BASE_DIR=`dirname "$0"`
CHANGE_FILES=$@

# 如果未找到 exit = 1
check_ip=$(grep "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)" -aEinor ${CHANGE_FILES[*]} | grep -v -f "$BASE_DIR/ip_white_list.dat" )

if [ -z "${check_ip}" ];then
    exit 0
else
	for tmp in ${check_ip};do
        echo "invalid:"${tmp}
	done
    exit 1
fi

exit 0