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
  script_task:
    dataid: 0
    max_timeout: 300s
    tasks:
      - bk_biz_id: 0
        {% raw %}command: {{ control_info.setup_path }}/{{ control_info.start_cmd}}{% endraw %}
        dataid: 0
        period: {% raw %}{{ period }}s{% endraw %}
        task_id: 0
        timeout: 300s
        user_env: {}
