### 功能描述

预解析 RecordingRule 配置

`POST /app/recording_rule/preview_config/`

调用查询服务解析 MetricQL、来源 VMRT 和 BKBase 来源资源信息。不会写入规则、版本、事件、输出资源或下发 Flow。编辑预览可传 id，以排除已有规则自身的输出；名称不可修改。

返回 data.config（规范化单 group）和 data.records。每条结果包含 record、metricql、labels、interval、src_vm_table_ids、src_result_table_configs。解析失败会定位到 config.rules[index]。

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| bk_biz_id | integer | 否 | 业务 ID，与 space_uid 至少提供一个 |
| space_uid | string | 否 | 空间 UID，与 bk_biz_id 至少提供一个 |
| config | object/string | 是 | AsCode 单 group 对象或 YAML 字符串，不含外层 groups |
| id | integer | 否 | 规则组 ID，必须属于当前租户及指定空间且未软删除 |

bk_biz_id 与 space_uid 至少提供一个。租户取认证上下文，配置内容中不填写租户或空间字段。ID 必须属于当前租户、指定空间且未软删除。

### 请求示例

```json
{
  "bk_biz_id": 2,
  "config": {
    "name": "cpu_summary",
    "interval": "1min",
    "labels": {
      "env": "prod"
    },
    "bkmonitor": {
      "description": "CPU 平均使用率",
      "auto_refresh": false,
      "desired_status": "running"
    },
    "rules": [
      {
        "record": "cpu_usage_avg",
        "expr": "avg(system_cpu_usage)"
      }
    ]
  }
}
```

### 返回结果

沿用网关标准的 result、code、message、data 响应结构。请求处理成功不等于下发成功；有 execution 的接口需同时检查 execution.succeeded。
