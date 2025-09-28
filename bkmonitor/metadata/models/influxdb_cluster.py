# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import json
import logging
import time
from typing import List, Optional

import influxdb
from bkcrypto.contrib.django.fields import SymmetricTextField
from django.conf import settings
from django.db import models
from django.utils.translation import gettext as _

from core.drf_resource.exceptions import CustomException
from metadata import config
from metadata.models import constants
from metadata.models.common import BaseModel
from metadata.utils import consul_tools, go_time
from metadata.utils.redis_tools import RedisTools

logger = logging.getLogger("metadata")


class InfluxDBTool:
    @classmethod
    def push_to_redis(cls, key: str, field: str, value: str, is_publish: bool = True):
        """推送数据到 redis"""
        redis_key = f"{constants.INFLUXDB_KEY_PREFIX}:{key}"
        msg_suffix = f"key: {redis_key}, field: {field}, value: {value}"
        try:
            RedisTools.hset_to_redis(redis_key, field, value)
        except Exception as e:
            logger.error("push redis failed, %s, err: %s", msg_suffix, e)
        else:
            logger.info("push redis successfully, %s", msg_suffix)
        # 发布
        if is_publish:
            RedisTools.publish(constants.INFLUXDB_KEY_PREFIX, [key])
            logger.info("publish redis successfully, channel: %s, msg: %s", constants.INFLUXDB_KEY_PREFIX, key)

    @classmethod
    def clean_redis_config(cls, key: str, exist_list: List):
        """清理不存在的数据"""
        # 获取 redis 中指定 key 的数据
        redis_key = f"{constants.INFLUXDB_KEY_PREFIX}:{key}"
        configs = RedisTools.hgetall(redis_key)
        # 获取对应的集群
        data_list = [c.decode("utf8") for c in configs]
        if not data_list:
            logger.info("redis data is null of key: %s", redis_key)
            return
        # 获取需要删除的信息
        need_del_list = list(set(data_list) - set(exist_list))
        RedisTools.hdel(redis_key, need_del_list)
        # 发布
        RedisTools.publish(constants.INFLUXDB_KEY_PREFIX, [key])

        logger.info(
            "delete influxdb config from redis successfully, deleted key: %s, field: %s",
            redis_key,
            json.dumps(need_del_list),
        )


