"""
Tencent is pleased to support the open source community by making 蓝鲸智云 - 监控平台 (BlueKing - Monitor) available.
Copyright (C) 2017-2025 Tencent. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# dcgm(物理整卡)<-> qGPU/elastic(原生 gpu_*/container_*)双源兼容映射 —— 唯一真值源。
#
# 容器观测 GPU 场景目录(scenario/*.py)保持 source-blind,只声明原生指标名;本表把每个
# 原生"原始指标名"映射到 dcgm 等价表达式。查询层 gpu_or() 在叶子处产出
# `(原生{filter} or dcgm等价(filter))`,数据存在性自动决定走哪支(同集群同 dataid/VM,
# 缺席支为 VM 侧一次索引 miss,廉价)。
#
# 增删一个 GPU 指标 = 改 scenario/*.py 目录 + 本表一行;meta.py 生成逻辑零改
# (前提:新引用的 DCGM_FI_* 已在 chart dcgm ServiceMonitor 的 keep 白名单内)。
#
# 约束:dcgm 合成支必须锚定在某个 DCGM_FI_* 选择器上(乘 0 加常量),非 dcgm 集群该支为空,
# or 才能正确回退到原生支。


# ---- 合成原语:入参 filter_string,返回 promql 片段(纯字符串,无 Django 依赖)----


def _rename(dcgm_metric):
    """直接改名:dcgm 指标本身即原生语义(util/显存/温度/功耗)。"""
    return lambda fs: f"{dcgm_metric}{{{fs}}}"


def _fb_total():
    """整卡总显存 = USED + FREE + RESERVED(三段同标签逐卡相加),单位 MiB,与 elastic 一致。"""
    return lambda fs: (f"(DCGM_FI_DEV_FB_USED{{{fs}}} + DCGM_FI_DEV_FB_FREE{{{fs}}} + DCGM_FI_DEV_FB_RESERVED{{{fs}}})")


def _card_count():
    """整卡数量:dcgm 无 gpu_count,用每卡一条的 GPU_UTIL 计数合成,按 (bcs_cluster_id, node) 出数。"""
    return lambda fs: f"count by (bcs_cluster_id, node) (DCGM_FI_DEV_GPU_UTIL{{{fs}}})"


# ---- 映射表:原生原始指标名 -> dcgm 等价 ----
GPU_DCGM_EQUIV = {
    # capacity 容量场景(卡/节点级,与 dcgm 同为卡级设备遥测,对得最干净)
    "gpu_core_utilization_percentage": _rename("DCGM_FI_DEV_GPU_UTIL"),
    "gpu_mem_usage": _rename("DCGM_FI_DEV_FB_USED"),
    "gpu_mem_each_card": _fb_total(),
    "gpu_power_usage": _rename("DCGM_FI_DEV_POWER_USAGE"),
    "gpu_temprature": _rename("DCGM_FI_DEV_GPU_TEMP"),  # exporter 原始拼写,勿改
    "gpu_count": _card_count(),  # 仅 anomaly_count 掉卡判定引用(不经 tpl 叶子)
    # 注:tke_gpu 容器场景的 container_* 映射(整卡 request 常量/总显存/百分比)留待容器场景任务,
    # 届时连同 dcgm 侧 pod->pod_name 对齐一起加;此处不放,避免在 cluster 层提前激活、带 pod 对齐缺口。
}


def gpu_or(metric_name, filter_string):
    """叶子级双源合并:GPU 指标 -> (原生 or dcgm等价);非 GPU 指标原样返回。"""
    native = f"{metric_name}{{{filter_string}}}"
    equiv = GPU_DCGM_EQUIV.get(metric_name)
    if equiv is None:
        return native
    return f"({native} or {equiv(filter_string)})"
