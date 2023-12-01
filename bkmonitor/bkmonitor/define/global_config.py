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

from collections import OrderedDict

from django.conf import settings
from django.db.utils import DatabaseError
from django.utils.translation import ugettext_lazy as _
from rest_framework import serializers as slz

ADVANCED_OPTIONS = OrderedDict(
    [
        ("UNIFY_QUERY_ROUTING_RULES", slz.ListField(label=_("统一查询路由规则"), default=[])),
        (
            "ALARM_BACKEND_CLUSTER_ROUTING_RULES",
            slz.ListField(
                label=_("集群路由规则"),
                default=[
                    {"target_type": "biz", "cluster_name": "default", "matcher_type": "true", "matcher_config": None}
                ],
            ),
        ),
        ("FRONTEND_REPORT_DATA_ID", slz.IntegerField(label=_("前端上报数据ID"), default=0)),
        ("FRONTEND_REPORT_DATA_TOKEN", slz.CharField(label=_("前端上报数据Token"), default="")),
        ("FRONTEND_REPORT_DATA_HOST", slz.CharField(label=_("前端上报地址"), default="")),
        ("QOS_DROP_ALARM_THREADHOLD", slz.IntegerField(label=_("流控丢弃阈值"), default=3)),
        ("QOS_DROP_ACTION_THRESHOLD", slz.IntegerField(label=_("处理动作流控丢弃阈值"), default=100)),
        ("QOS_DROP_ACTION_WINDOW", slz.IntegerField(label=_("处理动作流控窗口大小(秒)"), default=60)),
        ("QOS_ALERT_THRESHOLD", slz.IntegerField(label=_("告警生成流控丢弃阈值"), default=100)),
        ("QOS_ALERT_WINDOW", slz.IntegerField(label=_("告警生成流控窗口大小(秒)"), default=60)),
        ("SAAS_APP_CODE", slz.CharField(label=_("SAAS 应用码"), default=settings.APP_CODE)),
        ("SAAS_SECRET_KEY", slz.CharField(label=_("SAAS 应用密钥"), default=settings.SECRET_KEY)),
        ("CELERY_WORKERS", slz.IntegerField(label=_("后台处理队列的子进程数（需重启scheduler:*）"), default=0, min_value=0)),
        ("HEALTHZ_ALARM_CONFIG", slz.JSONField(label=_("healthz告警配置"), default={}, binary=True)),
        ("ENABLE_MESSAGE_QUEUE", slz.BooleanField(label=_("是否开启告警通知队列"), default=True)),
        ("COMPATIBLE_ALARM_FORMAT", slz.BooleanField(label=_("是否兼容老版本数据字段格式"), default=False)),
        ("ENABLE_RESOURCE_DATA_COLLECT", slz.BooleanField(label=_("是否开启Resource数据收集"), default=False)),
        ("RESOURCE_DATA_COLLECT_RATIO", slz.IntegerField(label=_("Resource数据采样率"), default=0)),
        ("DIMENSION_COLLECT_THRESHOLD", slz.IntegerField(label=_("同维度汇总阈值"), default=2)),
        ("DIMENSION_COLLECT_WINDOW", slz.IntegerField(label=_("同维度汇总时间窗口"), default=120)),
        ("MULTI_STRATEGY_COLLECT_THRESHOLD", slz.IntegerField(label=_("多策略汇总阈值"), default=3)),
        ("MULTI_STRATEGY_COLLECT_WINDOW", slz.IntegerField(label=_("多策略汇总时间窗口"), default=120)),
        ("WEBHOOK_TIMEOUT", slz.IntegerField(label=_("Webhook超时时间"), default=3)),
        ("ENABLE_DEFAULT_STRATEGY", slz.BooleanField(label=_("是否开启默认策略"), default=True)),
        ("IS_ENABLE_VIEW_CMDB_LEVEL", slz.BooleanField(label=_("是否开启前端视图部分的CMDB预聚合"), default=False)),
        # === BKDATA & AIOPS 相关配置 开始 ===
        ("AIOPS_BIZ_WHITE_LIST", slz.ListField(label=_("开启智能异常算法的业务白名单"), default=[])),
        ("BK_DATA_PROJECT_ID", slz.IntegerField(label=_("监控在计算平台使用的公共项目ID"), default=1)),
        ("BK_DATA_BK_BIZ_ID", slz.IntegerField(label=_("监控在计算平台使用的公共业务ID"), default=2)),
        (
            "BK_DATA_RT_ID_PREFIX",
            slz.CharField(label=_("监控在计算平台的数据表前缀(prefix)"), default=settings.BKAPP_DEPLOY_PLATFORM),
        ),
        ("BK_DATA_PROJECT_MAINTAINER", slz.CharField(label=_("计算平台项目的维护人员"), default="admin")),
        ("BK_DATA_DATA_EXPIRES_DAYS", slz.IntegerField(label=_("计算平台中结果表(MYSQL)默认保存天数"), default=30)),
        ("BK_DATA_DATA_EXPIRES_DAYS_BY_HDFS", slz.IntegerField(label=_("计算平台中结果表(HDFS)默认保存天数"), default=180)),
        (
            "BK_DATA_MYSQL_STORAGE_CLUSTER_NAME",
            slz.CharField(label=_("计算平台 MYSQL 存储集群名称"), default="default", allow_blank=True),
        ),
        (
            "BK_DATA_HDFS_STORAGE_CLUSTER_NAME",
            slz.CharField(label=_("计算平台 HDFS 存储集群名称"), default="hdfs-default", allow_blank=True),
        ),
        (
            "BK_DATA_DRUID_STORAGE_CLUSTER_NAME",
            slz.CharField(label=_("计算平台 DRUID 存储集群名称"), default="", allow_blank=True),
        ),
        ("BK_DATA_KAFKA_BROKER_URL", slz.CharField(label=_("与计算平台对接的消息队列BROKER地址"), default="")),
        ("BK_DATA_INTELLIGENT_DETECT_DELAY_WINDOW", slz.IntegerField(label=_("数据接入计算平台后dataflow延时时间"), default=5)),
        ("BK_DATA_SCENE_ID_INTELLIGENT_DETECTION", slz.IntegerField(label=_("计算平台单指标异常检测场景ID"), default=0)),
        ("BK_DATA_SCENE_ID_TIME_SERIES_FORECASTING", slz.IntegerField(label=_("计算平台时序预测场景ID"), default=0)),
        ("BK_DATA_SCENE_ID_ABNORMAL_CLUSTER", slz.IntegerField(label=_("计算平台离群检测场景ID"), default=0)),
        ("BK_DATA_SCENE_ID_MULTIVARIATE_ANOMALY_DETECTION", slz.IntegerField(label=_("计算平台多指标异常检测场景ID"), default=0)),
        ("BK_DATA_SCENE_ID_METRIC_RECOMMENDATION", slz.IntegerField(label=_("计算平台指标推荐场景ID"), default=0)),
        ("BK_DATA_FLOW_CLUSTER_GROUP", slz.CharField(label=_("计算平台 dataflow 计算集群组"), default="default_inland")),
        ("BK_DATA_REALTIME_NODE_WAIT_TIME", slz.IntegerField(label=_("计算平台 实时节点等待时间"), default=10)),
        (
            "BK_DATA_DIMENSION_DRILL_PROCESSING_ID",
            slz.CharField(label=_("维度下钻 API Serving 请求的数据处理ID"), default="multidimension_drill"),
        ),
        (
            "BK_DATA_METRIC_RECOMMEND_PROCESSING_ID_PREFIX",
            slz.CharField(label=_("指标推荐 API Serving 请求的数据处理ID前缀"), default="metric_recommendation"),
        ),
        (
            "BK_DATA_METRIC_RECOMMEND_SOURCE_PROCESSING_ID",
            slz.CharField(label=_("指标推荐 FLOW 数据源"), default="ieod_system_multivariate_delay"),
        ),
        # === AIOPS 相关配置 结束 ===
        ("EVENT_NO_DATA_TOLERANCE_WINDOW_SIZE", slz.IntegerField(label=_("Event 模块最大容忍无数据周期数"), default=5)),
        (
            "ANOMALY_RECORD_COLLECT_WINDOW",
            slz.IntegerField(label=_("单事件异常点清理触发计数"), default=100),
        ),
        ("SAAS_VERSION", slz.CharField(label=_("SaaS版本号"), default="unknown")),
        ("BACKEND_VERSION", slz.CharField(label=_("Backend版本号"), default="unknown")),
        ("WXWORK_BOT_WEBHOOK_URL", slz.CharField(label=_("企业微信机器人回调地址"), default="", allow_blank=True)),
        ("ACCESS_TIME_PER_WINDOW", slz.IntegerField(label=_("access模块策略拉取耗时限制（每10分钟）"), default=30)),
        ("RSA_PRIVATE_KEY", slz.CharField(label=_("RSA PRIVATE KEY"), default=settings.RSA_PRIVATE_KEY)),
        ("SKIP_PLUGIN_DEBUG", slz.BooleanField(label=_("跳过插件调试"), default=False)),
        ("BKUNIFYLOGBEAT_METRIC_BIZ", slz.IntegerField(label=_("日志采集器指标所属业务"), default=0)),
        ("EVENT_RELATED_INFO_LENGTH", slz.IntegerField(label=_("事件关联信息截断长度"), default=1024)),
        (
            "NOTICE_MESSAGE_MAX_LENGTH",
            slz.DictField(label=_("各渠道通知消息最大长度"), default={"rtx": 4000, "wxwork-bot": 5120}),
        ),
        ("STRATEGY_NOTICE_BUCKET_WINDOW", slz.IntegerField(label=_("策略告警限流窗口(s)"), default=60)),
        ("STRATEGY_NOTICE_BUCKET_SIZE", slz.IntegerField(label=_("策略告警限流数量"), default=100)),
        ("GLOBAL_SHIELD_ENABLED", slz.BooleanField(label=_("是否开启全局告警屏蔽"), default=False)),
        ("BIZ_WHITE_LIST_FOR_3RD_EVENT", slz.ListField(label=_("第三方事件接入业务白名单"), default=[])),
        ("TIME_SERIES_METRIC_EXPIRED_DAYS", slz.IntegerField(label=_("自定义指标过期时间"), default=30)),
        ("FETCH_TIME_SERIES_METRIC_INTERVAL_SECONDS", slz.IntegerField(label=_("获取自定义指标的间隔时间"), default=7200)),
        ("ENABLE_BKDATA_METRIC_CACHE", slz.BooleanField(label=_("是否开启数据平台指标缓存"), default=True)),
        (
            "TRANSLATE_SNMP_TRAP_DIMENSIONS",
            slz.BooleanField(label=_("是否翻译snmp trap的oid维度"), default=settings.TRANSLATE_SNMP_TRAP_DIMENSIONS),
        ),
        ("FAKE_EVENT_AGG_INTERVAL", slz.IntegerField(label=_("事件型时序检测周期(默认60s，最小10s)"), default=60)),
        ("ENABLE_CREATE_CHAT_GROUP", slz.CharField(label=_("是否允许一键拉群"), default=False)),
        ("BK_PLUGIN_APP_INFO", slz.JSONField(label=_("蓝鲸插件实际调用APP"), default={})),
        ("DELAY_TO_GET_RELATED_INFO_INTERVAL", slz.IntegerField(label=_("重新获取关联信息时间间隔(ms)"), default=500)),
        ("NOISE_REDUCE_TIMEDELTA", slz.IntegerField(label=_("降噪时间窗口(min)"), default=5)),
        ("NO_DATA_ALERT_EXPIRED_TIMEDELTA", slz.IntegerField(label=_("无数据告警过期时间窗口(s)"), default=24 * 60 * 60)),
        ("APM_APP_DEFAULT_ES_STORAGE_CLUSTER", slz.IntegerField(label=_("APM应用默认集群ID"), default=-1)),
        ("APM_APP_DEFAULT_ES_RETENTION", slz.IntegerField(label=_("APM应用默认过期时间"), default=7)),
        ("APM_APP_DEFAULT_ES_SLICE_LIMIT", slz.IntegerField(label=_("APM应用ES索引集默认切分大小"), default=500)),
        ("APM_APP_DEFAULT_ES_REPLICAS", slz.IntegerField(label=_("APM应用默认副本数"), default=0)),
        ("APM_APP_DEFAULT_ES_SHARDS", slz.IntegerField(label=_("APM应用默认索引分片数"), default=3)),
        ("APM_APP_BKDATA_OPERATOR", slz.CharField(label=_("APM应用操作数据平台所用到的用户名"), default="")),
        ("APM_APP_BKDATA_VIRTUAL_METRIC_PROJECT_ID", slz.IntegerField(label=_("APM虚拟指标项目id"), default=0)),
        ("APM_APP_BKDATA_VIRTUAL_METRIC_STORAGE_EXPIRE", slz.IntegerField(label=_("APM虚拟指标存储过期时间"), default=30)),
        ("APM_APP_BKDATA_VIRTUAL_METRIC_STORAGE", slz.CharField(label=_("APM虚拟指标存储集群"), default="")),
        ("APM_APP_PRE_CALCULATE_STORAGE_SLICE_SIZE", slz.IntegerField(label=_("APM预计算存储ES分片大小"), default=500)),
        ("APM_APP_PRE_CALCULATE_STORAGE_RETENTION", slz.IntegerField(label=_("APM预计算存储ES过期时间"), default=30)),
        ("APM_APP_PRE_CALCULATE_STORAGE_SHARDS", slz.IntegerField(label=_("APM预计算存储ES分片数"), default=3)),
        ("IS_FTA_MIGRATED", slz.BooleanField(label=_("是否已经迁移自愈"), default=False)),
        ("FTA_MIGRATE_BIZS", slz.ListField(label=_("已经迁移的业务名单"), default=[])),
        ("APM_APP_QUERY_TRACE_MAX_COUNT", slz.IntegerField(label=_("APM单次查询TraceID最大的数量"), default=10)),
        ("SPECIFY_AES_KEY", slz.CharField(label=_("特别指定的AES使用密钥"), default="")),
        ("ENTERPRISE_CODE", slz.CharField(label=_("企业代号"), default="")),
        ("LINUX_GSE_AGENT_PATH", slz.CharField(label=_("Linux Agent 安装路径"), default="/usr/local/gse/")),
        ("LINUX_PLUGIN_DATA_PATH", slz.CharField(label=_("Linux 数据保存路径"), default="/var/lib/gse")),
        ("LINUX_PLUGIN_PID_PATH", slz.CharField(label=_("Linux PID 文件保存路径"), default="/var/run/gse")),
        ("LINUX_PLUGIN_LOG_PATH", slz.CharField(label=_("Linux 日志保存路径"), default="/var/log/gse")),
        ("LINUX_GSE_AGENT_IPC_PATH", slz.CharField(label=_("Linux IPC 路径"), default="/var/run/ipc.state.report")),
        ("WINDOWS_GSE_AGENT_PATH", slz.CharField(label=_("Windows Agent 安装路径"), default="C:\\gse")),
        ("WINDOWS_GSE_AGENT_IPC_PATH", slz.CharField(label=_("Windows IPC 路径"), default="127.0.0.1:47000")),
        ("WECOM_ROBOT_BIZ_WHITE_LIST", slz.ListField(label=_("分级告警业务白名单"), default=[])),
        ("WECOM_ROBOT_ACCOUNT", slz.DictField(label=_("分级告警企业微信机器人账户"), default={})),
        ("IS_WECOM_ROBOT_ENABLED", slz.BooleanField(label=_("是否启用分级机器人告警"), default=False)),
        ("MD_SUPPORTED_NOTICE_WAYS", slz.ListField(label=_("支持MD的通知方式列表"), default=["wxwork-bot"])),
        ("BK_DATA_PLAN_ID_INTELLIGENT_DETECTION", slz.IntegerField(label=_("ai设置单指标异常检测默认plan id"), default=0)),
        (
            "BK_DATA_PLAN_ID_MULTIVARIATE_ANOMALY_DETECTION",
            slz.IntegerField(label=_("ai设置多指标异常检测默认plan id"), default=0),
        ),
        (
            "BK_DATA_PLAN_ID_METRIC_RECOMMENDATION",
            slz.IntegerField(label=_("指标推荐默认plan id"), default=0),
        ),
        (
            "BK_DATA_MULTIVARIATE_HOST_RT_ID",
            slz.CharField(
                label=_("多指标异常检测通用flow结果输出表"), default=f"2_{settings.BKAPP_DEPLOY_PLATFORM}_host_multivariate"
            ),
        ),
        (
            "BK_DATA_ROBOT_LINK_LIST",
            slz.ListField(
                label=_("机器人默认跳转链接列表"),
                default=[
                    {
                        "link": "https://bk.tencent.com/docs/document/7.0/248/40001",
                        "name": _("产品白皮书"),
                        "icon_name": "icon-bangzhuzhongxin",
                    }
                ],
            ),
        ),
        ("WECOM_ROBOT_CONTENT_LENGTH", slz.IntegerField(label=_("分级机器人内容最大长度（0表示不限制）"), default=0)),
        (
            "ALARM_DISABLE_STRATEGY_RULES",
            slz.JSONField(
                label=_('告警后台禁用策略规则{"strategy_ids":[],"bk_biz_ids":[],"data_source_label":"","data_type_label":""}'),
                default=[],
            ),
        ),
        ("ACCESS_DATA_TIME_DELAY", slz.IntegerField(label=_("access数据拉取延迟时间(s)"), default=10)),
        ("KAFKA_AUTO_COMMIT", slz.BooleanField(label="kafka是否自动提交", default=True)),
        ("MAX_BUILD_EVENT_NUMBER", slz.IntegerField(label="单次告警生成任务处理的event数量", default=0)),
        ("HOST_DYNAMIC_FIELDS", slz.ListField(label=_("主机动态属性"), default=[])),
        ("METRIC_CACHE_TASK_PERIOD", slz.IntegerField(label="指标缓存任务周期(min)", default=10)),
        ("LAST_MIGRATE_VERSION", slz.CharField(label=_("最后一次迁移版本"), default="")),
        ("EXTERNAL_APIGW_PUBLIC_KEY", slz.CharField(label=_("外部APIGW公钥"), default="")),
        ("APIGW_PUBLIC_KEY", slz.CharField(label=_("APIGW公钥"), default="")),
        ("GSE_MANAGERS", slz.ListField(label=_("GSE平台管理员"), default=[])),
        ("OFFICIAL_PLUGINS_MANAGERS", slz.ListField(label=_("官方插件管理员"), default=[])),
        (
            "HEADER_FOOTER_CONFIG",
            slz.JSONField(
                label=_("header footer 配置"),
                default={
                    "header": [{"zh-cn": "监控平台 | 腾讯蓝鲸智云", "en": "Monitor | Tencent BlueKing"}],
                    "footer": [
                        {
                            "zh-cn": [
                                {
                                    "text": "技术支持",
                                    "link": "https://wpa1.qq.com/KziXGWJs?_type=wpa&qidian=true",
                                },
                                {"text": "社区论坛", "link": "https://bk.tencent.com/s-mart/community/"},
                                {"text": "产品官网", "link": "https://bk.tencent.com/index/"},
                            ],
                            "en": [
                                {
                                    "text": "Support",
                                    "link": "http://wpa.b.qq.com/cgi/wpa.php?"
                                    "ln=1&key=XzgwMDgwMjAwMV80NDMwOTZfODAwODAyMDAxXzJf",
                                },
                                {"text": "Forum", "link": "https://bk.tencent.com/s-mart/community"},
                                {"text": "Official", "link": "https://bk.tencent.com/"},
                            ],
                        }
                    ],
                    "copyright": "Copyright © 2012-{current_year} Tencent BlueKing. All Rights Reserved. ",
                },
            ),
        ),
        ("SHOW_REALTIME_STRATEGY", slz.BooleanField(label="是否默认展示策略模块实时功能", default=False)),
        ("BKDATA_CMDB_LEVEL_TABLES", slz.ListField(label=_("数据平台CMDB聚合表"), default=[])),
        ("MAX_TASK_PROCESS_NUM", slz.IntegerField(label="后台任务多进程并行数量", default=1)),
        ("MAX_TS_METRIC_TASK_PROCESS_NUM", slz.IntegerField(label="指标后台任务多进程并行数量", default=1)),
        ("QUERY_VM_SPACE_UID_LIST", slz.ListField(label="通过 vm 查询的空间列表", default=[])),
        ("MAIL_REPORT_FULL_PAGE_WAIT_TIME", slz.IntegerField(label="邮件报表整屏渲染等待时间", default=60)),
        ("KUBERNETES_CMDB_ENRICH_BIZ_WHITE_LIST", slz.ListField(label=_("容器关联关系丰富业务白名单"), default=[])),
        ("IS_RESTRICT_DS_BELONG_SPACE", slz.BooleanField(label="是否限制数据源归属具体空间", default=True)),
        ("MAX_FIELD_PAGE_SIZE", slz.IntegerField(label="最大的指标分片页查询的大小", default=1000)),
        ("BKPAAS_AUTHORIZED_DATA_ID_LIST", slz.ListField(label="需要授权的 PaaS 创建的数据源 ID", default=[])),
        ("ACCESS_DBM_RT_SPACE_UID", slz.ListField(label="访问 dbm 结果表的空间 UID", default=[])),
    ]
)