class InfluxDBTagInfo(models.Model, InfluxDBTool):
    """influxDB集群tag分区配置"""

    CONSUL_PREFIX_PATH = "%s/influxdb_info/tag_info" % config.CONSUL_PATH
    # 当前仅支持单个tag
    TagKeyFormat = "{}/{}/{}=={}"

    database = models.CharField("数据库名", max_length=128)
    measurement = models.CharField("表名", max_length=128)
    tag_name = models.CharField("tag名", max_length=128)
    tag_value = models.CharField("tag值", max_length=128)
    cluster_name = models.CharField("集群名", max_length=128)
    host_list = models.CharField("使用中的机器", max_length=128)
    # manual_unreadable_host influxdb-proxy无条件屏蔽该列表中的主机的读取操作，但可写入
    manual_unreadable_host = models.CharField("静态不可读机器", max_length=128, blank=True, default="", null=True)
    force_overwrite = models.BooleanField("是否强制写入", default=False)

    class Meta:
        verbose_name = "influxDB集群tag分区信息"
        verbose_name_plural = "influxDB集群tag分区信息表"
        unique_together = ("database", "measurement", "tag_name", "tag_value", "cluster_name")

    @classmethod
    def export_data(cls):
        items = cls.objects.all()
        data = list(
            items.values(
                "database",
                "measurement",
                "tag_name",
                "tag_value",
                "cluster_name",
                "host_list",
                "manual_unreadable_host",
                "force_overwrite",
            )
        )
        return data

    @classmethod
    def import_data(cls, data):
        items = data
        delete_list = []
        for info in cls.objects.all():
            exist = False
            for item in items:
                if (
                    (item["database"] == info.database)
                    and (item["measurement"] == info.measurement)
                    and (item["tag_name"] == info.tag_name)
                    and (item["tag_value"] == info.tag_value)
                    and (item["cluster_name"] == info.cluster_name)
                ):
                    exist = True
            if not exist:
                delete_list.append(info)

        for info in delete_list:
            data = info.__dict__
            info.delete()
            logger.info("delete tag info:{}".format(data))

        for item in items:
            obj, created = cls.objects.update_or_create(
                database=item["database"],
                measurement=item["measurement"],
                tag_name=item["tag_name"],
                tag_value=item["tag_value"],
                cluster_name=item["cluster_name"],
                defaults=item,
            )
            if created:
                logger.info("create new tag info:{}".format(str(item)))
            else:
                logger.info("update tag info to:{}".format(str(item)))

    @classmethod
    def put_into_consul(cls, path, data):
        """
        consul交互底层写入方法
        """
        hash_consul = consul_tools.HashConsul()
        hash_consul.put(key=path, value=data)

    @classmethod
    def notify_consul_changed(cls, prefix, cluster_name):
        path = "{}/{}/{}/".format(prefix, cluster_name, "version")
        cls.put_into_consul(path, time.time())

    @classmethod
    def anaylize_tag_key(cls, tag_key):
        items = tag_key.split("/")
        cluster_name = items[0]
        database = items[1]
        measurement = items[2]
        tags = items[3].split("==")
        tag_name = tags[0]
        tag_value = tags[1]

        return {
            "database": database,
            "measurement": measurement,
            "cluster_name": cluster_name,
            "tag_name": tag_name,
            "tag_value": tag_value,
        }

    @classmethod
    def is_ready(cls, item):
        value = item["Value"]
        info = json.loads(value)
        if "status" in info.keys() and info["status"] == "ready":
            return True
        return False

    @classmethod
    def clean_consul_config(cls):
        """
        清理掉不存在的consul key
        """
        # 遍历consul,删除已经不存在的key
        hash_consul = consul_tools.HashConsul()
        clusters = {}
        result_data = hash_consul.list(cls.CONSUL_PREFIX_PATH)
        if not result_data[1]:
            return
        for item in result_data[1]:
            key = item["Key"]
            tag_key = key.replace(cls.CONSUL_PREFIX_PATH + "/", "")
            # 跳过version
            if tag_key.endswith("version/"):
                continue
            # 跳过执行迁移中的任务
            if not cls.is_ready(item):
                continue
            key_map = cls.anaylize_tag_key(tag_key)
            # 数据库里找不到的，就删掉
            length = len(cls.objects.filter(**key_map))
            if length == 0:
                if key_map["cluster_name"] not in clusters.keys():
                    clusters[key_map["cluster_name"]] = True
                hash_consul.delete(key)
                logger.info("tag info:{} deleted in consul".format(key))
            else:
                logger.info("key:{} has {} result,not delete".format(key, length))
        for cluster in clusters.keys():
            cls.notify_consul_changed(cls.CONSUL_PREFIX_PATH, cluster)

    @classmethod
    def clean_redis_tag_config(cls):
        """清理已经不存在的 redis 中的数据"""
        all_objs = cls.objects.all()
        # 根据数据获取已经存在的信息
        exist_tag_list = []
        for obj in all_objs:
            exist_tag_list.append(obj.get_redis_field())
        super().clean_redis_config(constants.INFLUXDB_TAG_INFO_KEY, exist_tag_list)

    @classmethod
    def refresh_consul_tag_config(cls):
        """
        刷新一个tag分区配置配置到Consul上
        :return: None
        """
        # 循环遍历所有的项，逐个处理
        items = cls.objects.all()
        clusters = {}
        for item in items:
            # 将处理的集群记录
            if item.cluster_name not in clusters.keys():
                clusters[item.cluster_name] = True
            # 强制刷新模式下，直接刷新对应tag的数据即可
            # 否则要走一套增删改逻辑
            if item.force_overwrite:
                item.add_consul_info()
                continue
            # 根据item信息,到consul中获取数据
            info = item.get_consul_info()
            # 如果对应consul位置没有数据，则直接新增
            if not info[1]:
                item.add_consul_info()
                continue
            json_info = json.loads(info[1]["Value"])
            # 否则进行更新
            item.modify_consul_info(json_info)
        for cluster in clusters.keys():
            cls.notify_consul_changed(cls.CONSUL_PREFIX_PATH, cluster)

    def generate_new_info(self, old_info):
        # 根据当前指向的机器，生成增删列表
        delete_list = []
        add_list = []
        old_host_list = old_info["host_list"]
        new_host_list = self.host_list.split(",")
        # 获取需要删除的主机列表
        for old_host in old_host_list:
            exist = False
            for new_host in new_host_list:
                if new_host == old_host:
                    exist = True
                    break
            if not exist:
                delete_list.append(old_host)

        # 获取需要增加的主机列表
        for new_host in new_host_list:
            exist = False
            for old_host in old_host_list:
                if old_host == new_host:
                    exist = True
            if not exist:
                add_list.append(new_host)
        if len(add_list) == 0 and len(delete_list) == 0:
            return old_info
        # 使用中的主机列表不动，进行预新增和预删除，该info会被transport继续处理
        new_info = {
            "host_list": old_host_list,
            "unreadable_host": add_list,
            "delete_host_list": delete_list,
            "status": "changed",
            "transport_start_at": 0,
            "transport_last_at": 0,
            "transport_finish_at": 0,
        }
        return new_info

    def modify_consul_info(self, old_info):
        # 如果状态不为ready，则不应修改
        if "status" not in old_info.keys():
            return
        if old_info["status"] != "ready":
            return
        new_info = self.generate_new_info(old_info)
        path = self.get_path()
        self.put_into_consul(path, new_info)
        # 写入 redis
        super().push_to_redis(constants.INFLUXDB_TAG_INFO_KEY, self.get_redis_field(), json.dumps(new_info))

    def add_consul_info(self):
        # 生成简单数据
        path = self.get_path()
        unreadable = []
        if self.manual_unreadable_host:
            unreadable = self.manual_unreadable_host.split(",")
        info = {"host_list": self.host_list.split(","), "unreadable_host": unreadable, "status": "ready"}
        # 然后写入
        self.put_into_consul(path, info)
        # 写入redis
        super().push_to_redis(constants.INFLUXDB_TAG_INFO_KEY, self.get_redis_field(), json.dumps(info))
        return

    def generate_tag_key(self):
        """
        生成tag key
        """
        base = self.TagKeyFormat.format(self.database, self.measurement, self.tag_name, self.tag_value)
        return base

    def get_path(self):
        return "{}/{}/{}".format(self.CONSUL_PREFIX_PATH, self.cluster_name, self.generate_tag_key())

    def get_redis_field(self):
        return f"{self.cluster_name}/{self.generate_tag_key()}"

    def get_consul_info(self):
        """
        获取对应的consul数据
        """
        path = self.get_path()
        hash_consul = consul_tools.HashConsul()
        return hash_consul.get(key=path)


