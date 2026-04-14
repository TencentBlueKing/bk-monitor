import pytest
from rest_framework.exceptions import ValidationError

from fta_web.alert.resources import AlertTopNResource


class TestAlertTopNResource:
    def test_request_serializer_rejects_too_many_nested_fields(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"tags.field_{index}" for index in range(21)],
                "size": 10,
            }
        )

        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)

    def test_request_serializer_allows_nested_fields_within_limit(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"tags.field_{index}" for index in range(20)],
                "size": 10,
            }
        )

        serializer.is_valid(raise_exception=True)
        assert len(serializer.validated_data["fields"]) == 20

    def test_request_serializer_rejects_prefixed_nested_fields(self):
        serializer = AlertTopNResource.RequestSerializer(
            data={
                "bk_biz_ids": [2],
                "conditions": [],
                "query_string": "",
                "start_time": 1711900800,
                "end_time": 1711987200,
                "fields": [f"-tags.field_{index}" for index in range(21)],
                "size": 10,
            }
        )

        with pytest.raises(ValidationError):
            serializer.is_valid(raise_exception=True)
