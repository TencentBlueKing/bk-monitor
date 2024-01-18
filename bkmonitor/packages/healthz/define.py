# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2021 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
# deprecated in 3.8.x

import copy
import json

from django.db.utils import DatabaseError

from constants.action import ActionPluginType, ConvergeType

backend_collector_nodes = (
    ("gse_data", "Gse_data", "Gse_data状态"),
    ("pre_kafka", "Pre_kafka", "Pre_kafka状态"),
    ("etl", "Etl", "Etl状态"),
    ("tsdb_proxy", "Tsdb_proxy", "Tsdb_proxy状态"),
    ("influxdb", "Influxdb", "Influxdb状态"),
)

backend_component_nodes = (
    ("redis", "Redis", "Redis状态"),
    ("kafka", "Kafka", "Kafkaa状态"),
    ("mysql", "Mysql", "Mysql状态"),
    ("consul", "Consul", "Consul状态"),
    ("system", "Server", "Server状态"),
    ("supervisor", "Supervisor", "Supervisor状态"),
    ("elasticsearch", "Elasticsearch", "Elasticsearch状态"),
)

saas_component_nodes = (("rabbitmq", "RabbitMQ", "RabbitMQ状态"),)

backend_process_nodes = (
    ("data_access", "指标获取", "指标获取状态"),
    ("nodata_alarm", "无数据检测", "无数据检测状态"),
    ("detect", "告警检测", "告警检测状态"),
    ("poll_alarm", "告警拉取", "告警拉取状态"),
    ("match_alarm", "告警匹配", "告警匹配状态"),
    ("converge_alarm", "收敛", "收敛状态"),
    ("process_alarm", "告警处理", "告警处理状态"),
    ("recovery_alarm", "告警恢复", "告警恢复状态"),
)

saas_process_nodes = (("bk_monitor_web", "监控web服务", "监控web服务状态"),)

nodes = backend_component_nodes + saas_component_nodes + backend_process_nodes + saas_process_nodes

backend_collector_nodes_metrics = [
    {
        "node_name": node[0],
        "description": node[2],
        "category": node[0],
        "collect_metric": "%s.status" % node[0],
        "collect_args": "",
        "collect_interval": 300,
        "collect_type": "backend",
        "metric_alias": "%s.status" % node[0],
        "solution": "",
    }
    for node in backend_collector_nodes
    if node[0] not in ["pre_kafka", "etl", "tsdb_proxy"]
]

# pre_kafka
backend_collector_nodes_metrics.append(
    {
        "node_name": "pre_kafka",
        "description": "清洗前kafka状态",
        "category": "pre_kafka",
        "collect_metric": "pre_kafka.status",
        "collect_args": "",
        "collect_interval": 300,
        "collect_type": "backend",
        "metric_alias": "pre_kafka.status",
        "solution": "",
    }
)

backend_collector_nodes_metrics.append(
    {
        "node_name": "pre_kafka",
        "description": "清洗前kafka副本配置",
        "category": "pre_kafka",
        "collect_metric": "pre_kafka.config",
        "collect_args": "",
        "collect_interval": 300,
        "collect_type": "backend",
        "metric_alias": "pre_kafka.config",
        "solution": '[{"reason": "清洗前kafka副本配置出错","solution": "查看kafka副本配置是否正确"}]',
    }
)

backend_collector_nodes_metrics.append(
    {
        "node_name": "pre_kafka",
        "description": "清洗前kafka的topic数据",
        "category": "pre_kafka",
        "collect_metric": "pre_kafka.topic_data",
        "collect_args": "",
        "collect_interval": 300,
        "collect_type": "backend",
        "metric_alias": "pre_kafka.topic_data",
        "solution": '[{"reason": "清洗前kafka的topic数据出错","solution": "查看kafka的topic数据是否正确"}]',
    }
)

backend_component_nodes_metrics = [
    {
        "node_name": node[0],
        "description": node[2],
        "category": node[0],
        "collect_metric": "%s.status" % node[0],
        "collect_args": "",
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "%s.status" % node[0],
        "solution": "",
    }
    for node in backend_component_nodes
]