class InfluxDBClusterInfo(models.Model, InfluxDBTool):
    """influxDB存储集群后台信息"""

    DEFAULT_CLUSTER_NAME = "default"
    CONSUL_PREFIX_PATH = "%s/influxdb_info/cluster_info" % config.CONSUL_PATH

    host_name = models.CharField("主机名", max_length=128)
    cluster_name = models.CharField("归属集群名", max_length=128)
    host_readable = models.BooleanField("是否在该集群中可读", default=True)

    class Meta:
        verbose_name = "influxDB集群信息"
        verbose_name_plural = "influxDB集群信息表"
        unique_together = ("cluster_name", "host_name")

    @classmethod
    def export_data(cls):
        items = cls.objects.all()
        data = list(items.values("host_name", "cluster_name", "host_readable"))
        return data

    @classmethod
    def import_data(cls, data):
        items = data
        delete_list = []
        for info in cls.objects.all():
            exist = False
            for item in items:
                if (item["host_name"] == info.host_name) and (item["cluster_name"] == info.cluster_name):
                    exist = True
            if not exist:
                delete_list.append(info)

        for info in delete_list:
            data = info.__dict__
            info.delete()
            logger.info("delete cluster info:{}".format(data))

        for item in items:
            obj, created = cls.objects.update_or_create(
                cluster_name=item["cluster_name"],
                host_name=item["host_name"],
                defaults=item,
            )
            if created:
                logger.info("create new cluster info:{}".format(str(item)))
            else:
                logger.info("update cluster info to:{}".format(str(item)))

    @classmethod
    def is_default_cluster_exists(cls):
        """
        判断是否存在默认集群
        :return: True | False
        """

        return cls.objects.filter(cluster_name=cls.DEFAULT_CLUSTER_NAME).exists()

    @classmethod
    def clean_consul_config(cls):
        """
        清理掉不存在的consul key
        """
        # 遍历consul,删除已经不存在的key
        hash_consul = consul_tools.HashConsul()
        result_data = hash_consul.list(cls.CONSUL_PREFIX_PATH)
        if not result_data[1]:
            return
        for item in result_data[1]:
            key = item["Key"]
            # 取路径最后一段，为主机名
            name = key.split("/")[-1]
            # 数据库里找不到的，就删掉
            length = len(cls.objects.filter(cluster_name=name))
            if length == 0:
                hash_consul.delete(key)
                logger.info("cluster info:{} deleted in consul".format(key))
            else:
                logger.info("cluster:{} has {} result,not delete".format(key, length))

    @classmethod
    def clean_redis_cluster_config(cls):
        """清理不存在的数据"""
        exist_cluster_list = cls.objects.values_list("cluster_name", flat=True)
        super().clean_redis_config(constants.INFLUXDB_CLUSTER_INFO_KEY, exist_cluster_list)

        logger.info("delete influxdb cluster info successfully")

    @classmethod
    def refresh_consul_cluster_config(cls, cluster_name=None):
        """
        刷新一个influxDB集群的配置到Consul上
        :param cluster_name: 是否有指定集群的信息刷新，如果未指定，则全量刷新
        :return: None
        """

        hash_consul = consul_tools.HashConsul()

        # 1. 获取需要刷新的信息列表
        info_list = cls.objects.all()
        if cluster_name is not None:
            info_list = info_list.filter(cluster_name=cluster_name)

        total_count = info_list.count()
        logger.debug("total find->[{}] info to refresh with cluster_name->[{}]".format(total_count, cluster_name))

        # 2. 构建需要刷新的字典信息
        refresh_dict = {}
        for cluster_info in info_list:
            try:
                refresh_dict[cluster_info.cluster_name].append(cluster_info)
            except KeyError:
                refresh_dict[cluster_info.cluster_name] = [cluster_info]

        # 3. 遍历所有的字典信息并写入至consul
        for cluster_name, cluster_info_list in list(refresh_dict.items()):
            consul_path = "/".join([cls.CONSUL_PREFIX_PATH, cluster_name])
            host_name_list = [cluster_info.host_name for cluster_info in cluster_info_list]
            unreadable_host_list = [
                cluster_info.host_name for cluster_info in cluster_info_list if cluster_info.host_readable is False
            ]
            val = {"host_list": host_name_list, "unreadable_host_list": unreadable_host_list}
            hash_consul.put(key=consul_path, value=val)
            logger.debug("consul path->[{}] is refresh with value->[{}] success.".format(consul_path, host_name_list))

            # TODO: 待推送 redis 数据稳定后，删除推送 consul 功能
            super().push_to_redis(constants.INFLUXDB_CLUSTER_INFO_KEY, cluster_name, json.dumps(val))

        logger.info("all influxDB cluster info is refresh to consul success count->[%s]." % total_count)


