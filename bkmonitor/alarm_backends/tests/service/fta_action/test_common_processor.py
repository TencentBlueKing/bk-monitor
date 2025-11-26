import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from alarm_backends.core.cache.action_config import ActionConfigCacheManager
from bkmonitor.models import ActionInstance, ActionPlugin
from constants.action import ActionSignal

pytestmark = pytest.mark.django_db(databases="__all__")


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment(django_db_setup, django_db_blocker):
    """
    配置测试环境
    """
    from django.conf import settings
    from alarm_backends.service.scheduler.app import app

    # 配置 celery 同步执行
    app.conf.task_always_eager = True
    app.conf.task_eager_propagates = True

    # 配置测试环境变量
    settings.BK_ITSM_V4_API_URL = "https://test.apigw.com/api/cw-aitsm/prod"
    settings.BK_ITSM_V4_HOST = "https://test.itsm_v4.com"
    settings.BK_ITSM_V4_SYSTEM_ID = "bkmonitor"

    # 使用 django_db_blocker 允许在 session 级别的 fixture 中访问数据库
    with django_db_blocker.unblock():
        register_builtin_plugins()

    yield


def register_builtin_plugins():
    from django.conf import settings
    import json

    if not ActionPlugin.objects.filter(name="新版ITSM流程服务").exists():
        initial_file = Path(settings.PROJECT_ROOT, "support-files/fta/action_plugin_initial.json")
        itsm_config = None
        for config in json.loads(initial_file.read_text()):
            if config["name"] == "新版ITSM流程服务":
                itsm_config = config
                break
        ActionPlugin.objects.create(**itsm_config)


def get_action_configs():
    """
    获取处理套餐配置
    :return:
    """
    action_configs = {
        1: {  # 1：处理套餐ID
            "id": 2133,
            "plugin_id": 10,
            "desc": "",
            "execute_config": {
                "template_detail": {
                    "ticket__title": "bkmonitor事件管理-测试",
                    "event_name": "测试",
                    "level": "1",
                    "start_time": "周二晚上6点",
                },
                "template_id": "20251119120300001201",
                "timeout": 600,
            },
            "name": "bkmonitor事件管理-测试",
            "bk_biz_id": 2,
            "is_enabled": True,
            "is_deleted": False,
            "create_user": "admin",
            "update_user": "admin",
            "is_builtin": False,
            "plugin_name": "新版ITSM流程服务",
            "plugin_type": "common",
            "strategy_count": 1,
            "edit_allowed": True,
        }
    }
    return action_configs


def get_action_plugin_config(plugin_name):
    """
    获取动作插件配置
    """
    action_plugin = ActionPlugin.objects.filter(name=plugin_name).first()

    # 手动构建字典，因为 ActionPlugin 模型没有 to_dict() 方法
    return {
        "id": action_plugin.id,
        "plugin_type": action_plugin.plugin_type,
        "plugin_key": action_plugin.plugin_key,
        "name": action_plugin.name,
        "description": action_plugin.description,
        "is_builtin": action_plugin.is_builtin,
        "is_peripheral": action_plugin.is_peripheral,
        "plugin_source": action_plugin.plugin_source,
        "has_child": action_plugin.has_child,
        "category": action_plugin.category,
        "config_schema": action_plugin.config_schema,
        "backend_config": action_plugin.backend_config,
    }


@pytest.fixture(scope="module", autouse=True)
def mock_get_action_config_by_id():
    action_configs = get_action_configs()
    with patch.object(ActionConfigCacheManager, "get_action_config_by_id", action_configs.get):
        yield mock_get_action_config_by_id


@pytest.fixture()
def mock_action_processor(monkeypatch):
    from alarm_backends.core.context import utils

    monkeypatch.setattr(utils, "get_notice_display_mapping", lambda *args, **kwargs: "")

    global ActionProcessor
    from alarm_backends.service.fta_action.common.processor import ActionProcessor

    monkeypatch.setattr(ActionProcessor, "set_start_to_execute", MagicMock)
    monkeypatch.setattr(ActionProcessor, "jinja_render", lambda self, x: x)


