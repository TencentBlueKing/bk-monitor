"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from copy import deepcopy
from typing import Any

from django.utils.functional import Promise
from django.utils.translation import gettext_lazy as _


Hover = dict[str, Any]
Text = str | Promise
Source = tuple[Text, str]

RESOURCE_TIMING_SOURCE: Source = (_("W3C · Resource Timing"), "https://www.w3.org/TR/resource-timing/")
SERVICE_WORKER_SOURCE: Source = (
    _("W3C · Service Worker respondWith"),
    "https://w3c.github.io/ServiceWorker/#fetch-event-respondwith",
)
NAVIGATION_TIMING_SOURCE: Source = (
    _("W3C · Navigation Timing Level 2"),
    "https://www.w3.org/TR/navigation-timing-2/",
)
LOADING_TIME_SOURCE: Source = (
    _("Datadog · Loading Time"),
    "https://docs.datadoghq.com/real_user_monitoring/browser/monitoring_page_performance/",
)
VITAL_SOURCES: dict[str, Source] = {
    "ttfb": (_("web.dev · Time to First Byte"), "https://web.dev/articles/ttfb"),
    "fcp": (_("web.dev · First Contentful Paint"), "https://web.dev/articles/fcp"),
    "lcp": (_("web.dev · Largest Contentful Paint"), "https://web.dev/articles/lcp"),
    "inp": (_("web.dev · Interaction to Next Paint"), "https://web.dev/articles/inp"),
    "cls": (_("web.dev · Cumulative Layout Shift"), "https://web.dev/articles/cls"),
}


def _hover(
    title: Text,
    description: Text,
    *,
    user_experience: Text | None = None,
    source: Source | None = None,
) -> Hover:
    result: Hover = {"title": title, "description": description}
    if user_experience is not None:
        result["user_experience"] = user_experience
    if source is not None:
        result["source"] = {"label": source[0], "url": source[1]}
    return result


