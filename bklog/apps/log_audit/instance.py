__doc__ = """
from audit.instance import *
from bk_audit.log.exporters import BaseExporter
from rest_framework.test import APIRequestFactory
class ConsoleExporter(BaseExporter):
    is_delay = False
    def export(self, events):
        for event in events:
            print(event.to_json_str())
bk_audit_client.add_exporter(ConsoleExporter())
factory = APIRequestFactory()
request = factory.get("/grafana/api/dashboards/home", data={})
request.biz_id=2
class User:
    username = "admin"
setattr(request, "user", User())
push_event(request)
"""
import json
import re

from bk_audit.log.models import AuditContext, AuditInstance

from apps.iam import ActionEnum
from apps.log_audit.client import bk_audit_client


def get_request_parameters(request):
    params = {}

    # 获取表单数据
    form_data = request.POST.dict()
    params.update(form_data)

    # 获取 JSON 数据
    try:
        if request.body:
            json_data = json.loads(request.body)
            if isinstance(json_data, dict):
                params.update(json_data)
    except ValueError:
        # 忽略无效的 JSON 数据
        pass

    return params


class BaseLogInstance(object):
    action = None
    resource_id = ""

    @property
    def instance(self):
        return AuditInstance(self)

    @property
    def extend_data(self):
        return {"action_name": str(self.action.name)}

    @property
    def resource_type(self):
        class ResourceType(object):
            id = ""

        _resource_type = ResourceType()
        _resource_type.id = self.resource_id
        return _resource_type


class LogExtractInstance(BaseLogInstance):
    action = ActionEnum.MANAGE_EXTRACT_CONFIG
    resource_id = "LogExtract"

    def __init__(self, uid=""):
        self.instance_id = uid
        self.instance_name = uid


class LogSearchInstance(BaseLogInstance):
    action = ActionEnum.SEARCH_LOG
    resource_id = "LogSearch"

    def __init__(self, uid=""):
        self.instance_id = uid
        self.instance_name = uid


def push_event(request):
    """
    基于request对象，自动上报审计日志
    """
    key_params = ["user"]
    # request 合法性验证
    for key in key_params:
        if not hasattr(request, key):
            return

    instance = None
    for regex, instance_cls in InstanceFilter:
        ret = regex.match(request.get_full_path())
        if ret:
            instance = instance_cls(**ret.groupdict())
            break

    if instance is None:
        return

    context = AuditContext(request=request)

    extend_data = {
        "external_user": getattr(request, "external_user", ""),
        "request_data": get_request_parameters(request),
        "request_url": request.build_absolute_uri(),
        "request_method": request.method,
    }
    extend_data.update(instance.extend_data)
    bk_audit_client.add_event(
        action=instance.action,
        resource_type=instance.resource_type,
        audit_context=context,
        instance=instance.instance,
        extend_data=json.dumps(extend_data),
    )
    bk_audit_client.export_events()


InstanceFilter = (
    # 检索-SearchViewSet
    (re.compile(r"/api/v1/search/index_set/\?space_uid=\w+"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/search"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/fields"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/context"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/tail_f"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/export"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/async_export"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/export_history"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/history"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/option/history"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/config/"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/create_config"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/update_config"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/retrieve_config"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/list_config/"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/delete_config"), LogSearchInstance),
    # 聚合-AggsViewSet
    (re.compile(r"/api/v1/search/index_set/\d+/aggs/terms"), LogSearchInstance),
    (re.compile(r"/api/v1/search/index_set/\d+/aggs/date_histogram"), LogSearchInstance),
    # 收藏-FavoriteViewSet
    (re.compile(r"/api/v1/search/favorite/\d+"), LogSearchInstance),  # retrieve 和 destory合并
    (re.compile(r"/api/v1/search/favorite/\?space_uid=\w+"), LogSearchInstance),  # list
    (re.compile(r"/api/v1/search/favorite/list_by_group"), LogSearchInstance),
    (re.compile(r"/api/v1/search/favorite/$"), LogSearchInstance),  # update  # TODO 和create合并
    (re.compile(r"/api/v1/search/favorite/batch_update"), LogSearchInstance),
    (re.compile(r"/api/v1/search/favorite/batch_delete"), LogSearchInstance),
    (re.compile(r"/api/v1/search/favorite/get_search_fields"), LogSearchInstance),
    (re.compile(r"/api/v1/search/favorite/generate_query"), LogSearchInstance),
    (re.compile(r"/api/v1/search/favorite/inspect"), LogSearchInstance),
    # 收藏组-FavoriteGroupViewSet
    (re.compile(r"/api/v1/search/favorite/\?space_uid=\w+"), LogSearchInstance),
    (re.compile(r"/api/v1/search/favorite_group/$"), LogSearchInstance),
    (re.compile(r"/api/v1/search/favorite_group/\d+"), LogSearchInstance),
    # IP选择器
    (re.compile(r"/api/v1/ipchooser/topo/trees"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/topo/query_path"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/topo/query_hosts"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/topo/query_host_id_infos"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/topo/agent_statistics"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/host/check"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/host/details"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/template/templates"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/template/nodes"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/template/hosts"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/template/agent_statistics"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/dynamic_group/dynamic_groups"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/dynamic_group/execute_dynamic_group"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/dynamic_group/agent_statistics"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/config/global_config"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/config/batch_get"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/config/update_config"), LogSearchInstance),
    (re.compile(r"/api/v1/ipchooser/config/batch_delete"), LogSearchInstance),
    # # 收藏联合查询-FavoriteUnionSearchViewSet
    (re.compile(r"/api/v1/search/favorite_union/\?space_uid=\w+"), LogSearchInstance),
    # BizsViewSet
    (re.compile(r"/api/v1/bizs/\d+/get_display_name"), LogSearchInstance),
    #  日志提取-ExplorerViewSet
    (re.compile(r"/api/v1/log_extract/explorer/list_file"), LogExtractInstance),
    (re.compile(r"/api/v1/log_extract/explorer/strategies"), LogExtractInstance),
    (re.compile(r"/api/v1/log_extract/explorer/topo/"), LogExtractInstance),
    (re.compile(r"/api/v1/log_extract/explorer/tree/"), LogExtractInstance),
    (re.compile(r"/api/v1/log_extract/explorer/query_hosts"), LogExtractInstance),
    (re.compile(r"/api/v1/log_extract/explorer/query_host_id_infos"), LogExtractInstance),
    # # 日志提取-TaskViewSet
    (re.compile(r"/api/v1/log_extract/tasks"), LogSearchInstance),
    (re.compile(r"/api/v1/log_extract/tasks/download"), LogSearchInstance),
    (re.compile(r"/api/v1/log_extract/tasks/recreate"), LogSearchInstance),
    (re.compile(r"/api/v1/log_extract/tasks/polling"), LogSearchInstance),
    (re.compile(r"/api/v1/log_extract/tasks/\d+"), LogSearchInstance),
    (re.compile(r"/api/v1/log_extract/tasks/link_list"), LogSearchInstance),
    (re.compile(r"/api/v1/log_extract/tasks/download"), LogSearchInstance),
    # META-MetaViewSet
    (re.compile(r"/api/v1/meta/mine"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/spaces/mine"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/projects"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/index_html_environment"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/projects/mine"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/msg_type"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/scenario"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/globals"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/biz_maintainer"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/footer_html"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/user_guide"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/update_user_guide"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/language"), LogSearchInstance),
    (re.compile(r"/api/v1/meta/menu/\?space_uid=\w+"), LogSearchInstance),
    (re.compile(r"/api/v1/get_docs_link"), LogSearchInstance),
)
