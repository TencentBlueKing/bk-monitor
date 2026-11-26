"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from django.utils.translation import gettext_lazy as _

from semconv.rum.field import HoverConfig


TTFB: HoverConfig = {
    "title": _("TTFB（首字节响应）"),
    "description": _("从用户开始打开页面，到浏览器收到服务器返回的第一小段数据。"),
    "user_experience": _("页面多久开始得到服务器回应；过慢时会感觉页面一直没有反应。"),
    "source": {"label": _("web.dev · Time to First Byte"), "url": "https://web.dev/articles/ttfb"},
}
FCP: HoverConfig = {
    "title": _("FCP（首次内容绘制）"),
    "description": _("从打开页面到第一次显示文字、图片等内容的时间。"),
    "user_experience": _("页面不再是纯白，用户第一次看到有意义的内容。"),
    "source": {"label": _("web.dev · First Contentful Paint"), "url": "https://web.dev/articles/fcp"},
}
LCP: HoverConfig = {
    "title": _("LCP（最大内容绘制）"),
    "description": _("从打开页面到视窗内最大的图片、文本块或视频画面渲染完成的时间。"),
    "user_experience": _("页面主要内容已经出现，用户能够判断页面内容。"),
    "source": {"label": _("web.dev · Largest Contentful Paint"), "url": "https://web.dev/articles/lcp"},
}
INP: HoverConfig = {
    "title": _("INP（交互到下一次绘制）"),
    "description": _("记录用户点击、触摸或键盘操作后，到浏览器完成下一帧画面的整体延迟。"),
    "user_experience": _("用户操作后，页面多久给出视觉反馈；数值越低，操作越跟手。"),
    "source": {"label": _("web.dev · Interaction to Next Paint"), "url": "https://web.dev/articles/inp"},
}
CLS: HoverConfig = {
    "title": _("CLS（累积布局偏移）"),
    "description": _("记录页面元素在没有用户操作时发生的意外位移；CLS 没有时间单位，数值越小越稳定。"),
    "user_experience": _("文字、按钮和图片是否突然跳动；数值过高容易导致看错内容或点错按钮。"),
    "source": {"label": _("web.dev · Cumulative Layout Shift"), "url": "https://web.dev/articles/cls"},
}