RESOURCE_PHASE_HOVERS: dict[str, Hover] = {
    "total": _hover(
        _("总耗时"),
        _("从请求开始到收到响应最后一个字节的总时长。"),
        user_experience=_("从这次请求开始，到浏览器收完全部内容为止。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "redirect": _hover(
        _("重定向"),
        _("服务器返回 3xx 和新地址后，浏览器立即请求新地址，可能经过多次跳转，每次都多一次往返。"),
        user_experience=_("浏览器正在按服务器给出的新地址重新请求。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "prepare": _hover(
        _("发起前等待"),
        _("资源进入 DNS 查询前的准备阶段，可能包含 Service Worker、缓存或连接复用等浏览器处理。"),
        user_experience=_("浏览器正在确定资源来源和请求方式，尚未开始接收内容。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "queueing": _hover(
        _("[资源调度] 正在排队"),
        _("请求在连接开始前被排入队列，原因可能是有更高优先级的请求，或者同一来源的连接数已满。"),
        user_experience=_("浏览器正在排队，等待处理这次请求。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "sw_startup": _hover(
        _("[ServiceWorker] 启动"),
        _("浏览器启动 Service Worker，以便由它处理这次请求。"),
        user_experience=_("浏览器正在启动 Service Worker。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "sw_request": _hover(
        _("[ServiceWorker] 发送请求"),
        _("浏览器把请求发送给 Service Worker 处理。"),
        user_experience=_("浏览器正在把请求发送给 Service Worker。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "sw_respond_with": _hover(
        _("[ServiceWorker] respondWith"),
        _("Service Worker 拦截请求后自行提供响应，例如读缓存或访问网络。"),
        user_experience=_("Service Worker 正在处理请求，浏览器在等它交回响应。"),
        source=SERVICE_WORKER_SOURCE,
    ),
    "dns": _hover(
        _("DNS 查询"),
        _("浏览器把资源域名解析为服务器地址；命中本地缓存或复用连接时，该阶段可能为零。"),
        user_experience=_("浏览器正在查找资源所在的服务器。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "connect": _hover(
        _("连接建立"),
        _("浏览器与服务器建立网络连接；复用已有连接时，该阶段可能为零。"),
        user_experience=_("浏览器正在与资源服务器建立通信通道。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "tls": _hover(
        _("TLS 握手"),
        _("HTTPS 连接在传输内容前确认服务器身份并建立加密通道；非 HTTPS 或复用连接时可能没有该阶段。"),
        user_experience=_("浏览器正在确认连接安全并协商加密方式。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "first_byte": _hover(
        _("等待首字节"),
        _("浏览器发出请求后等待响应首字节，期间包含请求传输、服务端处理和网络往返。"),
        user_experience=_("请求已经发出，正在等待服务器开始返回内容。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
    "download": _hover(
        _("内容下载"),
        _("浏览器从收到响应首字节开始，持续接收资源内容，直到响应结束。"),
        user_experience=_("浏览器正在接收资源内容。"),
        source=RESOURCE_TIMING_SOURCE,
    ),
}

VIEW_PHASE_HOVERS: dict[str, Hover] = {
    "prepare": _hover(
        _("浏览器准备与重定向"),
        _("浏览器正式发出网络请求前的准备时间，包括地址重定向和 Service Worker 启动等工作。"),
        user_experience=_("浏览器正在确定最终地址和请求方式，尚未连接目标服务器。"),
        source=VITAL_SOURCES["ttfb"],
    ),
    "dns": _hover(
        _("DNS 查询"),
        _("浏览器把页面域名解析为服务器地址；命中本地缓存时，该阶段通常接近零。"),
        user_experience=_("浏览器正在查找网站服务器所在的位置。"),
        source=VITAL_SOURCES["ttfb"],
    ),
    "connect": _hover(
        _("连接与安全握手"),
        _("浏览器与服务器建立网络连接，HTTPS 页面还会确认身份并建立加密通道。"),
        user_experience=_("浏览器正在与服务器接通，并确认通信安全。"),
        source=VITAL_SOURCES["ttfb"],
    ),
    "first_byte": _hover(
        _("请求发送与首字节响应"),
        _("连接建立后，浏览器发送请求并等待服务器返回第一小段响应。"),
        user_experience=_("请求已经发出，正在等待服务器开始返回页面内容。"),
        source=VITAL_SOURCES["ttfb"],
    ),
    "dom_processing": _hover(
        _("内容传输与 DOM 处理"),
        _("浏览器接收 HTML 并构建页面结构，期间可能执行会暂停解析的同步脚本和初始化逻辑。"),
        user_experience=_("页面骨架正在形成，可能仍是白屏或只显示部分内容。"),
        source=NAVIGATION_TIMING_SOURCE,
    ),
    "resource_load": _hover(
        _("剩余资源加载"),
        _("页面结构准备后，浏览器继续等待图片、样式、字体和子页面等初始资源。"),
        user_experience=_("页面主体已经出现，最后一批视觉内容正在补齐。"),
        source=NAVIGATION_TIMING_SOURCE,
    ),
    "page_stable": _hover(
        _("页面稳定等待"),
        _("RUM 在 Load 事件后继续观察网络请求、资源加载和 DOM 变化，直到页面在一段时间内没有活动。"),
        user_experience=_("页面不再继续跳动、补充内容或频繁请求，用户感觉页面趋于稳定。"),
        source=LOADING_TIME_SOURCE,
    ),
}

MILESTONE_HOVERS: dict[str, Hover] = {
    "dom_complete": _hover(
        _("DOM Complete"),
        _("浏览器认为文档和初始子资源已经加载完成，之后仍可能出现异步请求或页面变化。"),
        user_experience=_("页面主体已经出现，最后一批图片、样式或嵌入内容完成补齐。"),
        source=NAVIGATION_TIMING_SOURCE,
    ),
    "load_event": _hover(
        _("Load Event"),
        _("浏览器发出初始页面加载完成通知，网站可能在此时继续执行埋点或组件初始化回调。"),
        user_experience=_("首屏通常已经完整显示；回调较重时，页面可能短暂卡顿。"),
        source=NAVIGATION_TIMING_SOURCE,
    ),
    "page_stable": _hover(
        _("页面稳定"),
        _("RUM 观察到页面在一段时间内没有新的网络请求、资源加载或 DOM 变化。"),
        user_experience=_("页面不再继续跳动或补充内容，用户感觉页面已经安定。"),
        source=LOADING_TIME_SOURCE,
    ),
}

VITAL_HOVERS: dict[str, Hover] = {
    "ttfb": _hover(
        _("TTFB（首字节响应）"),
        _("从用户开始打开页面，到浏览器收到服务器返回的第一小段数据。"),
        user_experience=_("页面多久开始得到服务器回应；过慢时会感觉页面一直没有反应。"),
        source=VITAL_SOURCES["ttfb"],
    ),
    "fcp": _hover(
        _("FCP（首次内容绘制）"),
        _("从打开页面到第一次显示文字、图片等内容的时间。"),
        user_experience=_("页面不再是纯白，用户第一次看到有意义的内容。"),
        source=VITAL_SOURCES["fcp"],
    ),
    "lcp": _hover(
        _("LCP（最大内容绘制）"),
        _("从打开页面到视窗内最大的图片、文本块或视频画面渲染完成的时间。"),
        user_experience=_("页面主要内容已经出现，用户能够判断页面内容。"),
        source=VITAL_SOURCES["lcp"],
    ),
    "inp": _hover(
        _("INP（交互到下一次绘制）"),
        _("记录用户点击、触摸或键盘操作后，到浏览器完成下一帧画面的整体延迟。"),
        user_experience=_("用户操作后，页面多久给出视觉反馈；数值越低，操作越跟手。"),
        source=VITAL_SOURCES["inp"],
    ),
    "cls": _hover(
        _("CLS（累积布局偏移）"),
        _("记录页面元素在没有用户操作时发生的意外位移；CLS 没有时间单位，数值越小越稳定。"),
        user_experience=_("文字、按钮和图片是否突然跳动；数值过高容易导致看错内容或点错按钮。"),
        source=VITAL_SOURCES["cls"],
    ),
}

RATING_HOVERS: dict[str, Hover] = {
    "good": _hover(_("良好"), _("指标处于推荐区间，通常代表用户体验良好。")),
    "needs_improvement": _hover(_("需改进"), _("指标处于中间区间，部分用户可能已经感受到性能问题。")),
    "poor": _hover(_("差"), _("指标超出推荐区间，用户较可能感受到明显的性能问题。")),
}


def clone_hover(hover: Hover | None) -> Hover | None:
    return deepcopy(hover) if hover is not None else None


def get_vital_hover(metric: str) -> Hover | None:
    return clone_hover(VITAL_HOVERS.get(metric.lower()))


def get_milestone_hover(milestone: str) -> Hover | None:
    return clone_hover(MILESTONE_HOVERS.get(milestone))


def get_rating_hover(rating: str) -> Hover | None:
    return clone_hover(RATING_HOVERS.get(rating))
