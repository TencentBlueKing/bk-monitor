from bk_monitor_base.space import SpaceTypeEnum


def test_SpaceTypeEnum():
    """
    空间类型枚举测试
    """

    assert SpaceTypeEnum.BKCC.value == "bkcc"
    assert SpaceTypeEnum.BKCI.value == "bkci"
    assert SpaceTypeEnum.BKSAAS.value == "bksaas"
