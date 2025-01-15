# -*- coding: utf-8 -*-
import json
import logging
from typing import Dict, List, Optional, Tuple

import influxdb.client
from django.conf import settings
from django.db import models
from django.template import Context, Template
from django.utils.functional import cached_property
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from influxdb.line_protocol import quote_ident

from bkmonitor.dataflow.auth import ensure_has_permission_with_rt_id
from bkmonitor.utils import consul
from bkmonitor.utils.common_utils import gen_bk_data_rt_id_without_biz_id
from bkmonitor.utils.db import JsonField
from bkmonitor.utils.time_tools import strftime_local
from core.drf_resource import api
from metadata import config
from metadata.utils import consul_tools, go_time
from metadata.utils.basic import getitems

from .constants import (
    AGG_FUNC_LIST,
    DATA_HUB_CLEAN_TEMPLATE,
    DEFAULT_RP_NAME,
    DEFAULT_TIME_FORMAT,
    DEFAULT_TIMESTAMP_LEN,
    DURATION,
    FIXED_METRIC_CALC_TEMPLATE,
    METRIC_VALUE_TYPE,
    MULTI_METRIC_CALC_TEMPLATE,
    RP_1M_RESOLUTION,
    RP_RESOLUTION_MAP,
    SECOND_TIMESTAMP_FORMAT,
    SECOND_TIMESTAMP_LEN,
    SINGLE_METRIC_CALC_TEMPLATE,
    SINGLE_METRIC_FIELD_TEMPLATE,
    SINGLE_METRIC_TEMPLATE,
    BkDataTaskStatus,
    MeasurementType,
)
from .data_source import DataSource, DataSourceOption, DataSourceResultTable
from .result_table import ResultTable, ResultTableField, ResultTableOption
from .storage import (
    InfluxDBClusterInfo,
    InfluxDBHostInfo,
    InfluxDBStorage,
    KafkaStorage,
)

logger = logging.getLogger(__name__)


class multidict(dict):
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value


class influxTool:
    instances = multidict()

    @classmethod
    def get_client(cls, database: str, host: str) -> influxdb.client.InfluxDBClient:
        return cls.instances[database][host]

    @classmethod
    def list_client(cls, database: str) -> List:
        """
        通过 database -> proxy_cluster_name -> host_name -> domain_name/port 获取InfluxDB的实例列表
        :return:
        """
        if not cls.instances[database]:
            logger.info(
                "influxdb database->[{}] load client".format(
                    database,
                )
            )
            for cluster in InfluxDBStorage.objects.filter(database=database).values("proxy_cluster_name").distinct():
                for info in (
                    InfluxDBClusterInfo.objects.filter(cluster_name=cluster["proxy_cluster_name"])
                    .values("host_name")
                    .distinct()
                ):
                    db = InfluxDBHostInfo.objects.get(host_name=info["host_name"])
                    client = influxdb.client.InfluxDBClient(host=db.domain_name, port=db.port)
                    if db.username != "" and db.password != "":
                        client.switch_user(username=db.username, password=db.password)
                    cls.instances[database][db.domain_name] = client
        return cls.instances[database]


class DownsampledDatabase(models.Model):
    """downsampled 数据库基本配置"""

    CONSUL_PATH = "%s/downsampled" % config.CONSUL_PATH

    database = models.CharField("数据库名", max_length=128, unique=True)
    tag_name = models.CharField("维度KEY", max_length=128, blank=True)
    tag_value = models.CharField("维度值", max_length=128, blank=True)
    enable = models.BooleanField("是否开启", default=False)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "降精度数据库配置"
        verbose_name_plural = "降精度数据库配置"

    @property
    def consul_config_path(self) -> str:
        """
        获取consul配置路径
        :return: eg: bk_monitorv3_community_production/metadata/downsampled/{database}/cq
        """

        return "/".join([self.CONSUL_PATH, self.database, "cq"])

    @property
    def consul_config_json(self) -> dict:
        """
        对tag_value去重排序
        :return:
        """
        new_tag_value = list(set(self.tag_value.split(",")))
        new_tag_value.sort()
        result_config = {
            "tag_name": self.tag_name,
            "tag_value": new_tag_value,
            "enable": self.enable,
            "last_modify_time": strftime_local(self.last_modify_time),
        }
        return result_config

    @classmethod
    def clean_consul_config(cls) -> None:
        """
        清理不存在的consul key
        1、查询 database 列表；
        2、遍历 consul 下是否 database 路径，如果不在上述 database 列表则删除；
        :return:
        """
        database_list = []
        for db in cls.objects.all():
            database_list.append(db.database)

        client = consul.BKConsul()
        # bk_monitorv3_community_production/metadata/downsampled/
        consul_keys = client.kv.get("/".join([cls.CONSUL_PATH, ""]), keys=True)[1]
        # consul 获取对应的值可能为空
        if not consul_keys:
            return

        for consul_key in consul_keys:
            key_list = consul_key.split("/")
            # 只处理 bk_monitorv3_community_production/metadata/downsampled/{database}/cq 的路径
            if len(key_list) == 5:
                if key_list[-2] not in database_list:
                    if client.kv.delete(consul_key):
                        client.kv.delete("/".join([consul_key, ""]))

                    logger.info(
                        "consul delete key->[{}],because database->[{}] not in database_list->[{}]".format(
                            consul_key,
                            key_list[-2],
                            database_list,
                        )
                    )
        return

    def refresh_consul_config(self) -> None:
        """
        同步刷新consul配置
        :return:
        """
        hash_consul = consul_tools.HashConsul()
        # bk_monitorv3_community_production/metadata/downsampled/{database}/cq
        hash_consul.put(key=self.consul_config_path, value=self.consul_config_json)
        return

    def sync_database_config(self) -> None:
        """
        同步降采样配置
        :return:
        """
        # 刷新consul
        self.refresh_consul_config()
        logger.debug("consul database->[%s] refresh consul config success." % self.database)
        return


