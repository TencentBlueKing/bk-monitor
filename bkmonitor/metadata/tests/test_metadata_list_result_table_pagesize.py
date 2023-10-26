# -*- coding: utf-8 -*-
import pytest

from metadata import models
from metadata.resources import ListResultTableResource
from metadata.utils.bcs import get_bcs_dataids


@pytest.mark.django_db
class TestApiPagesize:
    """
    测试分页功能
    """

    def test_pagesize(self, mocker):
        result = ListResultTableResource().request(page=1, page_size=3)
        assert 3 == len(result["info"])

        data_ids, data_id_cluster_map = get_bcs_dataids()
        table_ids = [
            item["table_id"]
            for item in models.DataSourceResultTable.objects.exclude(bk_data_id__in=data_ids)
            .values("table_id")
            .distinct()
        ]
        count = models.ResultTable.objects.filter(table_id__in=table_ids).count()
        result = ListResultTableResource().request()
        assert count == len(result)
