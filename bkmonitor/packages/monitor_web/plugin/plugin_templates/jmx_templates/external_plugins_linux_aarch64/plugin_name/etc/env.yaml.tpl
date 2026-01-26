{% verbatim %}GSE_AGENT_HOME: {{ control_info.gse_agent_home }}
BK_PLUGIN_LOG_PATH: {{ control_info.log_path }}
BK_PLUGIN_PID_PATH: {{ control_info.pid_path }}
BK_CONFIG_PATH: etc/config.yaml

BK_LISTEN_HOST: {{ host }}
BK_LISTEN_PORT: {{ port }}{% endverbatim %}