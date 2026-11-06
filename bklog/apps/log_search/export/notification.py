"""分片导出终态邮件通知；由周期任务扫描终态任务后触发，发送失败只记日志，不重试。"""

import copy
import json
from urllib.parse import urlencode

import arrow
from django.conf import settings
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from apps.feature_toggle.handlers.toggle import FeatureToggleObject
from apps.log_search.constants import (
    ASYNC_EXPORT_EMAIL_ERR_TEMPLATE,
    ASYNC_EXPORT_EMAIL_TEMPLATE,
    FEATURE_ASYNC_EXPORT_COMMON,
    FEATURE_ASYNC_EXPORT_NOTIFY_TYPE,
    ExportJobStatus,
    ExportSearchType,
    IndexSetType,
)
from apps.log_search.export import state
from apps.log_search.export.storage import build_storage
from apps.log_search.models import LogIndexSet, Space
from apps.utils.local import get_local_param, get_request, get_request_external_user_email, get_request_language_code
from apps.utils.log import logger
from apps.utils.notify import NotifyType


def build_notification_context(search_params, space_uid, index_set_type, index_set_ids):
    request = get_request(peaceful=True)
    search_url = ""
    if request is not None:
        base_url = f"{request.scheme}://{request.get_host()}{settings.SITE_URL}#/retrieve"
        if index_set_type == ExportSearchType.SCENE:
            search_url = f"{base_url}/scene"
        else:
            params = copy.deepcopy(search_params)
            params.pop("sort_list", None)
            params.update(bizId=params.get("bk_biz_id"), spaceUid=space_uid)
            if index_set_type == IndexSetType.UNION.value:
                params["unionList"] = index_set_ids
            else:
                base_url = f"{base_url}/{index_set_ids[0]}"
            params = {
                key: json.dumps(value) if isinstance(value, dict | list) else value for key, value in params.items()
            }
            search_url = f"{base_url}?{urlencode(params)}"
    return {
        "language": get_request_language_code(),
        "external_user_email": get_request_external_user_email(),
        # 邮件在异步任务中发送，创建时固化用户时区，避免只能使用部署时区
        "time_zone": get_local_param("time_zone"),
        "search_url": search_url,
    }


def notify_terminal_job(job_id):
    """
    终态任务的通知入口：先原子占位再发送，同一个任务最多发送一次。

    不重试也不保证成功：占位后发送失败只记日志，任务不会回到待通知状态。
    """
    job = state.claim_notification(job_id)
    if job is None:
        # 已被其它执行认领
        return
    send_export_notification(job)


def _notify_channel():
    """按 feature_async_export 的 notify_type 取通知渠道实例。"""
    notify_type = FeatureToggleObject.toggle(FEATURE_ASYNC_EXPORT_COMMON).feature_config.get(
        FEATURE_ASYNC_EXPORT_NOTIFY_TYPE
    )
    return NotifyType.get_instance(notify_type=notify_type)()


def _index_set_summary(job):
    """邮件里展示的索引集名称与索引名；场景化检索没有索引集。"""
    if job.search_type == ExportSearchType.SCENE:
        return _("场景化检索"), []
    index_sets = list(LogIndexSet.objects.filter(pk__in=job.index_set_ids))
    index_set_name = ",".join(index.index_set_name for index in index_sets) or str(job.index_set_ids)
    indexes = [item["result_table_id"].replace(".", "_") for index in index_sets for item in index.indexes]
    return index_set_name, indexes


def _title_template(job, success):
    """标题模板与旧异步导出链路保持一致。"""
    if job.search_type == ExportSearchType.SCENE:
        return _("【{platform}】场景化检索导出") if success else _("【{platform}】场景化检索导出失败")
    if job.index_set_type == IndexSetType.UNION.value:
        return (
            _("【{platform}】【{index_set_names}】 检索导出")
            if success
            else _("【{platform}】【{index_set_names}】 检索导出失败")
        )
    return _("【{platform}】{index_set_name} 检索导出") if success else _("【{platform}】{index_set_name} 检索导出失败")


def _download_url(job):
    """整包下载链接；邮件需允许稍后打开，有效期取产物的剩余保留时间，接口短签名策略不变。"""
    remaining = int((job.expires_at - timezone.now()).total_seconds())
    if remaining <= 0:
        raise ValueError("导出产物已过期")
    return build_storage(external=job.is_external).generate_download_url(
        file_name=job.merged_object_key, expired=remaining
    )


def send_export_notification(job):
    try:
        context = job.notification_context
        receivers = context.get("external_user_email") if job.is_external else job.created_by
        if not receivers:
            logger.warning("[sharded_export_notification_skipped] job_id=%s missing receiver", job.pk)
            return
        language = context["language"]
        time_zone = context.get("time_zone") or settings.TIME_ZONE
        success = job.status == ExportJobStatus.SUCCESS
        with translation.override(language):
            platform = settings.EMAIL_TITLE["en"] if language == "en" else settings.EMAIL_TITLE["zh"]
            index_set_name, indexes = _index_set_summary(job)
            notify = _notify_channel()
            download_url = _download_url(job) if success else ""
            title = notify.title(
                _title_template(job, success),
                platform=platform,
                index_set_name=index_set_name,
                index_set_names=index_set_name,
            )
            content = notify.content(
                name=ASYNC_EXPORT_EMAIL_TEMPLATE if success else ASYNC_EXPORT_EMAIL_ERR_TEMPLATE,
                language=language,
                file={
                    "platform": platform,
                    "created_at": arrow.get(job.created_at).to(time_zone).format("YYYY-MM-DD HH:mm:ss"),
                    "index_set_name": index_set_name,
                    "index": ",".join(indexes),
                    "create_by": job.created_by,
                    "size": max(round((job.merged_bytes or 0) / (1024 * 1024), 2), 0.01),
                    "request_param": json.dumps(job.raw_params or job.search_params),
                    "search_url": context.get("search_url", ""),
                    "download_url": download_url,
                },
            )
            notify.send(
                receivers=receivers,
                title=title,
                content=content,
                is_external=job.is_external,
                bk_tenant_id=Space.get_tenant_id(space_uid=job.space_uid),
            )
        logger.info("[sharded_export_notification_sent] job_id=%s status=%s", job.pk, job.status)
    except Exception:  # pylint: disable=broad-except
        logger.exception("[sharded_export_notification_failure] job_id=%s status=%s", job.pk, job.status)
