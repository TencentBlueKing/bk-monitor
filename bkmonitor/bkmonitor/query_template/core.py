"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

import abc
import copy
import json
from typing import Any

from bkmonitor.models import query_template as models

from . import constants, serializers


class BaseQuery:
    def __init__(
        self,
        name: str,
        bk_biz_id: int,
        query_configs: list[dict[str, Any]],
        alias: str | None = None,
        namespace: str | None = None,
        description: str | None = None,
        expression: str | None = None,
        space_scope: list[str] | None = None,
        functions: list[dict[str, Any] | str] | None = None,
        **kwargs,
    ):
        self.name: str = name
        self.bk_biz_id: int = bk_biz_id
        self.alias: str = alias or ""
        self.namespace: str = namespace or constants.Namespace.DEFAULT.value
        self.description: str = description or ""
        self.query_configs: list[dict[str, Any]] = query_configs
        self.expression: str = expression or ""
        self.space_scope: list[str] = space_scope or []
        self.functions: list[dict[str, Any] | str] = functions or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "bk_biz_id": self.bk_biz_id,
            "name": self.name,
            "alias": self.alias,
            "namespace": self.namespace,
            "description": self.description,
            "query_configs": self.query_configs,
            "expression": self.expression,
            "space_scope": self.space_scope,
            "functions": self.functions,
        }


class QueryInstance(BaseQuery):
    pass


class BaseVariableRender(abc.ABC):
    TYPE: str = None

    def __init__(self, variables: list[dict[str, Any]], query_instance: QueryInstance):
        self._variables = [variable for variable in variables if variable["type"] == self.TYPE]
        self._query_instance = query_instance

    @classmethod
    def to_template(cls, name: str) -> str:
        return "${" + name + "}"

    @classmethod
    def get_value(cls, context: dict[str, Any], variable: dict[str, Any]) -> Any:
        value: Any = context.get(variable["name"])
        if value is not None:
            return value

        return variable["config"].get("default")

    @abc.abstractmethod
    def render(self, context: dict[str, Any] = None) -> QueryInstance:
        raise NotImplementedError


class ConstantVariableRender(BaseVariableRender):
    TYPE: str = constants.VariableType.CONSTANTS.value

    def render(self, context: dict[str, Any] = None) -> QueryInstance:
        tmpl: str = json.dumps(
            {
                "functions": self._query_instance.functions,
                "expression": self._query_instance.expression,
                "query_configs": self._query_instance.query_configs,
            }
        )
        for variable in self._variables:
            # TODO type check
            value: str | int | None = self.get_value(context, variable)
            if value is None:
                continue

            tmpl = tmpl.replace(self.to_template(variable["name"]), str(value))

        rendered = json.loads(tmpl)
        self._query_instance.functions = rendered["functions"]
        self._query_instance.expression = rendered["expression"]
        self._query_instance.query_configs = rendered["query_configs"]
        return self._query_instance


class GroupByVariableRender(BaseVariableRender):
    TYPE = constants.VariableType.GROUP_BY.value

    def render(self, context: dict[str, Any] = None) -> QueryInstance:
        for variable in self._variables:
            value: list[str] | None = self.get_value(context, variable)
            if value is None:
                continue

            val_tmpl: str = self.to_template(variable["name"])
            for query_config in self._query_instance.query_configs:
                group_by: list[str] = query_config.get("group_by") or []
                if val_tmpl not in group_by:
                    continue

                # 移除变量并填充变量值。
                query_config["group_by"] = list(set(group_by + value) - {val_tmpl})

        return self._query_instance


class TagValuesVariableRender(BaseVariableRender):
    TYPE = constants.VariableType.TAG_VALUES.value

    def render(self, context: dict[str, Any] = None) -> QueryInstance:
        for variable in self._variables:
            value: list[str] | None = self.get_value(context, variable)
            if value is None:
                continue

            val_tmpl: str = self.to_template(variable["name"])
            for query_config in self._query_instance.query_configs:
                where: list[dict[str, Any] | str] = query_config.get("where") or []
                for cond in where:
                    if not isinstance(cond, dict):
                        continue

                    cond_value: str | list[str] | None = cond.get("value")
                    if cond_value == val_tmpl:
                        # 场景-1：[{"key": "rpc_system", "method": "eq", "value": "${TAG_VALUES}"}]
                        # 直接从 context 深拷贝一份，避免重复引用。
                        cond["value"] = copy.deepcopy(value)
                    elif isinstance(cond_value, list) and val_tmpl in cond["value"]:
                        # 场景-2：[{"key": "rpc_system", "method": "in", "value": ["${TAG_VALUES}"]}]
                        cond["value"] = list(set(cond_value + value) - {val_tmpl})

        return self._query_instance


