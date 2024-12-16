# -*- coding: utf-8 -*-

import re
from copy import deepcopy

import ujson as json
from django.utils.translation import gettext as _

from core.drf_resource import api
from fta_web.fta_migrate.constants import (
    FTA_COMPONENTS_DICT,
    FTA_SOPS_MAPPING,
    FTA_SOPS_QUICK_ACTION_MAPPING,
)
from fta_web.fta_migrate.pipeline.flow import (
    EmptyEndEvent,
    ExclusiveGateway,
    ServiceActivity,
    SubProcess,
)
from fta_web.fta_migrate.pipeline.tree_components import (
    activity_result_constant,
    fta_bak_ip_constants,
    node_uniqid,
    sops_constant_skeleton,
)

VAR_STR_MATCH = re.compile(r"\$\{\s*[\w\|]+\s*\}")
VAR_NAME_MATCH = re.compile(r"\$\{\s*([\w\|]+)\s*\}")


# #————————————————————————————以下部分是解析fta tree—————————————————————————————————#
class FtaTreeDecode:
    def __init__(self, fta_flow, start_node, end_node, tree_constants, component_data, bk_biz_id, builtin_templates):
        self.bk_biz_id = bk_biz_id
        self.fta_flow = fta_flow
        self.all_nodes = sorted(self.fta_flow.keys())
        self.acts = {}
        self.tree = start_node
        self.end_node = end_node
        self.tree_constants = tree_constants
        self.component_data = component_data
        self.component_version = {}
        self.replace_ip = False
        self.builtin_templates = builtin_templates

    def connect_activity(self, activity, next_event=None):
        if next_event is None:
            next_event = self.end_node

        if not activity.outgoing:
            # 父节点没有任何输出，直接拼接当前节点即可
            activity.extend(next_event)
            return

        for act in activity.outgoing:
            if next_event in act.outgoing:
                # 下一个节点已经存在输出中，直接返回
                continue

            if act.outgoing:
                # 当前节点还有其他输出
                self.connect_activity(act, next_event)
                continue

            if isinstance(act, EmptyEndEvent) and isinstance(next_event, EmptyEndEvent):
                # 当前输出节点和下一个连接节点都是结束节点时直接返回
                continue

            act.extend(next_event)

    def compile_tree(self, real_solutions):
        # 计算出二叉树的高度
        height = self.compute_flow_height()
        acts = {node_id: self.compile_service_activity(real_solutions, node_id) for node_id in self.all_nodes}

        # 构造出第一个第一个
        self.tree.extend(acts[1])
        if height == 1:
            self.connect_activity(acts[1])
            return
        for level in range(0, height):
            current_level = height - level
            current_level_nodes = self.find_current_nodes(current_level)
            current_level_nodes.sort()
            skipped_nodes = []
            for node_id in current_level_nodes:
                if self.is_leaf_node(node_id):
                    self.connect_activity(acts[node_id])
                if node_id in skipped_nodes:
                    continue
                parent_node_id = self.find_parent_node(node_id)
                parent_node = acts[parent_node_id]
                parent_node = parent_node.outgoing[-1] if parent_node.outgoing else parent_node
                connect_act = acts[node_id]
                if self.is_left_node(node_id):
                    # 如果是左值，查找是否有右值，如果有，需要创建网关作为链接
                    right_node_id = self.find_right_node(node_id)
                    if right_node_id:
                        # 如果有右节点， 创建一个网关，并且将当前网关加入到忽略的节点中
                        skipped_nodes.append(right_node_id)

                        connect_act, result_var = self.compile_gateway(
                            parent_node_id, parent_node, acts[node_id], acts[right_node_id]
                        )
                        self.tree_constants.update(result_var)
                else:
                    connect_act, result_var = self.compile_gateway(parent_node_id, parent_node, None, acts[node_id])
                    self.tree_constants.update(result_var)

                self.connect_activity(parent_node, connect_act)

    def compile_service_activity(self, real_solutions, current_node_id):
        """
        组装标准运维插件
        """
        relate_solution = real_solutions[self.fta_flow[current_node_id]]
        fta_id_code = "id|%s" % relate_solution.id
        fta_type_code = "solution_type|%s" % relate_solution.solution_type

        if fta_id_code in FTA_COMPONENTS_DICT:
            # 先按照id来获取
            fta_component = FTA_COMPONENTS_DICT[fta_id_code]
        elif fta_type_code in FTA_COMPONENTS_DICT:
            # 先按照快捷类型来获取

            if fta_type_code == "solution_type|notice" and "_approve" in relate_solution.config:
                fta_type_code = "solution_type|notice|approve"
            fta_component = FTA_COMPONENTS_DICT[fta_type_code]
            if fta_type_code == "solution_type|get_bak_ip":
                self.tree_constants.update(fta_bak_ip_constants(relate_solution))
        else:
            # 其他的非快捷类型的，按照config配置参数来获取
            fta_config_code = "config|%s" % self.config_decode(relate_solution.config)
            fta_component = FTA_COMPONENTS_DICT.get(fta_config_code)
        if not fta_component:
            raise Exception(_("错误，不存在的组件！！{} {}").format(relate_solution.id, relate_solution.title))

        if fta_type_code == "solution_type|switch_ip":
            self.replace_ip = True
        if not isinstance(fta_component, list):
            fta_component = [fta_component]

        act = None
        for one_component in fta_component:
            new_act = self.create_service_activity(one_component, relate_solution, current_node_id)
            if act is None:
                act = new_act
                continue
            self.connect_activity(act, new_act)

        self.acts[current_node_id] = act
        return act

    def create_service_activity(self, fta_component, relate_solution, current_node_id):
        if fta_component["code"] == "subprocess":
            template_info = self.get_sops_template_info(fta_component, relate_solution)
            act = SubProcess(
                id=node_uniqid(),
                template_id=template_info.get("id"),
                name=fta_component.get("name", relate_solution.title),
            )
            self.component_version[act.id] = ""
            self.component_data[act.id] = template_info.get("pipeline_tree", {}).get("constants", {})
        else:
            act = ServiceActivity(
                id=node_uniqid(),
                component_code=fta_component["code"],
                name=relate_solution.title or fta_component.get("name", "--"),
            )
            self.component_data[act.id] = deepcopy(fta_component["data"])
            self.component_version[act.id] = fta_component.get("version", "legacy")
            for constant_data in self.component_data[act.id].values():
                constant_value = constant_data.get("value")
                if self.replace_ip:
                    # 如果存在替换ip处理的内容，需要进行ip的替换
                    str_constant_value = json.dumps(constant_value)
                    var_keys = VAR_STR_MATCH.findall(str_constant_value)
                    if "${fault_ip}" in var_keys:
                        constant_data["value"] = json.loads(str_constant_value.replace("${fault_ip}", "${bak_ip}"))

                if hasattr(FtaSolutionConfigConvert, str(constant_value)) is False:
                    continue
                convert_function = getattr(FtaSolutionConfigConvert, str(constant_value))
                constant_data["value"] = convert_function(
                    relate_solution,
                    self.tree_constants,
                    bk_biz_id=self.bk_biz_id,
                    parent_node_id=self.find_parent_node(current_node_id),
                    acts=self.acts,
                )

        FtaSolutionConfigConvert.convert_config(json.dumps(self.component_data), self.tree_constants)
        return act

    def get_sops_template_info(self, fta_component, solution):
        """
        获取标准运维的信息
        :param fta_component:
        :param solution:
        :return:
        """
        if solution.solution_type == "gcloud":
            config = json.loads(solution.config)
            template_id = config.get("template")
            return api.sops.get_template_info(bk_biz_id=self.bk_biz_id, template_id=template_id)

        return self.builtin_templates.get(
            FTA_SOPS_QUICK_ACTION_MAPPING.get(fta_component["fta_code"], fta_component["fta_code"])
        )

    def compile_gateway(self, parent_node_id, parent_node, left_node, right_node):
        """
        组装一个分支网关
        """
        if left_node is None:
            # 没有成功的时候，成功直接表示结束
            left_node = self.end_node
        result_key = "${_result_%s}" % parent_node_id
        conditions = {0: "%s == True" % result_key, 1: "%s == False" % result_key}
        result_var = {result_key: activity_result_constant(parent_node.id, result_key)}
        gateway = ExclusiveGateway(conditions=conditions, name="")
        parent_node.error_ignorable = True
        if self.fta_flow[parent_node_id] == 155:
            # ping不通为失败的情况，需要设置为反的
            gateway.connect(right_node, left_node)
        else:
            gateway.connect(left_node, right_node)
        return gateway, result_var

    @staticmethod
    def config_decode(config):
        task_kwargs = json.loads(config) if isinstance(config, str) else config
        if task_kwargs:
            return "{module_name}.{task_name}".format(
                module_name=task_kwargs.get("module_name", ""), task_name=task_kwargs.get("task_name", "")
            )
        return "other"

    def compute_flow_height(self):
        # 计算出组合套餐的最大高度
        max_node_id = max(self.all_nodes)
        height = 0
        while max_node_id:
            max_node_id = max_node_id // 2
            if max_node_id >= 0:
                height += 1
        return height

    def is_left_node(self, node_id):
        return node_id % 2 == 0

    def find_parent_node(self, node_id):
        return node_id // 2

    def find_right_node(self, node_id):
        right_node = node_id + 1
        if right_node in self.all_nodes:
            return right_node

    def find_current_nodes(self, level):
        return [node_id for node_id in self.all_nodes if pow(2, level) <= node_id < pow(2, level + 1)]

    def is_leaf_node(self, current_node):
        """
        找到下一个节点
        """
        left_node = current_node * 2
        right_node = left_node + 1
        return len(list({left_node, right_node}.intersection(set(self.all_nodes)))) == 0


