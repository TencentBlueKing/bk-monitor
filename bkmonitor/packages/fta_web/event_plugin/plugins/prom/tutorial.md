1. 点击安装并填写对应的安装参数，本插件支持告警字段清洗规则配置，语法可参考 [jmespath](https://jmespath.org/tutorial.html)

2. 拉取Prometheus的数据格式如下
    ```json
    {
      "status": "success",
      "data": {
        "alerts": [
          {
            "labels": {
              "alertname": "hostCpuUsageAlert",
              "instance": "localhost:10001",
              "severity": "1",
              "target_type": "server"
            },
            "annotations": {
              "description": "localhost:10001 CPU usage above 1% (current value: 0.059166666664774915)",
              "summary": "Instance localhost:10001 CPU usgae high"
            },
            "state": "firing",
            "activeAt": "2023-02-03T08:29:53.485388894Z",
            "value": "5.9166666664774915e-02"
          },
          {
            "labels": {
              "alertname": "hostMemUsageAlert",
              "instance": "localhost:10001",
              "job": "node_exporter",
              "node": "127.0.0.1",
              "severity": "2",
              "target_type": "db"
            },
            "annotations": {
              "description": "localhost:10001 MEM usage above 1% (current value: 0.9329973762988476)",
              "summary": "Instance localhost:10001 MEM usgae high"
            },
            "state": "firing",
            "activeAt": "2023-02-03T08:29:53.485388894Z",
            "value": "9.329973762988476e-01"
          }
        ]
      }
    }
    ```
3. 安装完成之后，系统自动拉取Prometheus的告警记录并且推送到蓝鲸监控告警中心
4. 完成