class DownsampledRetentionPolicies(models.Model):
    """downsampled rp 基本配置"""

    CONSUL_PATH = "%s/downsampled" % config.CONSUL_PATH

    database = models.CharField("数据库名", max_length=128)
    name = models.CharField("RP名称", max_length=128)
    resolution = models.IntegerField("RP精度", default=0)
    duration = models.CharField("保存时间", max_length=120)
    replication = models.IntegerField("副本数", default=1)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    # rp 缓存
    retentionPolicies = multidict()

    class Meta:
        verbose_name = "降精度rp配置"
        verbose_name_plural = "降精度rp配置"
        unique_together = ("database", "name")

    @property
    def rp_name(self) -> str:
        """
        预留rp名定义入口
        :return:
        """
        return self.name

    @property
    def consul_config_path(self) -> str:
        """
        获取consul配置路径
        :return: eg: bk_monitorv3_community_production/metadata/downsampled/{database}/rp/{rp_name}
        """
        return "/".join([self.CONSUL_PATH, self.database, "rp", self.rp_name])

    @property
    def consul_config_json(self) -> dict:
        result_config = {
            "duration": self.duration,
            "resolution": self.resolution,
            "last_modify_time": strftime_local(self.last_modify_time),
        }
        return result_config

    @cached_property
    def check_status(self) -> bool:
        # 判断该数据库是否配置
        return DownsampledDatabase.objects.filter(database=self.database).exists()

    def refresh_consul_config(self) -> None:
        """
        同步刷新consul配置
        :return:
        """
        # 如果开启计算平台降精度，但是查询不使用计算平台计算后的数据时，rp 不需要写入 consul
        if settings.ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA and not settings.ENABLE_UNIFY_QUERY_DOWNSAMPLE_BY_BKDATA:
            return

        # 1. 获取consul的句炳
        hash_consul = consul_tools.HashConsul()

        # 2. 刷新当前RP的配置
        hash_consul.put(key=self.consul_config_path, value=self.consul_config_json)

    def get_retention_policy(self, host: str) -> Dict:
        """
        获取 rp
        :param host:
        :return:
        """
        if not self.retentionPolicies[host][self.database]:
            client = influxTool.get_client(database=self.database, host=host)
            res = client.get_list_retention_policies(database=self.database)
            logger.info(
                "influxdb host->[{}] database->[{}] get list retention policies".format(
                    host,
                    self.database,
                )
            )
            for r in res:
                self.retentionPolicies[host][self.database][r["name"]]["duration"] = r.get("duration", "")
        return self.retentionPolicies[host][self.database][self.rp_name]

    def create_retention_policy(self, host: str) -> None:
        """
        新增 rp
        :param host:
        :return:
        """
        client = influxTool.get_client(database=self.database, host=host)
        client.create_retention_policy(
            name=self.rp_name,
            database=self.database,
            duration=self.duration,
            replication=self.replication,
            default=False,
        )
        self.retentionPolicies[host][self.database][self.rp_name]["duration"] = self.duration
        logger.info(
            "influxdb database->[{}] rp->[{} | {}] is create on client->[{}]".format(
                self.database,
                self.rp_name,
                self.duration,
                client,
            )
        )

    def update_retention_policy(self, host: str) -> None:
        """
        更新 rp
        :param host:
        :return:
        """
        # 更新过期时间，这里要加shard_duration计算函数
        client = influxTool.get_client(database=self.database, host=host)
        client.alter_retention_policy(name=self.rp_name, database=self.database, duration=self.duration)
        self.retentionPolicies[host][self.database][self.rp_name]["duration"] = self.duration
        logger.info(
            "influxdb database->[{}] rp->[{} | {}] is updated on host->[{}]".format(
                self.database,
                self.rp_name,
                self.duration,
                host,
            )
        )

    def delete_retention_policy(self, host: str) -> None:
        """
        删除 rp
        :param host:
        :return:
        """
        if self.retentionPolicies[host][self.database][self.rp_name]:
            del self.retentionPolicies[host][self.database][self.rp_name]

        logger.info(
            "influxdb database->[{}] rp->[{}] is delete on host->[{}]".format(
                self.database,
                self.rp_name,
                host,
            )
        )

    def sync_retention_policy(self) -> None:
        """
        更新RP
        1. 通过 database -> cluster_name -> influxdb_instance 更新RP
        2. 同步刷新consul配置

        :return:
        """
        # 判断配置是否齐全
        if not self.check_status:
            return

        # 通过数据库名，获取对应InfluxDB Client
        for host in influxTool.list_client(database=self.database):
            # 判断rp是否已经存在
            rp = self.get_retention_policy(host=host)
            if not rp:
                # 如果没有找到, 那么需要创建一个RP
                self.create_retention_policy(host)
            else:
                duration = rp.get("duration", "")

                # 判断字段是否更新是否一致
                if duration != self.duration:
                    # 更新过期时间，这里要加shard_duration计算函数
                    self.update_retention_policy(host)

        # 刷新consul
        self.refresh_consul_config()
        logger.debug("consul database->[%s] refresh consul config success." % self.database)
        return

    @classmethod
    def clean_consul_config(cls, database: str) -> None:
        """
        清理掉不存在的consul key
        1、根据 database 从 DownsampledRetentionPolicies 获取 rp 列表；
        2、遍历 consul 当前 database 下的 rp，不在上述 rp 列表的则删除；
        :return:
        """
        if database == "":
            logger.error("clean_consul_config database is null")
            return

        rp_list = []
        for rp in cls.objects.filter(database=database):
            rp_list.append(rp.name)

        client = consul.BKConsul()
        consul_keys = client.kv.get("/".join([cls.CONSUL_PATH, database, "rp", ""]), keys=True)[1]
        for consul_key in consul_keys:
            key_list = consul_key.split("/")
            # 判断是否当前database，bk_monitor_enterprise_development/metadata/downsampled/demo/rp/5m
            if database == key_list[-3]:
                if key_list[-1] not in rp_list:
                    client.kv.delete(consul_key)
                    logger.info(
                        "consul delete key->[{}],because rp->[{}] not in rp_list->[{}]".format(
                            consul_key,
                            key_list[-1],
                            rp_list,
                        )
                    )
        return

    @classmethod
    def sync_all(cls, database: str) -> None:
        """
        清理 influxdb 的 rp 风险较高，暂不处理
        :param database: influxdb 数据库名称
        :return:
        """
        rp_name_list = []
        for rp in cls.objects.filter(database=database):
            # 同步当前数据
            rp.sync_retention_policy()
            rp_name_list.append(rp.name)

        # 不清理influxdb rp

        # 清理consul
        cls.clean_consul_config(database)
        return