class FtaSolutionConfigConvert:
    """ "
    负责变量的替换
    """

    @classmethod
    def bk_notify_content_convert(cls, solution, tree_constants, **kwargs):
        """通知套餐内容的转换"""

        config = cls.convert_config(solution.config, tree_constants, **kwargs)
        return json.loads(config).get("message", "")

    @classmethod
    def bk_timing_convert(cls, solution, tree_constants, **kwargs):
        """通知套餐内容的转换"""
        config = cls.convert_config(solution.config, tree_constants, **kwargs)
        return json.loads(config).get("seconds", "")

    @classmethod
    def bak_ips_set_convert(cls, solution, tree_constants, **kwargs):
        config = cls.convert_config(solution.config, tree_constants, **kwargs)
        return json.loads(config).get("set_id", "")

    @classmethod
    def bak_ips_module_convert(cls, solution, tree_constants, **kwargs):
        config = cls.convert_config(solution.config, tree_constants, **kwargs)
        return json.loads(config).get("app_module_id", "")

    @staticmethod
    def cc_biz_id_convert(solution, tree_constants, **kwargs):
        return kwargs.get("bk_biz_id")

    @staticmethod
    def convert_config(config, tree_constants, **kwargs):
        """
        获取配置参数里的
        :param config:
        :param tree_constants:
        :param kwargs:
        :return:
        """
        constant_keys = VAR_STR_MATCH.findall(config)
        for new_key in constant_keys:
            if new_key not in tree_constants:
                tree_constants[new_key] = sops_constant_skeleton(new_key, name=new_key)

    @classmethod
    def template_id(cls, solution, tree_constants, **kwargs):
        config = cls.convert_config(solution.config, tree_constants, **kwargs)
        config_dir = json.loads(config)
        task_kwargs = json.loads(config_dir["task_kwargs"])
        return str(task_kwargs.get("template_id"))

    @classmethod
    def bk_http_request_url_convert(cls, solution, tree_constants, **kwargs):
        tree_constants["${bk_http_request_body}"] = sops_constant_skeleton("${bk_http_request_body}", _("回调内容"))
        config = json.loads(solution.config)
        return config.get("url", "")

    @classmethod
    def global_vars_convert(cls, solution, tree_constants, **kwargs):
        param_prefix = "parms_"
        config = json.loads(solution.config)
        job_values = []
        for key, value in config.items():
            if param_prefix not in key:
                continue
            [category, field] = key.lstrip(param_prefix).split("_")
            for fta_v, sops_v in FTA_SOPS_MAPPING.items():
                if fta_v in value:
                    value = value.replace(fta_v, sops_v)
            if int(category) == 3 and "${fault_ip}" in value:
                value = value.replace("${fault_ip}", "${bk_cloud_id}:${fault_ip}")
            job_values.append({"id": field, "category": category, "name": "name", "value": value, "description": ""})
        return job_values

    @classmethod
    def task_id_convert(cls, solution, tree_constants, **kwargs):
        config = json.loads(solution.config)
        return config.get("task_id", "")
