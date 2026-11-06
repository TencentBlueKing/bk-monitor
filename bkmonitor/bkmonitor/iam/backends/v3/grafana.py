"""V3 Grafana 实例授权范围：保留原产品策略解析语义，不依赖本地候选存在性。"""


def policy_resource_ids(policy, org_id, bk_biz_id):
    """旧 DashboardPermission.get_policy_resources 的 IAM 侧适配。

    返回当前组织的 dashboard/folder ID；文件夹展开仍由产品权限服务处理。
    不以本地 DB 中是否存在对应仪表盘改变 V3 已授权资源范围。
    """
    if not policy:
        return set()
    op = policy.get("op", "").lower()
    raw_ids = set()
    if op == "or":
        for child in policy["content"]:
            raw_ids.update(policy_resource_ids(child, org_id, bk_biz_id))
    elif op == "in":
        raw_ids.update(policy["value"])
    elif op == "eq":
        raw_ids.add(policy["value"])
    elif op == "and":
        iam_biz_id = None
        instance_ids = set()
        for child in policy["content"]:
            if child.get("field") == "grafana_dashboard._bk_iam_path_":
                path = child["value"].split(",")
                if len(path) == 2 and path[0] == "/space":
                    iam_biz_id = int(path[1][:-1])
                    break
            elif child.get("field") == "grafana_dashboard.id":
                instance_ids.update(policy_resource_ids(child, org_id, bk_biz_id))
        if not iam_biz_id or iam_biz_id == int(bk_biz_id):
            raw_ids.update(instance_ids)

    resource_ids = set()
    for raw_id in raw_ids:
        raw_id = str(raw_id)
        if raw_id.startswith("folder:"):
            parts = raw_id[len("folder:") :].split("|", 1)
            if len(parts) == 2:
                try:
                    if int(parts[0]) == org_id:
                        resource_ids.add(f"folder:{org_id}|{int(parts[1])}")
                except ValueError:
                    pass
            continue
        uid = raw_id
        if "|" in raw_id:
            org, candidate_uid = raw_id.split("|", 1)
            try:
                if int(org) != org_id:
                    continue
                uid = candidate_uid
            except ValueError:
                pass
        if uid:
            resource_ids.add(f"{org_id}|{uid}")
    return resource_ids
