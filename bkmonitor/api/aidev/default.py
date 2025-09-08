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
import json
from json import JSONDecodeError

from django.conf import settings
from django.http import StreamingHttpResponse
from rest_framework import serializers

from core.drf_resource import APIResource


class AidevAPIGWResource(APIResource):
    base_url = settings.AIDEV_API_BASE_URL
    # 模块名
    module_name = "aidev"

    def get_headers(self):
        headers = super().get_headers()
        authorization = json.loads(headers["x-bkapi-authorization"])

        authorization.update(
            {
                "bk_app_code": settings.BK_PLUGIN_APP_INFO.get("bk_app_code", settings.APP_CODE),
                "bk_app_secret": settings.BK_PLUGIN_APP_INFO.get("bk_app_secret", settings.SECRET_KEY),
            }
        )
        headers["x-bkapi-authorization"] = json.dumps(authorization)

        return headers


class OnlyKnowledgebaseQueryResource(AidevAPIGWResource):
    """
    仅知识库检索
    """

    class RequestSerializer(serializers.Serializer):
        query = serializers.CharField(required=True, allow_blank=False)
        type = serializers.ChoiceField(required=True, allow_blank=False, choices=["nature", "index_specific"])
        polish = serializers.BooleanField(required=False, default=False)
        stream = serializers.BooleanField(required=False, default=False)
        topk = serializers.IntegerField(required=False, default=20)
        index_query_kwargs = serializers.ListField(required=False, child=serializers.DictField(), allow_empty=True)

    action = "/aidev/resource/knowledgebase/query/"
    method = "POST"


class CreateKnowledgebaseQueryResource(OnlyKnowledgebaseQueryResource):
    """
    创建知识库查询，检索并回答
    """

    class RequestSerializer(serializers.Serializer):
        query = serializers.CharField(required=True, allow_blank=False)
        type = serializers.ChoiceField(required=True, allow_blank=False, choices=["nature", "index_specific"])
        knowledge_base_id = serializers.ListField(required=True, child=serializers.IntegerField())
        polish = serializers.BooleanField(required=False, default=True)
        stream = serializers.BooleanField(required=False, default=True)
        topk = serializers.IntegerField(required=False, default=20)
        index_query_kwargs = serializers.ListField(required=False, child=serializers.DictField(), allow_empty=True)

    action = "/aidev/resource/knowledgebase/query/"
    method = "POST"
    IS_STREAM = True

    @classmethod
    def _get_wx_link(cls):
        for item in settings.BK_DATA_ROBOT_LINK_LIST:
            if item["icon_name"] == "icon-kefu":
                return item["link"]

    def handle_stream_response(self, response):
        # 处理流式响应
        def event_stream():
            reject = False
            for line in response.iter_lines():
                if not line:
                    continue
                result = line.decode('utf-8') + '\n\n'
                try:
                    res_data = json.loads(result.split("data: ", 1)[-1])
                    if res_data.get("reject"):
                        reject = True
                    if res_data.get("event") == "reference_doc":
                        doc_link_html = parse_doc_link(res_data)
                        yield doc_link_html
                        continue
                    if res_data.get("event") == "done" and reject:
                        # done 的时候， 同时reject了，需要补一个引导尾巴
                        yield add_guide(res_data)
                except JSONDecodeError:
                    # 非json格式原样返回
                    # data: [DONE]
                    pass
                yield result

        def add_guide(res_data):
            link_tmp = """<a href="{doc_link}" target="_blank">【BK助手】</a>"""
            res_data["content"] = "\n如果以上回答不能解决您的问题，您可以尝试换个问法或点击立即联系" + link_tmp.format(doc_link=self._get_wx_link())
            res_data["event"] = "text"
            return "data: " + json.dumps(res_data) + "\n\n"

        def parse_doc_link(res_data):
            section_tmp = """<section class="knowledge-tips">
          <i class="ai-blueking-icon ai-blueking-angle-up"></i>
          <span class="knowledge-summary">
            <i class="ai-blueking-icon ai-blueking-help-document"></i>
            引用 {doc_count} 篇资料作为参考
          </span>
          {doc_link_html}
        </section>"""
            link_tmp = """<a href="{doc_link}" target="_blank" class="knowledge-link">
            {doc_name}
            <i class="ai-blueking-icon ai-blueking-cc-jump-link"></i>
          </a>"""
            # 最多5个文档引用
            docs = res_data.pop("documents", [])
            link_map = {}
            for doc in docs:
                doc_name = doc["metadata"]["file_path"].rsplit("/")[-1]
                doc_link = doc["metadata"]["path"]
                if doc_link not in link_map:
                    link_map[doc_link] = doc_name
                    if len(link_map) >= 5:
                        break

            doc_link_html = "\n".join(
                [link_tmp.format(doc_name=file_name, doc_link=link) for link, file_name in link_map.items()]
            )
            section_html = section_tmp.format(doc_count=len(link_map), doc_link_html=doc_link_html)
            data = {"event": "text", "content": ""}
            data["content"] += section_html if len(link_map) else ""
            return "data: " + json.dumps(data) + "\n\n"

        # 返回 StreamingHttpResponse
        sr = StreamingHttpResponse(event_stream(), content_type="text/event-stream; charset=utf-8")
        sr.headers["Cache-Control"] = "no-cache"
        sr.headers["X-Accel-Buffering"] = "no"
        return sr
