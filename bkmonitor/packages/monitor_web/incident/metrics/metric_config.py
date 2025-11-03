"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from typing import Any
from monitor_web.incident.metrics.utils import transform_to_ip4, is_ipv4
from monitor_web.incident.metrics.constants import EntityType, MetricName, MetricDimension

# APM 公共配置模板
APM_BASE_QUERY_CONFIG = {
    "data_source_label": "custom",
    "data_type_label": "time_series",
    "interval": "{interval}",
    "interval_unit": "s",
    "time_field": "time",
}

# BCS 公共配置模板
BCS_BASE_QUERY_CONFIG = {
    "data_source_label": "prometheus",
    "data_type_label": "time_series",
    "interval": "{interval}",
    "alias": "a",
    "filter_dict": {},
}

# Host 公共配置模板
HOST_BASE_QUERY_CONFIG = {
    "data_source_label": "bk_monitor",
    "data_type_label": "time_series",
    "interval": "{interval}",
    "functions": [{"id": "time_shift", "params": [{"id": "n"}]}],
}

# BCS监控指标模板
BCS_PROMQL_TEMPLATE = {
    # CPU使用量
    MetricName.BCS_PERFORMANCE_CPU_USAGE.value: {
        "promql": 'sum(rate(container_cpu_usage_seconds_total{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }[1m]  ))'
    },
    # CPU request使用率
    MetricName.BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE.value: {
        "promql": 'sum(rate(container_cpu_usage_seconds_total{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }[1m]  )) / sum(kube_pod_container_resource_requests_cpu_cores{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }  )'
    },
    # CPU limit使用率
    MetricName.BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE.value: {
        "promql": 'sum(rate(container_cpu_usage_seconds_total{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }[1m]  )) / sum(kube_pod_container_resource_limits_cpu_cores{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }  )',
    },
    # 内存使用量
    MetricName.BCS_PERFORMANCE_MEMORY_USAGE.value: {
        "promql": 'sum(container_memory_working_set_bytes{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }  )',
    },
    # 内存 request使用率
    MetricName.BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE.value: {
        "promql": 'sum(container_memory_working_set_bytes{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }  ) / sum(kube_pod_container_resource_requests_memory_bytes{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }  )',
    },
    # 内存 limit使用率
    MetricName.BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE.value: {
        "promql": 'sum(container_memory_working_set_bytes{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }  ) / sum(kube_pod_container_resource_limits_memory_bytes{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", container_name!="{container_name}" \
        }  )',
    },
    # 网络入带宽
    MetricName.BCS_TRAFFIC_IN.value: {
        "promql": 'sum(rate(container_network_receive_bytes_total{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", \
        }[1m]  ))',
    },
    # 网络出带宽
    MetricName.BCS_TRAFFIC_OUT.value: {
        "promql": 'sum(rate(container_network_transmit_bytes_total{ \
        bcs_cluster_id="{bcs_cluster_id}", namespace=~"^({namespace})$", pod_name=~"^({pod_name})$", \
        }[1m]  ))',
    },
}

