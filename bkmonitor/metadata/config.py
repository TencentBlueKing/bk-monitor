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


import os

from django.conf import settings

from constants.result_table import (  # noqa
    RT_RESERVED_WORD_EXACT,
    RT_RESERVED_WORD_FUZZY,
)

# META配置的Consul路径
CONSUL_PATH = "{}_{}_{}/{}".format(settings.APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, "metadata")
# SERVICE 配置的Consul路径
CONSUL_SERVICE_PATH = "{}_{}_{}/{}".format(settings.APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, "service")
# migration通常由web模块执行，需要使用后台app code
MIGRATION_CONSUL_PATH = "{}_{}_{}/{}".format(
    settings.BACKEND_APP_CODE, settings.PLATFORM, settings.ENVIRONMENT, "metadata"
)
# consul data_id 路径模板
CONSUL_DATA_ID_PATH_FORMAT = "{consul_path}/v1/{{transfer_cluster_id}}/data_id/{{data_id}}".format(
    consul_path=CONSUL_PATH
)

# consul transfer 路径模板
CONSUL_TRANSFER_PATH = "{consul_service_path}/v1/".format(consul_service_path=CONSUL_SERVICE_PATH)

# 配置CRONTAB任务定时任务锁的路径
CONSUL_CRON_LOCK_PATH = "%s/cron_lock" % CONSUL_PATH
# 配置CONSUL定时更新的间隔时间, 单位秒
CONSUL_UPDATE_GAP = 60

# 获取各个Data ID
_platform_module = __import__("config.default", globals(), locals(), ["*"])
for config in dir(_platform_module):
    if config.endswith("_DATAID"):
        locals()[config] = getattr(_platform_module, config)

# 监控ID区间为 [500, 600)
ZK_GSE_DATA_CLUSTER_ID = 500

# 调用GSE的'接收端配置接口'以及'路由接口'时使用
DEFAULT_GSE_API_PLAT_NAME = "bkmonitor"  # GSE分配给监控的平台名称，不随APP_CODE变更，请不要修改

# kafka的topic前缀
# 与gse对接的kafka topic，由于会存在data_id隔离，因此前缀一致可以接受
# 保持一致，是为了使得3.1和3.2可以并存同样的topic，降低基础性能上报占用kafka空间
KAFKA_TOPIC_PREFIX = "0bkmonitor_"
# 自行存储的topic需要区别，主要是因为topic拼接与table_id相关
# 3.1与3.2环境可能存在table_id冲突，因此需要增加app_code隔离
KAFKA_TOPIC_PREFIX_STORAGE = "0{}_storage_".format(settings.APP_CODE)

# Redis的key前缀
# 配置理由，同KAFKA_TOPIC_PREFIX_STORAGE
REDIS_KEY_PREFIX = settings.APP_CODE

# GSE DATA_ID最大值和最小值的判断
MIN_DATA_ID = 1500000  # 3.2版本将该值增大20w，防止与3.1版本冲突
MAX_DATA_ID = 2097151

# 允许ES转发的URL
ES_ROUTE_ALLOW_URL = ["_cat", "_cluster", "_nodes", "_stats"]


def is_built_in_data_id(bk_data_id):
    return 1000 <= bk_data_id <= 1020 or 1100000 <= bk_data_id <= 1199999


# CMDB层级拆分的公共配置项内容
# 源结果表输出的数据源名称
RT_CMDB_LEVEL_DATA_SOURCE_NAME = "{}_cmdb_level_split"
# CMDB层级拆分的ETL配置名
RT_CMDB_LEVEL_ETL_CONFIG = "bk_cmdb_level_split"
# CMDB层级差费的RT分配名
RT_CMDB_LEVEL_RT_NAME = "{}_cmdb_level"

# 获取需要增加事务的DB链接名
DATABASE_CONNECTION_NAME = getattr(settings, "BACKEND_DATABASE_NAME", "monitor_api")

# ES存储默认版本
ES_CLUSTER_VERSION_DEFAULT = 7

ES_SHARDS_CONFIG = os.environ.get("ES_SHARDS_NUMBER", 1)
ES_REPLICAS_CONFIG = os.environ.get("ES_REPLICAS_CONFIG", 0)

BCS_TABLE_ID_PREFIX = "bkmonitor_bcs"

# 容器配置相关内容
# 资源组名
BCS_RESOURCE_GROUP_NAME = "monitoring.bk.tencent.com"
# 资源版本号
BCS_RESOURCE_VERSION = "v1beta1"
# data_id注入资源类型
BCS_RESOURCE_DATA_ID_RESOURCE_KIND = "DataID"
# data_id注入类型查询名
BCS_RESOURCE_DATA_ID_RESOURCE_PLURAL = "dataids"

# BCS集群相关数据源
k8s_metric_name = "K8SMetric"
cluster_custom_metric_name = "CustomMetric"
k8s_event_name = "K8SEvent"

# 周期任务锁的超时时间
PERIODIC_TASK_DEFAULT_TTL = 7200

# 创建记录时，默认用户名为system
DEFAULT_USERNAME = "system"

# 默认kafka sasl配置
KAFKA_SASL_MECHANISM = "SCRAM-SHA-512"
KAFKA_SASL_PROTOCOL = "SASL_PLAINTEXT"

# vm 存储类型
VM_STORAGE_TYPE = "vm"
# metadata 结果表白名单 key
METADATA_RESULT_TABLE_WHITE_LIST = "metadata:query_metric:table_id_list"