class InfluxDBHostInfo(models.Model, InfluxDBTool):
    """influxDB存储集群主机信息"""

    CONSUL_PATH = "%s/influxdb_info/host_info" % config.CONSUL_PATH

    host_name = models.CharField("主机名", max_length=128, primary_key=True)

    domain_name = models.CharField("集群域名", max_length=128)
    port = models.IntegerField("端口")

    # 用户名及密码配置
    username = models.CharField("用户名", blank=True, max_length=64, default="")
    password = SymmetricTextField("密码", blank=True, default="")

    description = models.CharField("集群备注说明信息", max_length=256, default="")

    # 主机状态码
    status = models.BooleanField("是否禁用", default=False)
    backup_rate_limit = models.FloatField("备份恢复速率限制", default=0)

    grpc_port = models.IntegerField("GRPC端口", default=8089)
    protocol = models.CharField("协议", max_length=16, default="http")
    read_rate_limit = models.FloatField("读取速率", default=0)

    class Meta:
        verbose_name = "influxDB主机信息"
        verbose_name_plural = "influxDB主机信息表"

    @classmethod
    def export_data(cls):
        items = cls.objects.all()
        data = list(
            items.values(
                "host_name",
                "domain_name",
                "port",
                "username",
                "password",
                "description",
                "status",
                "backup_rate_limit",
                "grpc_port",
                "protocol",
                "read_rate_limit",
            )
        )
        return data

    @classmethod
    def import_data(cls, data):
        items = data

        # 先检查输入的信息是否正确
        for item in items:
            # 检查是否可达以及是否认证信息无误
            valid_message = cls.check_host_valid(item)
            if valid_message:
                # 脱敏
                item["password"] = "xxxx"
                raise CustomException("host->{} check valid failed,reason->{}".format(item, valid_message))

        # 整理删除主机信息
        delete_list = []
        for info in cls.objects.all():
            exist = False
            for item in items:
                if item["host_name"] == info.host_name:
                    exist = True
            if not exist:
                delete_list.append(info)

        for info in delete_list:
            data = info.__dict__
            info.delete()
            data["password"] = "xxxx"
            logger.info("delete host info:{}".format(data))

        # 新增或更新主机信息
        for item in items:
            obj, created = cls.objects.update_or_create(host_name=item["host_name"], defaults=item)
            # 脱敏
            item["password"] = "xxxx"
            if created:
                logger.info("create new host info:{}".format(str(item)))
            else:
                logger.info("update host info to:{}".format(str(item)))

    @classmethod
    def check_host_valid(cls, item):
        """
        检查对应主机是否处于可用状态，可达且用户名密码正确
        """
        domain_name = item.get("domain_name", None)
        port = item.get("port", None)
        username = item.get("username", None)
        password = item.get("password", None)
        if not domain_name or not port:
            return "missing influxdb address"

        client = influxdb.InfluxDBClient(host=domain_name, port=port)
        # 如果有配置用户名和密码，则使用之
        if username and password:
            client.switch_user(username, password)

        try:
            client.get_list_database()
        except Exception as e:
            return e

    @property
    def consul_config_path(self):
        """
        获取consul配置路径
        :return: eg: bkmonitor_enterprise_production/metadata/influxdb_info/host_info/${hostname}/
        """

        return "/".join([self.CONSUL_PATH, self.host_name])

    @property
    def consul_config(self):
        """
        获取consul配置
        :return: {
            "domain_name": "127.0.0.1",
            "port": 3306
            "username": "admin",
            "password": "123123"
            "status": "true",
            "backup_rate_limit": 0,
        }
        """

        return {
            "domain_name": self.domain_name,
            "port": self.port,
            "username": self.username,
            "password": self.password,
            "status": self.status,
            "backup_rate_limit": self.backup_rate_limit,
            "grpc_port": self.grpc_port,
            "protocol": self.protocol,
            "read_rate_limit": self.read_rate_limit,
        }

    @classmethod
    def create_host_info(cls, host_name, domain_name, port, username=None, password=None, description=None):
        """
        创建一个influxdb机器描述信息
        :param host_name: 主机代号名
        :param domain_name: 域名
        :param port: 端口
        :param username: 用户名
        :param password: 密码。注意：如果用户名为空，密码即使提供也不会生效
        :param description: 机器描述内容
        :return: InfluxDBHostInfo object
        """
        # 1. 判断是否存在重名的主机信息
        if cls.objects.filter(host_name=host_name).exists():
            logger.error("try to create host_name->[%s] but is exists and nothing will do." % host_name)
            raise ValueError(_("主机信息[%s]已经存在，请确认") % host_name)

        host_info = {"host_name": host_name, "domain_name": domain_name, "port": port}
        # 2. 判断是否存在username，否则password不生效
        if username is not None:
            host_info["username"] = username
            host_info["password"] = password
            # 密码为了脱敏，不实际打印
            logger.debug("host->[{}] create with password->[xxxx] username->[{}]".format(host_name, username))

        # 3. 创建并返回
        new_host_info = cls.objects.create(**host_info)
        logger.info("new host->[{}] is create id->[{}]".format(host_name, new_host_info.pk))

        return new_host_info

    def update_default_rp(self, refresh_databases):
        """
        更新本机各个DB的RP的默认配置是否和DB的一致
        :return: True
        """

        client = influxdb.client.InfluxDBClient(
            host=self.domain_name,
            port=self.port,
        )

        # 如果用户名和密码有配置，需要配置生效使用
        if self.username or self.password:
            client.switch_user(username=self.username, password=self.password)
            logger.debug("host->[{}] is set with username and password.".format(self.domain_name))

        duration_str = "{}d".format(settings.TS_DATA_SAVED_DAYS)

        for db in client.get_list_database():
            # 判断该db是否在需要刷新的set当中
            # 如果不是，则直接跳过
            if db["name"] not in refresh_databases:
                continue

            for rp in client.get_list_retention_policies(database=db["name"]):
                # 忽略不是默认的rp配置
                if not rp["default"]:
                    logger.debug("host->[{}] found rp->[{}] is not default, jump it".format(self.host_name, rp["name"]))
                    continue

                # 如果发现默认配置和settings中的配置是一致的，可以直接跳过到下一个DB
                if go_time.parse_duration(rp["duration"]) == go_time.parse_duration(duration_str):
                    break
                else:
                    # 否则需要更新配置
                    try:
                        # 判断出合理的shard再对RP进行修改
                        shard_duration = InfluxDBHostInfo.judge_shard(duration_str)
                    except ValueError as e:
                        logger.error("host->[{}] update default rp failed: [{}]".format(self.host_name, e))
                        break
                    client.alter_retention_policy(
                        name=rp["name"],
                        database=db["name"],
                        duration=duration_str,
                        default=True,
                        shard_duration=shard_duration,
                    )
                    logger.warning(
                        "host->[{}] database->[{}] default rp->[{}] now is set to ->[{} | {}]".format(
                            self.host_name, db["name"], rp["name"], duration_str, shard_duration
                        )
                    )
                    break
        logger.info("host->[{}] check all database default rp success.".format(self.host_name))
        return True

    @classmethod
    def clean_consul_config(cls):
        """
        清理掉不存在的consul key
        """
        # 遍历consul,删除已经不存在的key
        hash_consul = consul_tools.HashConsul()
        result_data = hash_consul.list(cls.CONSUL_PATH)
        if not result_data[1]:
            return
        for item in result_data[1]:
            key = item["Key"]
            # 取路径最后一段，为主机名
            name = key.split("/")[-1]
            # 数据库里找不到的，就删掉
            length = len(cls.objects.filter(host_name=name))
            if length == 0:
                hash_consul.delete(key)
                logger.info("host info:{} deleted in consul".format(key))
            else:
                logger.info("host:{} has {} result,not delete".format(key, length))

    @classmethod
    def clean_redis_host_config(cls):
        """清理不存在的 redis 中的主机信息"""
        exist_host_list = cls.objects.values_list("host_name", flat=True)
        super().clean_redis_config(constants.INFLUXDB_HOST_INFO_KEY, exist_host_list)

        logger.info("delete influxdb host info successfully")

    def refresh_consul_cluster_config(self):
        """
        更新一个主机的信息到consul中
        :return: None
        """

        hash_consul = consul_tools.HashConsul()

        hash_consul.put(key=self.consul_config_path, value=self.consul_config)

        logger.info("host->[%s] refresh consul config success." % self.host_name)

        # 推送到redis
        super().push_to_redis(constants.INFLUXDB_HOST_INFO_KEY, self.host_name, json.dumps(self.consul_config))
        return

    @staticmethod
    def duration_rationality_judgment(duration: str = ""):
        """
        数据库中（用户输入的）duration进行输入合理性判断
        输入的duration的值有几个要求：
        1、不能为空
        2、输入的值是数字加时间单位的组合，时间的值不可以是小数，时间单位只能用小写，不可以用大写
        3、输入的值要大于等于1h（1个小时）
        :param duration:数据库中存储的TSDB物理表配置（用户在metadata前端页面中输入的数据）
        :return: True | raise Exception
        """
        if go_time.parse_duration(duration) <= 0:
            raise ValueError("source_duration_time format is incorrect!")
        # 判断输入的值换算后是否为0s或者是否小于1h（1个小时）
        duration_value = go_time.parse_duration(duration)
        if duration_value > 0:
            if duration_value < 3600:
                raise ValueError("retention policy duration must be at least 1h0m0s")
        return True

    @staticmethod
    def judge_shard(duration: str = "inf") -> str:
        """
        用于根据数据保留时间判断shard的长度
        1、当输入为inf时，可以忽略大小写，并表示无限保留，此时的shard为7d
        2、duration大于1h小于2d时，shard为1h
        3、duration大于2d小于180d时，shard为1d
        4、duration大于180d时，shard为7d
        :param duration:数据库中存储的TSDB物理表配置（用户在metadata前端页面中输入的数据）, 默认长度为7天
        :return: str（合理的shard的长度）| raise Exception
        """
        # 先进行数据合理性判断
        if duration.lower() == "inf":
            return "7d"
        InfluxDBHostInfo.duration_rationality_judgment(duration)
        duration_value = go_time.parse_duration(duration)
        if duration_value < 172800:
            return "1h"
        elif 172800 <= duration_value <= 15552000:
            return "1d"
        else:
            return "7d"


