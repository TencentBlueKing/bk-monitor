{{ collector_json.config_yaml | safe }}
  version: {{ collector_json.snmp_version }}
  auth:
    community: {% raw %}"{{ community }}"{% endraw %}
    security_level: {% raw %}"{{ security_level }}"{% endraw %}
    username: {% raw %}"{{ username }}"{% endraw %}
    password: {% raw %}"{{ password }}"{% endraw %}
    auth_protocol: {% raw %}"{{ auth_protocol }}"{% endraw %}
    priv_protocol: {% raw %}"{{ priv_protocol }}"{% endraw %}
    priv_password: {% raw %}"{{ priv_password }}"{% endraw %}
    context_name: {% raw %}"{{ context_name }}"{% endraw %}