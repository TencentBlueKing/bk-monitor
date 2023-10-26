#!/bin/bash
source ~/.bashrc
SCRIPT_DIR=`dirname $0`
cd $SCRIPT_DIR && cd .. || exit 1

workon bkmonitorv3-monitor

MODE=${1:-stable}

if [ "$MODE" = lite ]; then
  cat ../../etc/supervisor-bkmonitorv3-monitor-lite.conf > ../../etc/supervisor-bkmonitorv3-monitor.conf
else
  MODE=stable
  cat ../../etc/supervisor-bkmonitorv3-monitor-stable.conf > ../../etc/upervisor-bkmonitorv3-monitor.conf
fi

supervisorctl -c ../../etc/supervisor-bkmonitorv3-monitor.conf reload

echo "switch deploy mode: [$MODE] reloading..."