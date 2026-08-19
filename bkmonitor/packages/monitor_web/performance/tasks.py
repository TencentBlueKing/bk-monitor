import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from celery import shared_task
from django.conf import settings

from bkmonitor.utils.tenant import set_local_tenant_id
from bkmonitor.utils.user import set_local_username
from monitor_web.constants import AGENT_STATUS
from monitor_web.performance.resources import SearchHostMetricResource, resolve_host_metric_snapshot_scope
from monitor_web.performance.snapshot import (
    SNAPSHOT_SECTIONS,
    HostMetricSnapshotStore,
    SnapshotState,
    SnapshotUnavailable,
    build_host_ids_hash,
)

logger = logging.getLogger(__name__)


def _build_snapshot_section(
    section,
    bk_biz_id,
    hosts,
    start_time,
    end_time,
    scope,
    bk_tenant_id=None,
    username=None,
):
    if bk_tenant_id is not None:
        set_local_tenant_id(bk_tenant_id)
    if username is not None:
        set_local_username(username)
    host_ids = {host.bk_host_id for host in hosts}
    is_partial = False

    def mark_partial():
        nonlocal is_partial
        is_partial = True

    target_filter = {} if scope["type"] == "business" else None
    if section == "agent_status":
        data = {host_id: {} for host_id in host_ids}
        SearchHostMetricResource.get_agent_status(
            bk_biz_id,
            hosts,
            data,
            start_time,
            end_time,
            fail_on_incomplete=False,
            target_filter=target_filter,
            incomplete_callback=mark_partial,
        )
    elif section == "performance_data":
        data = {host_id: {} for host_id in host_ids}
        SearchHostMetricResource.get_performance_data(
            bk_biz_id,
            hosts,
            data,
            start_time,
            end_time,
            fail_on_incomplete=False,
            target_filter=target_filter,
            incomplete_callback=mark_partial,
        )
    elif section == "process_status":
        data = {host_id: {} for host_id in host_ids}
        SearchHostMetricResource.get_process_status(
            bk_biz_id,
            hosts,
            data,
            start_time,
            end_time,
            fail_on_incomplete=False,
            target_filter=target_filter,
            incomplete_callback=mark_partial,
        )
    elif section == "alarm_count":
        data = {host_id: {"alarm_count": []} for host_id in host_ids}
        SearchHostMetricResource.get_alarm_count(
            bk_biz_id,
            hosts,
            data,
            start_time,
            end_time,
            filter_by_host_ip=scope["type"] != "business",
        )
    else:
        raise ValueError(f"unknown host metric snapshot section: {section}")
    if not is_partial:
        defaults = {
            "agent_status": {"status": AGENT_STATUS.UNKNOWN},
            "performance_data": {
                "cpu_load": None,
                "cpu_usage": None,
                "disk_in_use": None,
                "io_util": None,
                "mem_usage": None,
                "psc_mem_usage": None,
            },
            "process_status": {"component": []},
            "alarm_count": {"alarm_count": []},
        }[section]
        for host_data in data.values():
            for field, value in defaults.items():
                host_data.setdefault(field, value)
    return {"data": data, "state": SnapshotState.PARTIAL if is_partial else SnapshotState.READY}


@shared_task(ignore_result=True, queue="celery_resource", soft_time_limit=55, time_limit=60)
def build_host_metric_snapshot(snapshot_id: str):
    if not settings.ENABLE_HOST_METRIC_PROGRESSIVE:
        return
    try:
        store = HostMetricSnapshotStore()
        manifest = store.get_manifest(snapshot_id)
        if not manifest or manifest["state"] != SnapshotState.RUNNING:
            return
        current = store.get_current(manifest["fingerprint"])
        if not current or current["snapshot_id"] != snapshot_id:
            return
        if not store.renew_capacity(manifest):
            store.expire(snapshot_id)
            return
        if time.time() > manifest["deadline_at"]:
            store.mark_deadline(snapshot_id)
            return

        set_local_tenant_id(manifest["bk_tenant_id"])
        set_local_username(manifest["username"])
        scope, hosts = resolve_host_metric_snapshot_scope(
            {
                "bk_biz_id": manifest["bk_biz_id"],
                **{key: value for key, value in manifest["scope"].items() if key != "type"},
            }
        )
        host_ids_hash = build_host_ids_hash(host.bk_host_id for host in hosts)
        if scope != manifest["scope"] or (manifest.get("host_ids_hash") and host_ids_hash != manifest["host_ids_hash"]):
            store.expire(snapshot_id)
            return
        current = store.get_current(manifest["fingerprint"])
        if not current or current["snapshot_id"] != snapshot_id:
            return
        if not store.owns_capacity(manifest):
            store.expire(snapshot_id)
            return
        store.update_manifest(
            snapshot_id, host_count=len({host.bk_host_id for host in hosts}), host_ids_hash=host_ids_hash
        )

        failed_sections = []
        partial_sections = []
        with ThreadPoolExecutor(max_workers=len(SNAPSHOT_SECTIONS)) as executor:
            futures = {
                executor.submit(
                    _build_snapshot_section,
                    section,
                    manifest["bk_biz_id"],
                    hosts,
                    manifest["canonical_start_time"],
                    manifest["canonical_end_time"],
                    scope,
                    manifest["bk_tenant_id"],
                    manifest["username"],
                ): section
                for section in SNAPSHOT_SECTIONS
            }
            for future in as_completed(futures):
                section = futures.pop(future)
                try:
                    section_result = future.result()
                except Exception:
                    logger.exception(
                        "build host metric snapshot section failed, bk_biz_id=%s, section=%s",
                        manifest["bk_biz_id"],
                        section,
                    )
                    failed_sections.append(section)
                    continue
                if isinstance(section_result, dict) and "data" in section_result and "state" in section_result:
                    data = section_result["data"]
                    section_state = section_result["state"]
                else:
                    data = section_result
                    section_state = SnapshotState.READY
                if section_state == SnapshotState.PARTIAL:
                    partial_sections.append(section)
                current = store.get_current(manifest["fingerprint"])
                if not current or current["snapshot_id"] != snapshot_id:
                    return
                if not store.owns_capacity(manifest):
                    store.expire(snapshot_id)
                    return
                if time.time() > manifest["deadline_at"]:
                    store.mark_deadline(snapshot_id)
                    return
                store.write_section(snapshot_id, section, data)
                store.mark_section_ready(snapshot_id, section, state=section_state)

        if failed_sections or partial_sections:
            store.mark_degraded(
                snapshot_id,
                failed_sections=sorted(failed_sections),
                partial_sections=sorted(partial_sections),
            )
            return
        store.mark_ready(snapshot_id, expected_sections=set(SNAPSHOT_SECTIONS))
    except SnapshotUnavailable:
        logger.warning("host metric snapshot Redis unavailable, snapshot_id=%s", snapshot_id)
    except Exception:
        logger.exception("build host metric snapshot failed, snapshot_id=%s", snapshot_id)
        try:
            HostMetricSnapshotStore().fail(snapshot_id, "task_failed")
        except SnapshotUnavailable:
            pass
