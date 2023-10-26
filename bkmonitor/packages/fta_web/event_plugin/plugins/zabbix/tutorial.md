1. 下载推送脚本

    下载对应版本的脚本至 zabbix 的 alertscripts 目录（一般在 /usr/lib/zabbix/）

    <a href="./asset/zabbix_fta_alarm_v3.py" download="zabbix_fta_alarm.py">V3.x</a>
    <a href="./asset/zabbix_fta_alarm_v4.py" download="zabbix_fta_alarm.py">V4.x</a>
    <a href="./asset/zabbix_fta_alarm_v5.py" download="zabbix_fta_alarm.py">V5.x</a>

2. 初始化告警配置

    在alertscripts目录下执行下载的文件zabbix_fta_alarm.py（参数输入API URL、Zabbix管理员账号、密码，会自动创建Action、 Script等）

    ```
   chmod a+x zabbix_fta_alarm.py
   chown -R zabbix:zabbix zabbix_fta_alarm.py
   ./zabbix_fta_alarm.py --init http://localhost/zabbix/api_jsonrpc.php Admin zabbix
   ```

3. 完成
