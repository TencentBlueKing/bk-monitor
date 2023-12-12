# -*- coding: utf-8 -*-
from rest_framework import status
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.response import Response
from rest_framework.viewsets import GenericViewSet

from bkm_search_module.constants import list_route, detail_route
from bkm_search_module.handlers.log_search_handler import SearchModuleHandler
from bkm_search_module.serializers import (
    IndexSetListSerializer,
    SearchConditionOptionsSerializer,
    SearchInspectSerializer,
    UserConfigSerializer,
    SearchAttrSerializer,
    SearchFieldsSerializer,
    CreateIndexSetFieldsConfigSerializer,
    UpdateIndexSetFieldsConfigSerializer,
    SearchUserIndexSetConfigSerializer,
    SearchContextSerializer,
    SearchTailFSerializer,
    DeleteIndexSetConfigSerializer,
    ExportSerializer,
    DownLoadUrlSeaializer
)


class CsrfExemptSessionAuthentication(SessionAuthentication):
    def enforce_csrf(self, request):
        # To not perform the csrf check previously happening
        return


class CommonViewSet(GenericViewSet):
    # TODO: 根据实际系统权限模型补充
    permission_classes = ()

    authentication_classes = (CsrfExemptSessionAuthentication, BasicAuthentication)

    def params_valid(self, serializer, params=None):
        """
        校验参数是否满足 serializer 规定的格式，支持传入serializer
        """
        # 校验request中的参数
        if not params:
            if self.request.method in ["GET"]:
                params = self.request.query_params
            else:
                params = self.request.data

        _serializer = serializer(data=params)
        _serializer.is_valid(raise_exception=True)
        return dict(_serializer.data)

    @property
    def validated_data(self):
        """
        校验的数据
        """
        if self.request.method == "GET":
            data = self.request.query_params
        else:
            data = self.request.data

        # 从 esb 获取参数
        bk_username = self.request.META.get("HTTP_BK_USERNAME")
        bk_app_code = self.request.META.get("HTTP_BK_APP_CODE")

        data = data.copy()
        data.setdefault("bk_username", bk_username)
        data.setdefault("bk_app_code", bk_app_code)

        serializer = self.serializer_class or self.get_serializer_class()
        return self.params_valid(serializer, data)

    def finalize_response(self, request, response, *args, **kwargs):
        # 目前仅对 Restful Response 进行处理
        if isinstance(response, Response):
            response.data = {"result": True, "data": response.data, "code": 0, "message": ""}
            response.status_code = status.HTTP_200_OK

        # 返回响应头禁用浏览器的类型猜测行为
        response.headers["x-content-type-options"] = ("X-Content-Type-Options", "nosniff")
        return super(CommonViewSet, self).finalize_response(request, response, *args, **kwargs)


class SearchModuleUserSettingsViewSet(CommonViewSet):
    pagination_class = None

    def get_serializer_class(self):
        action_serializer_map = {
            "create": UserConfigSerializer,
        }
        return action_serializer_map.get(self.action)

    def create(self, request, *args, **kwargs):
        """
        保存用户配置
        """
        return Response(SearchModuleHandler().update_or_create_config(
            username=request.user.username,
            config=self.validated_data["config"])
        )

    def list(self, request, *args, **kwargs):
        """
        获取用户配置
        """
        return Response(SearchModuleHandler().retrieve_user_config(username=request.user.username))


class SearchModuleIndexSetSettingsViewSet(CommonViewSet):
    lookup_field = "config_id"
    pagination_class = None

    def get_serializer_class(self):
        action_serializer_map = {
            "create": CreateIndexSetFieldsConfigSerializer,
            "save_user_config": SearchUserIndexSetConfigSerializer
        }
        return action_serializer_map.get(self.action)

    def create(self, request, index_set_id, *args, **kwargs):
        """
        创建索引集表格配置
        """
        return Response(SearchModuleHandler().create_fields_config(
            index_set_id=int(index_set_id),
            params=self.validated_data
        ))

    @list_route(methods=["PUT"], url_path="update", serializer_class=UpdateIndexSetFieldsConfigSerializer)
    def update_config(self, request, index_set_id, *args, **kwargs):
        """
        更新索引集表格配置
        """
        params = self.validated_data
        return Response(SearchModuleHandler().update_fields_config(
            index_set_id=int(index_set_id),
            params=params
        ))

    def list(self, request, index_set_id, *args, **kwargs):
        """
        获取索引集配置列表
        """
        return Response(SearchModuleHandler().list_fields_config(index_set_id=int(index_set_id)))

    @list_route(methods=["POST"], url_path="delete", serializer_class=DeleteIndexSetConfigSerializer)
    def delete_config(self, request, index_set_id, *args, **kwargs):
        """
        删除索引集配置列表
        """
        params = self.validated_data
        return Response(SearchModuleHandler().delete_fields_config(config_id=int(params["config_id"])))

    @list_route(methods=["PUT"], url_path="user")
    def save_user_config(self, request, index_set_id, *args, **kwargs):
        """
        保存用户索引集配置
        """
        return Response(SearchModuleHandler().save_user_config(
            index_set_id=int(index_set_id),
            config_id=self.validated_data["config_id"]
        ))


