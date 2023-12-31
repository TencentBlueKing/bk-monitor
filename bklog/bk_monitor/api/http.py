# -*- coding: utf-8 -*-

import logging

import curlify
import requests
from bk_monitor.constants import ErrorEnum
from bk_monitor.exceptions import MonitorReportRequestException
from django.conf import settings

logger = logging.getLogger("bk_monitor")


# headers 添加
def _gen_header():
    headers = {
        "Content-Type": "application/json",
    }
    return headers


def get_desensitization_params(data: dict):
    """
    去除敏感参数
    """
    return {key: value for key, value in data.items() if key not in settings.SENSITIVE_PARAMS}


# 实际的请求访问
def _http_request(
    method,
    url,
    headers=None,
    data=None,
    verify=False,
    cert=None,
    timeout=None,
    cookies=None,
):
    resp = requests.Response()
    try:
        if method == "GET":
            resp = requests.get(
                url=url,
                headers=headers,
                params=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "HEAD":
            resp = requests.head(
                url=url,
                headers=headers,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "POST":
            resp = requests.post(
                url=url,
                headers=headers,
                json=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "DELETE":
            resp = requests.delete(
                url=url,
                headers=headers,
                json=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        elif method == "PUT":
            resp = requests.put(
                url=url,
                headers=headers,
                json=data,
                verify=verify,
                cert=cert,
                timeout=timeout,
                cookies=cookies,
            )
        else:
            raise MonitorReportRequestException(ErrorEnum.REQUEST_METHOD_NOT_ALLOWED, f"not allowed method => {method}")
    except requests.exceptions.RequestException as e:
        raise MonitorReportRequestException(
            ErrorEnum.REQUEST_ERROR,
            f"http error! request: [method='{method}',  url=`{url}`, e= '{e}']",
        )
    else:
        request_id = resp.headers.get("X-Request-Id")

        content = resp.content if resp.content else ""
        if not logger.isEnabledFor(logging.DEBUG) and len(content) > 200:
            content = content[:200] + b"......"

        exception_message_format = (
            "request: [method=`%s`, url=`%s`] response: [status_code=`%s`, request_id=`%s`, content=`%s`]"
        )
        log_message_format = (
            "request: [method=`%s`, url=`%s`, data=`%s`] response: [status_code=`%s`, request_id=`%s`, content=`%s`]"
        )
        desensitization_data = get_desensitization_params(data)
        if resp.status_code != 200:
            raise MonitorReportRequestException(
                ErrorEnum.REQUEST_STATUS_ERROR,
                exception_message_format % (method, url, resp.status_code, request_id, content),
            )
        logger.info(
            log_message_format % (method, url, str(desensitization_data), resp.status_code, request_id, content)
        )
        return resp.json()
    finally:
        if resp.request is None:
            resp.request = requests.Request(method, url, headers=headers, data=data, cookies=cookies).prepare()

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "the request_id: `%s`. curl: `%s`",
                resp.headers.get("X-Request-Id", ""),
                curlify.to_curl(resp.request, verify=False),
            )


def http_get(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="GET",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )


def http_post(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="POST",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )


def http_put(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="PUT",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )


def http_delete(url, data, headers=None, verify=False, cert=None, timeout=None, cookies=None):
    if not headers:
        headers = _gen_header()
    return _http_request(
        method="DELETE",
        url=url,
        headers=headers,
        data=data,
        verify=verify,
        cert=cert,
        timeout=timeout,
        cookies=cookies,
    )
