#### 1. 根据配置自动拉取一天以内的腾讯云告警历史

#### 2.返回数据格式
腾讯云回调地址： www.webhook.com

配置告警回调方法、： https://cloud.tencent.com/document/product/248/50409
```json
    {"Histories": [
            {
                "AlarmId": "c36494f8-ae38-45cb-8089-e14006bcfc67",
                "MonitorType": "MT_QCE",
                "Namespace": "cvm_device",
                "AlarmObject": "127.0.0.1 (内) | 服务器01 | 基础网络",
                "Content": "CPU利用率 >0%",
                "FirstOccurTime": 1603117860,
                "LastOccurTime": 1603162964,
                "AlarmStatus": "ALARM",
                "PolicyId": "policy-abc01",
                "PolicyName": "CVM告警策略1",
                "VPC": "0",
                "ProjectId": 0,
                "ProjectName": "默认项目",
                "InstanceGroup": [
                    {
                        "Id": 430,
                        "Name": "example-instance-group"
                    }
                ],
                "ReceiverUids": [],
                "ReceiverGroups": [
                    1544
                ],
                "NoticeWays": [
                    "SMS",
                    "EMAIL",
                    "WECHAT"
                ],
                "EventId": 0,
                "AlarmType": "METRIC",
                "OriginId": "1278441",
                "Region": "gz",
                "PolicyExists": 1,
                "MetricsInfo": [
                    {
                        "QceNamespace": "qce/cvm",
                        "MetricName": "CpuUsage",
                        "Period": 60,
                        "Value": "86.5",
                        "Description": "CPU利用率"
                    }
                ],
                "Dimensions": null
            }]
  }
```