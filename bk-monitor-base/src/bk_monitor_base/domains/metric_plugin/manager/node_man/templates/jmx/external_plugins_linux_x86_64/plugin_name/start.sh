#!/bin/bash

export LC_ALL=C
export LANG=C

source ./parse_yaml.sh
create_variables etc/env.yaml
mkdir -p $(dirname ${BK_PLUGIN_PID_PATH})
mkdir -p ${BK_PLUGIN_LOG_PATH}

log_filepath=${BK_PLUGIN_LOG_PATH}/{{ plugin_id }}.log

# 设置 SSL_ENABLED 默认值为 false
SSL_ENABLED=${SSL_ENABLED:-false}

if [ ${SSL_ENABLED} = true ]; then
  java_args=(
    "-Djavax.net.ssl.trustStore=${SSL_TRUST_STORE}"
    "-Djavax.net.ssl.trustStorePassword=${SSL_TRUST_STORE_PASSWORD}"
    "-Djavax.net.ssl.keyStore=${SSL_KEY_STORE}"
    "-Djavax.net.ssl.keyStorePassword=${SSL_KEY_STORE_PASSWORD}"
    "-jar"
    "jmx_exporter.jar"
    "${BK_LISTEN_HOST}:${BK_LISTEN_PORT}"
    "${BK_CONFIG_PATH}"
  )
  java "${java_args[@]}" > "${log_filepath}" 2>&1 &
else
  java -jar jmx_exporter.jar ${BK_LISTEN_HOST}:${BK_LISTEN_PORT} ${BK_CONFIG_PATH} > ${log_filepath} 2>&1 &
fi

pid=$!

echo "process tried to start, pid: ${pid}"

echo "checking process status..."
# wait process start successfully
sleep 2s

ps aux | awk '{print $2}'| grep -w ${pid}

ret=$?

if [ ${ret} -ne 0 ]; then
  echo "process exited too quickly, pid: ${pid}"
  echo "process log: "
  cat ${log_filepath}
  exit 1
else
  echo "process started successfully, pid: ${pid}"
  echo ${pid} > ${BK_PLUGIN_PID_PATH}
  exit 0
fi
