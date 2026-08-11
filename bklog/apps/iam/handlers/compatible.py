import copy

from django.conf import settings
from django.core.cache import cache

from apps.utils.log import logger
from iam import IAM
from iam.exceptions import AuthAPIError


class CompatibleIAM(IAM):
    """
    兼容模式的IAM客户端
    """

    def in_compatibility_mode(self):
        if hasattr(CompatibleIAM, "__compatibility_mode"):
            return getattr(CompatibleIAM, "__compatibility_mode")

        from apps.log_search.models import GlobalConfig

        # 存在V1操作时，通过开关去判断是否开启兼容模式
        try:
            compatibility_mode = GlobalConfig.objects.get(config_id="IAM_V1_COMPATIBLE").configs
        except GlobalConfig.DoesNotExist:
            # 配置不存在时，默认打开兼容模式
            compatibility_mode = True

        setattr(CompatibleIAM, "__compatibility_mode", compatibility_mode)

        logger.info("[CompatibleIAM] in compatibility mode: %s", compatibility_mode)
        return compatibility_mode

    def _patch_policy_expression(self, expression):
        """
        将业务资源表达式转换为空间
        """
        if not expression:
            return
        if expression["op"] == "OR":
            for sub_expr in expression["content"]:
                self._patch_policy_expression(sub_expr)
        else:
            if expression["field"] == "biz.id":
                expression["field"] = "space.id"
            if "biz" in expression["value"]:
                expression["value"] = expression["value"].replace("biz", "space")

    def _do_policy_query(self, request, with_resources=True):
        if not self.in_compatibility_mode():
            return super()._do_policy_query(request, with_resources)

        data = request.to_dict()
        logger.debug("the request: %s", data)

        # NOTE: 不向服务端传任何resource, 用于统一类资源的批量鉴权
        # 将会返回所有策略, 然后遍历资源列表和策略列表, 逐一计算
        if not with_resources:
            data["resources"] = []

        ok, message, policies = self._client.policy_query(data)
        if data["action"]["id"].endswith("_v2"):
            v1_data = copy.deepcopy(data)

            # 替换action_id
            v1_data["action"]["id"] = v1_data["action"]["id"].replace("_v2", "")

            # 替换资源名称
            for resource in v1_data["resources"]:
                if resource["type"] == "space":
                    resource["system"] = "bk_cmdb"
                    resource["type"] = "biz"
                iam_path = resource.get("attribute", {}).get("_bk_iam_path_", "")
                if "space" in iam_path:
                    resource["attribute"]["_bk_iam_path_"] = iam_path.replace("space", "biz")

            v1_ok, v1_message, v1_policies = self._client.policy_query(v1_data)
            self._patch_policy_expression(v1_policies)

            if v1_policies:
                if not policies:
                    policies = v1_policies
                else:
                    # 将两个版本的 action 的策略组合起来
                    policies = {
                        "op": "OR",
                        "content": [policies, v1_policies],
                    }

        if not policies and not ok:
            raise AuthAPIError(message)
        return policies

    def _do_policy_query_by_actions(self, request, with_resources=True):
        if not self.in_compatibility_mode():
            return super()._do_policy_query_by_actions(request, with_resources)

        data = request.to_dict()
        logger.debug("the request: %s", data)

        # NOTE: 不向服务端传任何resource, 用于统一类资源的批量鉴权
        # 将会返回所有策略, 然后遍历资源列表和策略列表, 逐一计算
        if not with_resources:
            data["resources"] = []

        ok, message, action_policies = self._client.policy_query_by_actions(data)

        # v2的action需要查一下v1的action是否有权限
        v2_actions = [action["id"] for action in data["actions"] if action["id"].endswith("_v2")]

        if v2_actions:
            v1_data = copy.deepcopy(data)

            # 替换action_id
            v1_data["actions"] = [{"id": action_id.replace("_v2", "")} for action_id in v2_actions]

            v1_ok, v1_message, v1_action_policies = self._client.policy_query_by_actions(v1_data)
            for v1_policy in v1_action_policies:
                v1_policy["action"]["id"] += "_v2"
                # 替换资源名称
                self._patch_policy_expression(v1_policy["condition"])

                for policy in action_policies:
                    # 与V2的策略做比对，如果V2是空，就用V1的
                    if v1_policy["action"]["id"] != policy["action"]["id"]:
                        continue

                    if not v1_policy["condition"]:
                        continue

                    if not policy["condition"]:
                        policy["condition"] = v1_policy["condition"]
                    else:
                        policy["condition"] = {
                            "op": "OR",
                            "content": [policy["condition"], v1_policy["condition"]],
                        }

        if not ok:
            raise AuthAPIError(message)
        return action_policies


class V4CallbackIAM(CompatibleIAM):
    """V4 资源回调鉴权客户端：token 从 bkiam(V4) 拉取，而不是 V3 的 bk-iam 网关。"""

    def get_token(self, system):
        from apps.iam.backends.v4.config import resolve_effective_v4_system_id

        if system == resolve_effective_v4_system_id() and getattr(settings, "BK_IAM_V4_APIGATEWAY_URL", ""):
            return self._get_v4_auth_token(system)

        return super().get_token(system)

    def _get_v4_auth_token(self, system_id: str):
        from apps.iam.backends.v4.client import V4Client
        from apps.iam.backends.v4.config import V4Options

        bk_tenant_id = getattr(self._client, "_bk_tenant_id", "") or settings.BK_APP_TENANT_ID
        try:
            options = V4Options.from_settings(bk_tenant_id=bk_tenant_id, for_resource_callback=True)
        except Exception as error:  # pylint: disable=broad-except
            logger.error("[V4CallbackIAM] build V4 options failed: system=%s error=%s", system_id, error)
            return False, str(error), ""
        cache_key = f"bklog:iam:v4:auth-token:{bk_tenant_id}:{system_id}"
        try:
            cached_token = cache.get(cache_key)
        except Exception as error:  # pylint: disable=broad-except
            logger.warning(
                "[V4CallbackIAM] read auth token cache failed: system=%s tenant=%s error=%s",
                system_id,
                bk_tenant_id,
                error,
            )
            cached_token = None
        if cached_token:
            return True, "success", str(cached_token)

        try:
            client = V4Client(
                options,
                bk_tenant_id=bk_tenant_id,
            )
            token = client.retrieve_system_auth_token(system_id)
        except Exception as error:  # pylint: disable=broad-except
            logger.error("[V4CallbackIAM] get V4 auth token failed: system=%s error=%s", system_id, error)
            return False, str(error), ""

        if not token:
            return False, "empty auth_token from IAM V4", ""

        if options.auth_token_cache_seconds > 0:
            try:
                cache.set(cache_key, token, options.auth_token_cache_seconds)
            except Exception as error:  # pylint: disable=broad-except
                # 缓存故障不应使已经成功获取的 token 失效。
                logger.warning(
                    "[V4CallbackIAM] write auth token cache failed: system=%s tenant=%s error=%s",
                    system_id,
                    bk_tenant_id,
                    error,
                )
        return True, "success", token
