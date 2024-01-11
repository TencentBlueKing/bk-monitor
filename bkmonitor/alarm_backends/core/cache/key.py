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

from django.conf import settings

from alarm_backends.constants import (
    CONST_MINUTES,
    CONST_ONE_DAY,
    CONST_ONE_HOUR,
    CONST_ONE_WEEK,
)
from alarm_backends.core.cluster import get_cluster
from alarm_backends.core.storage.redis_cluster import RedisProxy
from bkmonitor.utils.text import underscore_to_camel

TTL_NOT_SET = CONST_ONE_WEEK

prefix_tpl = "{app_code}.{platform}{env}"

# 环境缩写
platform_abbreviation = {"enterprise": "ee", "community": "ce"}


def get_cache_key_prefix():
    env = "[{}]".format(settings.ENVIRONMENT)
    if settings.ENVIRONMENT == "production":
        env = ""

    platform = platform_abbreviation.get(settings.PLATFORM, settings.PLATFORM)
    prefix = prefix_tpl.format(app_code=settings.APP_CODE, platform=platform, env=env)
    return prefix


PUBLIC_KEY_PREFIX = get_cache_key_prefix()

if not get_cluster().is_default():
    KEY_PREFIX = "{}.{}".format(PUBLIC_KEY_PREFIX, get_cluster().name)
else:
    KEY_PREFIX = PUBLIC_KEY_PREFIX


class RedisDataKey(object):
    """
    redis 的Key对象
    """

    def __init__(self, key_tpl=None, ttl=None, backend=None, is_global=False, **extra_config):
        self._cache = None
        if not all([key_tpl, ttl, backend]):
            raise ValueError
        # key 模板
        self.key_tpl = key_tpl
        # 过期时间
        self.ttl = ttl
        # 对应cache backend
        self.backend = backend
        # key 类型 (public/cluster)
        self.is_global = is_global
        for k, v in list(extra_config.items()):
            setattr(self, k, v)

    @property
    def client(self):
        if self._cache is None:
            self._cache = RedisProxy(self.backend)
        return self._cache

    def get_key(self, **kwargs):
        key = self.key_tpl.format(**kwargs)

        if self.is_global:
            key_prefix = PUBLIC_KEY_PREFIX
        else:
            key_prefix = KEY_PREFIX
        if not key.startswith(key_prefix):
            key = ".".join([key_prefix, key])
        strategy_id = int(kwargs.get("strategy_id") or 0)
        key = SimilarStr(key)
        key.strategy_id = strategy_id
        return key

    def expire(self, **key_kwargs):
        # 注意在pipeline中使用pipeline调用expire方法，不要调用该对象自身的expire方法
        self.client.expire(self.get_key(**key_kwargs), self.ttl)


class SimilarStr(str):
    _strategy_id = 0

    @property
    def strategy_id(self):
        return self._strategy_id

    @strategy_id.setter
    def strategy_id(self, value):
        try:
            value = int(value)
        except (ValueError, TypeError):
            value = 0
        self._strategy_id = value


class StringKey(RedisDataKey):
    """
    String 数据结构的Key对象
    """


class HashKey(RedisDataKey):
    """
    Hash 数据结构的Key对象
    extra_config:
        field_tpl=""
    """

    def __init__(self, key_tpl=None, ttl=None, backend=None, **extra_config):
        super(HashKey, self).__init__(key_tpl, ttl, backend, **extra_config)
        if "field_tpl" not in extra_config:
            raise ValueError("keyword argument 'field_tpl' is required")

    def get_field(self, **kwargs):
        return self.field_tpl.format(**kwargs)


class SetKey(RedisDataKey):
    """
    Set 数据结构的Key对象
    """


class ListKey(RedisDataKey):
    """
    List 数据结构的Key对象
    """


class SortedSetKey(RedisDataKey):
    """
    SortedSet 数据结构的Key对象
    """


def register_key_with_config(config):
    """
    支持的类型： hash、set、list、sorted_set
    :param config:
    :rtype: RedisDataKey
    """
    key_type = config["key_type"]
    key_cls = globals().get("{}Key".format(underscore_to_camel(key_type)))
    if not key_cls:
        raise TypeError("unsupported key type: {}".format(key_type))
    return key_cls(**config)


