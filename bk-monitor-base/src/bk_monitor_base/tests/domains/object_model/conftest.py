"""
object_model 测试配置
"""

import pytest
from django.conf import settings

from bk_monitor_base.domains.object_model.define import DatasourceType, ObjectModel
from bk_monitor_base.infras.i18n.language import Language, get_language


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests(db):
    """为所有测试启用数据库访问"""
    pass


@pytest.fixture
def mock_object_model():
    """创建模拟的对象模型实体"""

    return ObjectModel(
        object_model_id=1,
        object_model_code="test_model",
        object_model_name="测试模型",
        object_model_group_id=1,
        datasource=DatasourceType.CMDB,
        is_default=False,
        bk_cmdb_obj_id="test_cmdb_obj",
        display_fields=[{"field": "name"}],
        inst_display_name="test_display",
    )


@pytest.fixture
def mock_child_object_model():
    """创建模拟的子对象模型实体"""

    return ObjectModel(
        object_model_id=2,
        object_model_code="test_child_model",
        object_model_name="测试子模型",
        object_model_group_id=1,
        datasource=DatasourceType.CMDB,
        is_default=False,
        bk_cmdb_obj_id="test_cmdb_obj",
        display_fields=[{"field": "name"}],
        inst_display_name="test_display",
    )


@pytest.fixture
def default_language() -> Language:
    return get_language(code=settings.LANGUAGE_CODE)