graph_exporter_node_metric = {
    "node_name": "graph_exporter",
    "description": "图片导出服务状态",
    "category": "graph_exporter",
    "collect_metric": "graph_exporter.status",
    "collect_args": "",
    "collect_interval": 60,
    "collect_type": "backend",
    "metric_alias": "graph_exporter.status",
    "solution": '[{"reason": "graph_exporter库依赖的phantomjs无法启动", '
    '"solution": "监控后台执行：yum install libXext libXrender fontconfig libfontconfig.so.1 -y"}]',
}


backend_component_nodes_metrics.append(graph_exporter_node_metric)


saas_component_nodes_metrics = [
    {
        "node_name": node[0],
        "description": node[2],
        "category": node[0],
        "collect_metric": "%s.status" % node[0],
        "collect_args": "",
        "collect_interval": 60,
        "collect_type": "saas",
        "metric_alias": "%s.status" % node[0],
        "solution": "",
    }
    for node in saas_component_nodes
]

saas_process_nodes_metrics = [
    {
        "node_name": node[0],
        "description": node[2],
        "category": node[0],
        "collect_metric": "%s.status" % node[0],
        "collect_args": '{"name": "%s"}' % node[0],
        "collect_interval": 60,
        "collect_type": "saas",
        "metric_alias": "%s.status" % node[0],
        "solution": "",
    }
    for node in saas_process_nodes
]

default_metrics = (
    backend_component_nodes_metrics
    + saas_component_nodes_metrics
    + saas_process_nodes_metrics
    + backend_collector_nodes_metrics
)

redis_metrics = [
    {
        "category": "redis",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Redis 状态",
        "collect_metric": "redis.status",
        "solution": "",
        "node_name": "redis",
        "metric_alias": "redis.status",
        "collect_args": '{"backend":"cache"}',
    },
    {
        "category": "redis",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Redis 可读状态",
        "collect_metric": "redis.read.status",
        "solution": "",
        "node_name": "redis",
        "metric_alias": "redis.read.status",
        "collect_args": '{"backend":"cache"}',
    },
    {
        "category": "redis",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Redis 可写状态",
        "collect_metric": "redis.write.status",
        "solution": "",
        "node_name": "redis",
        "metric_alias": "redis.write.status",
        "collect_args": '{"backend":"cache"}',
    },
    {
        "category": "redis",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Redis内存碎片使用率",
        "collect_metric": "redis.stats.mem_fragmentation_ratio",
        "solution": "",
        "node_name": "redis",
        "metric_alias": "redis.status.mem_fragmentation_ratio",
        "collect_args": "{}",
    },
]

elasticsearch_metrics = [
    {
        "category": "elasticsearch",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "集群状态",
        "collect_metric": "elasticsearch.status",
        "solution": '[{"reason": "集群状态: 集群处于不可用状态边缘或无法连接", "solution": "确保集群状态正常: 请运维及时检查处理",}]',
        "node_name": "elasticsearch",
        "metric_alias": "elasticsearch.status",
        "collect_args": "{}",
    },
    {
        "category": "elasticsearch",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "非正常index",
        "collect_metric": "elasticsearch.abnormal_index",
        "solution": "",
        "node_name": "elasticsearch",
        "metric_alias": "elasticsearch.abnormal_index",
        "collect_args": "{}",
    },
    {
        "category": "elasticsearch",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "集群shard数",
        "collect_metric": "elasticsearch.active_shards",
        "solution": "",
        "node_name": "elasticsearch",
        "metric_alias": "elasticsearch.active_shards",
        "collect_args": "{}",
    },
    {
        "category": "elasticsearch",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "集群shard可用性",
        "collect_metric": "elasticsearch.active_shards.percent",
        "solution": "",
        "node_name": "elasticsearch",
        "metric_alias": "elasticsearch.active_shards.percent",
        "collect_args": "{}",
    },
]

