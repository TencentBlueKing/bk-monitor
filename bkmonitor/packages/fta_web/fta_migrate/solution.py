# -*- coding: utf-8 -*-
import base64
import datetime
import hashlib
import json
import logging

import ujson
from django.utils.translation import gettext as _

from bkmonitor.models import ActionConfig
from core.drf_resource import api
from fta_web.fta_migrate.constants import SALT, SOPS_CONSTANTS_MAPPING
from fta_web.fta_migrate.pipeline import builder
from fta_web.fta_migrate.pipeline.flow import EmptyEndEvent, EmptyStartEvent
from fta_web.fta_migrate.pipeline.tree_components import (
    fta_public_constants,
    get_template_skeleton,
    node_uniqid,
    tree_skeleton,
)
from fta_web.fta_migrate.pipeline.utils import replace_all_id
from fta_web.fta_migrate.pipeline_compile import FtaTreeDecode
from fta_web.models.old_fta import Solution

logger = logging.getLogger("root")


class MigrateDiySolution:
    def __init__(self, bk_biz_id, builtin_action_template_ids=None):
        self.bk_biz_id = bk_biz_id
        self.builtin_action_template_ids = builtin_action_template_ids or {}
        self.builtin_action_templates = {}

    def get_builtin_templates(self):
        for code, template_id in self.builtin_action_template_ids.items():
            self.builtin_action_templates[code] = api.sops.get_template_info(
                bk_biz_id=self.bk_biz_id, template_id=template_id
            )

    def migrate_solutions(self):
        """迁移流程"""
        # step 1 迁移组合套餐至标准运维的流程
        logger.info("step 1 迁移组合套餐至标准运维的流程 %s", self.bk_biz_id)
        # TODO： 组合套餐的迁移，一定更需要确认
        solution_template_relates, old_solutions, failed_solutions = self.import_templates_to_sops()

        # step 2 故障自愈新的数据库创建新的套餐
        logger.info("step 2 故障自愈新的数据库创建新的套餐 %s", self.bk_biz_id)
        return self.convert_solutions(solution_template_relates, old_solutions)

    def translate_sops_template_solution(self, template_id):
        params = {"template_id": template_id, "bk_biz_id": self.bk_biz_id}
        template_info = api.sops.get_template_info(**params)
        template_detail = {}
        for param_key in template_info["pipeline_tree"]["constants"]:
            # TODO 标准运维环境参数转换为新版的变量 变成ActionConfig
            fta_param_key = SOPS_CONSTANTS_MAPPING.get(param_key)
            if not fta_param_key:
                fta_param_key = "|".join(set(param_key.split("__")))
            template_detail[param_key] = fta_param_key

        return {"template_detail": template_detail, "template_id": template_id, "timeout": 600}

    def convert_solutions(self, solution_template_relates, old_solutions):
        """
        用标准运维方式在新的FTA上创建套餐
        """
        diy_actions = {}
        for solution in old_solutions:
            if str(solution.id) in solution_template_relates:
                execute_config = self.translate_sops_template_solution(solution_template_relates[str(solution.id)])
                diy_actions[str(solution.id)] = ActionConfig.objects.create(
                    **{
                        "name": _("[{}]组合套餐迁移").format(solution.title or solution.id),
                        "plugin_id": 4,
                        "bk_biz_id": solution.cc_biz_id,
                        "desc": _("{}（组合套餐迁移）").format(solution.title or solution.id),
                        "execute_config": execute_config,
                        "is_builtin": False,
                    }
                ).id
        return diy_actions

    def translate_solutions(self):
        """ "
        解析某个业务下的DIY处理套餐至标准运维流程
        """
        # 组合套餐
        diy_solutions = Solution.objects.filter(solution_type="diy", cc_biz_id=self.bk_biz_id, is_deleted=False).using(
            "fta"
        )

        if diy_solutions:
            self.get_builtin_templates()

        related_solution_ids = []
        diy_solutions_config = {}
        # 获取所有组合套餐相关的
        for diy_solution in diy_solutions:
            # 组合树转换为整型
            diy_solution.config = json.loads(json.loads(diy_solution.config)["real_solutions"])
            diy_solutions_config[diy_solution.id] = {int(key): int(value) for key, value in diy_solution.config.items()}
            related_solution_ids.extend(diy_solution.config.values())

        related_solutions = Solution.objects.filter(id__in=related_solution_ids).using("fta")
        related_solutions = {relate_solution.id: relate_solution for relate_solution in related_solutions}
        failed_solutions = {}
        template_data = {
            "pipeline_template_data": {"refs": {}, "template": {}},
            "template": {},
            "override_forbidden": True,
            "template_source": "project",
        }
        solutions = []

        # 获取跟组合套餐相关的内容
        all_translate_solutions = Solution.objects.filter(id__in=diy_solutions_config.keys()).using("fta")

        for diy_solution in all_translate_solutions:
            solution_id = diy_solution.id
            fta_flow = diy_solutions_config[diy_solution.id]
            try:
                self.create_template_data(fta_flow, related_solutions, diy_solution, template_data)
                solutions.append(diy_solution)
            except BaseException as error:
                import traceback

                failed_solutions[solution_id] = str(error)
                print("error : %s" % repr(error))
                traceback.print_exc()
                logger.exception("error : %s" % str(error))

        # 计算 digest
        data_string = (ujson.dumps(template_data, sort_keys=True) + SALT).encode("utf-8")
        digest = hashlib.md5(data_string).hexdigest()

        template_file_data = {"template_data": template_data, "digest": digest}

        template_dat_file_content = base64.b64encode(
            ujson.dumps(template_file_data, sort_keys=True).encode("utf-8")
        ).decode("utf-8")
        return template_dat_file_content, solutions, failed_solutions

    def create_template_data(self, fta_flow, real_solutions, diy_solution, template_data):
        """
        创建流程导入模板的数据
        """
        pipeline_tree = self.create_pipeline_tree(fta_flow, real_solutions)
        # 组装 pipeline_template_data
        pipeline_template_id = node_uniqid()
        utc_now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M:%S %Z")
        template_name = _("{}||{}【故障自愈】").format(diy_solution.id, diy_solution.title or "组合套餐")

        pipeline_template_data = {
            "edit_time": utc_now,
            "create_time": utc_now,
            "is_deleted": False,
            "description": "",
            "name": template_name,
            "creator": diy_solution.create_user,
            "tree": pipeline_tree,
            "template_id": pipeline_template_id,
            "editor": diy_solution.update_user,
        }
        template_data["template"].update(
            {str(diy_solution.id): get_template_skeleton(diy_solution.id, pipeline_template_id, self.bk_biz_id)}
        )
        template_data["pipeline_template_data"]["template"][pipeline_template_id] = pipeline_template_data

    def create_pipeline_tree(self, fta_flow, real_solutions):
        # 使用 builder 构造出流程描述结构
        fta_tree = tree_skeleton()
        tree_constants = fta_public_constants()
        tree = EmptyStartEvent(id=node_uniqid(), name="")
        end_node = EmptyEndEvent(name="", id=node_uniqid())
        component_data = {}
        fta_flow_obj = FtaTreeDecode(
            fta_flow, tree, end_node, tree_constants, component_data, self.bk_biz_id, self.builtin_action_templates
        )
        fta_flow_obj.compile_tree(real_solutions)
        pipeline_tree = builder.build_tree(fta_flow_obj.tree, replace_id=False)
        pipeline_tree["constants"] = fta_flow_obj.tree_constants
        fta_tree.update(pipeline_tree)
        for act_id, act in fta_tree["activities"].items():
            if act["type"] == "ServiceActivity":
                act["component"]["data"] = component_data[act_id]
                act["component"]["version"] = fta_flow_obj.component_version[act_id]
            else:
                act["constants"] = component_data[act_id]
                act["version"] = fta_flow_obj.component_version[act_id]
        for gateway in fta_tree["gateways"].values():
            if gateway["type"] == "ConvergeGateway":
                # 合并网关忽略
                continue
            for condition in gateway["conditions"].values():
                if "== True" in condition["evaluate"]:
                    condition["name"] = _("成功")
                else:
                    condition["name"] = _("失败")
        replace_all_id(fta_tree)
        return fta_tree

    def import_templates_to_sops(self):
        """
        调用接口导入流程
        """
        template_dat_file_content, solutions, failed_solutions = self.translate_solutions()
        if len(solutions) == 0:
            return {}, [], {}
        try:
            api.sops.import_project_template(template_data=template_dat_file_content, project_id=self.bk_biz_id)
        except BaseException as error:
            logger.exception("import_project_template error : %s" % str(error))
            raise
        solution_ids = [str(solution.id) for solution in solutions]
        solution_template_relates = {}
        all_templates = api.sops.get_template_list(bk_biz_id=self.bk_biz_id)
        for template in all_templates:
            solution_id = template["name"].split("||")[0]
            if solution_id in solution_ids and solution_id not in solution_template_relates:
                solution_template_relates[solution_id] = template["id"]
        return solution_template_relates, solutions, failed_solutions
