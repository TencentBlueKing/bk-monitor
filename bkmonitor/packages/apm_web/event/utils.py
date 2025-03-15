from ..models import Application


def is_enabled_metric_tags(bk_biz_id: int, app_name: str):
    application = Application.objects.filter(bk_biz_id=bk_biz_id, app_name=app_name).first()
    return application is not None and application.event_config["is_enabled_metric_tags"]
