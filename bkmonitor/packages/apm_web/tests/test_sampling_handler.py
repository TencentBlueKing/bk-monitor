"""验证采样配置在尾采 Flow 与 bk-collector 之间的分工：不重复采样、不采样等价随机 100%、未开尾采不建 Flow。"""

import pytest
from django.test import override_settings

from apm_web.constants import SamplerTypeChoices
from apm_web.meta.handlers.sampling_handler import SamplingHelpers
from apm_web.models import ApmMetaConfig, Application
from constants.apm import FlowType

RANDOM_100 = {"sampler_config": {"sampling_percentage": 100, "sampler_type": SamplerTypeChoices.RANDOM}}


def _build_helper(mocker, db_config, tail_opened=False):
    """绕过应用查询构造 SamplingHelpers：库中采样配置为 db_config，API 全部打桩。"""
    helper = SamplingHelpers.__new__(SamplingHelpers)
    helper.application = mocker.Mock(application_id=1, sampler_config=db_config)
    helper.application.get_sampler_config = lambda: Application.get_sampler_config(helper.application)
    helper.application_id = 1
    helper.bk_biz_id = 2
    helper.app_name = "demo"
    mocker.patch.object(ApmMetaConfig, "get_application_config_value", return_value=mocker.Mock(config_value=db_config))
    # 显式传 new：drf_resource 的 api 对象不支持 mock 默认的属性探测
    api = mocker.patch("apm_web.meta.handlers.sampling_handler.api", new=mocker.MagicMock())
    api.apm_api.get_bkdata_flow_detail.return_value = {"id": 1} if tail_opened else None
    return helper, api


@pytest.mark.parametrize(
    "sample_config",
    [
        # 随机采样由 bk-collector 按比例执行，Flow 全量放行
        {"sampler_type": SamplerTypeChoices.RANDOM, "sampler_percentage": 30},
        # 不采样等价随机 100%，Flow 也全量放行
        {"sampler_type": SamplerTypeChoices.EMPTY},
    ],
)
def test_random_and_empty_keep_all_in_flow(sample_config):
    helper = SamplingHelpers.__new__(SamplingHelpers)
    assert helper._change_to_tail_sampling_config(sample_config) == {"tail_percentage": 100, "tail_conditions": []}


def test_tail_keeps_percentage_and_conditions():
    conditions = [{"key": "status.code", "method": "eq", "value": ["2"]}]
    helper = SamplingHelpers.__new__(SamplingHelpers)
    assert helper._change_to_tail_sampling_config(
        {"sampler_type": SamplerTypeChoices.TAIL, "sampler_percentage": 30, "tail_conditions": conditions}
    ) == {"tail_percentage": 30, "tail_conditions": conditions}


def test_empty_transfers_as_random_100(mocker):
    """库里的不采样配置没有比例，下发 bk-collector 时转成随机 100%。"""
    application = mocker.Mock(sampler_config={"sampler_type": SamplerTypeChoices.EMPTY})
    assert Application.get_sampler_config(application) == RANDOM_100


def test_unchanged_config_skips_tail_sampling(mocker):
    """采样配置与库中一致（如只改了应用别名）时，不再下发尾采、不暂停数据源、不写库。"""
    db_config = {"sampler_type": SamplerTypeChoices.TAIL, "sampler_percentage": 30, "tail_conditions": []}
    helper, api = _build_helper(mocker, db_config, tail_opened=True)

    helper.setup(dict(db_config))

    api.apm_api.create_or_update_bkdata_flow.assert_not_called()
    api.apm_api.operate_apm_data_id.assert_not_called()
    helper.application.setup_config.assert_not_called()


@pytest.mark.parametrize(
    "db_config,new_config,expected_transfer",
    [
        (
            {"sampler_type": SamplerTypeChoices.RANDOM, "sampler_percentage": 50},
            {"sampler_type": SamplerTypeChoices.EMPTY},
            RANDOM_100,
        ),
        (
            {"sampler_type": SamplerTypeChoices.EMPTY},
            {"sampler_type": SamplerTypeChoices.RANDOM, "sampler_percentage": 50},
            {"sampler_config": {"sampling_percentage": 50, "sampler_type": SamplerTypeChoices.RANDOM}},
        ),
    ],
)
@override_settings(IS_ACCESS_BK_DATA=True)
def test_not_opened_random_and_empty_only_update_db(mocker, db_config, new_config, expected_transfer):
    """未开过尾采时，随机与不采样互切只写库并下发 bk-collector，不建尾采 Flow、不暂停数据源。"""
    helper, api = _build_helper(mocker, db_config)

    helper.setup(new_config)

    api.apm_api.create_or_update_bkdata_flow.assert_not_called()
    api.apm_api.operate_apm_data_id.assert_not_called()
    helper.application.setup_config.assert_called_once()
    assert helper.get_transfer_config() == expected_transfer


@override_settings(IS_ACCESS_BK_DATA=True)
def test_not_opened_tail_still_creates_flow(mocker):
    """未开过尾采时选择尾部采样，仍按页面比例和条件创建 Flow。"""
    helper, api = _build_helper(mocker, {"sampler_type": SamplerTypeChoices.RANDOM, "sampler_percentage": 100})

    helper.setup({"sampler_type": SamplerTypeChoices.TAIL, "sampler_percentage": 30, "tail_conditions": []})

    api.apm_api.create_or_update_bkdata_flow.assert_called_once_with(
        bk_biz_id=2,
        app_name="demo",
        flow_type=FlowType.TAIL_SAMPLING.value,
        config={"tail_percentage": 30, "tail_conditions": []},
    )


@pytest.mark.parametrize(
    "new_config,expected_transfer",
    [
        # 尾采切回随机 30%：Flow 全量放行，只在 bk-collector 采样
        (
            {"sampler_type": SamplerTypeChoices.RANDOM, "sampler_percentage": 30},
            {"sampler_config": {"sampling_percentage": 30, "sampler_type": SamplerTypeChoices.RANDOM}},
        ),
        # 尾采切到不采样：等价随机 100%
        ({"sampler_type": SamplerTypeChoices.EMPTY}, RANDOM_100),
    ],
)
@override_settings(IS_ACCESS_BK_DATA=True)
def test_opened_switch_off_tail_keeps_all_in_flow(mocker, new_config, expected_transfer):
    helper, api = _build_helper(
        mocker,
        {"sampler_type": SamplerTypeChoices.TAIL, "sampler_percentage": 30, "tail_conditions": []},
        tail_opened=True,
    )

    helper.setup(new_config)

    api.apm_api.create_or_update_bkdata_flow.assert_called_once_with(
        bk_biz_id=2,
        app_name="demo",
        flow_type=FlowType.TAIL_SAMPLING.value,
        config={"tail_percentage": 100, "tail_conditions": []},
    )
    assert helper.get_transfer_config() == expected_transfer