STANDARD_CONFIGS = OrderedDict(
    [
        ("ENABLE_PING_ALARM", slz.BooleanField(label=_("全局 Ping 告警开关"), default=True)),
        ("ENABLE_AGENT_ALARM", slz.BooleanField(label=_("全局 Agent失联 告警开关"), default=True)),
        ("ALARM_MOBILE_NOTICE_WAY", slz.ListField(label=_("移动端告警的通知渠道"), default=[])),
        ("ALARM_MOBILE_URL", slz.CharField(label=_("移动端告警访问链接"), default="")),
        (
            "FILE_SYSTEM_TYPE_IGNORE",
            slz.ListField(
                label=_("全局磁盘类型屏蔽配置"), default=["iso9660", "tmpfs", "udf"], help_text=_("可通过该配置屏蔽指定类型的磁盘的告警")
            ),
        ),
        (
            "ANOMALY_RECORD_SAVE_DAYS",
            slz.IntegerField(
                label=_("异常记录保留天数"),
                default=30,
                min_value=1,
                help_text=_("异常记录表用于展示告警事件的收敛记录，清理后会导致历史事件的流转记录展示不全。" "后台每分钟都会对过期异常记录进行清理，每次清理不超过 1000 条。"),
            ),
        ),
        ("GRAPH_WATERMARK", slz.BooleanField(label=_("显示图表水印"), default=True, help_text=_("开启后，页面上的数据图表将带上当前用户名的水印"))),
        ("ENABLED_NOTICE_WAYS", slz.ListField(label=_("告警通知渠道"), default=["weixin", "mail", "sms", "voice"])),
        (
            "MESSAGE_QUEUE_DSN",
            slz.CharField(
                label=_("告警通知消息队列DSN"),
                default="",
                allow_blank=True,
                help_text=_('例如 "redis://:${passowrd}@${host}:${port}/${db}/${key}" ，' "注意用户名和密码需要进行 urlencode"),
            ),
        ),
        (
            "TS_DATA_SAVED_DAYS",
            slz.IntegerField(
                label=_("监控采集数据保存天数"),
                default=30,
                min_value=1,
                help_text=_("采集上报数据在influxdb的保留天数，" "超出保留天数的将被清理。数值越大对存储资源要求越高"),
            ),
        ),
        (
            "MESSAGE_QUEUE_MAX_LENGTH",
            slz.IntegerField(label=_("通知消息队列长度上限"), default=0, help_text=_("若队列长度超出该值，则丢弃旧消息。值为 0 代表无长度限制")),
        ),
        ("IS_AUTO_DEPLOY_CUSTOM_REPORT_SERVER", slz.BooleanField(label=_("是否自动部署自定义上报服务"), default=True)),
        ("CUSTOM_REPORT_DEFAULT_PROXY_IP", slz.ListField(label=_("自定义上报默认服务器"), default=[])),
        ("CUSTOM_REPORT_DEFAULT_PROXY_DOMAIN", slz.ListField(label=_("自定义上报默认服务器(域名显示)"), default=[])),
        ("PING_SERVER_TARGET_NUMBER_LIMIT", slz.IntegerField(label=_("单台机器Ping采集目标数量限制"), default=6000)),
        (
            "MAX_AVAILABLE_DURATION_LIMIT",
            slz.IntegerField(label=_("拨测任务最大超时限制(ms)"), default=60000, min_value=1000),
        ),
        ("HOST_DISABLE_MONITOR_STATES", slz.ListField(label=_("主机不监控字段列表"), default=[_("备用机"), _("测试中"), _("故障中")])),
        ("HOST_DISABLE_NOTICE_STATES", slz.ListField(label=_("主机不告警字段列表"), default=[_("运营中[无告警]"), _("开发中[无告警]")])),
        (
            "OS_GLOBAL_SWITCH",
            slz.MultipleChoiceField(
                label=_("操作系统全局开关"),
                default=["linux", "windows", "linux_aarch64"],
                choices=(
                    ("linux", "Linux"),
                    ("windows", "Windows"),
                    ("aix", "AIX"),
                    ("linux_aarch64", "Linux_aarch64"),
                ),
            ),
        ),
        ("IS_ALLOW_ALL_CMDB_LEVEL", slz.BooleanField(label=_("是否允许所有数据源配置CMDB聚合"), default=False)),
        ("ES_RETAIN_INVALID_ALIAS", slz.BooleanField(label=_("当 ES 存在不合法别名时，是否保留该索引"), default=True)),
        ("DEMO_BIZ_ID", slz.IntegerField(label=_("Demo业务ID"), default=0)),
        ("DEMO_BIZ_WRITE_PERMISSION", slz.BooleanField(label=_("Demo业务写权限"), default=False)),
        ("DEMO_BIZ_APPLY", slz.CharField(label=_("业务接入链接"), default="", allow_blank=True)),
        ("APM_ACCESS_URL", slz.CharField(label=_("APM接入链接"), default="", allow_blank=True)),
        ("APM_BEST_PRACTICE_URL", slz.CharField(label=_("APM最佳实践链接"), default="", allow_blank=True)),
        ("APM_METRIC_DESCRIPTION_URL", slz.CharField(label=_("APM指标说明"), default="", allow_blank=True)),
        ("APM_APDEX_T_VALUE", slz.IntegerField(label=_("APM平台apdex_t默认配置"), default=800)),
        ("APM_SAMPLING_PERCENTAGE", slz.IntegerField(label=_("APM中默认采样比例"), default=100)),
        ("APM_APP_QPS", slz.IntegerField(label=_("APM中应用默认QPS"), default=500)),
        ("APM_CUSTOM_EVENT_REPORT_CONFIG", slz.DictField(label=_("APM事件上报配置"), default={})),
        ("APM_TRACE_DIAGRAM_CONFIG", slz.DictField(label=_("APM Trace 检索图表配置"), default={})),
        ("APM_DORIS_STORAGE_CONFIG", slz.DictField(label=_("APM Doris 存储配置"), default={})),
        ("APM_PROFILING_ENABLED_APPS", slz.DictField(label=_("APM Profiling 开启应用白名单"), default={})),
        ("APM_EBPF_ENABLED", slz.BooleanField(label=_("APM 前端是否开启EBPF功能"), default=False)),
        ("WXWORK_BOT_NAME", slz.CharField(label=_("蓝鲸监控机器人名称"), default="BK-Monitor", allow_blank=True)),
        ("WXWORK_BOT_SEND_IMAGE", slz.BooleanField(label=_("蓝鲸监控机器人发送图片"), default=True)),
        ("THROTTLE_APP_WHITE_LIST", slz.ListField(label=_("对数据查询API执行流控的APP白名单"), default=[])),
        ("COLLECTING_CONFIG_FILE_MAXSIZE", slz.IntegerField(label=_("采集配置文件参数最大值(M)"), default=2)),
        (
            "UNIFY_QUERY_URL",
            slz.CharField(label=_("统一查询模块地址(后台自动刷新)"), default="http://unify-query.bkmonitorv3.service.consul:10205/"),
        ),
        (
            "INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME",
            slz.CharField(label=_("influxdb proxy默认使用集群名"), default="default", allow_blank=False),
        ),
        (
            "INFLUXDB_DEFAULT_PROXY_CLUSTER_NAME_FOR_K8S",
            slz.CharField(label=_("influxdb proxy给k8s默认使用集群名"), default="default", allow_blank=False),
        ),
        (
            "DEFAULT_TRANSFER_CLUSTER_ID",
            slz.CharField(label=_("默认Transfer集群ID"), default="default", allow_blank=False),
        ),
        (
            "TRANSFER_BUILTIN_CLUSTER_ID",
            slz.CharField(label=_("Transfer内置的集群ID，不需要在页面展示(多个以逗号分隔)"), default="", allow_blank=True),
        ),
        (
            "DEFAULT_TRANSFER_CLUSTER_ID_FOR_K8S",
            slz.CharField(label=_("默认容器监控使用的Transfer集群ID"), default="default", allow_blank=False),
        ),
        ("TRANSFER_ALLOW_MAX_OFFSET_DELTA", slz.CharField(label=_("transfer消费kafka的offset告警阈值"), default=10000)),
        ("TRANSFER_CONSUMER_GROUP_ID", slz.CharField(label=_("transfer默认消费组"), default="bkmonitorv3_transfer")),
        # 订阅报表相关配置
        ("MAIL_REPORT_BIZ", slz.CharField(label=_("订阅报表默认业务ID(为0时关闭)"), default="0")),
        ("MAIL_REPORT_ALL_BIZ_USERNAMES", slz.ListField(label=_("全业务订阅报表接收人"), default=[])),
        ("MONITOR_MANAGERS", slz.ListField(label=_("监控平台管理员"), default=[])),
        ("DISABLE_BIZ_ID", slz.ListField(label=_("业务黑名单"), default=[])),
        ("BCS_GRAY_CLUSTER_ID_LIST", slz.ListField(label=_("BCS集群灰度ID名单"), default=[])),
        ("BCS_API_DATA_SOURCE", slz.ChoiceField(label=_("BCS集群元数据获取方式"), default="db", choices=("db", "api"))),
        ("ENABLE_BCS_GRAY_CLUSTER", slz.BooleanField(label=_("是否启用BCS集群灰度模式"), default=False)),
        ("NOTICE_TITLE", slz.CharField(label=_("告警通知标题"), default="蓝鲸监控")),
        ("DEFAULT_KAFKA_STORAGE_CLUSTER_ID", slz.CharField(label=_("默认 kafka 存储集群ID"), default=None, allow_null=True)),
        ("BCS_KAFKA_STORAGE_CLUSTER_ID", slz.CharField(label=_("BCS kafka 存储集群ID"), default=None, allow_null=True)),
        ("BCS_CUSTOM_EVENT_STORAGE_CLUSTER_ID", slz.CharField(label=_("自定义上报存储集群ID"), default=None, allow_null=True)),
        ("ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA", slz.BooleanField(label=_("是否启用计算平台处理influxdb降精度流程"), default=False)),
        (
            "ENABLE_UNIFY_QUERY_DOWNSAMPLE_BY_BKDATA",
            slz.BooleanField(label=_("是否启用unify-query查询计算平台降精度数据"), default=False),
        ),
        ("FTA_ES_SLICE_SIZE", slz.IntegerField(label=_("自愈ES分裂索引的大小(G)"), default=50)),
        ("FTA_ES_RETENTION", slz.IntegerField(label=_("自愈ES数据保留时间"), default=365)),
        ("DOUBLE_CHECK_SUM_STRATEGY_IDS", slz.ListField(label=_("适用 SUM 聚合方法二次确认的策略ID列表"), default=[])),
        ("SMS_CONTENT_LENGTH", slz.IntegerField(label=_("发送短信内容最大长度（0表示不限制）"), default=0)),
        ("IS_ACCESS_BK_DATA", slz.BooleanField(label=_("是否开启与计算平台的功能对接"), default=False)),
        ("BCS_CLUSTER_BK_ENV_LABEL", slz.CharField(label=_("BCS 集群配置来源标签"), default="")),
        # IPv6相关配置
        ("IPV6_SUPPORT_BIZ_LIST", slz.ListField(label=_("支持ipv6的业务列表"), default=[])),
        (
            "HOST_DISPLAY_FIELDS",
            slz.ListField(label=_("主机展示字段"), default=["bk_host_innerip", "bk_host_name", "bk_host_innerip_v6"]),
        ),
        ("HOST_VIEW_DISPLAY_FIELDS", slz.ListField(label=_("主机视图展示字段"), default=["display_name", "bk_host_name"])),
        ("USE_GSE_AGENT_STATUS_NEW_API", slz.BooleanField(label=_("是否使用新的gse agent状态接口"), default=True)),
        (
            "UPTIMECHECK_OUTPUT_FIELDS",
            slz.ListField(label=_("拨测默认输出字段"), default=["bk_host_innerip", "bk_host_innerip_v6"]),
        ),
        # 接入计算平台配置
        ("DEFAULT_BKDATA_BIZ_ID", slz.IntegerField(label="接入计算平台使用的业务 ID", default=0)),
        ("IS_SUBSCRIPTION_ENABLED", slz.BooleanField(label="是否开启采集订阅巡检功能", default=True)),
    ]
)

