from types import SimpleNamespace

from monitor_web.notice_group.resources import front
from monitor_web.notice_group.resources.front import GetReceiverResource, normalize_members


def test_normalize_members():
    assert normalize_members(None) == []
    assert normalize_members("") == []
    assert normalize_members("admin") == ["admin"]
    assert normalize_members("admin, developer") == ["admin", "developer"]
    assert normalize_members(["admin", "", None, "developer"]) == ["admin", "developer"]
    assert normalize_members(("admin", "developer")) == ["admin", "developer"]
    assert normalize_members(1) == []


def test_get_receiver_supports_empty_and_string_business_roles(mocker):
    business = SimpleNamespace(
        bk_biz_maintainer="admin, developer",
        bk_bak_operator=None,
        # 自定义角色返回列表时不应被逐字符拆分
        bk_pmp_group_user=["developer"],
        bk_pmp_ope_pm="motionsun",
    )
    get_app_by_id = mocker.Mock(return_value=business)
    get_notify_roles = mocker.Mock(
        return_value={
            "bk_biz_maintainer": "运维人员",
            "bk_bak_operator": "备份负责人",
            "bk_pmp_group_user": "运维小组组长",
            "bk_pmp_ope_pm": "运营规划",
        },
    )
    get_all_user = mocker.Mock(
        return_value={
            "results": [
                {"username": "admin", "display_name": "admin"},
                {"username": "developer", "display_name": "developer"},
                {"username": "motionsun", "display_name": "motionsun"},
            ]
        },
    )
    mocker.patch.object(
        front,
        "resource",
        SimpleNamespace(cc=SimpleNamespace(get_app_by_id=get_app_by_id, get_notify_roles=get_notify_roles)),
    )
    mocker.patch.object(front, "api", SimpleNamespace(bk_login=SimpleNamespace(get_all_user=get_all_user)))

    result = GetReceiverResource().perform_request({"bk_biz_id": 2})

    assert get_all_user.call_args.kwargs["exact_lookups"] == "admin,developer,motionsun"
    groups = {group["id"]: group for group in result[0]["children"]}
    assert groups["bk_biz_maintainer"]["members"] == [
        {"id": "admin", "display_name": "admin"},
        {"id": "developer", "display_name": "developer"},
    ]
    assert groups["bk_bak_operator"]["members"] == []
    assert groups["bk_pmp_group_user"]["members"] == [{"id": "developer", "display_name": "developer"}]
    assert groups["bk_pmp_ope_pm"]["members"] == [{"id": "motionsun", "display_name": "motionsun"}]


def test_get_receiver_batches_members_by_step_size(mocker):
    # 构造超过一批（step_size=50）的成员，验证会分批查询且结果正确合并
    members = [f"user{index:03d}" for index in range(120)]
    business = SimpleNamespace(bk_biz_maintainer=members)
    get_app_by_id = mocker.Mock(return_value=business)
    get_notify_roles = mocker.Mock(return_value={"bk_biz_maintainer": "运维人员"})

    def fake_get_all_user(**kwargs):
        lookups = kwargs["exact_lookups"].split(",")
        return {"results": [{"username": name, "display_name": name.upper()} for name in lookups]}

    get_all_user = mocker.Mock(side_effect=fake_get_all_user)
    mocker.patch.object(
        front,
        "resource",
        SimpleNamespace(cc=SimpleNamespace(get_app_by_id=get_app_by_id, get_notify_roles=get_notify_roles)),
    )
    mocker.patch.object(front, "api", SimpleNamespace(bk_login=SimpleNamespace(get_all_user=get_all_user)))

    result = GetReceiverResource().perform_request({"bk_biz_id": 2})

    # 120 个成员按 50 一批拆成 3 批
    assert get_all_user.call_count == 3
    queried = set()
    for call in get_all_user.call_args_list:
        queried.update(call.kwargs["exact_lookups"].split(","))
    assert queried == set(members)

    group = result[0]["children"][0]
    assert len(group["members"]) == 120
    assert {"id": "user000", "display_name": "USER000"} in group["members"]
