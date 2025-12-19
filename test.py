# 在 Django shell 中运行的测试代码
# 使用方法: python manage.py shell
# 然后复制粘贴以下代码

import time
from metadata.resources.resources import QueryTimeSeriesScopeResource

# 初始化资源
resource = QueryTimeSeriesScopeResource()

# 准备测试数据
test_data = {
    "bk_tenant_id": "system",  # 根据实际情况修改
    "group_id": 1012,  # 根据实际情况修改为存在的 group_id
    # 可选参数
    # 'scope_ids': [1, 2, 3],  # 如果需要测试特定的 scope_ids
    # 'scope_name': '测试分组',  # 如果需要按名称过滤
}


# 测试单次请求响应时间
def test_single_request(data):
    """测试单次请求的响应时间"""
    start_time = time.time()
    try:
        result = resource.request(data)
        end_time = time.time()
        elapsed_time = (end_time - start_time) * 1000  # 转换为毫秒

        print("✓ 请求成功")
        print(f"响应时间: {elapsed_time:.2f} ms")
        print(f"返回结果数量: {len(result) if isinstance(result, list) else 'N/A'}")

        # 打印第一个元素
        if isinstance(result, list) and len(result) > 0:
            print("\n第一个元素内容:")
            print("-" * 60)
            import json

            print(json.dumps(result[0], indent=2, ensure_ascii=False))
            print("-" * 60)
        elif isinstance(result, list) and len(result) == 0:
            print("\n返回结果为空列表")

        return elapsed_time, result
    except Exception as e:
        end_time = time.time()
        elapsed_time = (end_time - start_time) * 1000
        print(f"✗ 请求失败: {str(e)}")
        print(f"失败耗时: {elapsed_time:.2f} ms")
        return elapsed_time, None


# 测试多次请求并计算平均响应时间
def test_multiple_requests(data, count=10):
    """测试多次请求并计算统计信息"""
    print(f"\n{'=' * 60}")
    print(f"开始测试 {count} 次请求...")
    print(f"{'=' * 60}\n")

    times = []
    success_count = 0

    for i in range(count):
        print(f"第 {i + 1}/{count} 次请求:")
        elapsed_time, result = test_single_request(data)
        times.append(elapsed_time)
        if result is not None:
            success_count += 1
        print()

    # 计算统计信息
    if times:
        avg_time = sum(times) / len(times)
        min_time = min(times)
        max_time = max(times)

        print(f"{'=' * 60}")
        print("测试统计结果:")
        print(f"{'=' * 60}")
        print(f"总请求次数: {count}")
        print(f"成功次数: {success_count}")
        print(f"失败次数: {count - success_count}")
        print(f"平均响应时间: {avg_time:.2f} ms")
        print(f"最快响应时间: {min_time:.2f} ms")
        print(f"最慢响应时间: {max_time:.2f} ms")
        print(f"{'=' * 60}\n")

        return {"avg": avg_time, "min": min_time, "max": max_time, "success_rate": success_count / count * 100}
    return None


# 测试不同参数组合的响应时间
def test_different_scenarios():
    """测试不同场景下的响应时间"""
    scenarios = [
        {
            "name": "基础查询（仅 group_id）",
            "data": {
                "bk_tenant_id": "default",
                "group_id": 1,
            },
        },
        {
            "name": "带 scope_ids 过滤",
            "data": {
                "bk_tenant_id": "default",
                "group_id": 1,
                "scope_ids": [1, 2],
            },
        },
        {
            "name": "带 scope_name 过滤",
            "data": {
                "bk_tenant_id": "default",
                "group_id": 1,
                "scope_name": "测试",
            },
        },
    ]

    results = {}
    for scenario in scenarios:
        print(f"\n{'#' * 60}")
        print(f"场景: {scenario['name']}")
        print(f"{'#' * 60}")
        elapsed_time, result = test_single_request(scenario["data"])
        results[scenario["name"]] = elapsed_time
        print()

    print(f"\n{'=' * 60}")
    print("不同场景响应时间对比:")
    print(f"{'=' * 60}")
    for name, time_ms in results.items():
        print(f"{name}: {time_ms:.2f} ms")
    print(f"{'=' * 60}\n")

    return results


# 执行测试
print("开始测试 QueryTimeSeriesScopeResource 响应时间\n")

# 1. 单次请求测试
# print("=" * 60)
# print("1. 单次请求测试")
# print("=" * 60)
# test_single_request(test_data)

# 2. 多次请求测试（可以根据需要调整次数）
stats = test_multiple_requests(test_data, count=10)

# 3. 不同场景测试（需要根据实际数据调整）
# scenario_results = test_different_scenarios()

print("\n测试完成！")
print("\n提示:")
print("- 如需测试多次请求，取消注释 test_multiple_requests 行")
print("- 如需测试不同场景，取消注释 test_different_scenarios 行")
print("- 请根据实际数据库中的数据修改 test_data 中的参数")
