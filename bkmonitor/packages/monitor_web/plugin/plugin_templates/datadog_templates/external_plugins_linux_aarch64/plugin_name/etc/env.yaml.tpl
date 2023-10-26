PYTHONIOENCODING: utf-8
{% verbatim %}PYTHON_PATH: {{ python_path | default('python', true) }}
GSE_AGENT_HOME: {{ control_info.gse_agent_home }}
BK_PLUGIN_LOG_PATH: {{ control_info.log_path }}
BK_PLUGIN_PID_PATH: {{ control_info.pid_path }}
BK_PLUGIN_DATA_PATH: {{ control_info.data_path }}{% endverbatim %}
DATADOG_CHECK_NAME: {{ collector_json.datadog_check_name }}

{% for config_param in config_json %}
{% if config_param.mode == "env" %}
{{ config_param.name }}: {{ "{" }}{{ "{" }} {{ config_param.name }} {{ "}" }}{{ "}" }}
{% endif %}
{% endfor %}