class ConditionsVariableRender(BaseVariableRender):
    _VARIABLE_FIELD: str = "where"
    TYPE = constants.VariableType.CONDITIONS.value

    def render(self, context: dict[str, Any] = None) -> QueryInstance:
        for variable in self._variables:
            value: list[dict[str, Any]] | None = self.get_value(context, variable)
            if value is None:
                continue

            val_tmpl: str = self.to_template(variable["name"])
            for query_config in self._query_instance.query_configs:
                where: list[dict[str, Any] | str] = query_config.get(self._VARIABLE_FIELD) or []
                if val_tmpl not in where:
                    continue

                query_config[self._VARIABLE_FIELD] = []
                for cond in where:
                    if cond == val_tmpl:
                        query_config[self._VARIABLE_FIELD].extend(value)
                        continue
                    query_config[self._VARIABLE_FIELD].append(cond)

        return self._query_instance


class FunctionsVariableRender(ConditionsVariableRender):
    _VARIABLE_FIELD: str = "functions"
    TYPE = constants.VariableType.FUNCTIONS.value


class MethodVariableRender(BaseVariableRender):
    TYPE = constants.VariableType.METHOD.value

    def render(self, context: dict[str, Any] = None) -> QueryInstance:
        for variable in self._variables:
            value: str | None = self.get_value(context, variable)
            if value is None:
                continue

            val_tmpl: str = self.to_template(variable["name"])
            for query_config in self._query_instance.query_configs:
                metrics: list[dict[str, Any]] = query_config.get("metrics") or []
                if not metrics:
                    continue

                for metric in metrics:
                    if val_tmpl != metric.get("method"):
                        continue
                    metric["method"] = value

        return self._query_instance


class ExpressionFunctionsVariableRender(BaseVariableRender):
    TYPE = constants.VariableType.EXPRESSION_FUNCTIONS.value

    def render(self, context: dict[str, Any] = None) -> QueryInstance:
        for variable in self._variables:
            value: list[dict[str, Any]] | None = self.get_value(context, variable)
            if value is None:
                continue

            result_functions: list[dict[str, Any]] = []
            val_tmpl: str = self.to_template(variable["name"])
            for function in self._query_instance.functions:
                if function == val_tmpl:
                    result_functions.extend(value)
                else:
                    result_functions.append(function)
            self._query_instance.functions = result_functions

        return self._query_instance


VARIABLE_HANDLERS: dict[str, type[BaseVariableRender]] = {
    constants.VariableType.CONSTANTS.value: ConstantVariableRender,
    constants.VariableType.GROUP_BY.value: GroupByVariableRender,
    constants.VariableType.TAG_VALUES.value: TagValuesVariableRender,
    constants.VariableType.CONDITIONS.value: ConditionsVariableRender,
    constants.VariableType.FUNCTIONS.value: FunctionsVariableRender,
    constants.VariableType.METHOD.value: MethodVariableRender,
    constants.VariableType.EXPRESSION_FUNCTIONS.value: ExpressionFunctionsVariableRender,
}


class QueryTemplateWrapper(BaseQuery):
    def __init__(
        self,
        name: str,
        bk_biz_id: int,
        query_configs: list[dict[str, Any]],
        alias: str | None = None,
        namespace: str | None = None,
        description: str | None = None,
        expression: str | None = None,
        space_scope: list[str] | None = None,
        functions: list[dict[str, Any] | str] | None = None,
        variables: list[dict[str, Any]] | None = None,
        **kwargs,
    ):
        self.variables: list[dict[str, Any]] = variables or []
        self._type_to_variables: dict[str, list[dict[str, Any]]] = {}
        for variable in self.variables:
            self._type_to_variables.setdefault(variable["type"], []).append(variable)

        super().__init__(
            name=name,
            bk_biz_id=bk_biz_id,
            query_configs=query_configs,
            alias=alias,
            namespace=namespace,
            description=description,
            expression=expression,
            space_scope=space_scope,
            functions=functions,
            **kwargs,
        )

    def render(self, context: dict[str, Any] = None) -> dict[str, Any]:
        context = context or {}
        query_instance: QueryInstance = QueryInstance(**copy.deepcopy(self.to_dict()))
        for var_type, variables in self._type_to_variables.items():
            if var_type not in VARIABLE_HANDLERS:
                continue

            query_instance = VARIABLE_HANDLERS[var_type](variables, query_instance).render(context)

        return query_instance.to_dict()

    def to_dict(self) -> dict[str, Any]:
        data = super().to_dict()
        data["variables"] = self.variables
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QueryTemplateWrapper":
        serializer = serializers.QueryTemplateSerializer(data=data)
        serializer.is_valid(raise_exception=True)
        return QueryTemplateWrapper(**serializer.validated_data)

    @classmethod
    def from_obj(cls, obj: models.QueryTemplate) -> "QueryTemplateWrapper":
        # 序列化器承担版本兼容转换的职责，故模型对象统一走 from_dict，以确保数据格式正确。
        return cls.from_dict(
            {
                "bk_biz_id": obj.bk_biz_id,
                "name": obj.name,
                "alias": obj.alias,
                "namespace": obj.namespace,
                "description": obj.description,
                "query_configs": obj.query_configs,
                "expression": obj.expression,
                "space_scope": obj.space_scope,
                "functions": obj.functions,
                "variables": obj.variables,
            }
        )