# 实体类型指标配置映射
EntityTypeMetricConfigMapping = {
    EntityType.APMService.value: {
        MetricName.APM_REQUEST_COUNT.value: {
            MetricDimension.TOTAL.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                        "group_by": [],
                        "display": True,
                        "where": [],
                        "table": "{table}",
                        "filter_dict": "{filter_dict}",
                        "interval": "{interval}",
                    }
                ],
            },
            MetricDimension.ACTIVE.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                        "group_by": [],
                        "display": True,
                        "where": [
                            {"key": "kind", "method": "eq", "value": ["3"]},
                            {"condition": "or", "key": "kind", "method": "eq", "value": ["4"]},
                        ],  # kind=3 or kind=4 代表主调
                        "table": "{table}",
                        "filter_dict": "{filter_dict}",
                        "interval": "{interval}",
                    }
                ],
            },
            MetricDimension.PASSIVE.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                        "group_by": [],
                        "display": True,
                        "where": [
                            {"key": "kind", "method": "eq", "value": ["2"]},
                            {"condition": "or", "key": "kind", "method": "eq", "value": ["5"]},
                        ],  # kind=2 or kind=5 代表被调
                        "table": "{table}",
                        "filter_dict": "{filter_dict}",
                        "interval": "{interval}",
                    }
                ],
            },
        },
        MetricName.APM_ERROR_COUNT.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "A"}],
                        "group_by": [],
                        "display": True,
                        "where": [{"key": "status_code", "method": "eq", "value": ["2"], "condition": "and"}],
                        "table": "{table}",
                        "filter_dict": "{filter_dict}",
                        "interval": "{interval}",
                    }
                ],
            }
        },
        MetricName.APM_ERROR_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "b / c",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "b"}],
                        "group_by": [],
                        "where": [{"key": "status_code", "method": "eq", "value": ["2"], "condition": "and"}],
                        "table": "{table}",
                        "filter_dict": "{filter_dict}",
                        "interval": "{interval}",
                    },
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_count", "method": "SUM", "alias": "c"}],
                        "group_by": [],
                        "where": [],
                        "table": "{table}",
                        "filter_dict": "{filter_dict}",
                        "interval": "{interval}",
                    },
                ],
            }
        },
        MetricName.APM_DURATION.value: {
            MetricDimension.AVG.label: {
                "expression": "a / b",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_duration_sum", "method": "SUM", "alias": "a"}],
                        "group_by": [],
                        "where": [],
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                        "table": "{table}",
                        "filter_dict": "{filter_dict}",
                        "interval": "{interval}",
                    },
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "bk_apm_total", "method": "SUM", "alias": "b"}],
                        "group_by": [],
                        "where": [],
                        "functions": [{"id": "increase", "params": [{"id": "window", "value": "2m"}]}],
                        "table": "{table}",
                        "filter_dict": {},
                        "interval": "{interval}",
                    },
                ],
            },
            MetricDimension.P99.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "table": "{table}",
                        "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                        "group_by": ["le"],
                        "display": True,
                        "where": [],
                        "filter_dict": "{filter_dict}",
                        "functions": [
                            {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.99}]},
                        ],
                        "interval": "{interval}",
                    }
                ],
            },
            MetricDimension.P95.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "table": "{table}",
                        "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                        "group_by": ["le"],
                        "display": True,
                        "where": [],
                        "filter_dict": "{filter_dict}",
                        "functions": [
                            {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.95}]},
                        ],
                        "interval": "{interval}",
                    }
                ],
            },
            MetricDimension.P50.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **APM_BASE_QUERY_CONFIG,
                        "table": "{table}",
                        "metrics": [{"field": "bk_apm_duration_bucket", "method": "SUM", "alias": "A"}],
                        "group_by": ["le"],
                        "display": True,
                        "where": [],
                        "filter_dict": "{filter_dict}",
                        "functions": [
                            {"id": "rate", "params": [{"id": "window", "value": "2m"}]},
                            {"id": "histogram_quantile", "params": [{"id": "scalar", "value": 0.5}]},
                        ],
                        "interval": "{interval}",
                    }
                ],
            },
        },
    },
    EntityType.BcsPod.value: {
        MetricName.BCS_PERFORMANCE_CPU_USAGE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {**BCS_BASE_QUERY_CONFIG, **BCS_PROMQL_TEMPLATE[MetricName.BCS_PERFORMANCE_CPU_USAGE.value]}
                ],
                "down_sample_range": "6s",
            }
        },
        MetricName.BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **BCS_BASE_QUERY_CONFIG,
                        **BCS_PROMQL_TEMPLATE[MetricName.BCS_PERFORMANCE_CPU_REQUEST_USAGE_RATE.value],
                    }
                ],
                "down_sample_range": "10s",
            }
        },
        MetricName.BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **BCS_BASE_QUERY_CONFIG,
                        **BCS_PROMQL_TEMPLATE[MetricName.BCS_PERFORMANCE_CPU_LIMIT_USAGE_RATE.value],
                    }
                ],
                "down_sample_range": "10s",
            }
        },
        MetricName.BCS_PERFORMANCE_MEMORY_USAGE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {**BCS_BASE_QUERY_CONFIG, **BCS_PROMQL_TEMPLATE[MetricName.BCS_PERFORMANCE_MEMORY_USAGE.value]}
                ],
                "down_sample_range": "10s",
            }
        },
        MetricName.BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **BCS_BASE_QUERY_CONFIG,
                        **BCS_PROMQL_TEMPLATE[MetricName.BCS_PERFORMANCE_MEMORY_REQUEST_USAGE_RATE.value],
                    }
                ],
                "down_sample_range": "10s",
            }
        },
        MetricName.BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **BCS_BASE_QUERY_CONFIG,
                        **BCS_PROMQL_TEMPLATE[MetricName.BCS_PERFORMANCE_MEMORY_LIMIT_USAGE_RATE.value],
                    }
                ],
                "down_sample_range": "10s",
            }
        },
        MetricName.BCS_TRAFFIC_IN.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [{**BCS_BASE_QUERY_CONFIG, **BCS_PROMQL_TEMPLATE[MetricName.BCS_TRAFFIC_IN.value]}],
                "down_sample_range": "10s",
            }
        },
        MetricName.BCS_TRAFFIC_OUT.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [{**BCS_BASE_QUERY_CONFIG, **BCS_PROMQL_TEMPLATE[MetricName.BCS_TRAFFIC_OUT.value]}],
                "down_sample_range": "10s",
            }
        },
    },
    EntityType.BkNodeHost.value: {
        MetricName.HOST_CPU_FIVE_MINUTE_AVERAGE_LOAD.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **HOST_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "load5", "method": "MAX", "alias": "A"}],
                        "table": "system.load",
                        "group_by": [],
                        "where": [],
                        "filter_dict": {
                            "targets": [
                                {"bk_target_ip": "{bk_target_ip}", "bk_target_cloud_id": "{bk_target_cloud_id}"}
                            ]
                        },
                    }
                ],
                "down_sample_range": "18s",
            }
        },
        MetricName.HOST_CPU_USAGE_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **HOST_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "usage", "method": "MAX", "alias": "A"}],
                        "table": "system.cpu_summary",
                        "group_by": [],
                        "where": [],
                        "filter_dict": {
                            "targets": [
                                {"bk_target_ip": "{bk_target_ip}", "bk_target_cloud_id": "{bk_target_cloud_id}"}
                            ]
                        },
                    }
                ],
                "down_sample_range": "18s",
            }
        },
        MetricName.HOST_MEM_PHYSICAL_FREE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **HOST_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "free", "method": "MAX", "alias": "A"}],
                        "table": "system.mem",
                        "group_by": [],
                        "where": [],
                        "filter_dict": {
                            "targets": [
                                {"bk_target_ip": "{bk_target_ip}", "bk_target_cloud_id": "{bk_target_cloud_id}"}
                            ]
                        },
                    }
                ],
                "down_sample_range": "18s",
            }
        },
        MetricName.HOST_NIC_IN_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **HOST_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "speed_recv_bit", "method": "MAX", "alias": "A"}],
                        "table": "system.net",
                        "group_by": ["device_name"],
                        "where": [],
                        "filter_dict": {
                            "targets": [
                                {"bk_target_ip": "{bk_target_ip}", "bk_target_cloud_id": "{bk_target_cloud_id}"}
                            ]
                        },
                    }
                ],
                "down_sample_range": "19s",
            }
        },
        MetricName.HOST_NIC_OUT_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **HOST_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "speed_sent_bit", "method": "MAX", "alias": "A"}],
                        "table": "system.net",
                        "group_by": ["device_name"],
                        "where": [],
                        "filter_dict": {
                            "targets": [
                                {"bk_target_ip": "{bk_target_ip}", "bk_target_cloud_id": "{bk_target_cloud_id}"}
                            ]
                        },
                    }
                ],
                "down_sample_range": "19s",
            }
        },
        MetricName.HOST_DISK_USAGE_RATE.value: {
            MetricDimension.DEFAULT.label: {
                "expression": "A",
                "query_configs": [
                    {
                        **HOST_BASE_QUERY_CONFIG,
                        "metrics": [{"field": "in_use", "method": "MAX", "alias": "A"}],
                        "table": "system.disk",
                        "group_by": ["mount_point"],
                        "where": [],
                        "filter_dict": {
                            "targets": [
                                {"bk_target_ip": "{bk_target_ip}", "bk_target_cloud_id": "{bk_target_cloud_id}"}
                            ]
                        },
                    }
                ],
                "down_sample_range": "19s",
            }
        },
    },
}


