# bkmonitorbeat_test.conf
output.console:
logging.level: debug
bkmonitorbeat:
  node_id: 0
  ip: 127.0.0.1
  bk_cloud_id: 0
  bk_biz_id: 0
  clean_up_timeout: 1s
  event_buffer_size: 10
  mode: check
  heart_beat:
    global_dataid: 1100001
    child_dataid: 1100002
    period: 60s
  http_task:
    dataid: {{ data_id | default(1011, true) }}
    max_buffer_size: {{ max_buffer_size | default(10240, true) }}
    max_timeout: {{ max_timeout | default("30s", true) }}
    min_period: {{ min_period | default("3s", true) }}
    tasks: {% for task in tasks %}
      - task_id: {{ task.task_id }}
        bk_biz_id: {{ task.bk_biz_id }}
        period: {{ task.period }}
        available_duration: {{ task.available_duration }}
        insecure_skip_verify: {{ task.insecure_skip_verify | lower }}
        disable_keep_alives: {{ task.disable_keep_alives | lower }}
        timeout: {{ task.timeout | default("3s", true) }}
        dns_check_mode: {{ task.dns_check_mode | default("single", true) }}
        target_ip_type: {{ task.target_ip_type | default(0, true) }}
        steps: {% for step in task.steps %}
          - url_list: {% for url in step.url_list %}
            - {{ url }}{% endfor %}
            method: {{ step.method }}
            headers: {% for key,value in step.headers.items() %}
                {{ key }}: {{ value }}
            {% endfor %}
            available_duration: {{ step.available_duration }}
            request: {{ step.request or '' }}
            request_format: {{ step.request_format | default("raw", true) }}
            response: {{ step.response or '' }}
            response_format: {{ step.response_format | default("eq", true) }}
            response_code: {{ step.response_code }}{% endfor %}{% endfor %}
