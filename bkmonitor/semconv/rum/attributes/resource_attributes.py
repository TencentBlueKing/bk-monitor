"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _

from semconv.rum import composite
from semconv.rum.field import FieldSpec
from semconv.rum.constants import ResourceType, ResourceRenderBlockingStatus
from semconv.constants import FieldUnit


RESOURCE_TYPE = FieldSpec(field_name="resource.type", field_alias=_("资源类型"), option_values=ResourceType)
RESOURCE_INITIATOR_TYPE = FieldSpec(field_name="resource.initiator_type", field_alias=_("资源发起方式"))
RESOURCE_SIZE = FieldSpec(
    field_name="resource.size",
    field_alias=_("资源大小"),
    field_unit=FieldUnit.BYTES.value,
    extra_config={"composite": composite.RESOURCE_SIZE},
)
RESOURCE_TRANSFER_SIZE = FieldSpec(
    field_name="resource.transfer_size", field_alias=_("传输大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_ENCODED_BODY_SIZE = FieldSpec(
    field_name="resource.encoded_body_size", field_alias=_("压缩后大小"), field_unit=FieldUnit.BYTES.value
)
RESOURCE_PROTOCOL = FieldSpec(field_name="resource.protocol", field_alias=_("资源协议"))
RESOURCE_DELIVERY_TYPE = FieldSpec(field_name="resource.delivery_type", field_alias=_("资源获取方式"))
RESOURCE_RENDER_BLOCKING_STATUS = FieldSpec(
    field_name="resource.render_blocking_status",
    field_alias=_("渲染阻塞状态"),
    option_values=ResourceRenderBlockingStatus,
)