##################################################
#           Definition of key in redis           #
#                                                #
# Contains:                                      #
# - key_type:  hash, set, list, sorted_set, etc. #
# - key_tpl:   Key generation rule.              #
# - field_tpl: Field generation rule, if any.    #
# - ttl:       10(unit:seconds).                 #
# - backend:   "queue", "service", "log", etc.   #
# - label:     Description of the key.           #
##################################################

##################################################
# queue(db:9)[重要，不可清理] services之间交互的队列   #
##################################################
DATA_LIST_KEY = register_key_with_config(
    {
        "label": "[access]待检测数据队列",
        "key_type": "list",
        "key_tpl": "access.data.{strategy_id}.{item_id}",
        "ttl": 30 * CONST_MINUTES,
        "backend": "queue",
    }
)

DATA_SIGNAL_KEY = register_key_with_config(
    {
        "label": "[access]待检测数据信号队列",
        "key_type": "list",
        "key_tpl": "access.data.signal",
        "ttl": 30 * CONST_MINUTES,
        "backend": "queue",
    }
)

NO_DATA_LIST_KEY = register_key_with_config(
    {
        "label": "[access]无数据告警待检测队列",
        "key_type": "list",
        "key_tpl": "access.nodata.{strategy_id}.{item_id}",
        "ttl": 10 * CONST_MINUTES,
        "backend": "queue",
    }
)

HISTORY_DATA_KEY = register_key_with_config(
    {
        "label": "[detect]待检测数据对应历史数据",
        "key_type": "hash",
        "key_tpl": "detect.history.data.{strategy_id}.{item_id}.{timestamp}",
        "field_tpl": "{dimensions_md5}",
        "ttl": 30 * CONST_MINUTES,
        "backend": "service",
    }
)

ANOMALY_LIST_KEY = register_key_with_config(
    {
        "label": "[detect]检测结果详情队列",
        "key_type": "list",
        "key_tpl": "detect.anomaly.list.{strategy_id}.{item_id}",
        "ttl": 30 * CONST_MINUTES,
        "backend": "queue",
    }
)

ANOMALY_SIGNAL_KEY = register_key_with_config(
    {
        "label": "[detect]异常信号队列",
        "key_type": "list",
        "key_tpl": "detect.anomaly.signal",
        "ttl": 30 * CONST_MINUTES,
        "backend": "queue",
    }
)

TRIGGER_EVENT_LIST_KEY = register_key_with_config(
    {
        "label": "[trigger]异常触发信号队列",
        "key_type": "list",
        "key_tpl": "trigger.event",
        "ttl": 30 * CONST_MINUTES,
        "backend": "queue",
    }
)

#####################################################
# service(db:10) [重要，不可清理] service自身的数据      #
#####################################################
STRATEGY_SNAPSHOT_KEY = register_key_with_config(
    {
        "label": "[detect]异常检测使用的策略快照",
        "key_type": "string",
        "key_tpl": "cache.strategy.snapshot.{strategy_id}.{update_time}",
        "ttl": CONST_ONE_HOUR,
        "backend": "service",
    }
)

STRATEGY_CHECKPOINT_KEY = register_key_with_config(
    {
        "label": "[access]策略数据拉取到的最后一条数据的时间",
        "key_type": "string",
        "key_tpl": "checkpoint.strategy_group_{strategy_group_key}",
        "ttl": CONST_ONE_HOUR,
        "backend": "service",
    }
)

ACCESS_RUN_TIMESTAMP_KEY = register_key_with_config(
    {
        "label": "[access]access任务运行时间",
        "key_type": "string",
        "key_tpl": "access.run.strategy_group_{strategy_group_key}",
        "ttl": CONST_ONE_HOUR,
        "backend": "service",
    }
)

ACCESS_DUPLICATE_KEY = register_key_with_config(
    {
        "label": "[access]数据拉取去重",
        "key_type": "set",
        "key_tpl": "access.data.duplicate.strategy_group_{strategy_group_key}.{dt_event_time}",
        "ttl": 10 * CONST_MINUTES,
        "backend": "service",
    }
)

ACCESS_PRIORITY_KEY = register_key_with_config(
    {
        "label": "[access]数据拉取优先级",
        "key_type": "hash",
        "key_tpl": "access.data.priority.{priority_group_key}",
        "field_tpl": "{dimensions_md5}",
        "ttl": 10 * CONST_MINUTES,
        "backend": "service",
    }
)

