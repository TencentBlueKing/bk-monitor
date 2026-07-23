"""
Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
License for BK-LOG 蓝鲸日志平台:
--------------------------------------------------------------------
Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
The above copyright notice and this permission notice shall be included in all copies or substantial
portions of the Software.
THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
We undertake not to change the open source license (MIT license) applicable to the current version of
the project delivered to anyone in the future.
"""

"""
TAPD5: VIEW_CLIENT_LOG 存量迁移命令。

背景：
  客户端日志"查看"能力原先借用粗粒度的 VIEW_BUSINESS 兜底（apps/tgpa/views.py），
  本期新增细粒度的 VIEW_CLIENT_LOG action，要求存量已有 VIEW_BUSINESS 的用户/用户组，
  在同业务下自动补授 VIEW_CLIENT_LOG，避免上线后（鉴权点切换）出现批量断权。

实现思路（对照 iam_upgrade_action_v2.py 的既有模式，基于IAM策略查询+批量授权，
不使用本地 ORM 表 SQL join，因为权限数据实际存储在权限中心 IAM）：
  1. query_polices(VIEW_BUSINESS)：分页查询权限中心中 VIEW_BUSINESS 的全部策略（含 subject/expression/expired_at）
  2. expression_to_resource_paths()：把每条策略的 expression 转换为资源路径列表（biz -> space 资源类型转换）
  3. policy_to_resource()：为每条 VIEW_BUSINESS 策略构造一条等价的 VIEW_CLIENT_LOG 批量授权请求
     （subject/resources/expired_at 均照抄原策略，仅 action 替换为 view_client_log）
  4. grant_resource()：通过 IAMApi.batch_path() 批量下发 VIEW_CLIENT_LOG 授权（operate=grant，天然幂等，可安全重跑）
  5. compute_diff()：迁移前后对比 VIEW_BUSINESS 与 VIEW_CLIENT_LOG 的 (subject, resource) 集合，输出差异清单
  6. --revoke：支持撤销当前全部 VIEW_CLIENT_LOG 授权，用于 action 回退（迁移方向仅为"增授权"，方向安全）

顺序要求（严禁颠倒，否则会造成批量断权）：
  先注册 action（apps/iam/handlers/actions.py + support-files/iam/initial.json，已完成并需先执行
  `python manage.py iam_upgrade_action_v2` 使新 action upsert 到权限中心）
  -> 跑本命令完成批量授权
  -> 用 --dry-run 或核对日志确认覆盖率（VIEW_BUSINESS 存量集合 == VIEW_CLIENT_LOG 存量集合）
  -> 再切换鉴权点上线 / 开启灰度（本次代码已直接切换鉴权点，需确保迁移在发布前跑完）

用法：
  python manage.py iam_migrate_view_client_log --dry-run      # 仅打印差异清单，不下发授权
  python manage.py iam_migrate_view_client_log                # 执行批量授权（幂等，可重复执行续跑）
  python manage.py iam_migrate_view_client_log -u zhangsan     # 仅处理指定用户（用于分批/重试单个用户）
  python manage.py iam_migrate_view_client_log --revoke        # 回退：撤销当前全部 VIEW_CLIENT_LOG 授权
"""
import time
from multiprocessing.pool import ThreadPool

from django.conf import settings
from django.core.management.base import BaseCommand
from iam.auth.models import Action
from iam.auth.models import ApiBatchAuthRequest as OldApiBatchAuthRequest
from iam.auth.models import ApiBatchAuthResourceWithPath, Subject

from apps.api import IAMApi
from apps.iam import ActionEnum, Permission, ResourceEnum
from apps.iam.handlers.actions import ActionMeta
from apps.iam.handlers.compatible import CompatibleIAM
from apps.log_search.models import Space