transfer_metrics = [
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "transfer状态",
        "collect_metric": "prometheus.status",
        "solution": "",
        "node_name": "transfer",
        "metric_alias": "transfer.status",
        "collect_args": '{"domain": "{{settings.TRANSFER_HOST}}",' '"port": "{{settings.TRANSFER_PORT}}"}',
    },
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "goroutine数量",
        "collect_metric": "prometheus.gauge",
        "solution": "",
        "node_name": "transfer",
        "metric_alias": "transfer.go_goroutines",
        "collect_args": '{"metric_name": "go_goroutines",'
        '"domain": "{{settings.TRANSFER_HOST}}",'
        '"port": "{{settings.TRANSFER_PORT}}",'
        '"allow_null": false}',
    },
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "系统线程数量",
        "collect_metric": "prometheus.gauge",
        "solution": "",
        "node_name": "transfer",
        "metric_alias": "transfer.go_threads",
        "collect_args": '{"metric_name": "go_threads",'
        '"domain": "{{settings.TRANSFER_HOST}}",'
        '"port": "{{settings.TRANSFER_PORT}}",'
        '"allow_null": false}',
    },
]

influxdb_proxy_metrics = [
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "influxdb_proxy启动状态",
        "collect_metric": "prometheus.status",
        "solution": "",
        "node_name": "influxdb_proxy",
        "metric_alias": "influxdb_proxy.status",
        "collect_args": '{"domain": "{{settings.INFLUXDB_HOST}}",' '"port": "{{settings.INFLUXDB_PORT}}"}',
    },
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Backend连接状态",
        "collect_metric": "prometheus.counter",
        "solution": "",
        "node_name": "influxdb_proxy",
        "metric_alias": "influxdb_proxy.backend_alive_status",
        "collect_args": '{"metric_name": "influxdb_proxy_backend_alive_status",'
        '"domain": "{{settings.INFLUXDB_HOST}}",'
        '"port": "{{settings.INFLUXDB_PORT}}",'
        '"allow_null": false}',
    },
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Kafka连接状态",
        "collect_metric": "prometheus.counter",
        "solution": "",
        "node_name": "influxdb_proxy",
        "metric_alias": "influxdb_proxy.kafka_alive_status",
        "collect_args": '{"metric_name": "influxdb_proxy_kafka_alive_status",'
        '"domain": "{{settings.INFLUXDB_HOST}}",'
        '"port": "{{settings.INFLUXDB_PORT}}",'
        '"allow_null": false}',
    },
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Consul连接状态",
        "collect_metric": "prometheus.counter",
        "solution": "",
        "node_name": "influxdb_proxy",
        "metric_alias": "influxdb_proxy.consul_alive_status",
        "collect_args": '{"metric_name": "influxdb_proxy_consul_alive_status",'
        '"domain": "{{settings.INFLUXDB_HOST}}",'
        '"port": "{{settings.INFLUXDB_PORT}}",'
        '"allow_null": false}',
    },
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "goroutine数量",
        "collect_metric": "prometheus.gauge",
        "solution": "",
        "node_name": "influxdb_proxy",
        "metric_alias": "influxdb_proxy.go_goroutines",
        "collect_args": '{"metric_name": "go_goroutines",'
        '"domain": "{{settings.INFLUXDB_HOST}}",'
        '"port": "{{settings.INFLUXDB_PORT}}",'
        '"allow_null": false}',
    },
    {
        "category": "prometheus",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "系统线程数量",
        "collect_metric": "prometheus.gauge",
        "solution": "",
        "node_name": "influxdb_proxy",
        "metric_alias": "influxdb_proxy.go_threads",
        "collect_args": '{"metric_name": "go_threads",'
        '"domain": "{{settings.INFLUXDB_HOST}}",'
        '"port": "{{settings.INFLUXDB_PORT}}",'
        '"allow_null": false}',
    },
]

kafka_metrics = [
    {
        "category": "kafka",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Kafka状态",
        "collect_metric": "kafka.status",
        "solution": "",
        "node_name": "kafka",
        "metric_alias": "kafka.status",
        "collect_args": "{}",
    },
    {
        "category": "kafka",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Kafka集群数",
        "collect_metric": "kafka.cluster.count",
        "solution": "",
        "node_name": "kafka",
        "metric_alias": "kafka.cluster.count",
        "collect_args": "{}",
    },
]