@pytest.fixture()
def mock_create_ticket(monkeypatch):
    """
    mock 创建单据

    该 fixture 模拟 ITSM 创建单据的 API 调用，返回创建成功后的单据信息

    返回:
        MagicMock: 模拟的 CommonBaseResource 实例，包含创建单据的响应数据
    """
    with patch("api.common.default.CommonBaseResource") as mock_common_base_resource:
        instance = MagicMock()

        ticket_id = "102025112415273000002503"
        frontend_url = (
            "https://test.itsm_v4.com/cw--aitsm/#/ticket/ticketInfo?type=ticket&ticketId=102025112415273000002503"
        )
        sn = "SQ2025112400000001"

        instance.request.return_value = {
            "approve_result": False,
            "callback_result": {},
            "created_at": "2025-11-24 15:27:30",
            "creator": "admin",
            "current_processors": [],
            "current_steps": [],
            "end_at": None,
            "form_data": {
                "event_name": "测试",
                "level": "1",
                "start_time": "周二晚上6点",
                "ticket__title": "bkmonitor事件管理-测试",
            },
            "frontend_url": frontend_url,
            "id": ticket_id,
            "jsonschema": {},
            "options": None,
            "portal_id": "DEFAULT",
            "service_id": None,
            "sn": sn,
            "status": "draft",
            "status_display": "草稿",
            "system_id": None,
            "title": "bkmonitor事件管理-测试",
            "updated_at": "2025-11-24 15:27:30",
            "workflow_id": "20251119120300001201",
        }

        mock_common_base_resource.return_value = instance
        mock_common_base_resource._instance = instance
        mock_common_base_resource._ticket_id = ticket_id
        mock_common_base_resource._frontend_url = frontend_url
        mock_common_base_resource._sn = sn

        yield mock_common_base_resource


@pytest.fixture()
def mock_get_ticket_detail(monkeypatch):
    """
    mock 获取单据详情

    该 fixture 模拟 ITSM 获取单据详情的 API 调用，返回单据的完整信息
    包括单据状态、处理人、当前步骤等详细信息

    返回:
        MagicMock: 模拟的 CommonBaseResource 实例，包含单据详情的响应数据
    """
    with patch("api.common.default.CommonBaseResource") as mock_common_base_resource:
        instance = MagicMock()

        ticket_id = "102025112418061200002901"
        frontend_url = (
            "https://test.itsm_v4.com/cw--aitsm/#/ticket/ticketInfo?type=ticket&ticketId=102025112418061200002901"
        )
        sn = "SQ2025112400000002"

        instance.request.return_value = {
            "id": ticket_id,
            "sn": sn,
            "title": "bkmonitor事件管理-测试",
            "created_at": "2025-11-24 18:06:12",
            "updated_at": "2025-11-24 18:06:12",
            "creator": "admin",
            "end_at": None,
            "status": "running",
            "status_display": "处理中",
            "workflow_id": "20251119120300001201",
            "workflow_key": None,
            "service_id": None,
            "service_name": None,
            "portal_id": "DEFAULT",
            "current_processors": [],
            "who_processors": [],
            "history_processors": [],
            "current_steps": [{"ticket_id": ticket_id, "name": "审批节点: 任务[102025112418061200000403]"}],
            "frontend_url": frontend_url,
            "form_data": {
                "level": "1",
                "event_name": "测试",
                "start_time": "周二晚上6点",
                "ticket__title": "bkmonitor事件管理-测试",
            },
            "jsonschema": {
                "type": "object",
                "properties": {
                    "level": {"type": "string", "title": "级别"},
                    "event_name": {"type": "string", "title": "事件名称"},
                    "start_time": {"type": "string", "title": "开始时间"},
                    "ticket__title": {"type": "string", "title": "标题"},
                },
                "additionalProperties": False,
            },
            "approve_result": False,
            "callback_result": {},
            "system_id": None,
            "options": None,
        }

        mock_common_base_resource.return_value = instance
        mock_common_base_resource._instance = instance
        mock_common_base_resource._ticket_id = ticket_id
        mock_common_base_resource._frontend_url = frontend_url
        mock_common_base_resource._sn = sn
        mock_common_base_resource._status = "running"
        mock_common_base_resource._status_display = "处理中"

        yield mock_common_base_resource


