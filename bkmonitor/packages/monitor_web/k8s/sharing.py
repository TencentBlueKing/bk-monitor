from bkmonitor.models import ApiAuthToken
from bkmonitor.share.handler import BaseApiAuthChecker
from bkmonitor.utils.request import get_request_tenant_id
from core.errors.share import InvalidParamsError, ParamsPermissionDeniedError, TokenValidatedError


class K8sOverviewGraphApiAuthChecker(BaseApiAuthChecker):
    """The new K8s page shares an interactive cluster overview, including its detail drawers."""

    def get_query_params(self):
        data = self.token.params.get("data", {})
        query = data.get("query", {})
        if query.get("sceneId") != "kubernetes":
            raise InvalidParamsError({"key": "data.query.sceneId"})
        cluster_id = query.get("cluster")
        if not isinstance(cluster_id, str) or not cluster_id:
            raise InvalidParamsError({"key": "data.query.cluster"})
        # filterBy/groupBy/scene are interactive presentation state, like the legacy overview.
        return {"bk_biz_id": self.bk_biz_id, "bcs_cluster_id": cluster_id}, {}, {}

    def query_configs_check(self, query_configs):
        # The graph resource enforces the validated cluster through required_promql_match.
        # Client-reported where conditions do not constrain raw PromQL selectors.
        pass


def get_k8s_overview_graph_checker(request):
    if not getattr(request, "token", None):
        return None
    try:
        token = ApiAuthToken.objects.get(token=request.token, bk_tenant_id=get_request_tenant_id())
    except ApiAuthToken.DoesNotExist:
        raise TokenValidatedError
    if token.type != "kubernetes":
        return None
    data = token.params.get("data", {})
    if data.get("query", {}).get("sceneType") == "detail":
        # Legacy detail panels are authorized through their existing scene endpoint.
        raise ParamsPermissionDeniedError({"key": "sceneType", "error_params": "detail", "correct_params": "overview"})
    if data.get("name") != "k8s-new" and data.get("path") != "/k8s-new":
        return None
    if "sceneType" in data.get("query", {}):
        # Legacy overview tokens keep their existing parameter checks.
        return None
    return K8sOverviewGraphApiAuthChecker(token)
