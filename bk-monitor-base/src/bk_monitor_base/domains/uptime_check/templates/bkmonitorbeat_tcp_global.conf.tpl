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
  tcp_task:
    dataid: {{ data_id | default(1009, true) }}
    max_buffer_size: {{ max_buffer_size | default(10240, true) }}
    max_timeout: {{ max_timeout | default("30s", true) }}
    min_period: {{ min_period | default("3s", true) }}
    tasks: {% for task in tasks %}
      - task_id: {{ task.task_id }}
        bk_biz_id: {{ task.bk_biz_id }}
        period: {{ task.period }}
        timeout: {{ task.timeout | default("3s", true) }}
        dns_check_mode: {{ task.dns_check_mode | default("single", true) }}
        target_ip_type: {{ task.target_ip_type | default(0, true) }}
        target_host_list: {% for target_host in task.target_host_list %}
        - {{ target_host }}{% endfor %}
        target_port: {{ task.target_port }}
        available_duration: {{ task.available_duration }}
        request: {{ task.request or ''  }}
        request_format: {{ task.request_format | default("raw", true) }}
        response: {{ task.response or ''  }}
        response_format: {{ task.response_format | default("eq", true) }}{% endfor %}
