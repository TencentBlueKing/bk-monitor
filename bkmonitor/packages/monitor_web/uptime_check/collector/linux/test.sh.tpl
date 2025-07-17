#!/bin/bash
echo "{{ divide_symbol | safe }}"
mkdir -p {{ download_path | safe }}

cat << 'EOF' > {{ test_config_file_path }}
{{ test_config_yml | safe }}
EOF

cd {{ setup_path }}
./bkmonitorbeat -T  -c {{ test_config_file_path }}
code=$?

# rm -f {{ test_config_file_path }}  >/dev/null 2>&1

exit $code
