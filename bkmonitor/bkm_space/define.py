# -*- coding: utf-8 -*-
from dataclasses import asdict, dataclass, fields
from enum import Enum
from typing import Union

from django.conf import settings


class SpaceTypeEnum(Enum):
    """
    空间类型枚举
    """

    BKCC = "bkcc"  # CMDB 业务
    BCS = "bcs"  # BCS
    BKCI = "bkci"  # 蓝盾
    BKSAAS = "bksaas"  # 蓝鲸应用


class SpaceFunction(Enum):
    """
    空间能力枚举
    """

    APM = "APM"
    CUSTOM_REPORT = "CUSTOM_REPORT"  # 自定义上报
    HOST_COLLECT = "HOST_COLLECT"  # 主机采集
    CONTAINER_COLLECT = "CONTAINER_COLLECT"  # 容器采集
    HOST_PROCESS = "HOST_PROCESS"  # 主机监控
    UPTIMECHECK = "UPTIMECHECK"  # 自建拨测
    K8S = "K8S"  # Kubernetes
    CI_BUILDER = "CI_BUILDER"  # CI构建机
    PAAS_APP = "PAAS_APP"  # 蓝鲸应用


@dataclass
class Space:
    """
    空间格式
    """

    to_dict = asdict

    id: int
    space_type_id: str
    space_id: str
    space_name: str
    status: str
    space_code: Union[None, str]
    space_uid: str
    type_name: Union[None, str]
    bk_biz_id: int
    is_demo: bool = False
    time_zone: str = "Asia/Shanghai"

    @classmethod
    def from_dict(cls, data, cleaned=False):
        init_fields = {f.name for f in fields(cls) if f.init}
        filtered_data = {k: data.pop(k, None) for k in init_fields}
        if not cleaned:
            if filtered_data["space_type_id"] == SpaceTypeEnum.BKCC.value:
                filtered_data["bk_biz_id"] = int(filtered_data["space_id"])
            else:
                filtered_data["bk_biz_id"] = -int(filtered_data["id"])
            if filtered_data["bk_biz_id"] == int(settings.DEMO_BIZ_ID or 0):
                filtered_data["is_demo"] = True
            else:
                filtered_data["is_demo"] = False
        instance = cls(**filtered_data)
        setattr(instance, "extend", data)
        return instance

    @property
    def display_name(self):
        extend = getattr(self, "extend", {})
        return extend.get("display_name", self.space_name)
