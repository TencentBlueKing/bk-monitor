{% verbatim %}GSE_AGENT_HOME: {{ control_info.gse_agent_home }}
BK_PLUGIN_LOG_PATH: {{ control_info.log_path }}
BK_PLUGIN_PID_PATH: {{ control_info.pid_path }}
BK_CONFIG_PATH: etc/config.yaml

BK_LISTEN_HOST: {{ host }}
BK_LISTEN_PORT: {{ port }}
SSL_ENABLED: {{ ssl_enabled }}
SSL_TRUST_STORE: {{ ssl_trust_store }}
SSL_TRUST_STORE_PASSWORD: {{ ssl_trust_store_password }}
SSL_KEY_STORE: {{ ssl_key_store }}
SSL_KEY_STORE_PASSWORD: {{ ssl_key_store_password }}{% endverbatim %}