# 每个group，在每10分钟内允许占用的worker时间上限： 50秒。当key不存在时，新的token周期或者新的策略，初始化token。
# 每次占用资源后，对token进行削减。token不足时，不能再拉取数据了，必须等到key过期后，重新发token。
STRATEGY_TOKEN_BUCKET_KEY = register_key_with_config(
    {
        "label": "[access]数据拉取token桶",
        "key_type": "string",
        "key_tpl": "access.data.token.strategy_group_{strategy_group_key}",
        "ttl": 10 * CONST_MINUTES,
        "backend": "service",
    }
)

QOS_CONTROL_KEY = register_key_with_config(
    {
        "label": "[access]QOS控制开关",
        "key_type": "hash",
        "key_tpl": "access.event.qos.control",
        "ttl": 30 * CONST_MINUTES,
        "backend": "service",
        "field_tpl": "{dimensions_md5}",
    }
)

OLD_MD5_TO_DIMENSION_CACHE_KEY = register_key_with_config(
    {
        "label": "[detect]维度信息缓存(type:Hash)(key: dimensions_md5, value: 维度字典 json(dict))",
        "key_type": "hash",
        "key_tpl": "dimensions.cache.key",
        "ttl": TTL_NOT_SET,
        "backend": "service",
        "field_tpl": ".{service_type}.{strategy_id}.{item_id}.{dimensions_md5}",
    }
)

MD5_TO_DIMENSION_CACHE_KEY = register_key_with_config(
    {
        "label": "[detect]维度信息缓存(type:Hash)(key: dimensions_md5, value: 维度字典 json(dict))",
        "key_type": "hash",
        "key_tpl": "dimensions.cache.key.{service_type}.{strategy_id}.{item_id}",
        "ttl": CONST_ONE_DAY,
        "backend": "service",
        "field_tpl": "{dimensions_md5}",
    }
)

LAST_CHECKPOINTS_CACHE_KEY = register_key_with_config(
    {
        "label": "[detect|nodata]最后检测时间点(type:Hash)(key: (strategy_id, item_id, dimensions_md5)"
        "value: 最后检测点时间戳(int))",
        "key_type": "hash",
        "key_tpl": "detect.last.checkpoint.{strategy_id}.{item_id}",
        "ttl": TTL_NOT_SET,
        "backend": "service",
        # 这里的field_tpl需要保持和CHECK_RESULT_CACHE_KEY的key_tpl一致
        "field_tpl": "detect.result.{dimensions_md5}.{level}",
    }
)

NO_DATA_LAST_ANOMALY_CHECKPOINTS_CACHE_KEY = register_key_with_config(
    {
        "label": "[nodata]最后检测异常点(type:Hash)(key: (strategy_id, item_id, dimensions_md5), value: 最后异常点时间戳(int))",
        "key_type": "hash",
        "key_tpl": "nodata.last.anomaly.checkpoint.cache.key",
        "ttl": TTL_NOT_SET,
        "backend": "service",
        "field_tpl": "{strategy_id}.{item_id}.{dimensions_md5}",
    }
)

CHECK_RESULT_CACHE_KEY = register_key_with_config(
    {
        "label": "[detect]检测结果缓存: (type:SortedSet)"
        "(score: 数据时间戳(int), name：正常->'timestamp|value' 异常: 'timestamp|{ANOMALY_LABEL}')",
        "key_type": "sorted_set",
        # 这里的key_tpl修改后，需要同步修改LAST_CHECKPOINTS_CACHE_KEY的field_tpl
        "key_tpl": "{prefix}.detect.result.{{strategy_id}}.{{item_id}}."
        "{{dimensions_md5}}.{{level}}".format(prefix=KEY_PREFIX),
        "ttl": CONST_ONE_HOUR,
        "backend": "service",
    }
)

NOTICE_VOICE_COLLECT_KEY = register_key_with_config(
    {
        "label": "[notice]电话单维度通知汇总",
        "key_type": "string",
        "key_tpl": "action.notice.phone_collect.{receiver}",
        "ttl": 2 * CONST_MINUTES,
        "backend": "service",
    }
)