class SearchModuleIndexSetViewSet(CommonViewSet):
    lookup_field = "index_set_id"
    pagination_class = None

    @list_route(methods=["POST"], url_path="list", serializer_class=IndexSetListSerializer)
    def list_index_set(self, request, *args, **kwargs):
        """
        索引集列表
        """
        scope_list = self.validated_data["scopeList"]
        return Response(SearchModuleHandler().list_index_set(scope_list=scope_list))

    @detail_route(methods=["GET"], url_path="condition")
    def search_condition(self, request, index_set_id, *args, **kwargs):
        """
        获取查询条件
        """
        return Response(SearchModuleHandler().search_condition(index_set_id=int(index_set_id)))

    @detail_route(methods=["POST"], url_path="condition/options", serializer_class=SearchConditionOptionsSerializer)
    def search_condition_options(self, request, index_set_id, *args, **kwargs):
        """
        获取查询条件选项
        """
        return Response(SearchModuleHandler().search_condition_options(
            index_set_id=int(index_set_id),
            fields=self.validated_data["condition_id"])
        )

    @detail_route(methods=["GET"], url_path="history")
    def search_history(self, request, index_set_id, *args, **kwargs):
        """
        获取查询历史
        """
        return Response(SearchModuleHandler().search_history(index_set_id=int(index_set_id)))

    @list_route(methods=["POST"], url_path="inspect", serializer_class=SearchInspectSerializer)
    def search_inspect(self, request, *args, **kwargs):
        """
        检索语句语法检测
        """
        return Response(SearchModuleHandler().search_inspect(query_string=self.validated_data["query_string"]))

    @detail_route(methods=["POST"], url_path="search", serializer_class=SearchAttrSerializer)
    def search(self, request, index_set_id, *args, **kwargs):
        """
        日志检索
        """
        return Response(SearchModuleHandler().search(
            index_set_id=int(index_set_id),
            params=self.validated_data
        ))

    @detail_route(methods=["POST"], url_path="fields", serializer_class=SearchFieldsSerializer)
    def search_fields(self, request, index_set_id, *args, **kwargs):
        """
        字段配置
        """
        return Response(SearchModuleHandler().search_fields(
            index_set_id=int(index_set_id),
            params=self.validated_data
        ))

    @detail_route(methods=["POST"], url_path="context", serializer_class=SearchContextSerializer)
    def context(self, request, index_set_id, *args, **kwargs):
        """
        上下文
        """
        return Response(SearchModuleHandler().context(
            index_set_id=int(index_set_id),
            params=self.validated_data
        ))

    @detail_route(methods=["POST"], url_path="tail_f", serializer_class=SearchTailFSerializer)
    def tail_f(self, request, index_set_id, *args, **kwargs):
        """
        实时日志
        """
        return Response(SearchModuleHandler().tail_f(
            index_set_id=int(index_set_id),
            params=self.validated_data
        ))

    @detail_route(methods=["POST"], url_path="aggs/date_histogram", serializer_class=SearchAttrSerializer)
    def date_histogram(self, request, index_set_id, *args, **kwargs):
        """
        趋势柱状图
        """
        return Response(SearchModuleHandler().date_histogram(
            index_set_id=int(index_set_id),
            params=self.validated_data
        ))

    @detail_route(methods=["GET"], url_path="export")
    def export(self, request, index_set_id, *args, **kwargs):
        """
        日志下载
        """
        params = self.params_valid(ExportSerializer)
        return SearchModuleHandler().export(index_set_id=int(index_set_id), cache_key=params["cache_key"])

    @detail_route(methods=["POST"], url_path="download_url", serializer_class=DownLoadUrlSeaializer)
    def download_url(self, request, index_set_id, *args, **kwargs):
        """
        获取导出日志下载连接
        """
        return Response(SearchModuleHandler().download_url(
            index_set_id=int(index_set_id),
            params=self.validated_data
        ))