class ApiBatchAuthRequest(OldApiBatchAuthRequest):
    def __init__(self, *args, expired_at=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.expired_at = expired_at

    def to_dict(self):
        request_dict = super().to_dict()
        if self.expired_at is not None:
            request_dict["expired_at"] = self.expired_at
        return request_dict


class Command(BaseCommand):
    OPERATOR = "admin"
    SOURCE_ACTION: ActionMeta = ActionEnum.VIEW_BUSINESS
    TARGET_ACTION: ActionMeta = ActionEnum.VIEW_CLIENT_LOG

    def add_arguments(self, parser):
        parser.add_argument("-c", "--concurrency", help="并发数，默认50")
        parser.add_argument("-u", "--username", help="仅处理指定 subject id（用户名/用户组ID），用于分批或重试")
        parser.add_argument(
            "--revoke",
            action="store_true",
            help="回退：撤销当前权限中心里全部 VIEW_CLIENT_LOG 授权（用于 action 回退，谨慎使用）",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="仅查询并打印 VIEW_BUSINESS/VIEW_CLIENT_LOG 差异清单，不实际调用IAM授权/回收接口",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.spaces = {
            str(space["bk_biz_id"]): space["space_name"] for space in Space.objects.values("bk_biz_id", "space_name")
        }
        self.iam_client: CompatibleIAM | None = None
        self.system_id = settings.BK_IAM_SYSTEM_ID
        self.username = None

    def handle(self, concurrency=None, username=None, revoke=False, dry_run=False, bk_tenant_id=None, **options):
        if not bk_tenant_id:
            bk_tenant_id = settings.BK_APP_TENANT_ID
        self.iam_client = Permission.get_iam_client(bk_tenant_id)
        self.username = username
        concurrency = int(concurrency) if concurrency else 50

        if revoke:
            self.revoke_view_client_log(concurrency, dry_run=dry_run)
            return

        print("[iam_migrate_view_client_log] ##### START #####")
        start_time = time.time()

        source_policies = self.query_polices(self.SOURCE_ACTION.id)
        target_policies = self.query_polices(self.TARGET_ACTION.id)

        diff_policies = self.compute_diff(source_policies, target_policies)
        self.print_diff(diff_policies, source_policies, target_policies)

        if dry_run:
            print("[iam_migrate_view_client_log] dry-run 模式，未执行实际授权，仅供核对差异")
            return

        if not diff_policies:
            print("[iam_migrate_view_client_log] 存量已对齐，无需迁移")
            return

        self.grant_policies(diff_policies, concurrency)

        end_time = time.time()
        print(f"[iam_migrate_view_client_log] ##### END #####, Cost: {end_time - start_time}")

        # 迁移后重新核对覆盖率
        self.check_coverage()

    # ────────────────────────────────────────────────
    #  查询 & 差异计算
    # ────────────────────────────────────────────────

    def query_polices(self, action_id):
        """
        根据操作ID分页查询权限中心全量策略
        """
        page_size = 500
        page = 1

        policies = []
        query_result = self.iam_client.query_polices_with_action_id(
            self.system_id, {"action_id": action_id, "page": page, "page_size": page_size}
        )
        if not query_result["results"]:
            return policies

        policies.extend(query_result["results"])
        total = query_result["count"]

        while page * page_size < total:
            page += 1
            query_result = self.iam_client.query_polices_with_action_id(
                self.system_id, {"action_id": action_id, "page": page, "page_size": page_size}
            )
            policies.extend(query_result["results"])

        if self.username:
            policies = [policy for policy in policies if policy["subject"]["id"] == self.username]

        return policies

    def expression_to_resource_paths(self, expression, paths: list):
        """
        将权限表达式转换为资源路径（biz -> space 资源类型统一转换）
        """
        if expression["op"] == "OR":
            for sub_expr in expression["content"]:
                self.expression_to_resource_paths(sub_expr, paths)
        elif expression["op"] == "eq":
            resource_type = expression["field"].split(".")[0]
            if resource_type == "biz":
                resource_type = ResourceEnum.BUSINESS.id
            resource_id = expression["value"]
            paths.append([{"type": resource_type, "id": resource_id, "name": self.get_resource_name(resource_id)}])
        elif expression["op"] == "in":
            resource_type = expression["field"].split(".")[0]
            if resource_type == "biz":
                resource_type = ResourceEnum.BUSINESS.id
            for resource_id in expression["value"]:
                paths.append(
                    [{"type": resource_type, "id": resource_id, "name": self.get_resource_name(resource_id)}]
                )
        elif expression["op"] == "starts_with":
            # example: {'field': 'indices._bk_iam_path_', 'op': 'starts_with', 'value': '/biz,5/'}
            resource_id = expression["value"][1:-1].split(",")[1]
            paths.append(
                [{"type": ResourceEnum.BUSINESS.id, "id": resource_id, "name": self.get_resource_name(resource_id)}]
            )
        elif expression["op"] == "any":
            # 拥有全部权限
            paths.append([])

    def get_resource_name(self, resource_id):
        return self.spaces.get(str(resource_id), resource_id)

    def _extract_subject_resource_map(self, policies) -> dict:
        """
        将策略列表转换为 {(subject_type, subject_id): set(resource_ids) or "__any__"} 的映射，
        用于比较两个 action 的存量覆盖范围差异。
        """
        result = {}
        for policy in policies:
            subject_key = (policy["subject"]["type"], policy["subject"]["id"])
            paths: list = []
            self.expression_to_resource_paths(policy["expression"], paths)

            has_any = any(not path for path in paths)
            if has_any:
                result[subject_key] = "__any__"
                continue

            resource_ids = {path[0]["id"] for path in paths if path}
            existing = result.get(subject_key)
            if existing == "__any__":
                continue
            if existing is None:
                result[subject_key] = resource_ids
            else:
                result[subject_key] = existing | resource_ids
        return result

    def compute_diff(self, source_policies, target_policies) -> list:
        """
        计算需要补授的 VIEW_BUSINESS 策略清单：
        对每条 VIEW_BUSINESS 策略，若同 subject 在 VIEW_CLIENT_LOG 侧覆盖范围
        不包含该策略对应的资源（或 target 侧完全没有该 subject），则纳入待授权清单。
        直接复用整条原始 policy（而非拆分单个资源），保证 expired_at/subject 与源策略一致。
        """
        target_map = self._extract_subject_resource_map(target_policies)

        diff_policies = []
        for policy in source_policies:
            subject_key = (policy["subject"]["type"], policy["subject"]["id"])
            target_resources = target_map.get(subject_key)

            if target_resources == "__any__":
                # target 侧该 subject 已经拥有全量 VIEW_CLIENT_LOG，无需补授
                continue

            paths: list = []
            self.expression_to_resource_paths(policy["expression"], paths)
            has_any = any(not path for path in paths)
            source_resources = "__any__" if has_any else {path[0]["id"] for path in paths if path}

            if target_resources is None:
                diff_policies.append(policy)
                continue

            if source_resources == "__any__":
                # source 是 any 但 target 不是 any，仍需补授（以 source 的 any 覆盖 target）
                diff_policies.append(policy)
                continue

            if not source_resources.issubset(target_resources):
                diff_policies.append(policy)

        return diff_policies

    def print_diff(self, diff_policies, source_policies, target_policies):
        print(
            f"[iam_migrate_view_client_log] VIEW_BUSINESS 策略数: {len(source_policies)}, "
            f"VIEW_CLIENT_LOG 策略数: {len(target_policies)}, 待补授策略数: {len(diff_policies)}"
        )
        if not diff_policies:
            return
        print("[iam_migrate_view_client_log] ##### 差异清单(待补授 subject 列表) #####")
        for policy in diff_policies:
            subject = policy["subject"]
            print(f"  - subject_type={subject['type']}, subject_id={subject['id']}, policy_id={policy.get('id')}")

    # ────────────────────────────────────────────────
    #  批量授权
    # ────────────────────────────────────────────────

    def policy_to_resource(self, action: ActionMeta, policy):
        """
        将一条源 action 策略转换为等价的目标 action 授权请求体
        """
        paths = []
        self.expression_to_resource_paths(policy["expression"], paths)

        has_any_policy = any(not path for path in paths)
        if has_any_policy:
            paths = []

        resource = {
            "asynchronous": False,
            "operate": "grant",
            "system": self.system_id,
            "actions": [{"id": action.id}],
            "subject": policy["subject"],
            "resources": [
                {
                    "system": action.related_resource_types[0].system_id,
                    "type": action.related_resource_types[0].id,
                    "paths": paths,
                }
            ],
            "expired_at": policy["expired_at"],
        }
        return resource

    def grant_policies(self, policies, concurrency):
        print(f"[grant_resource] [START] target_action[{self.TARGET_ACTION.id}], policy count: {len(policies)}")

        resources = [self.policy_to_resource(self.TARGET_ACTION, policy) for policy in policies]

        pool = ThreadPool(concurrency)
        futures = [pool.apply_async(self.grant_resource, args=(resource,)) for resource in resources]
        pool.close()
        pool.join()

        success = 0
        for future in futures:
            try:
                future.get()
                success += 1
            except Exception as e:  # pylint: disable=broad-except
                print(f"[grant_resource] grant permission for action[{self.TARGET_ACTION.id}] failed: {e}")

        print(f"[grant_resource] [END] target_action[{self.TARGET_ACTION.id}], success: {success}/{len(resources)}")

    def grant_resource(self, resource):
        paths = resource["resources"][0]["paths"]
        size = 1000

        results = []
        if not paths:
            results.append(self.grant_resource_chunked(resource, []))
        else:
            chunked_paths = [paths[pos: pos + size] for pos in range(0, len(paths), size)]
            for chunk in chunked_paths:
                results.append(self.grant_resource_chunked(resource, chunk))
        return results

    def grant_resource_chunked(self, resource, paths):
        request = ApiBatchAuthRequest(
            system=resource["system"],
            subject=Subject(type=resource["subject"]["type"], id=resource["subject"]["id"]),
            actions=[Action(id=action["id"]) for action in resource["actions"]],
            resources=[
                ApiBatchAuthResourceWithPath(system=r["system"], type=r["type"], paths=paths)
                for r in resource["resources"]
            ],
            operate=resource["operate"],
            asynchronous=resource["asynchronous"],
            expired_at=resource["expired_at"],
        )
        return IAMApi.batch_path(request.to_dict())

    # ────────────────────────────────────────────────
    #  覆盖率核对 & 回退
    # ────────────────────────────────────────────────

    def check_coverage(self):
        """
        迁移后核对：VIEW_BUSINESS(subject) 集合 应为 VIEW_CLIENT_LOG(subject) 集合的子集。
        若仍有差异，打印剩余差异清单（正常应为空，否则说明批量授权有失败项，需重跑本命令续跑）。
        """
        source_policies = self.query_polices(self.SOURCE_ACTION.id)
        target_policies = self.query_polices(self.TARGET_ACTION.id)
        remaining_diff = self.compute_diff(source_policies, target_policies)

        print("[iam_migrate_view_client_log] ##### CHECK COVERAGE #####")
        if not remaining_diff:
            print("Congratulations! VIEW_CLIENT_LOG 迁移覆盖率核对通过，存量已对齐！")
            return True

        print(
            f"Sorry, 仍有 {len(remaining_diff)} 条 subject 授权未对齐，"
            f"请重新执行 `python manage.py iam_migrate_view_client_log` 续跑（幂等，可安全重复执行）"
        )
        self.print_diff(remaining_diff, source_policies, target_policies)
        return False

    def revoke_view_client_log(self, concurrency, dry_run=False):
        """
        回退：撤销当前权限中心里全部 VIEW_CLIENT_LOG 授权，用于 action 回退场景。

        注意：本命令自始至终是 VIEW_CLIENT_LOG 唯一的授权来源（该 action 为本期新增，
        上线前不存在任何其他授权入口），因此"当前全部 VIEW_CLIENT_LOG 授权"等价于"本批迁移授权"。
        """
        target_policies = self.query_polices(self.TARGET_ACTION.id)
        print(f"[iam_migrate_view_client_log] ##### REVOKE: 当前 VIEW_CLIENT_LOG 策略数: {len(target_policies)} #####")

        if dry_run:
            print("[iam_migrate_view_client_log] dry-run 模式，未执行实际回收")
            return

        if not target_policies:
            print("[iam_migrate_view_client_log] 无 VIEW_CLIENT_LOG 授权可回收")
            return

        resources = []
        for policy in target_policies:
            resource = self.policy_to_resource(self.TARGET_ACTION, policy)
            resource["operate"] = "revoke"
            resources.append(resource)

        pool = ThreadPool(concurrency)
        futures = [pool.apply_async(self.grant_resource, args=(resource,)) for resource in resources]
        pool.close()
        pool.join()

        success = 0
        for future in futures:
            try:
                future.get()
                success += 1
            except Exception as e:  # pylint: disable=broad-except
                print(f"[revoke_resource] revoke permission for action[{self.TARGET_ACTION.id}] failed: {e}")

        print(f"[iam_migrate_view_client_log] ##### REVOKE END #####, success: {success}/{len(resources)}")
