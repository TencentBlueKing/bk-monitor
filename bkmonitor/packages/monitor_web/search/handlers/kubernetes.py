# -*- coding: utf-8 -*-
from typing import List

from django.utils.translation import gettext as _
from furl import furl

from bkmonitor.iam import ActionEnum
from core.drf_resource import resource
from monitor_web.search.handlers.base import BaseSearchHandler, SearchResultItem


class K8sSearchHandler(BaseSearchHandler):
    SCENE = "kubernetes"

    def search_for_object(self, name: str, display_name: str, query: str, limit: int):
        resource_func = getattr(resource.scene_view, f"get_kubernetes_{name}_list")
        result = resource_func(bk_biz_id=self.bk_biz_id, page=1, page_size=limit, keyword=query, view_options={})
        if result["total"] > limit:
            return [
                SearchResultItem(
                    bk_biz_id=self.bk_biz_id,
                    title=_("搜索到 {count} {obj}").format(count=result["total"], obj=display_name),
                    view="k8s",
                    view_args={
                        "query": {
                            "sceneId": "kubernetes",
                            "dashboardId": name,
                            "sceneType": "overview",
                            "queryString": query,
                        }
                    },
                    is_collected=True,
                )
            ]

        search_results = []
        common_view_args = {"sceneId": "kubernetes", "dashboardId": name, "sceneType": "detail", "queryString": query}

        for obj in result["data"]:
            view_arg_list = furl(obj.get(f"{name}_link", {}).get("url", "")).args.listitems()
            view_args = {}
            for k, v in view_arg_list:
                if not v:
                    continue
                if len(v) == 1:
                    view_args[k] = v[0]
                else:
                    view_args[k] = v
            view_args.update(common_view_args)
            search_results.append(
                SearchResultItem(
                    bk_biz_id=self.bk_biz_id,
                    title=f"[{display_name}] {obj['name']}",
                    view="k8s-detail",
                    view_args={"query": view_args},
                )
            )

        return search_results

    def search_clusters(self, query: str, limit: int):
        clusters = resource.scene_view.get_kubernetes_cluster_list(bk_biz_id=self.bk_biz_id, data_type="simple")
        clusters_data = clusters["data"]
        clusters = [
            c
            for c in clusters_data
            if query.lower() in c["name"]["value"].lower() or query.lower() in c["bcs_cluster_id"]["value"].lower()
        ]

        if len(clusters) > limit:
            return [
                SearchResultItem(
                    bk_biz_id=self.bk_biz_id,
                    title=_("搜索到 {count} Cluster").format(count=len(clusters)),
                    view="k8s",
                    view_args={
                        "query": {
                            "sceneId": "kubernetes",
                            "dashboardId": "cluster",
                            "sceneType": "overview",
                            "queryString": query,
                        }
                    },
                    is_collected=True,
                )
            ]

        search_results = []
        for cluster in clusters:
            view_arg_list = furl(cluster.get("bcs_cluster_id", {}).get("url", "")).args.listitems()
            view_args = {}
            for k, v in view_arg_list:
                if not v:
                    continue
                if len(v) == 1:
                    view_args[k] = v[0]
                else:
                    view_args[k] = v
            view_args.update(
                {"sceneId": "kubernetes", "dashboardId": "cluster", "sceneType": "detail", "queryString": query}
            )
            search_results.append(
                SearchResultItem(
                    bk_biz_id=self.bk_biz_id,
                    title="[Cluster] {name}".format(name=cluster["name"]),
                    view="k8s-detail",
                    view_args={"query": view_args},
                )
            )
        return search_results

    def search(self, query: str, limit: int = 10) -> List[SearchResultItem]:
        search_results = self.search_clusters(query, limit)

        obj_types = [
            ("workload", "Workload"),
            ("service", "Service"),
            ("pod", "Pod"),
            ("container", "Container"),
            ("node", "Node"),
            ("service_monitor", "ServiceMonitor"),
            ("pod_monitor", "PodMonitor"),
        ]

        for name, display_name in obj_types:
            search_results.extend(
                self.search_for_object(name=name, display_name=display_name, query=query, limit=limit)
            )

        self.add_permission_for_results(results=search_results, action=ActionEnum.VIEW_BUSINESS)

        return search_results
