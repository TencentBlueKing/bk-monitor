"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

from core.drf_resource import Resource
from core.drf_resource.exceptions import CustomException
from core.drf_resource.tools import get_serializer_fields, render_schema


@dataclass
class KernelRPCFunction:
    func_name: str
    summary: str
    description: str
    handler: Callable[[dict[str, Any]], Any]
    params_schema: dict[str, Any] | None = None
    example_params: dict[str, Any] | None = None

    def to_summary(self) -> dict[str, Any]:
        return {"func_name": self.func_name, "summary": self.summary}

    def to_detail(self) -> dict[str, Any]:
        detail = {
            "func_name": self.func_name,
            "summary": self.summary,
            "description": self.description,
        }
        if self.params_schema is not None:
            detail["params_schema"] = self.params_schema
        if self.example_params is not None:
            detail["example_params"] = self.example_params
        return detail


class KernelRPCRegistry:
    META_PROTOCOL_FUNC_NAME = "__meta__"
    META_ACTION_LIST = "list"
    META_ACTION_DETAIL = "detail"

    _functions: dict[str, KernelRPCFunction] = {}
    _loaded = False

    @classmethod
    def ensure_loaded(cls) -> None:
        if cls._loaded:
            return

        from kernel_api.rpc.functions import load_builtin_functions

        load_builtin_functions()
        cls._loaded = True

    @classmethod
    def register(
        cls,
        func_name: str,
        *,
        summary: str,
        description: str,
        params_schema: dict[str, Any] | None = None,
        example_params: dict[str, Any] | None = None,
    ):
        def decorator(handler: Callable[[dict[str, Any]], Any]):
            cls.register_function(
                func_name=func_name,
                handler=handler,
                summary=summary,
                description=description,
                params_schema=params_schema,
                example_params=example_params,
            )
            return handler

        return decorator

    @classmethod
    def register_function(
        cls,
        *,
        func_name: str,
        handler: Callable[[dict[str, Any]], Any],
        summary: str,
        description: str,
        params_schema: dict[str, Any] | None = None,
        example_params: dict[str, Any] | None = None,
    ) -> None:
        func_name = (func_name or "").strip()
        if not func_name:
            raise ValueError("func_name cannot be empty")
        if func_name == cls.META_PROTOCOL_FUNC_NAME:
            raise ValueError(f"{cls.META_PROTOCOL_FUNC_NAME} is reserved for meta protocol")

        cls._functions[func_name] = KernelRPCFunction(
            func_name=func_name,
            summary=summary,
            description=description,
            handler=handler,
            params_schema=params_schema,
            example_params=example_params,
        )

    @classmethod
    def build_resource_params_schema(cls, resource_cls: type[Resource]) -> dict[str, Any] | None:
        request_serializer_class, _ = resource_cls._search_serializer_class()
        if not request_serializer_class:
            return None

        return {
            "resource": resource_cls.get_resource_name(),
            "request_serializer": (f"{request_serializer_class.__module__}.{request_serializer_class.__name__}"),
            "request_params": render_schema(get_serializer_fields(request_serializer_class)),
        }

    @classmethod
    def register_resource(
        cls,
        *,
        func_name: str,
        resource_cls: type[Resource],
        summary: str,
        description: str | None = None,
        params_schema: dict[str, Any] | None = None,
        example_params: dict[str, Any] | None = None,
    ) -> None:
        cls.register_function(
            func_name=func_name,
            handler=lambda params: resource_cls().request(params),
            summary=summary,
            description=description or (resource_cls.__doc__ or "").strip() or f"直接复用 {resource_cls.__name__}",
            params_schema=params_schema or cls.build_resource_params_schema(resource_cls),
            example_params=example_params,
        )

    @classmethod
    def register_resource_list(cls, resource_rpcs: list[dict[str, Any]]) -> None:
        for resource_rpc in resource_rpcs:
            cls.register_resource(**resource_rpc)

    @classmethod
    def list_functions(cls) -> list[dict[str, Any]]:
        cls.ensure_loaded()
        return [function.to_summary() for function in cls._functions.values()]

    @classmethod
    def get_function_detail(cls, func_name: str) -> dict[str, Any] | None:
        cls.ensure_loaded()
        if func_name == cls.META_PROTOCOL_FUNC_NAME:
            return {
                "func_name": cls.META_PROTOCOL_FUNC_NAME,
                "summary": "查询可调用函数列表及函数详细说明",
                "description": "通过 params.action 执行元信息查询，支持 list 和 detail 两种模式，用于渐进式披露。",
                "params_schema": {
                    "action": "list | detail",
                    "target_func_name": "当 action=detail 时必填，表示要查询的函数名",
                },
                "example_params": {
                    "action": "detail",
                    "target_func_name": "info",
                },
            }

        function = cls._functions.get(func_name)
        return function.to_detail() if function else None

    @classmethod
    def execute(cls, func_name: str, params: dict[str, Any]) -> Any:
        cls.ensure_loaded()
        function = cls._functions.get(func_name)
        if function is None:
            raise CustomException(
                message=(
                    f"未找到可调用函数: {func_name}。请先通过 {cls.META_PROTOCOL_FUNC_NAME} 协议查询可调用函数列表。"
                )
            )
        return function.handler(params)
