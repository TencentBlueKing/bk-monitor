from django.test import TestCase
from bkmonitor.models.base import ReportContents, ReportItems
from monitor_web.report.resources import ReportCreateOrUpdateResource

BK_TENANT_ID = "system"
VALIDATED_REQUEST_DATA = {
    "mail_title": "邮件标题623",
    "receivers": [{"id": "bk_biz_maintainer", "type": "group", "is_enabled": True}],
    "channels": [
        {"is_enabled": False, "channel_name": "email", "subscribers": []},
        {"is_enabled": False, "channel_name": "wxbot", "subscribers": []},
    ],
    "managers": [{"id": "bk_biz_maintainer", "type": "group"}],
    "frequency": {
        "type": 2,
        "day_list": [],
        "week_list": [1, 2, 3, 4, 5, 6, 7],
        "run_time": "14:45:25",
        "hour": 0.5,
        "data_range": {"time_level": "minutes", "number": 15},
    },
    "report_contents": [
        {
            "content_title": "子标题623",
            "content_details": "说明623",
            "row_pictures_num": 2,
            "width": 3000,
            "height": 1000,
            "graphs": ["2-fxHySlGNz-4"],
        }
    ],
    "is_link_enabled": False,
}
VALIDATED_REQUEST_UPDATE_DATA = {
    "mail_title": "邮件标题623",
    "receivers": [
        {"id": "bk_biz_maintainer", "type": "group", "is_enabled": True},
        {"id": "admin", "group": "bk_biz_maintainer", "type": "user", "is_enabled": True},
        {"id": "study1_ex", "group": "bk_biz_maintainer", "type": "user", "is_enabled": True},
        {"id": "lucas", "group": "bk_biz_maintainer", "type": "user", "is_enabled": True},
        {"id": "v_cscaichen", "group": "bk_biz_maintainer", "type": "user", "is_enabled": True},
    ],
    "channels": [
        {"is_enabled": False, "channel_name": "email", "subscribers": []},
        {"is_enabled": False, "channel_name": "wxbot", "subscribers": []},
    ],
    "managers": [{"id": "bk_biz_maintainer", "type": "group"}],
    "frequency": {
        "type": 2,
        "day_list": [],
        "week_list": [1, 2, 3, 4, 5, 6, 7],
        "run_time": "14:45:25",
        "hour": 0.5,
        "data_range": {"time_level": "minutes", "number": 15},
    },
    "report_contents": [
        {
            "content_title": "子标题623",
            "content_details": "说明623",
            "row_pictures_num": 1,
            "width": 4000,
            "height": 2000,
            "graphs": ["2-fxHySlGNz-4"],
        }
    ],
    "is_link_enabled": False,
}
REPORT_CONTENTS_RESULT_DATA2 = {"width": 4000, "height": 2000}


class TestReportCreateOrUpdateResource(TestCase):
    databases = {"default", "monitor_api"}

    def test_perform_request(self):
        ReportCreateOrUpdateResource().perform_request(VALIDATED_REQUEST_DATA)
        item = ReportContents.objects.filter(bk_tenant_id=BK_TENANT_ID)
        self.assertIsNotNone(item)

        item = ReportItems.objects.filter(bk_tenant_id=BK_TENANT_ID).first()
        self.assertIsNotNone(item)

        # 更新逻辑
        VALIDATED_REQUEST_UPDATE_DATA["report_item_id"] = item.id
        ReportCreateOrUpdateResource().perform_request(VALIDATED_REQUEST_UPDATE_DATA)
        result = (
            ReportContents.objects.filter(report_item=item.id, bk_tenant_id=BK_TENANT_ID)
            .values("width", "height")
            .first()
        )
        self.assertEqual(result, REPORT_CONTENTS_RESULT_DATA2)
