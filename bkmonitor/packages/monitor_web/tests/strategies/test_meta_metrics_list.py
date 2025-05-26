import logging

import pytest


from monitor_web.strategies.metric_list_cache import BkdataMetricCacheManager

logger = logging.getLogger("app")


@pytest.mark.django_db(databases=["default", "monitor_api"])
def test_bkdata_metric_list():
    logger.info("start")
    # 创建对象
    manager = BkdataMetricCacheManager(bk_biz_id=7)
    # 执行_run方法
    manager._run()