def fill_query_config(query_config: dict, key: str, value: Any):
    """
    填充/覆盖查询配置占位符

    Args:
        query_config: 查询配置
        key: 需要填充的key
        value: 需要填充的value
    """
    query_config[key] = value if query_config[key] == f"{{{key}}}" else query_config[key]


def replace_query_config(query_config: dict, key: str, pattern: str, value: Any):
    """
    替换查询配置占位符(替换所有)

    Args:
        query_config: 查询配置
        key: 需要替换的key
        pattern: 需要替换的pattern
        value: 需要替换的value
    """
    query_config[key] = query_config[key].replace(pattern, value)


def get_apm_config(dimensions: dict[str, Any], **kwargs):
    """获取APM配置

    Args:
        request_data: 请求数据，包含以下字段：
            - table: APM表名
            - service_name: 服务名
            - start_time: 开始时间
            - end_time: 结束时间
            - bk_biz_id: 业务ID
            - interval: 时间间隔

    Returns:
        填充后的APM所有指标配置
    """

    # 获取APM配置模板
    apm_config = EntityTypeMetricConfigMapping[EntityType.APMService.value]

    # 复制所有配置
    filled_config = {}
    for metric_name, metric_config in apm_config.items():
        filled_config[metric_name] = metric_config.copy()
        # 填充每个指标的查询配置
        for dimension_type, query in filled_config[metric_name].items():
            for query_config in query["query_configs"]:
                fill_query_config(query_config, "table", kwargs.get("table", ""))
                fill_query_config(query_config, "filter_dict", {"service_name": dimensions.get("apm_service_name", "")})
                fill_query_config(query_config, "interval", kwargs.get("interval", 120))

            filled_config[metric_name][dimension_type].update(
                {
                    "start_time": kwargs.get("start_time"),
                    "end_time": kwargs.get("end_time"),
                    "bk_biz_id": kwargs.get("bk_biz_id"),
                }
            )
    return filled_config