mysql_metrics = [
    {
        "category": "database",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "数据库状态",
        "collect_metric": "database.status",
        "solution": "",
        "node_name": "mysql",
        "metric_alias": "database.status",
        "collect_args": "{}",
    },
    {
        "category": "database",
        "collect_interval": 600,
        "collect_type": "backend",
        "description": "最后告警时间",
        "collect_metric": "database.model.alarm_instance.last_time",
        "solution": "",
        "node_name": "mysql",
        "metric_alias": "database.model.alarm_instance.last_time",
        "collect_args": "{}",
    },
]

consul_metrics = [
    {
        "category": "consul",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Consul 状态",
        "collect_metric": "consul.status",
        "solution": "",
        "node_name": "consul",
        "metric_alias": "consul.status",
        "collect_args": "{}",
    },
]

rabbitmq_metrics = []

celery_metrics = [
    {
        "category": "celery",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "celery beat 状态",
        "node_name": "celery",
        "metric_alias": "celery.beat.status",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "scheduler", "process_name": "celery_beat"}',
        "solution": "",
    },
    {
        "category": "celery",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "celery worker 任务执行测试",
        "collect_metric": "celery.execution.status",
        "solution": "",
        "node_name": "celery",
        "metric_alias": "celery.execution.status",
        "collect_args": '{"queues": ["celery_service","celery_cron","celery_action","celery_interval_action",'
        '"celery_image_exporter", "celery_api_cron", "celery_converge", "celery_action_cron", '
        '"celery_alert_builder", "celery_alert_manager", "celery_running_action", '
        '"celery_report_cron", "celery_long_task_cron", "celery_metadata_task"]}',
    },
    {
        "category": "celery",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "celery worker 进程状态",
        "collect_metric": "celery.process.status",
        "solution": "",
        "node_name": "celery",
        "metric_alias": "celery.process.status",
        "collect_args": '{"group_name": "scheduler", "process_name": ["celery_beat",'
        '"celery_worker_service", "celery_worker_cron", "celery_image_exporter", '
        '"celery_worker_api_cron", "celery_worker_action", "celery_worker_service_access_event", '
        '"celery_worker_report_cron", "celery_worker_alert", "celery_worker_fta_action", '
        '"celery_worker_converge", "celery_worker_action_cron", "celery_worker_long_task_cron", '
        '"celery_metadata_task_worker"]}',
    },
]

system_metrics = [
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "可用内存",
        "collect_metric": "system.mem.available",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.mem.available",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "CPU核数",
        "collect_metric": "system.cpu.count",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.cpu.count",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "磁盘使用量",
        "collect_metric": "system.disk.used",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.disk.used",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "总内存",
        "collect_metric": "system.mem.total",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.mem.total",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "磁盘使用率",
        "collect_metric": "system.disk.usage",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.disk.usage",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "应用内存使用率",
        "collect_metric": "system.mem.process.usage",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.mem.process.usage",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "磁盘空闲量",
        "collect_metric": "system.disk.free",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.disk.free",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "系统状态",
        "collect_metric": "system.status",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.status",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "空闲内存",
        "collect_metric": "system.mem.free",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.mem.free",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "已用内存",
        "collect_metric": "system.mem.used",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.mem.used",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "磁盘总量",
        "collect_metric": "system.disk.total",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.disk.total",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "磁盘IO使用率",
        "collect_metric": "system.disk.ioutil",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.disk.ioutil",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "内存使用率",
        "collect_metric": "system.mem.usage",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.mem.usage",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "CPU使用率",
        "collect_metric": "system.cpu.percent",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.cpu.percent",
        "collect_args": "{}",
    },
    {
        "category": "system",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "各核CPU使用率",
        "collect_metric": "system.cpu.percent.all",
        "solution": "",
        "node_name": "system",
        "metric_alias": "system.cpu.percent.all",
        "collect_args": "{}",
    },
]

