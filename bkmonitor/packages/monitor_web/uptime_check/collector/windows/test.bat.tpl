@echo off
echo {{ divide_symbol | safe }}
if not exist {{ download_path | safe }} md {{ download_path | safe }}

(
{% for line in test_config_yml.splitlines %}
{% if line %}echo {{ line | safe }}{% endif %}{% endfor %}
) >{{ test_config_file_path | safe }}

cd {{ setup_path }}

bkmonitorbeat.exe -T  -c {{ test_config_file_path }} || exit 1