class InfluxDBProxyStorage(BaseModel, InfluxDBTool):
    CONSUL_PREFIX_PATH = f"{config.CONSUL_PATH}/{constants.INFLUXDB_PROXY_STORAGE_INFO_KEY}"
    CONSUL_PATH = f"{CONSUL_PREFIX_PATH}/{{service_name}}"

    proxy_cluster_id = models.IntegerField("influxdb proxy 集群 ID")
    service_name = models.CharField("influxdb proxy 服务名称", max_length=64)
    instance_cluster_name = models.CharField("实际存储集群名称", max_length=128)
    is_default = models.BooleanField("是否默认", default=False, help_text="是否为默认存储，当用户未指定时，使用默认值")

    class Meta:
        verbose_name = "InfluxDB Proxy 集群和实际存储集群关系表"
        verbose_name_plural = "InfluxDB Proxy 集群和实际存储集群关系表"
        unique_together = ("proxy_cluster_id", "instance_cluster_name")

    @property
    def consul_config_path(self):
        """获取推送到 consul 的路径"""
        return self.CONSUL_PATH.format(service_name=self.service_name)

    @classmethod
    def clean(cls):
        """清理已经废弃的集群信息"""
        try:
            cls.clean_consul()
            cls.clean_redis()
        except Exception as e:
            logger.error("clean consul and redis error, %s", e)

    @classmethod
    def clean_redis(cls):
        service_name_list = list(cls.objects.values_list("service_name", flat=True))
        super().clean_redis_config(constants.INFLUXDB_PROXY_STORAGE_INFO_KEY, service_name_list)

        logger.info("delete influxdb proxy cluster info successfully")

    @classmethod
    def clean_consul(cls):
        # 遍历 consul 路径
        hash_consul = consul_tools.HashConsul()
        result_data = hash_consul.list(cls.CONSUL_PREFIX_PATH)
        if not result_data[1]:
            return
        # 获取路径中的 service name
        # result_data[1] 格式: [{Key: 路径, Value: 推送的 value 值, ...}]
        consul_service_name_list = [i["Key"].split("/")[-1] for i in result_data[1]]
        # 获取存储的集群 service name 列表
        db_service_name_list = list(cls.objects.values_list("service_name", flat=True))
        diff_service_names = set(consul_service_name_list) - set(db_service_name_list)

        # 如果不需要删除直接返回
        if not diff_service_names:
            logger.info("not delete any path")
            return
        # 删除路径
        for i in diff_service_names:
            hash_consul.delete(f"{cls.CONSUL_PREFIX_PATH}/{i}")
        logger.warn("delete consul path: %s", json.dumps(list(diff_service_names)))

    @classmethod
    def push(cls, service_name: Optional[str] = None):
        """推送数据到 consul & redis"""
        objs = cls.objects.all()
        # 过滤指定的 proxy 集群
        if service_name is not None:
            objs = objs.filter(service_name=service_name)
        # 如果没有, 则返回
        if not objs:
            logger.error("not found proxy cluster storage record")
            return
        # 组装推送的数据, 格式: {service_name: [instance_cluster_name1, instance_cluster_name2]}
        data = {}
        for obj in objs:
            data.setdefault(obj.service_name, set()).add(obj.instance_cluster_name)
        # 推送数据, 现阶段推送到 consul 和 redis
        hash_consul = consul_tools.HashConsul()
        service_name_list = []
        for service_name, inst_set in data.items():
            inst_list = list(inst_set)
            cls.push_to_redis(service_name, inst_list, is_publish=False)
            cls.push_to_consul(service_name, inst_list, hash_consul)
            service_name_list.append(service_name)

        # 针对 redis 进行 publish
        RedisTools.publish(constants.INFLUXDB_KEY_PREFIX, service_name_list)
        logger.info("push proxy cluster storage info successfully")

    @classmethod
    def push_to_redis(cls, field: str, val: List[str], is_publish: Optional[bool] = True):
        """推送数据到 redis"""
        super().push_to_redis(constants.INFLUXDB_PROXY_STORAGE_INFO_KEY, field, json.dumps(val), is_publish)

    @classmethod
    def push_to_consul(cls, key: str, val: List[str], client: Optional[consul_tools.HashConsul] = None):
        """推送数据到 consul

        TODO: 是否可以不用推送 consul?
        """
        if client is None:
            client = consul_tools.HashConsul()

        try:
            client.put(key=cls.CONSUL_PATH.format(service_name=key), value=val)
        except Exception as e:
            logger.error("put consul data error, key: %s, value: %s, error: %s", key, json.dumps(val), e)
            return

        logging.info("push proxy cluster storage info to consul successfully")