def get_bcs_config(dimensions: dict[str, Any], **kwargs):
    """获取BCS配置

    Args:
        request_data: 请求数据，包含以下字段：
            - bcs_cluster_id: BCS集群ID
            - namespace: 命名空间
            - pod_name: Pod名称
            - start_time: 开始时间
            - end_time: 结束时间
            - bk_biz_id: 业务ID
            - interval: 时间间隔

    Returns:
        填充后的BCS所有指标配置
    """
    # 获取BCS配置模板
    bcs_config = EntityTypeMetricConfigMapping[EntityType.BcsPod.value]
    # 复制所有配置
    filled_config = {}
    for metric_name, metric_config in bcs_config.items():
        filled_config[metric_name] = metric_config.copy()
        # 填充每个指标的查询配置
        for dimension_type, query in filled_config[metric_name].items():
            # 替换PromQL中的bcs_filter占位符
            for query_config in query["query_configs"]:
                if "promql" in query_config:
                    replace_query_config(query_config, "promql", "{namespace}", dimensions.get("namespace", ""))
                    replace_query_config(query_config, "promql", "{pod_name}", dimensions.get("pod_name", ""))
                    replace_query_config(
                        query_config, "promql", "{container_name}", dimensions.get("container_name", "POD")
                    )
                    replace_query_config(query_config, "promql", "{bcs_cluster_id}", dimensions.get("cluster_id", ""))
                fill_query_config(query_config, "interval", kwargs.get("interval", 3600))
            filled_config[metric_name][dimension_type].update(
                {
                    "start_time": kwargs.get("start_time"),
                    "end_time": kwargs.get("end_time"),
                    "bk_biz_id": kwargs.get("bk_biz_id"),
                }
            )
    return filled_config


def get_host_config(dimensions: dict[str, Any], **kwargs):
    """获取Host配置

    Args:
        request_data: 请求数据，包含以下字段：
            - bk_target_ip: 目标IP
            - bk_target_cloud_id: 云区域ID
            - start_time: 开始时间
            - end_time: 结束时间
            - bk_biz_id: 业务ID
            - interval: 时间间隔

    Returns:
        填充后的Host所有指标配置
    """
    # 获取Host配置模板
    host_config = EntityTypeMetricConfigMapping[EntityType.BkNodeHost.value]

    # 复制所有配置
    filled_config = {}
    for metric_name, metric_config in host_config.items():
        filled_config[metric_name] = metric_config.copy()
        # 填充每个指标的查询配置
        for dimension_type, query in filled_config[metric_name].items():
            # 替换目标参数
            for query_config in query["query_configs"]:
                if "filter_dict" in query_config and "targets" in query_config["filter_dict"]:
                    target = query_config["filter_dict"]["targets"][0]
                inner_ip = dimensions.get("inner_ip")
                target["bk_target_ip"] = inner_ip if is_ipv4(inner_ip) else transform_to_ip4(inner_ip)
                target["bk_target_cloud_id"] = dimensions.get("bk_cloud_id")
                fill_query_config(query_config, "interval", kwargs.get("interval", 3600))
            filled_config[metric_name][dimension_type].update(
                {
                    "start_time": kwargs.get("start_time"),
                    "end_time": kwargs.get("end_time"),
                    "bk_biz_id": kwargs.get("bk_biz_id"),
                }
            )
    return filled_config
