output.console:
logging.level: debug
logging.to_files: true
logging.files:
{% raw %}
path.pid: {{ control_info.setup_path }}/pid
path.data: {{ control_info.data_path }}
seccomp.enabled: false
{% endraw %}

bkmonitorbeat:
  node_id: 0
  ip: 127.0.0.1
  bk_cloud_id: 0
  bk_biz_id: 0
  clean_up_timeout: 1s
  event_buffer_size: 10
  mode: daemon
  keep_one_dimension: true
  max_execution_time: 5m
  heart_beat:
    global_dataid: 101178
    child_dataid: 111110
    period: 60s
  metricbeat_task:
    dataid: 0
    max_buffer_size: 10240
    max_timeout: 300s
    min_period: 3s
    tasks:
      - task_id: 0
        bk_biz_id: 0
        timeout: 300s
        period: {% raw %}{{ period }}s{% endraw %}
        module:
            module: prometheus
            metricsets: ["collector"]
            enabled: true
            {% raw %}
            hosts: ["{{ metric_url }}"]
            {% endraw %}
            metrics_path: ''
            namespace: {{  plugin_id }}
        {% raw %}
        {% if labels %}labels:
        {% for label in labels %}{% for key, value in label.items() %}{{ "-" if loop.first else " "  }} {{ key }}: "{{ value }}"
        {% endfor %}{% endfor %}
        {% endif %}
        {% endraw %}
