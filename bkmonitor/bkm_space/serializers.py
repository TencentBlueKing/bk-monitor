from django.utils.translation import gettext as _
from rest_framework import serializers
from rest_framework.exceptions import NotFound, ParseError, PermissionDenied, ValidationError

from bkm_space.errors import NoRelatedResourceError
from bkm_space.utils import parse_space_uid
from bkm_space.validate import validate_bk_biz_id


def resolve_cmdb_biz_id(bk_biz_id: int, bk_inst_id=None) -> int:
    """解析关联业务，并校验当前空间的业务根别名。"""
    try:
        cmdb_biz_id = validate_bk_biz_id(bk_biz_id)
    except NoRelatedResourceError as error:
        raise NotFound(_("当前空间没有关联的 CMDB 业务")) from error
    if bk_inst_id is not None:
        try:
            node_id = int(bk_inst_id)
        except (TypeError, ValueError) as error:
            raise ParseError(_("业务节点 ID 无效")) from error
        if node_id not in (int(bk_biz_id), cmdb_biz_id):
            raise PermissionDenied(_("业务节点不属于当前空间"))
    return cmdb_biz_id


class CMDBScopeSerializer(serializers.Serializer):
    """主机数据接口使用关联业务，同时接受当前空间的根节点别名。"""

    def validate(self, attrs):
        if bool(attrs.get("bk_obj_id")) != (attrs.get("bk_inst_id") is not None):
            raise ParseError(_("拓扑模型和节点 ID 必须同时提供"))
        is_biz_node = attrs.get("bk_obj_id") == "biz"
        attrs["bk_biz_id"] = resolve_cmdb_biz_id(attrs["bk_biz_id"], attrs.get("bk_inst_id") if is_biz_node else None)
        if is_biz_node:
            attrs["bk_inst_id"] = attrs["bk_biz_id"]
        return attrs


class SpaceUIDField(serializers.CharField):
    def run_validation(self, *args, **kwargs):
        value = super().run_validation(*args, **kwargs)
        try:
            parse_space_uid(value)
        except ValueError:
            raise ValidationError(_('"{space_uid}" 不是合法的空间唯一标识符').format(space_uid=value))
        return value
