# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""
import datetime

from django.conf import settings
from django.template import engines
from django.utils.translation import get_language

from core.drf_resource.base import Resource

django_engine = engines["django"]


FOOTER_TEMPLATE = """
<footer class="monitor-navigation-footer">
    <div class="footer-link">
        {% for link in links %}{% if not forloop.first %} | {% endif %}<a href="{{ link.link }}">{{ link.text }}</a>{% endfor %}
    </div>
    <div>{{ copyright }} V{{ saas_version }}({{ backend_version }})</div>
</footer>
"""  # noqa


class GetFooterResource(Resource):
    def perform_request(self, validated_request_data):
        template = django_engine.from_string(FOOTER_TEMPLATE.strip())

        if get_language() == "en":
            links = settings.HEADER_FOOTER_CONFIG["footer"][0]["en"]
        else:
            links = settings.HEADER_FOOTER_CONFIG["footer"][0]["zh-cn"]

        now = datetime.datetime.now()
        return template.render(
            {
                "links": links,
                "saas_version": settings.SAAS_VERSION,
                "backend_version": settings.BACKEND_VERSION,
                "copyright": settings.HEADER_FOOTER_CONFIG["copyright"].format(current_year=now.year),
            }
        )
