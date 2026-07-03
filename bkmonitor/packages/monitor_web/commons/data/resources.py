"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.conf import settings
from django.utils.translation import gettext as _

from bkmonitor.utils.cache import CacheType, using_cache
from bkmonitor.utils.common_utils import safe_int
from bkmonitor.views import serializers
from common.log import logger
from constants.data_source import LabelType
from core.drf_resource import api, resource
from core.drf_resource.contrib.cache import CacheResource
from core.drf_resource.exceptions import CustomException


@using_cache(CacheType.DATA(60 * 60))
def get_key_alias(result_table_id):
    """获取字段的别名"""

    result = api.metadata.get_result_table(table_id=result_table_id)
    return {field["field_name"]: field["description"] or field["field_name"] for field in result["field_list"]}


def get_desc_by_field(rt_id, field):
    """
    获取表字段的中文描述
    """
    try:
        ret = get_key_alias(rt_id).get(field, field)
        return _(ret) if ret else ret
    except Exception as e:
        logger.warning("获取表字段的中文描述失败" + f" rt_id:{rt_id} field:{field}, except:{e}")
        return field


def trans_bkcloud_rt_bizid(result_table_id):
    # rt id 第一段为biz_id
    final_rt = result_table_id
    rt_id_infos = result_table_id.split("_")
    if (not rt_id_infos) or (len(rt_id_infos) < 2):
        return result_table_id
    biz_id = safe_int(rt_id_infos[0], 0)
    if biz_id < settings.RT_TABLE_PREFIX_VALUE:
        rt_id_infos[0] = "%s" % (int(biz_id) + settings.RT_TABLE_PREFIX_VALUE)
        final_rt = "_".join(rt_id_infos)
    return final_rt


class GetLabelResource(CacheResource):
    """
    列出结果表的分类标签
    """

    cache_type = CacheType.DATA

    class RequestSerializer(serializers.Serializer):
        # 标签层级, 层级从1开始计算, 该配置只在label_type为result_table时生效
        label_type = serializers.CharField(required=False, default=LabelType.ResultTableLabel, label="标签类别")
        level = serializers.IntegerField(required=False, label="标签层级")
        include_admin_only = serializers.BooleanField(required=False, default=True, label="是否展示管理员标签")

    def perform_request(self, validated_request_data):
        try:
            result = api.metadata.get_label(**validated_request_data)
        except Exception as e:
            raise CustomException(_("获取分类标签失败：{}").format(e))

        return_data = []
        index = 0
        first_mapping_second = {}
        for label_msg in result["result_table_label"]:
            if label_msg["level"] == 1:
                return_data.append(
                    {
                        "id": label_msg["label_id"],
                        "name": label_msg["label_name"],
                        "index": label_msg["index"],
                        "children": [],
                    }
                )
                first_mapping_second[label_msg["label_id"]] = index
                index += 1

        for label_msg in result["result_table_label"]:
            parent_label = label_msg.get("parent_label", None)
            if parent_label:
                index = first_mapping_second[parent_label]
                return_data[index]["children"].append(
                    {"id": label_msg["label_id"], "name": label_msg["label_name"], "index": label_msg["index"]}
                )

        return_data.sort(key=lambda x: x["index"])
        for label_msg in return_data:
            # children 的label 按index排序
            label_msg["children"].sort(key=lambda x: x["index"])
        return_data = [label_msg for label_msg in return_data if len(label_msg["children"]) > 0]
        return return_data


def get_label_msg(label):
    """
    根据二级标签获取一级标签信息；若 label 本身是一级标签则回退用一级标签信息；
    label 不存在于结果表标签中时记录 warning 并回退用 label 自身，避免导入/展示整体中断。
    """
    result = {}
    label_map = resource.commons.get_label()
    for first_label in label_map:
        for second_label in first_label["children"]:
            if second_label["id"] == label:
                result["first_label"] = first_label["id"]
                result["first_label_name"] = first_label["name"]
                result["second_label"] = second_label["id"]
                result["second_label_name"] = second_label["name"]
                return result

    # 未命中二级标签：label 可能本身是一级标签（如 others，无二级子标签，
    # 会被上面 get_label() 的 children 过滤丢掉，故改用原始 metadata 接口判断全部层级）。
    # include_admin_only 是后端 LabelResource 的必填参数，须显式传入。
    all_labels = api.metadata.get_label(label_type=LabelType.ResultTableLabel, include_admin_only=True)[
        "result_table_label"
    ]
    for label_info in all_labels:
        if label_info["level"] == 1 and label_info["label_id"] == label:
            return {
                "first_label": label_info["label_id"],
                "first_label_name": label_info["label_name"],
                "second_label": label_info["label_id"],
                "second_label_name": label_info["label_name"],
            }

    # 既非二级、也非真实一级标签：可能是拼错或已删除的无效标签。
    # 记录告警便于排查，但仍回退展示，避免导入配置包、插件、采集等场景因单个无效标签整体中断。
    logger.warning("get_label_msg 未匹配到结果表标签，可能为无效或已删除的标签: %s", label)
    return {
        "first_label": label,
        "first_label_name": label,
        "second_label": label,
        "second_label_name": label,
    }