supervisor_metrics = [
    {
        "category": "supervisor",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Supervisor 自身状态",
        "collect_metric": "supervisor.status",
        "solution": "",
        "node_name": "supervisor",
        "metric_alias": "supervisor.status",
        "collect_args": "{}",
    },
    {
        "category": "supervisor",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Supervisor 进程状态",
        "collect_metric": "supervisor.process.status",
        "solution": "",
        "node_name": "supervisor",
        "metric_alias": "supervisor.process.status",
        "collect_args": "{}",
    },
    {
        "category": "supervisor",
        "collect_interval": 60,
        "collect_type": "backend",
        "description": "Supervisor 逃逸进程",
        "collect_metric": "supervisor.escaped",
        "solution": "",
        "node_name": "supervisor",
        "metric_alias": "supervisor.escaped",
        "collect_args": '{"python_bin": "{{settings.PYTHON_HOME}}"}',
    },
]

access_data_metrics = [
    {
        "node_name": "access_data",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "access_data"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "access_data.status",
        "solution": "",
    },
]

access_real_time_data_metrics = [
    {
        "node_name": "access_real_time_data",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "access_real_time_data"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "access_real_time_data.status",
        "solution": "",
    },
]

access_event_metrics = [
    {
        "node_name": "access_event",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "access_event"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "access_event.status",
        "solution": "",
    },
]

detect_metrics = [
    {
        "node_name": "detect",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "detect"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "detect.status",
        "solution": "",
    },
    {
        "node_name": "detect",
        "description": "待检测信号队列长度",
        "category": "redis",
        "collect_type": "backend",
        "collect_metric": "redis.method.llen",
        "collect_args": ("{% load math_filters %} " '{"backend": "cache", "name": "{%get_key key.DATA_SIGNAL_KEY%}"}'),
        "collect_interval": 60,
        "metric_alias": "detect.signal.length",
    },
]

trigger_metrics = [
    {
        "node_name": "trigger",
        "description": "待处理信号队列长度",
        "category": "redis",
        "collect_type": "backend",
        "collect_metric": "redis.method.llen",
        "collect_args": (
            "{% load math_filters %} " '{"backend": "cache", "name": "{%get_key key.ANOMALY_SIGNAL_KEY%}"}'
        ),
        "collect_interval": 60,
        "metric_alias": "trigger.anomaly.length",
    },
    {
        "node_name": "trigger",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "trigger"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "trigger.status",
        "solution": "",
    },
]

alert_builder_metrics = [
    {
        "node_name": "alert_builder",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "alert"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "alert.builder.status",
        "solution": "",
    },
    {
        "node_name": "alert_builder",
        "description": "待处理队列长度",
        "category": "kafka",
        "collect_type": "backend",
        "collect_metric": "kafka.queue.size",
        "collect_args": '{"topic": "{{ settings.MONITOR_EVENT_KAFKA_TOPIC }}"}',
        "collect_interval": 60,
        "metric_alias": "alert.builder.length",
    },
]

alert_manager_metrics = [
    {
        "node_name": "alert_manager",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "scheduler", "process_name": "celery_worker_alert"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "alert.manager.status",
        "solution": "",
    },
]


composite_metrics = [
    {
        "node_name": "composite",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "scheduler", "process_name": "celery_worker_composite"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "composite.status",
        "solution": "",
    },
    {
        "node_name": "composite",
        "description": "待处理信号队列长度",
        "category": "redis",
        "collect_type": "backend",
        "collect_metric": "redis.method.llen",
        "collect_args": (
            "{% load math_filters %} " '{"backend": "cache", "name": "{%get_key key.ALERT_ACTION_SIGNAL%}"}'
        ),
        "collect_interval": 60,
        "metric_alias": "composite.signal.length",
    },
]


converge_metrics = [
    {
        "node_name": "converge",
        "description": "生产进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "converge"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "converge.producer.status",
        "solution": "",
    },
    {
        "node_name": "converge",
        "description": "消费进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "scheduler", "process_name": "celery_worker_converge"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "converge.consumer.status",
        "solution": "",
    },
] + [
    {
        "node_name": "converge",
        "description": "待收敛队列长度[{}]".format(converge_type),
        "category": "redis",
        "collect_type": "backend",
        "collect_metric": "redis.method.llen",
        "collect_args": (
            "{% load math_filters %}"
            + '{"backend": "cache", "name": "{%get_key key.CONVERGE_LIST_KEY converge_type="'
            + converge_type
            + '"%}"}'
        ),
        "collect_interval": 60,
        "metric_alias": f"converge.{converge_type}.length",
    }
    for converge_type in [ConvergeType.ACTION, ConvergeType.CONVERGE]
]


