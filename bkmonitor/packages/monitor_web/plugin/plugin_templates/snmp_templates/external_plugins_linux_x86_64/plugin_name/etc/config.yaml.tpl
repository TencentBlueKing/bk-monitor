{{ collector_json.config_yaml | safe }}
  version: {{ collector_json.snmp_version }}
  auth:
    community: {% verbatim %}"{{ community }}"{% endverbatim %}
    security_level: {% verbatim %}"{{ security_level }}"{% endverbatim %}
    username: {% verbatim %}"{{ username }}"{% endverbatim %}
    password: {% verbatim %}"{{ password }}"{% endverbatim %}
    auth_protocol: {% verbatim %}"{{ auth_protocol }}"{% endverbatim %}
    priv_protocol: {% verbatim %}"{{ priv_protocol }}"{% endverbatim %}
    priv_password: {% verbatim %}"{{ priv_password }}"{% endverbatim %}
    context_name: {% verbatim %}"{{ context_name }}"{% endverbatim %}