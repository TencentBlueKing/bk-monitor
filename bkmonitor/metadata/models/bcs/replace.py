# -*- coding: utf-8 -*-

import logging

from django.db import models

logger = logging.getLogger("metadata")


class ReplaceConfig(models.Model):
    REPLACE_TYPES_METRIC = "metric"
    REPLACE_TYPES_DIMENSION = "dimension"

    CUSTOM_LEVELS_CLUSTER = "cluster"
    CUSTOM_LEVELS_RESOURCE = "resource"

    RESOURCE_TYPES_SERVICE = "ServiceMonitor"
    RESOURCE_TYPES_POD = "PodMonitor"

    # 规则名称,用于用户作为区分标志
    rule_name = models.CharField("replace规则名", max_length=128, primary_key=True)
    # 是否通用配置，该配置为true时，custom_level,custom_level才生效
    is_common = models.BooleanField("是否是通用replace配置", db_index=True, max_length=128)
    source_name = models.CharField("数据源名称", max_length=128)
    target_name = models.CharField("replace目标名称", max_length=128)
    # replace的是指标还是维度
    replace_type = models.CharField(
        "replace类型",
        max_length=128,
        choices=[(REPLACE_TYPES_DIMENSION, REPLACE_TYPES_DIMENSION), (REPLACE_TYPES_METRIC, REPLACE_TYPES_METRIC)],
    )
    # 仅is_common=False时生效，该配置影响集群还是某个resource
    custom_level = models.CharField(
        "自定义影响层级",
        max_length=128,
        choices=[
            (CUSTOM_LEVELS_CLUSTER, CUSTOM_LEVELS_CLUSTER),
            (CUSTOM_LEVELS_RESOURCE, CUSTOM_LEVELS_RESOURCE),
        ],
        default=None,
        null=True,
        blank=True,
    )

    # 生效目标集群id
    cluster_id = models.CharField(
        "集群id",
        max_length=128,
        db_index=True,
        default=None,
        null=True,
        blank=True,
    )

    # resource信息 custom_level为resource时生效
    resource_name = models.CharField(
        "资源名",
        max_length=128,
        db_index=True,
        default=None,
        null=True,
        blank=True,
    )
    resource_type = models.CharField(
        "资源类型",
        max_length=128,
        db_index=True,
        choices=[
            (RESOURCE_TYPES_SERVICE, RESOURCE_TYPES_SERVICE),
            (RESOURCE_TYPES_POD, RESOURCE_TYPES_POD),
        ],
        default=None,
        null=True,
        blank=True,
    )
    resource_namespace = models.CharField(
        "资源命名空间",
        max_length=128,
        db_index=True,
        default=None,
        null=True,
        blank=True,
    )

    @classmethod
    def get_replace_config(cls, items) -> dict:
        metric_replace = {}
        dimension_replace = {}
        for item in items:
            if item.replace_type == cls.REPLACE_TYPES_METRIC:
                metric_replace[item.source_name] = item.target_name
            else:
                dimension_replace[item.source_name] = item.target_name
        return {cls.REPLACE_TYPES_METRIC: metric_replace, cls.REPLACE_TYPES_DIMENSION: dimension_replace}

    @classmethod
    def get_common_replace_config(cls) -> dict:
        """获取通用的replace配置"""
        return cls.get_replace_config(cls.objects.filter(is_common=True))

    @classmethod
    def get_cluster_replace_config(cls, cluster_id: str) -> dict:
        """获取集群层级的replace配置"""
        return cls.get_replace_config(
            cls.objects.filter(is_common=False, custom_level=cls.CUSTOM_LEVELS_CLUSTER, cluster_id=cluster_id)
        )

    @classmethod
    def get_resource_replace_config(
        cls, cluster_id: str, resource_name: str, resource_type: str, resource_namespace: str
    ):
        """获取resource层级的replace配置"""
        return cls.get_replace_config(
            cls.objects.filter(
                is_common=False,
                cluster_id=cluster_id,
                custom_level=cls.CUSTOM_LEVELS_RESOURCE,
                resource_name=resource_name,
                resource_type=resource_type,
                resource_namespace=resource_namespace,
            )
        )

    @classmethod
    def export_data(cls):
        items = cls.objects.all()
        data = list(
            items.values(
                "rule_name",
                "is_common",
                "source_name",
                "target_name",
                "replace_type",
                "custom_level",
                "cluster_id",
                "resource_name",
                "resource_type",
                "resource_namespace",
            )
        )
        return data

    @classmethod
    def import_data(cls, data):
        items = data
        # 遍历初始化rule_name
        for item in items:
            if not item.get("rule_name", ""):
                if item["is_common"]:
                    item["rule_name"] = "{}_{}_{}".format(item["source_name"], item["target_name"], "common")
                elif item["custom_level"] == cls.CUSTOM_LEVELS_RESOURCE:
                    item["rule_name"] = "{}_{}_{}_{}_{}_{}_{}".format(
                        item["source_name"],
                        item["target_name"],
                        item["custom_level"],
                        item["cluster_id"],
                        item["resource_name"],
                        item["resource_type"],
                        item["resource_namespace"],
                    )
                else:
                    item["rule_name"] = "{}_{}_{}_{}".format(
                        item["source_name"], item["target_name"], item["custom_level"], item["cluster_id"]
                    )
        # 整理删除目标
        delete_list = []
        for info in cls.objects.all():
            exist = False
            for item in items:
                if item["rule_name"] == info.rule_name:
                    exist = True
            if not exist:
                delete_list.append(info)

        for info in delete_list:
            data = info.__dict__
            info.delete()
            print("delete replace config:{}".format(data))
            logger.info("delete replace config:{}".format(data))

        # 新增或更新主机信息
        for item in items:
            obj, created = cls.objects.update_or_create(rule_name=item["rule_name"], defaults=item)
            if created:
                print("created replace config:{}".format(item))
                logger.info("create new replace config:{}".format(str(item)))
            else:
                print("updated replace config:{}".format(item))
                logger.info("update replace config to:{}".format(str(item)))