NOTICE_SHIELD_KEY_LOCK = register_key_with_config(
    {
        "label": "[notice]屏蔽通知锁",
        "key_type": "string",
        "key_tpl": "action.notice.shield.{shield_id}",
        "ttl": CONST_ONE_DAY,
        "backend": "service",
    }
)

SERVICE_LOCK_ACCESS = register_key_with_config(
    {
        "label": "access.lock.strategy_{strategy_group_key}",
        "key_type": "string",
        "key_tpl": "access.lock.{strategy_group_key}",
        "ttl": 3 * CONST_MINUTES,
        "backend": "service",
    }
)

SERVICE_LOCK_DETECT = register_key_with_config(
    {
        "label": "detect.lock.strategy_{strategy_id}",
        "key_type": "string",
        "key_tpl": "detect.lock.{strategy_id}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

SERVICE_LOCK_NODATA = register_key_with_config(
    {
        "label": "nodata.lock.strategy_{strategy_id}",
        "key_type": "string",
        "key_tpl": "detect.lock.{strategy_id}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

SERVICE_LOCK_TRIGGER = register_key_with_config(
    {
        "label": "[trigger]进程处理锁",
        "key_type": "string",
        "key_tpl": "trigger.lock.{strategy_id}_{item_id}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

SERVICE_LOCK_EVENT = register_key_with_config(
    {
        "label": "[event]进程处理锁",
        "key_type": "string",
        "key_tpl": "event.lock.{strategy_id}_{dimensions_md5}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

SERVICE_LOCK_RECOVERY = register_key_with_config(
    {
        "label": "[recovery]进程处理锁",
        "key_type": "string",
        "key_tpl": "recovery.lock.{strategy_id}_{dimensions_md5}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

SERVICE_LOCK_PULL_TRIGGER = register_key_with_config(
    {
        "label": "[event]trigger 结果拉取",
        "key_type": "string",
        "key_tpl": "trigger.event.pull",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

ACCESS_END_TIME_KEY = register_key_with_config(
    {
        "label": "[access]数据拉取的结束时间",
        "key_type": "string",
        "key_tpl": "access.data.last_end_time.group_key_{group_key}",
        "ttl": 5 * CONST_MINUTES,
        "backend": "service",
    }
)

ACCESS_EVENT_LOCKS = register_key_with_config(
    {
        "label": "[access]自定义上报事件不同Data ID的拉取锁",
        "key_type": "string",
        "key_tpl": "access.event.custom_event.lock_{data_id}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

STRATEGY_NOTICE_BUCKET = register_key_with_config(
    {
        "label": "[action]策略告警数量限流桶",
        "key_type": "sorted_set",
        "key_tpl": "action.strategy_alarm_limit_bucket.{strategy_id}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

MAIL_REPORT_GROUP_CACHE_KEY = register_key_with_config(
    {
        "label": "[mail_report]订阅报表组别信息保存",
        "key_type": "hash",
        "key_tpl": "service.mail_report.group",
        "ttl": CONST_ONE_WEEK,
        "backend": "service",
        "field_tpl": "",
    }
)

#####################################################
#            fta alert 模块相关队列                   #
#####################################################
ALERT_FIRST_HANDLE_RECORD = register_key_with_config(
    {
        "label": "[alert]告警首次处理记录",
        "key_type": "string",
        "key_tpl": "alert.composite.action.{strategy_id}.{alert_id}.{signal}",
        "ttl": 10 * CONST_MINUTES,
        "backend": "service",
    }
)

ALERT_CONTENT_KEY = register_key_with_config(
    {
        "label": "[alert]当前正在产生的告警内容",
        "key_type": "string",
        "key_tpl": "alert.builder.{dedupe_md5}.content",
        "ttl": 2 * CONST_ONE_HOUR,
        "backend": "service",
    }
)

ALERT_DEDUPE_CONTENT_KEY = register_key_with_config(
    {
        "label": "[alert]当前正在产生的告警内容",
        "key_type": "string",
        "key_tpl": "alert.builder.{strategy_id}.{dedupe_md5}.content",
        "ttl": 2 * CONST_ONE_HOUR,
        "backend": "service",
    }
)

ALERT_SNAPSHOT_KEY = register_key_with_config(
    {
        "label": "[alert]告警内容快照",
        "key_type": "string",
        "key_tpl": "alert.builder.snapshot.{strategy_id}.{alert_id}",
        "ttl": 30 * CONST_MINUTES,
        "backend": "service",
    }
)

EVENT_PULL_LOCKS = register_key_with_config(
    {
        "label": "[alert]事件拉取锁",
        "key_type": "string",
        "key_tpl": "alert.builder.event.lock.{data_id}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

ALERT_UPDATE_LOCK = register_key_with_config(
    {
        "label": "[alert]告警更新锁",
        "key_type": "string",
        "key_tpl": "alert.builder.alert.lock.{dedupe_md5}",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

ALERT_UUID_SEQUENCE = register_key_with_config(
    {
        "label": "[alert]告警的UUID自增序列",
        "key_type": "string",
        "key_tpl": "alert.uuid_sequence",
        "ttl": TTL_NOT_SET,
        "backend": "service",
    }
)

#####################################################
#            fta action模块相关队列                   #
#####################################################

CONVERGE_LIST_KEY = register_key_with_config(
    {
        "label": "[converge]待收敛队列",
        "key_type": "list",
        "key_tpl": "converge.{converge_type}",
        "ttl": CONST_ONE_WEEK,
        "backend": "queue",
    }
)

FTA_ACTION_LIST_KEY = register_key_with_config(
    {
        "label": "[fta_action]待执行队列",
        "key_type": "list",
        "key_tpl": "fta_action.{action_type}",
        "ttl": CONST_ONE_WEEK,
        "backend": "queue",
    }
)

LATEST_TIME_OF_SYNC_ACTION_KEY = register_key_with_config(
    {
        "label": "[fta_action]处理记录同步",
        "key_type": "string",
        "key_tpl": "fta_action.latest_time_of_sync_action",
        "ttl": TTL_NOT_SET,
        "backend": "service",
        "is_global": True,
    }
)

SYNC_ACTION_LOCK_KEY = register_key_with_config(
    {
        "label": "[fta_action]处理记录同步锁",
        "key_type": "string",
        "key_tpl": "fta_action.sync_action.lock",
        "ttl": CONST_MINUTES * 5,
        "backend": "service",
    }
)

LATEST_TIME_UPDATE_P_ACTION_KEY = register_key_with_config(
    {
        "label": "[fta_action]定期更新主任务状态",
        "key_type": "string",
        "key_tpl": "fta_action.latest_time_of_update_p_action",
        "ttl": TTL_NOT_SET,
        "backend": "service",
    }
)

#####################################################
#            fta composite 模块相关队列               #
#####################################################
COMPOSITE_DIMENSION_KEY_LOCK = register_key_with_config(
    {
        "label": "[composite]关联告警维度锁",
        "key_type": "string",
        "key_tpl": "composite.dimension.{strategy_id}.{dimension_hash}.lock",
        "ttl": CONST_MINUTES * 2,
        "backend": "service",
    }
)

COMPOSITE_DETECT_RESULT = register_key_with_config(
    {
        "label": "[composite]关联策略检测结果",
        "key_type": "string",
        "key_tpl": "composite.detect.{strategy_id}.{dimension_hash}",
        "ttl": CONST_ONE_HOUR * 2,
        "backend": "service",
    }
)

COMPOSITE_CHECK_RESULT = register_key_with_config(
    {
        "label": "[composite]关联策略检测结果缓存: score: 数据时间戳(int), name：告警ID(str)",
        "key_type": "sorted_set",
        "key_tpl": "composite.check_result.{strategy_id}.{query_config_id}.{dimension_hash}",
        "ttl": CONST_ONE_HOUR * 2,
        "backend": "service",
    }
)

ALERT_BUILD_QOS_COUNTER = register_key_with_config(
    {
        "label": "[alert builder]流控计数器",
        "key_type": "sorted_set",
        "key_tpl": "alert.qos.{strategy_id}.{signal}.{severity}.{alert_md5}",
        "ttl": CONST_MINUTES * 2,
        "backend": "service",
    }
)

COMPOSITE_QOS_COUNTER = register_key_with_config(
    {
        "label": "[composite]流控计数器",
        "key_type": "sorted_set",
        "key_tpl": "composite.qos.{strategy_id}.{signal}.{severity}.{alert_md5}",
        "ttl": CONST_MINUTES * 2,
        "backend": "service",
    }
)

ALERT_DETECT_KEY_LOCK = register_key_with_config(
    {
        "label": "[composite]单告警检测锁",
        "key_type": "string",
        "key_tpl": "alert.detect.{alert_id}.lock",
        "ttl": CONST_MINUTES * 2,
        "backend": "service",
    }
)

ALERT_DETECT_RESULT = register_key_with_config(
    {
        "label": "[composite]单告警检测结果",
        "key_type": "string",
        "key_tpl": "alert.detect.{alert_id}",
        "ttl": CONST_ONE_HOUR * 3,
        "backend": "service",
    }
)

ACTION_CONVERGE_KEY_PROCESS_LOCK = register_key_with_config(
    {
        "label": "[converge]收敛的发送锁",
        "key_type": "string",
        "key_tpl": "fta_action.converge.{dimension}.process.lock",
        "ttl": CONST_MINUTES,
        "backend": "service",
    }
)

ACTION_POLL_KEY_LOCK = register_key_with_config(
    {
        "label": "[action]轮询创建周期任务锁",
        "key_type": "string",
        "key_tpl": "fta_action.poll.process.lock",
        "ttl": CONST_MINUTES * 5,
        "backend": "service",
    }
)

TIMEOUT_ACTION_KEY_LOCK = register_key_with_config(
    {
        "label": "[action]超时设置周期任务",
        "key_type": "string",
        "key_tpl": "fta_action.timeout.process.lock",
        "ttl": 2 * CONST_MINUTES,
        "backend": "service",
    }
)

DEMO_ACTION_KEY_LOCK = register_key_with_config(
    {
        "label": "[action]执行调试任务锁",
        "key_type": "string",
        "key_tpl": "fta_action.demo.process.lock",
        "ttl": 4,
        "backend": "service",
    }
)

NOTICE_MAPPING_KEY = register_key_with_config(
    {
        "label": "[action]消息类型缓存",
        "key_type": "string",
        "key_tpl": "notice_display_mapping",
        "ttl": CONST_ONE_HOUR,
        "backend": "service",
    }
)

FTA_NOTICE_COLLECT_KEY = register_key_with_config(
    {
        "label": "[fta_notice]单告警汇总待发送池",
        "key_type": "string",
        "key_tpl": "fta_action.notice.{action_signal}.{notice_way}.{alert_id}",
        "ttl": CONST_ONE_DAY,
        "backend": "service",
        "field_tpl": "{receiver}",
    }
)

FTA_NOTICE_COLLECT_LOCK = register_key_with_config(
    {
        "label": "[fta_notice]单告警汇总发送锁",
        "key_type": "string",
        "key_tpl": "fta_action.notice.lock.{action_signal}.{notice_way}.{alert_id}",
        "ttl": 5 * CONST_MINUTES,
        "backend": "service",
        "field_tpl": "{receiver}",
    }
)

FTA_DIMENSION_NOTICE_COLLECT_KEY = register_key_with_config(
    {
        "label": "[fta_notice]汇总待发送池",
        "key_type": "string",
        "key_tpl": "fta_action.notice.collect.{action_signal}.{notice_way}",
        "ttl": CONST_ONE_DAY,
        "backend": "service",
        "field_tpl": "{receiver}",
    }
)

FTA_CONVERGE_DIMENSION_KEY = register_key_with_config(
    {
        "label": "[fta_converge]自愈收敛维度存储",
        "key_type": "sorted_set",
        "key_tpl": "fta_action.converge.{strategy_id}.{dimension}.{value}",
        "ttl": CONST_MINUTES * 30,
        "backend": "service",
    }
)

FTA_SUB_CONVERGE_DIMENSION_KEY = register_key_with_config(
    {
        "label": "[fta_converge]自愈二级收敛维度存储",
        "key_type": "sorted_set",
        "key_tpl": "fta_action.sub_converge.{bk_biz_id}.{signal}.{notice_way}.{notice_receiver}.{alert_level}",
        "ttl": CONST_MINUTES * 30,
        "backend": "service",
    }
)

FTA_SUB_CONVERGE_DIMENSION_LOCK_KEY = register_key_with_config(
    {
        "label": "[fta_converge]自愈二级收敛锁",
        "key_type": "string",
        "key_tpl": "fta_action.sub_converge.lock.{bk_biz_id}.{signal}.{notice_way}.{notice_receiver}.{alert_level}",
        "ttl": settings.MULTI_STRATEGY_COLLECT_WINDOW,
        "backend": "service",
    }
)

REAL_TIME_HOST_TOPIC_KEY = register_key_with_config(
    {
        "label": "[access]实时监控分配topic",
        "key_type": "hash",
        "key_tpl": "access.real_time.host_topic",
        "ttl": CONST_ONE_HOUR,
        "backend": "service",
        "field_tpl": "{host}",
    }
)

NOISE_REDUCE_TOTAL_KEY = register_key_with_config(
    {
        "label": "[access]记录策略对应的降噪基数",
        "key_type": "sorted_set",
        "key_tpl": "access.noise_reduce.total.{strategy_id}.{noise_dimension_hash}",
        "ttl": CONST_ONE_DAY,
        "backend": "service",
    }
)

NOISE_REDUCE_ABNORMAL_KEY = register_key_with_config(
    {
        "label": "[access]记录策略对应的降噪数量",
        "key_type": "sorted_set",
        "key_tpl": "access.noise_reduce.dimension_count.{strategy_id}.{noise_dimension_hash}.{severity}",
        "ttl": CONST_ONE_DAY,
        "backend": "service",
    }
)

NOISE_REDUCE_ALERT_KEY = register_key_with_config(
    {
        "label": "[access]记录策略对应的告警数量",
        "key_type": "sorted_set",
        "key_tpl": "access.noise_reduce.alert.{strategy_id}.{noise_dimension_hash}.{severity}",
        "ttl": CONST_ONE_DAY,
        "backend": "service",
    }
)

NOISE_REDUCE_INIT_LOCK_KEY = register_key_with_config(
    {
        "label": "[action]是否创建降噪窗口锁",
        "key_type": "string",
        "key_tpl": "access.noise_reduce.init.lock.{strategy_id}.{noise_dimension_hash}",
        "ttl": settings.NOISE_REDUCE_TIMEDELTA * CONST_MINUTES,
        "backend": "service",
    }
)

NOISE_REDUCE_OPERATE_LOCK_KEY = register_key_with_config(
    {
        "label": "[action]结束降噪窗口执行锁",
        "key_type": "string",
        "key_tpl": "access.noise_reduce.operate.lock.{strategy_id}.{noise_dimension_hash}",
        "ttl": settings.NOISE_REDUCE_TIMEDELTA * CONST_MINUTES,
        "backend": "service",
    }
)

ALERT_DATA_POLLER_LEADER_KEY = register_key_with_config(
    {
        "label": "[alert]告警生成数据拉取",
        "key_type": "string",
        "key_tpl": "alert.poller.leader",
        "ttl": 2 * CONST_MINUTES,
        "backend": "service",
    }
)

ALERT_HOST_DATA_ID_KEY = register_key_with_config(
    {
        "label": "[alert]告警生成数据分配",
        "key_type": "hash",
        "key_tpl": "alert.poller.host_data_id",
        "ttl": CONST_ONE_HOUR,
        "backend": "service",
        "field_tpl": "{host}",
    }
)

APM_TOPO_DISCOVER_LOCK = register_key_with_config(
    {
        "label": "[apm]TOPO自动发现周期锁",
        "key_type": "string",
        "key_tpl": "apm.tasks.topo.discover.{app_id}",
        "ttl": CONST_MINUTES * 10,
        "backend": "service",
    }
)

APM_EBPF_DISCOVER_LOCK = register_key_with_config(
    {
        "label": "[apm_ebpf]自动发现周期锁",
        "key_type": "string",
        "key_tpl": "apm_ebpf.tasks.discover.{bk_biz_id}",
        "ttl": CONST_MINUTES * 10,
        "backend": "service",
    }
)

APM_PROFILE_DISCOVER_LOCK = register_key_with_config(
    {
        "label": "[apm_profile]自动发现周期锁",
        "key_type": "string",
        "key_tpl": "apm_profile.tasks.discover.{bk_biz_id}:{app_name}",
        "ttl": CONST_MINUTES * 10,
        "backend": "service",
    }
)