GLOBAL_CONFIGS = list(ADVANCED_OPTIONS.keys()) + list(STANDARD_CONFIGS.keys())


def init_or_update_global_config(GlobalConfig):
    for config_key in GLOBAL_CONFIGS:
        if config_key in ADVANCED_OPTIONS:
            serializer = ADVANCED_OPTIONS[config_key]
            is_advanced = True
        elif config_key in STANDARD_CONFIGS:
            serializer = STANDARD_CONFIGS[config_key]
            is_advanced = False
        else:
            continue

        should_save = False

        try:
            config = GlobalConfig.objects.get(key=config_key)
        except GlobalConfig.DoesNotExist:
            config = GlobalConfig(
                key=config_key,
                value=serializer.default,
                is_advanced=is_advanced,
                is_internal=True,
            )
            should_save = True

        # 减少不必要的保存
        if config.description != serializer.label:
            config.description = serializer.label
            should_save = True

        data_type = serializer.__class__.__name__.replace("Field", "")
        if config.data_type != data_type:
            config.data_type = data_type
            should_save = True

        if config.options != serializer._kwargs:
            config.options = serializer._kwargs
            should_save = True

        # 更新配置是否为高级配置
        if config.is_advanced != is_advanced:
            config.is_advanced = is_advanced
            should_save = True

        if should_save:
            config.save()


def run(apps, *args):
    GlobalConfig = apps.get_model("bkmonitor.GlobalConfig")
    try:
        init_or_update_global_config(GlobalConfig)
    except DatabaseError:
        pass