action_metrics = [
    {
        "node_name": "action",
        "description": "生产进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "service", "process_name": "fta_action"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "action.producer.status",
        "solution": "",
    },
    {
        "node_name": "action",
        "description": "消费进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "scheduler", "process_name": "celery_worker_fta_action"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "action.consumer.status",
        "solution": "",
    },
] + [
    {
        "node_name": "action",
        "description": "待执行队列长度[{}]".format(action_type),
        "category": "redis",
        "collect_type": "backend",
        "collect_metric": "redis.method.llen",
        "collect_args": (
            "{% load math_filters %}"
            + '{"backend": "cache", "name": "{%get_key key.FTA_ACTION_LIST_KEY action_type="'
            + action_type
            + '"%}"}'
        ),
        "collect_interval": 60,
        "metric_alias": f"action.{action_type}.length",
    }
    for action_type in ActionPluginType.PLUGIN_TYPE_DICT.keys()
]


kernel_api_metrics = [
    {
        "node_name": "kernel_api",
        "description": "进程状态",
        "category": "supervisor",
        "collect_metric": "supervisor.process.info",
        "collect_args": '{"group_name": "kernel_api", "process_name": "kernel_api"}',
        "collect_interval": 60,
        "collect_type": "backend",
        "metric_alias": "kernel_api.status",
        "solution": "",
    },
]

node_metrics = (
    redis_metrics
    + kafka_metrics
    + transfer_metrics
    + influxdb_proxy_metrics
    + mysql_metrics
    + consul_metrics
    + rabbitmq_metrics
    + celery_metrics
    + system_metrics
    + supervisor_metrics
    + default_metrics
    + access_data_metrics
    + access_real_time_data_metrics
    + detect_metrics
    + access_event_metrics
    + trigger_metrics
    + alert_builder_metrics
    + alert_manager_metrics
    + composite_metrics
    + converge_metrics
    + action_metrics
    + kernel_api_metrics
    + elasticsearch_metrics
)

HEALTHZ_NODES = nodes
HEALTHZ_NODE_METRICS = node_metrics


def init_or_update_healthz_node():
    HealthzTopoNode.objects.all().delete()
    for node_name, node_description, no_use in HEALTHZ_NODES:
        node_obj, is_new = HealthzTopoNode.objects.get_or_create(
            node_name=node_name, defaults={"node_description": node_description}
        )
        if not is_new and node_obj.node_description != node_description:
            node_obj.node_description = node_description
            node_obj.save()


def init_or_update_healthz_node_metric():
    HealthzMetricConfig.objects.all().delete()
    for metric in HEALTHZ_NODE_METRICS:
        newmetric = copy.deepcopy(metric)
        for field in metric:
            field_name_list = [f.name for f in HealthzMetricConfig._meta.get_fields()]
            if field not in field_name_list:
                newmetric.pop(field)
        if newmetric["metric_alias"].endswith("status") and not newmetric["solution"]:
            newmetric["solution"] = json.dumps(
                [
                    {
                        "reason": "进程：%s未启动或连接不上" % newmetric["node_name"],
                        "solution": "确保进程：%s状态正常" % newmetric["node_name"],
                    }
                ]
            )
        metric_obj, is_new = HealthzMetricConfig.objects.get_or_create(
            metric_alias=metric["metric_alias"], defaults=newmetric
        )
        if not is_new:
            metric_obj.__dict__.update(newmetric)
            metric_obj.save()


def run(apps, *args):
    global HealthzTopoNode, HealthzMetricConfig
    HealthzTopoNode = apps.get_model("bkmonitor.HealthzTopoNode")
    HealthzMetricConfig = apps.get_model("bkmonitor.HealthzMetricConfig")
    try:
        init_or_update_healthz_node()
        init_or_update_healthz_node_metric()
    except DatabaseError:
        pass