class TestItsmV4ActionProcessor:
    """
    测试新版ITSM-V4动作处理
    """

    def get_action_instance(self) -> ActionInstance:
        action_instance = ActionInstance.objects.filter(generate_uuid="123456789").first()
        if action_instance:
            return action_instance

        itsm_v4_config = get_action_plugin_config(plugin_name="新版ITSM流程服务")

        action_instance = ActionInstance.objects.create(
            signal=ActionSignal.ABNORMAL,  # 触发信号，必需
            status="running",
            strategy_id=123,  # 策略ID，必需
            bk_biz_id="2",  # 业务ID，必需
            generate_uuid="123456789",
            action_config=get_action_configs(),
            action_plugin=itsm_v4_config,
            action_config_id=1,
        )

        return action_instance

    def get_action_processor(self):
        action_instance = self.get_action_instance()
        processor = ActionProcessor(action_instance.id, MagicMock())
        return processor

    def test_instantiate_common_base_resource(self):
        from api.common.default import CommonBaseResource

        url = "{{itsm_v4_api_url}}/api/v1/workflows/"
        common_base_resource = CommonBaseResource(url=url)
        assert common_base_resource.base_url == "https://test.apigw.com/api/cw-aitsm/prod/api/v1/workflows/"

    def test_create_ticket(self, mock_create_ticket, mock_action_processor):
        """
        测试创建单据（一次性操作）

        该测试验证以下功能：
        1. 验证 create_task 函数配置正确
        2. 模拟调用创建单据的 API
        3. 验证 API 调用参数（POST 方法、正确的 URL）
        4. 验证请求参数（workflow_key、form_data）
        5. 验证返回的输出数据（id、sn、url）
        6. 验证非轮询配置（无 finished_rule、need_schedule）

        返回:
            None
        """
        processor = self.get_action_processor()

        # 验证第一个函数配置是 create_task（创建单据）
        assert processor.backend_config[0]["function"] == "create_task"

        config = processor.function_config["create_task"]
        # 执行创建单据的请求
        outputs = processor.run_request_action(config)

        # 验证 API 被调用
        mock_create_ticket.assert_called_once()
        call_args = dict(mock_create_ticket.call_args[-1])

        # 验证请求方法和 URL
        assert call_args["method"] == "POST"
        assert "/api/v1/ticket/create/" in call_args["url"]

        # 验证 request 方法被调用，并验证参数
        request_obj: MagicMock = mock_create_ticket._instance.request
        request_obj.assert_called_once()
        request_call_args = dict(request_obj.call_args[-1])
        action_config = get_action_configs()[1]
        assert request_call_args["workflow_key"] == action_config["execute_config"]["template_id"]
        assert request_call_args["form_data"] == action_config["execute_config"]["template_detail"]

        # 验证输出数据
        assert outputs["id"] == mock_create_ticket._ticket_id
        assert outputs["sn"] == mock_create_ticket._sn
        assert outputs["url"] == mock_create_ticket._frontend_url

        # 验证非轮询配置（创建单据是一次性操作，不需要轮询）
        assert config.get("finished_rule") is None
        assert config.get("need_schedule") is None
        assert config.get("next_function") is None

    def test_get_ticket_detail(self, mock_get_ticket_detail, mock_action_processor):
        """
        测试获取单据详情（轮询状态）

        该测试验证以下功能：
        1. 验证 schedule 函数配置正确
        2. 模拟调用获取单据详情的 API
        3. 验证 API 调用参数（GET 方法、正确的 URL）
        4. 验证返回的输出数据（状态、URL）
        5. 验证轮询相关配置（finished_rule、need_schedule、next_function）

        返回:
            None
        """
        processor = self.get_action_processor()
        assert processor.backend_config[1]["function"] == "schedule"

        config = processor.function_config["schedule"]
        pre_node_outputs = {"id": mock_get_ticket_detail._ticket_id}
        outputs = processor.run_request_action(config, pre_node_outputs=pre_node_outputs)

        # 验证 API 被调用
        mock_get_ticket_detail.assert_called_once()
        call_args = dict(mock_get_ticket_detail.call_args[-1])

        # 验证请求方法和 URL
        assert call_args["method"] == "GET"
        assert "/api/v1/ticket/detail/" in call_args["url"]

        # 验证 request 方法被调用，并验证参数
        request_obj: MagicMock = mock_get_ticket_detail._instance.request
        request_obj.assert_called_once()
        request_call_args = dict(request_obj.call_args[-1])
        assert request_call_args["id"] == mock_get_ticket_detail._ticket_id

        # 验证输出数据
        assert outputs["current_status"] == mock_get_ticket_detail._status
        assert outputs["url"] == mock_get_ticket_detail._frontend_url

        # 验证轮询相关配置
        assert config.get("finished_rule") is not None
        assert config["finished_rule"]["key"] == "current_status"
        assert config["finished_rule"]["method"] == "equal"
        assert config["finished_rule"]["value"] == "finished"

        assert config.get("need_schedule") is True
        assert config.get("next_function") == "schedule"
        assert config.get("schedule_timedelta") == 2

        # 验证状态未完成时，需要继续轮询
        assert outputs["current_status"] != "finished"