class DownsampledContinuousQueries(models.Model):
    """downsampled measurement 配置"""

    CONSUL_PATH = "%s/downsampled" % config.CONSUL_PATH

    database = models.CharField("数据库名", max_length=128)
    measurement = models.CharField("表名", max_length=128, default="__all__")
    fields = models.CharField("字段列表", max_length=128)
    aggregations = models.CharField("聚合函数", max_length=128)
    source_rp = models.CharField("来源RP", max_length=128)
    target_rp = models.CharField("目标RP", max_length=128)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    # cq 缓存
    continuousQueries = multidict()

    class Meta:
        verbose_name = "降精度策略配置"
        verbose_name_plural = "降精度策略配置"
        unique_together = ("database", "measurement", "source_rp", "target_rp")

    @property
    def consul_config_path(self) -> list:
        """
        获取consul配置路径
        :return: eg:
        bk_monitor_enterprise_development/metadata/downsampled/{database}/cq
        /{measurement}/{field}/{aggregation}/{target_rp}
        """
        consul_key_list = []
        for field in self.field_list:
            for aggregation in self.aggregation_list:
                consul_key_list.append(
                    "/".join(
                        [self.CONSUL_PATH, self.database, "cq", self.measurement, field, aggregation, self.target_rp]
                    )
                )
        return consul_key_list

    @property
    def consul_config_json(self) -> dict:
        result_config = {
            "source_rp": self.source_rp,
            "last_modify_time": strftime_local(self.last_modify_time),
        }
        return result_config

    @property
    def cq_name_where(self) -> dict:
        result_list = {}
        downsampled_database = DownsampledDatabase.objects.get(database=self.database)
        if downsampled_database.tag_name != "" and downsampled_database.tag_value != "":
            for val in downsampled_database.tag_value.split(","):
                cq_name = "{}.{}.{}.{}".format(self.target_rp, self.measurement, downsampled_database.tag_name, val)
                result_list[cq_name] = "{}='{}'".format(quote_ident(downsampled_database.tag_name), val)
        else:
            cq_name = "{}.{}".format(self.target_rp, self.measurement)
            result_list[cq_name] = ""
        return result_list

    @property
    def table(self) -> str:
        if self.measurement == "__all__":
            return "/.*/"
        else:
            return self.measurement

    @cached_property
    def is_downsampled_rp(self) -> bool:
        return DownsampledRetentionPolicies.objects.filter(database=self.database, name=self.source_rp).exists()

    @property
    def aggregation_list(self) -> list:
        return self.aggregations.split(",")

    @property
    def field_list(self) -> list:
        return self.fields.split(",")

    @property
    def select(self) -> str:
        items = []
        for aggregation in self.aggregation_list:
            for field in self.field_list:
                new_field = field
                alias_filed = "{}_{}".format(aggregation, field)
                new_aggregation = aggregation
                if self.is_downsampled_rp:
                    new_field = alias_filed
                    # count之后的数据想要再次聚合必须要用sum
                    if aggregation.lower() == "count":
                        new_aggregation = "sum"

                items.append(
                    "{}({}) AS {}".format(
                        new_aggregation.lower(),
                        quote_ident(new_field),
                        alias_filed,
                    )
                )
        return ", ".join(items)

    @property
    def get_resample_for(self) -> str:
        t = go_time.parse_duration(self.target_rp)
        resampleFor = 2 * t
        return go_time.duration_string(resampleFor)

    @cached_property
    def check_status(self) -> bool:
        # 判断该数据库是否配置
        if not DownsampledDatabase.objects.filter(database=self.database).exists():
            logger.error("mysql database->[{}] is not exist", self.database)
            return False

        # 判断目标RP是否配置
        if not DownsampledRetentionPolicies.objects.filter(database=self.database, name=self.target_rp).exists():
            logger.error("mysql database->[{}] target_rp->[{}] is not exist", self.database, self.target_rp)
            return False
        return True

    @property
    def show_continuous_queries_ql(self) -> str:
        query_string = "SHOW CONTINUOUS QUERIES"
        return query_string

    @property
    def create_continuous_queries_ql(self) -> dict:
        query_list = {}
        for cq_name in self.cq_name_where:
            query_list[cq_name] = (
                "CREATE CONTINUOUS QUERY {} ON {} "
                "RESAMPLE EVERY {} FOR {} BEGIN "
                "SELECT {} INTO {}.{}.:MEASUREMENT "
                "FROM {}.{}.{}{} "
                "GROUP BY time({}), * END"
            ).format(
                quote_ident(cq_name),
                quote_ident(self.database),
                self.target_rp,
                self.get_resample_for,
                self.select,
                quote_ident(self.database),
                quote_ident(self.target_rp),
                quote_ident(self.database),
                quote_ident(self.source_rp),
                self.table,
                self.cq_name_where[cq_name] != "" and " WHERE {}".format(self.cq_name_where[cq_name]) or "",
                self.target_rp,
            )
        return query_list.items()

    @staticmethod
    def drop_continuous_query_ql(database: str, cq_name: str) -> str:
        query_string = "DROP CONTINUOUS QUERY {} ON {}".format(quote_ident(cq_name), quote_ident(database))
        return query_string

    def get_continuous_query(self, host: str, cq_name: str) -> str:
        """
        获取 cq
        :param host:
        :param cq_name:
        :return:
        """
        if not self.continuousQueries[host][self.database]:
            client = influxTool.get_client(database=self.database, host=host)
            res = client.query(self.show_continuous_queries_ql)
            for sk, cqs in res.items():
                for cq in list(cqs):
                    self.continuousQueries[host][sk[0]][cq["name"]] = cq["query"]
        return self.continuousQueries[host][self.database][cq_name]

    def create_continuous_query(self, host: str, cq_name: str, cq_query: str) -> None:
        """
        创建 cq
        :param host:
        :param cq_name:
        :param cq_query:
        :return:
        """
        # 如果开启计算平台降精度，则不需要创建 influxdb cq
        if settings.ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA:
            return

        client = influxTool.get_client(database=self.database, host=host)
        client.query(cq_query)
        self.continuousQueries[host][self.database][cq_name] = cq_query

    def update_continuous_query(self, host: str, cq_name: str, cq_query: str) -> None:
        """
        修改 cq
        :param host:
        :param cq_name:
        :param cq_query:
        :return:
        """
        # 如果开启计算平台降精度，则不需要更新 influxdb cq
        if settings.ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA:
            return

        client = influxTool.get_client(database=self.database, host=host)
        client.query(self.drop_continuous_query_ql(self.database, cq_name))
        client.query(cq_query)
        self.continuousQueries[host][self.database][cq_name] = cq_query

    def delete_continuous_query(self, host: str, cq_name: str) -> None:
        """
        删除 cq
        :param host:
        :param cq_name:
        :return:
        """
        client = influxTool.get_client(database=self.database, host=host)
        client.query(self.drop_continuous_query_ql(self.database, cq_name))

        if self.continuousQueries[host][self.database][cq_name]:
            del self.continuousQueries[host][self.database][cq_name]

    def refresh_consul_config(self) -> None:
        """
        同步consul配置
        1、查询consul当前 database/measurement 下的consul配置，清理多余的 filed 和 aggregation；
        2、根据 field_list 和 aggregation_list 组合，在指定的 database/measurement 下，写入对应的 fields 和 aggregation；
        :return:
        """
        # 如果开启计算平台降精度，但是查询不使用计算平台计算后的数据时，则不需要把 cq 写入 consul
        if settings.ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA and not settings.ENABLE_UNIFY_QUERY_DOWNSAMPLE_BY_BKDATA:
            return

        # 获取对应consul路径，清理多余的consul配置
        client = consul.BKConsul()
        # bk_monitor_enterprise_development/metadata/downsampled/demo/cq/__all__/
        consul_keys = client.kv.get("/".join([self.CONSUL_PATH, self.database, "cq", self.measurement, ""]), keys=True)[
            1
        ]
        if consul_keys:
            for consul_key in consul_keys:
                # bk_monitor_enterprise_development/metadata/downsampled/demo/cq/__all__/value/count/1h
                key_list = consul_key.split("/")
                if len(key_list) == 9:
                    measurement = key_list[-4]
                    if measurement == self.measurement:
                        field_key = key_list[-3]
                        aggregation_key = key_list[-2]
                        if field_key not in self.field_list or aggregation_key not in self.aggregation_list:
                            client.kv.delete(consul_key)
                            logger.info(
                                "consul key->[{}] deleted,because field_key->[{}] not in field_list->[{}] "
                                "or aggregation_key->[{}] not in aggregation_list->[{}]".format(
                                    consul_key,
                                    field_key,
                                    self.field_list,
                                    aggregation_key,
                                    self.aggregation_list,
                                )
                            )

        # 配置对应的consul
        hash_consul = consul_tools.HashConsul()
        for consul_key in self.consul_config_path:
            hash_consul.put(key=consul_key, value=self.consul_config_json)
            logger.info(
                "consul put key->[{}], value->[{}]".format(
                    consul_key,
                    self.consul_config_json,
                )
            )

    def sync_continuous_query(self) -> None:
        """
        更新降精度cq配置
        1、查询当前 InfluxDB 实例的所有cq配置；
        2、因为 cq 本身不支持修改，所以判断 cq 是否一致，如果不一致则先进行删除之后在添加；
        3、更新 consul 配置；
        :return:
        """
        if not self.check_status:
            return

        # 如果没有开启计算平台降精度，则需要创建或更新 influxdb cq
        if not settings.ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA:
            # 通过数据库名，获取对应InfluxDB Client
            for host in influxTool.list_client(database=self.database):
                for cq_name, cq_query in self.create_continuous_queries_ql:
                    cq = self.get_continuous_query(host, cq_name)
                    if not cq:
                        self.create_continuous_query(host, cq_name, cq_query)
                    else:
                        if cq_query != cq:
                            self.update_continuous_query(host, cq_name, cq_query)
        # 刷新consul
        self.refresh_consul_config()
        logger.debug("consul refresh_consul_config database->[%s]" % self.database)

    @classmethod
    def clean_consul_config(cls, database: str) -> None:
        """
        清理consul多余配置，consul_key 的组成路径包含 database/measurement/filed/aggregation/target_rp
        此逻辑处理 measurement 变化后的多余数据，field/aggregation/target_rp 在 refresh_consul_config 清理
        具体场景：
        1、DownsampledContinuousQueries 当前 database 下的 measurement 删除；
        2、DownsampledContinuousQueries 当前 database 不存在；
        :return:
        """
        if database == "":
            logger.error("database is null")
            return

        measurement_list = []
        target_rp_list = []
        for r in cls.objects.filter(database=database):
            if r.measurement not in measurement_list:
                measurement_list.append(r.measurement)
            if r.target_rp not in target_rp_list:
                target_rp_list.append(r.target_rp)

        client = consul.BKConsul()
        consul_keys = client.kv.get("/".join([cls.CONSUL_PATH, database, "cq", ""]), keys=True)[1]
        if consul_keys:
            for consul_key in consul_keys:
                # bk_monitor_enterprise_development/metadata/downsampled/demo/cq/__all__/value/count/1h
                key_list = consul_key.split("/")
                if len(key_list) == 9:
                    measurement = key_list[-4]
                    # 判断 measurement 是否存在
                    if measurement not in measurement_list:
                        client.kv.delete(consul_key)
                        logger.info(
                            "consul delete key->[{}],because measurement->[{}] not in measurement_list->[{}]".format(
                                consul_key,
                                measurement,
                                measurement_list,
                            )
                        )

                    # 判断 target_rp 是否存在
                    target_rp = key_list[-1]
                    if target_rp not in target_rp_list:
                        client.kv.delete(consul_key)
                        logger.info(
                            "consul delete key->[{}],because target_rp->[{}] not in target_rp_list->[{}]".format(
                                consul_key,
                                target_rp,
                                target_rp_list,
                            )
                        )

    @classmethod
    def sync_all(cls, database: str) -> None:
        """
        清理influxdb多余的cq配置，cq 的唯一ID：cq_name，由 database/measurement/tag_name/tag_value 拼装而成
        所以以上值有变化的场景需要清理，其中 database 的变化 在 DownsampledDatabase 处理
        具体场景：
        1. DownsampledContinuousQueries 表的数据删除；
        2. DownsampledContinuousQueries 表的 measurement 字段被修改；
        2. DownsampledDatabase 表的 tag_name 或 tag_value 字段被修改，
        :param database:
        :return:
        """

        cq_name_list = []
        for cq in cls.objects.filter(database=database):
            # 同步当前数据
            cq.sync_continuous_query()
            for cq_name in cq.cq_name_where:
                cq_name_list.append(cq_name)

        # 通过数据库名，获取对应InfluxDB Client
        for host in influxTool.list_client(database=database):
            for cq_name, cq_query in cls.continuousQueries[host][database].items():
                # cq 不存在需要删除
                if cq_name not in cq_name_list:
                    client = influxTool.get_client(database, host)
                    client.query(cls.drop_continuous_query_ql(database, cq_name))

        # 清理 consul
        cls.clean_consul_config(database)
        return

    @classmethod
    def refresh_consul_for_cq(cls, database: str):
        # 如果开启计算平台降精度，但是查询不使用计算平台计算后的数据时，则不需要把 cq 写入 consul
        if settings.ENABLE_METADATA_DOWNSAMPLE_BY_BKDATA and not settings.ENABLE_UNIFY_QUERY_DOWNSAMPLE_BY_BKDATA:
            return

        for cq in cls.objects.filter(database=database):
            # 同步当前数据
            cq.refresh_consul_config()
        # 清理 consul
        cls.clean_consul_config(database)


