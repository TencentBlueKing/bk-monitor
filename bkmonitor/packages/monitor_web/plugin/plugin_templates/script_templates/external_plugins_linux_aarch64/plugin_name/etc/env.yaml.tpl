{% verbatim %}GSE_AGENT_HOME: {{ control_info.gse_agent_home }}
BK_PLUGIN_LOG_PATH: {{ control_info.log_path }}
BK_PLUGIN_PID_PATH: {{ control_info.pid_path }}{% endverbatim %}

{% for config_param in config_json %}
{% if config_param.mode == "env" %}
{{ config_param.name }}: {{ "{" }}{{ "{" }} {{ config_param.name }} {{ "}" }}{{ "}" }}
{% endif %}
{% endfor %}

BK_CMD_ARGS: {% verbatim %}{{ cmd_args }}{% endverbatim %}