class DownsampleByDateFlow(models.Model):
    """借助计算平台能力进行数据降精度处理"""

    DEFAULT_BIZ_ID = 100147
    DEFAULT_PROJECT_ID = 8259
    DEFAULT_HDFS_CLUSTER = getattr(settings, "BKDATA_FLOW_HDFS_CLUSTER", "hdfsOnline4")
    DEFAULT_EXPIRE_DAYS = 3

    space_uid = models.CharField("空间唯一标识", max_length=128, blank=True, null=True)
    table_id = models.CharField("结果表名", max_length=128, unique=True)
    bk_biz_id = models.IntegerField("业务 ID", default=DEFAULT_BIZ_ID, help_text="降精度流程使用的业务")
    project_id = models.IntegerField("计算平台项目 ID", default=DEFAULT_PROJECT_ID, help_text="数据开发部分使用的项目，项目需要预先在计算平台创建")
    # NOTE: hdfs_cluster 为离线计算需要存储的集群, hdfs_expire_days 为存储数据的过期时间
    # 添加 hdfs_cluster 和 hdfs_expire_days 这两个字段，主要是便于后续集群资源不可用时，可以切换到其它集群
    hdfs_cluster = models.CharField("离线计算使用的存储集群", max_length=32, default=DEFAULT_HDFS_CLUSTER)
    hdfs_expire_days = models.IntegerField("离线计算存储数据的过期天数", default=DEFAULT_EXPIRE_DAYS)
    influxdb_db_name = models.CharField("计算后数据写入 influxdb 的db名称", max_length=128, null=True, blank=True)
    influxdb_rp_config = JsonField(
        "RP 配置",
        default={"influxdb_rp_1m": "1m", "influxdb_rp_5m": "5m", "influxdb_rp_1h": "1h", "influxdb_rp_12h": "12h"},
    )
    flow_id = models.IntegerField("计算任务的 ID", blank=True, null=True)
    status = models.CharField("计算任务的状态", max_length=32, default=BkDataTaskStatus.NO_ACCESS.value)
    create_time = models.DateTimeField("创建时间", auto_now_add=True)
    last_modify_time = models.DateTimeField("最后更新时间", auto_now=True)

    class Meta:
        verbose_name = "降精度计算配置"
        verbose_name_plural = "降精度计算配置"

    @property
    def raw_data_name(self) -> str:
        table_id = self.table_id
        table_id_str = ".".join([i.strip("_") for i in table_id.split(".")])
        return gen_bk_data_rt_id_without_biz_id(table_id_str)

    @property
    def bkdata_result_table_id(self) -> str:
        return f"{self.bk_biz_id}_{self.raw_data_name}"

    def save_flow_id(self, flow_id: int):
        """保存计算流程任务ID"""
        self.flow_id = flow_id
        self.save(update_fields=["flow_id"])

    def save_flow_status(self, status: str):
        """保存flow的状态"""
        self.status = status
        self.save(update_fields=["status"])

    def save_flow_id_and_status(self, flow_id: int, status: str):
        self.flow_id = flow_id
        self.status = status
        self.save(update_fields=["status", "flow_id"])

    def save_influxdb_db_name(self):
        """如果没有指定 influxdb， 则通过拆分 table id 获取"""
        if self.influxdb_db_name:
            return
        self.influxdb_db_name = self.table_id.split(".")[0]
        self.save(update_fields=["influxdb_db_name"])

    def access_and_calc_by_dataflow(self):
        """接入并计算数据

        主要分为下面几个步骤
        1. kafka数据接入计算平台并进行数据清洗
        2. 授权清洗后的数据，可以被当前项目使用
        3. 清洗后的数据进行处理，然后分1min、5min、1hour、12hour进行计算，并把计算后数据回写influxdb
           其中，1h和12h采用离线计算，以降低对资源的占用
        """
        # 获取结果表
        try:
            result_table = ResultTable.objects.get(table_id=self.table_id)
        except ResultTable.DoesNotExist:
            logger.error("table_id: %s not found", self.table_id)
            raise ValueError(_("结果表: {}不存在，请确认后重试").format(self.table_id))
        # 渲染计算后写入的db名称
        self.save_influxdb_db_name()

        # 获取结果表类型
        table_type = self.get_table_type(result_table.schema_type)

        bk_data_result_table_id = self.bkdata_result_table_id
        try:
            # 数据集成
            self.access(result_table.table_name_zh, table_type)
            # 授权给当前项目流程使用
            ensure_has_permission_with_rt_id(
                settings.BK_DATA_PROJECT_MAINTAINER, bk_data_result_table_id, self.project_id
            )
            # 数据计算，分为创建和启动流程
            self.create_calc_flow(table_type)
            self.start_calc_flow()
        except Exception:
            return
        # 创建rp记录
        try:
            self.create_rp(table_type)
        except Exception:
            logger.error("create rp of table_id: {} failed", self.table_id)

    def get_table_type(self, schema_type: str) -> str:
        # 获取结果表和数据源的关系
        try:
            dr = DataSourceResultTable.objects.get(table_id=self.table_id)
        except DataSourceResultTable.DoesNotExist:
            logger.error("table_id: %s not match any data id", self.table_id)
            raise ValueError(_("查询结果表: {}对应的 data id 不存在，请确认后重试").format(self.table_id))
        bk_data_id = dr.bk_data_id
        # 获取数据源信息
        try:
            ds = DataSource.objects.get(bk_data_id=bk_data_id)
        except DataSource.DoesNotExist:
            logger.error("bk_data_id: %s not found", bk_data_id)
            raise ValueError(_("数据源: {}不存在，请确认后重试").format(bk_data_id))
        # 获取etl_config
        etl_config = ds.etl_config
        # 获取结果表是否split
        rto = ResultTableOption.objects.filter(
            table_id=self.table_id, name=DataSourceOption.OPTION_IS_SPLIT_MEASUREMENT
        ).first()
        # 判断类型，以便于选择模板
        is_split = True
        if not rto:
            logger.warning(
                "result table: {} not found option: {}", self.table_id, DataSourceOption.OPTION_IS_SPLIT_MEASUREMENT
            )
            is_split = False
        else:
            is_split = True if rto.value == "true" else False
        return self._get_table_type(schema_type, is_split, etl_config)

    def _get_table_type(self, schema_type: str, is_split_measurement: bool, etl_config: Optional[str] = None) -> str:
        if schema_type == ResultTable.SCHEMA_TYPE_FIXED:
            return MeasurementType.BK_TRADITIONAL.value
        if schema_type == ResultTable.SCHEMA_TYPE_FREE:
            if is_split_measurement:
                return MeasurementType.BK_SPLIT.value
            else:
                # NOTE: 合并空间分支后，这一部分用常量表示
                if etl_config == "bk_standard_v2_time_series":
                    return MeasurementType.BK_STANDARD_V2_TIME_SERIES.value
                return MeasurementType.BK_EXPORTER.value

        # 如果为其它，设置为未知
        return MeasurementType.BK_TRADITIONAL.value

    def access(self, result_table_name_alias: str, table_type: str):
        """数据集成流程"""
        # 如果状态不为接入失败或者未接入状态时, 则直接返回
        if self.status not in [BkDataTaskStatus.NO_ACCESS.value, BkDataTaskStatus.ACCESS_FAILED.value]:
            return
        # 先设置状态，防止被重复执行
        self.save_flow_status(BkDataTaskStatus.ACCESSING.value)
        # 组装参数
        params = {
            "common": {"bk_biz_id": self.bk_biz_id},
            "raw_data": {
                "raw_data_name": self.raw_data_name,
                "raw_data_alias": result_table_name_alias,
                "data_scenario": {},
            },
        }
        # 获取 kafka 的配置
        kafka_config = self.get_kafka_config()
        params["raw_data"]["data_scenario"]["config"] = kafka_config
        params["clean"] = [self.render_clean_flow_config(table_type, self.raw_data_name, result_table_name_alias)]

        try:
            self.save_flow_status(BkDataTaskStatus.ACCESSING.value)
            api.bkdata.create_data_hub_for_downsample(**params)
            # 设置状态为未创建flow状态
            self.save_flow_status(BkDataTaskStatus.NO_CREATE.value)
        except Exception as e:
            self.save_flow_status(BkDataTaskStatus.ACCESS_FAILED.value)
            logger.error("create data hub failed, params: %s, error: %s", json.dumps(params), e)
            raise e

    def create_calc_flow(self, table_type: str):
        """数据计算流程"""
        # 判断状态，当不为未创建或者创建失败时，则直接返回
        if self.status not in [BkDataTaskStatus.NO_CREATE.value, BkDataTaskStatus.CREATE_FAILED.value]:
            return

        # 设置创建中状态
        self.save_flow_status(BkDataTaskStatus.CREATING.value)
        params = {"project_id": self.project_id, "flow_name": self.raw_data_name}
        config = self.render_calc_flow_config(self.bkdata_result_table_id, table_type)
        params.update({"nodes": config})
        try:
            data = api.bkdata.create_data_flow_for_downsample(**params)
            self.save_flow_id_and_status(data["flow_id"], BkDataTaskStatus.NO_START.value)
        except Exception as e:
            self.save_flow_status(BkDataTaskStatus.CREATE_FAILED.value)
            logger.error("create calc flow failed, params: %s, error: %s", json.dumps(params), e)
            raise e

    def start_calc_flow(self):
        # 判断状态，当不为未创建或者创建/停止失败时，则直接返回
        if self.status not in [
            BkDataTaskStatus.NO_START.value,
            BkDataTaskStatus.START_FAILED.value,
            BkDataTaskStatus.STOP_FAILED.value,
        ]:
            return
        # 如果处于启动失败状态，则执行停止任务，以便于再次启动
        if self.status in [BkDataTaskStatus.START_FAILED.value, BkDataTaskStatus.STOP_FAILED.value]:
            self.stop_calc_flow()
            return

        try:
            self.save_flow_status(BkDataTaskStatus.STARTING.value)
            api.bkdata.start_data_flow_for_downsample(flow_id=self.flow_id, resource_sets={})
        except Exception as e:
            self.save_flow_status(BkDataTaskStatus.START_FAILED.value)
            logger.error("start calc flow failed, flow id: %s, error: %s", self.flow_id, e)
            raise e

    def stop_calc_flow(self):
        try:
            self.save_flow_status(BkDataTaskStatus.STOPPING.value)
            api.bkdata.stop_data_flow_for_downsample(flow_id=self.flow_id)
        except Exception as e:
            self.save_flow_status(BkDataTaskStatus.START_FAILED.value)
            logger.error("stop calc flow failed, flow id: %s, error: %s", self.flow_id, e)
            raise e

    def check_and_update_status(self):
        """通过接口检查任务状态，并更新到对应的记录"""
        # 检查状态
        if self.status not in [BkDataTaskStatus.STARTING.value, BkDataTaskStatus.STOPPING.value]:
            return
        try:
            data = api.bkdata.get_flow_status_for_downsample(flow_id=self.flow_id)
            self.save_flow_status(data["status"])
        except Exception as e:
            logger.error("get flow status failed, flow id: %s, error: %s", self.flow_id, e)

    def get_kafka_config(self) -> Dict:
        """获取 kafka 的配置"""
        kafka_storage = KafkaStorage.objects.filter(table_id=self.table_id).first()
        if not kafka_storage:
            logger.warning("table: {} not found in kafka queue", self.table_id)
            kafka_storage = KafkaStorage.create_table(table_id=self.table_id, is_sync_db=True)

        consul_config = kafka_storage.storage_cluster.consul_config
        # 从配置中获取信息
        config = {
            "topic": kafka_storage.topic,
            "group": self.raw_data_name,
            "tasks": kafka_storage.partition,
        }
        # 获取 broker
        domain = getitems(consul_config, ["cluster_config", "domain_name"], "")
        port = getitems(consul_config, ["cluster_config", "port"], 0)
        broker = settings.BK_DATA_KAFKA_BROKER_URL
        if domain and port:
            broker = f"{domain}:{port}"
        config["broker"] = broker

        return config

    def render_clean_flow_config(self, table_type: str, result_table_name: str, result_table_name_alias: str) -> Dict:
        """渲染清洗模板配置"""
        if table_type not in [
            MeasurementType.BK_TRADITIONAL.value,
            MeasurementType.BK_EXPORTER.value,
            MeasurementType.BK_SPLIT.value,
        ]:
            logger.error("table type: %s not support", table_type)
            raise ValueError("table type: %s not supported", table_type)
        assigns, fields = self._get_field_assign_content(table_type)
        time_format, timestamp_len = self._get_time_format_and_len(table_type)
        config_str = Template(DATA_HUB_CLEAN_TEMPLATE).render(
            Context(
                {
                    "result_table_name": result_table_name,
                    "result_table_name_alias": result_table_name_alias,
                    "assigns": mark_safe(assigns),
                    "fields": mark_safe(fields),
                    "time_format": time_format,
                    "timestamp_len": timestamp_len,
                }
            )
        )
        # 转换为 Dict
        try:
            return json.loads(config_str)
        except Exception as e:
            logger.exception("render clean config failed, %s", e)
            return

    def _get_time_format_and_len(self, table_type: str) -> Tuple[str, int]:
        """获取时间格式及长度"""
        if table_type == MeasurementType.BK_TRADITIONAL.value:
            return SECOND_TIMESTAMP_FORMAT, SECOND_TIMESTAMP_LEN
        else:
            return DEFAULT_TIME_FORMAT, DEFAULT_TIMESTAMP_LEN

    def _get_table_metric_fields(self) -> List:
        return list(
            ResultTableField.objects.filter(table_id=self.table_id, tag="metric").values_list("field_name", flat=True)
        )

    def _get_field_assign_content(self, table_type: str) -> Tuple[str, str]:
        """获取对应的表指标

        1. 针对单指标单表，按照固定metric value 处理
        2. 非单指标单表，传递结果表对应的指标数据
        """
        if table_type == MeasurementType.BK_SPLIT.value:
            return json.dumps(SINGLE_METRIC_TEMPLATE), json.dumps(SINGLE_METRIC_FIELD_TEMPLATE)
        else:
            # 获取结果表的指标
            rt_fields = self._get_table_metric_fields()
            assigns = [{"type": "float", "assign_to": f, "key": f} for f in rt_fields]
            fields = [
                {
                    "field_name": f,
                    "field_type": METRIC_VALUE_TYPE,
                    "field_alias": f,
                    "is_dimension": False,
                    "field_index": i + 1,
                }
                for i, f in enumerate(rt_fields)
            ]
            field_count = len(rt_fields)
            fields.extend(
                [
                    {
                        "field_name": "time",
                        "field_type": "long",
                        "field_alias": "time",
                        "is_dimension": False,
                        "field_index": field_count + 1,
                    },
                    {
                        "field_name": "dimensions",
                        "field_type": "text",
                        "field_alias": "dimensions",
                        "is_dimension": False,
                        "field_index": field_count + 2,
                    },
                ]
            )
            return json.dumps(assigns), json.dumps(fields)

    def render_calc_flow_config(self, bk_data_result_table_id: str, table_type: str) -> Dict:
        """渲染计算模板配置

        :param source_table: 数据源
        :return: 返回渲染后的模板
        """
        # 获取 influx db 的信息
        try:
            influxdb_storage = InfluxDBStorage.objects.get(table_id=self.table_id)
        except InfluxDBStorage.DoesNotExist:
            raise ValueError(_("结果表: {}数据未写入 influxdb，请确认后重试").format(self.table_id))
        # 组装渲染参数
        table_fields = self._get_table_metric_fields()
        influxdb_url = f"http://{influxdb_storage.storage_cluster.domain_name}:{influxdb_storage.storage_cluster.port}"
        params = {
            "bk_biz_id": self.bk_biz_id,
            "data_source": bk_data_result_table_id,
            "step_suffix_name": self.raw_data_name,
            "influxdb_db": self.influxdb_db_name,
            "influxdb_url": influxdb_url,
            "hdfs_cluster": self.hdfs_cluster,
            "expires": self.hdfs_expire_days,
        }
        params.update(self.influxdb_rp_config)
        config_str = ""
        if table_type in [MeasurementType.BK_TRADITIONAL.value, FIXED_METRIC_CALC_TEMPLATE]:
            calc_func_fields, calc_fields_with_concat, calc_fields = [], "", []
            for field in table_fields:
                calc_func_fields.extend(
                    [
                        f"count(1) AS count_{field}",
                        f"max(`{field}`) AS max_{field}",
                        f"min(`{field}`) AS min_{field}",
                        f"sum(`{field}`) AS sum_{field}",
                        f"avg(`{field}`) AS mean_{field}",
                        f"last(`{field}`) AS last_{field}",
                    ]
                )
                calc_fields.extend(
                    [
                        f"CONCAT('count_{field}', '#', count_{field})",
                        f"CONCAT('max_{field}', '#', max_{field})",
                        f"CONCAT('min_{field}', '#', min_{field})",
                        f"CONCAT('sum_{field}', '#', sum_{field})",
                        f"CONCAT('mean_{field}', '#', mean_{field})",
                        f"CONCAT('last_{field}', '#', last_{field})",
                    ]
                )
                calc_fields_with_concat = f"CONCAT_WS('^', {','.join(calc_fields)}) AS concat_metric_info"
            params.update(
                {
                    "result_table_fields": ",".join(table_fields),
                    "measurement_name": self.table_id.split(".")[-1],
                    "fields_with_calc_func": ",".join(calc_func_fields),
                }
            )
            if table_type == MeasurementType.BK_TRADITIONAL.value:
                config_str = Template(MULTI_METRIC_CALC_TEMPLATE).render(Context(params))
            else:
                params.update(
                    {"calc_fields_with_concat": calc_fields_with_concat, "concat_metric_info": "concat_metric_info"}
                )
                config_str = Template(FIXED_METRIC_CALC_TEMPLATE).render(Context(params))
        else:
            config_str = Template(SINGLE_METRIC_CALC_TEMPLATE).render(Context(params))

        # 转换为 Dict
        try:
            return json.loads(config_str)
        except Exception as e:
            logger.exception("render calc config failed, %s", e)
            raise

    def create_rp(self, table_type: str):
        """创建RP相关"""
        database = self.table_id.split(".")[0]
        obj = DownsampledDatabase.objects.get_or_create(database=database, defaults={"enable": True})[0]
        obj.sync_database_config()
        # 添加 rp 基本配置
        measurement_name, fields = self._get_measurement_and_fields(table_type)
        aggs = ",".join(AGG_FUNC_LIST)
        for __, rp_name in self.influxdb_rp_config.items():
            DownsampledRetentionPolicies.objects.get_or_create(
                database=database,
                name=rp_name,
                defaults={"resolution": RP_RESOLUTION_MAP.get(rp_name, RP_1M_RESOLUTION), "duration": DURATION},
            )

            # 添加 cq consul 配置
            DownsampledContinuousQueries.objects.get_or_create(
                database=database,
                measurement=measurement_name,
                defaults={
                    "fields": fields,
                    "aggregations": aggs,
                    "source_rp": DEFAULT_RP_NAME,
                    "target_rp": rp_name,
                },
            )
        # 同步或刷新配置
        DownsampledRetentionPolicies.sync_all(database)
        DownsampledContinuousQueries.refresh_consul_for_cq(database)

    def _get_measurement_and_fields(self, table_type: str) -> Tuple[str, str]:
        """通过类型，获取measurement和字段信息
        - 多指标单表，返回表名和 半角逗号连接的 metric field
        - 固定指标单表，返回表名和 metric_value
        - 单指标单表，返回__all__和value
        """
        if table_type == MeasurementType.BK_TRADITIONAL.value:
            return self.table_id.split(".")[-1], ",".join(self._get_table_metric_fields())
        elif table_type == MeasurementType.BK_EXPORTER.value:
            return self.table_id.split(".")[-1], "metric_value"
        else:
            return "__all__", "value"
