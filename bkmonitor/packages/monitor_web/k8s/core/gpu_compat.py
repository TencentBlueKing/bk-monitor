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


def _mem_ratio():
    """整卡显存使用率% = 卡已用 / 整卡总显存 * 100(分子分母同标签逐卡相除),对标 container_mem_utilization_percentage。"""
    return lambda fs: (
        f"(DCGM_FI_DEV_FB_USED{{{fs}}} "
        f"/ (DCGM_FI_DEV_FB_USED{{{fs}}} + DCGM_FI_DEV_FB_FREE{{{fs}}} + DCGM_FI_DEV_FB_RESERVED{{{fs}}}) * 100)"
    )


def _const_oncard(value):
    """整卡 request 常量:容器独占整卡 -> 申请算力恒为 value%。乘 0 锚定在 GPU_UTIL 选择器上,
    非 dcgm 集群该支为空(or 才能正确回退到原生支)。"""
    return lambda fs: f"(DCGM_FI_DEV_GPU_UTIL{{{fs}}} * 0 + {value})"


def _attributed(fn):
    """容器场景护栏:dcgm 整卡遥测对所有物理卡都有数据(含空闲/未分配卡),而原生 container_* 只对真实容器存在。
    给 dcgm 支补 pod_name!="" —— 只取已归属到 pod 的卡。否则无 workload-join 的 namespace/cluster 汇总会把空闲卡
    (其 namespace 落到 dcgm-exporter 自身所在的 kube-system)算进来,产出原生从不产出的伪造行。
    原生支不受影响(container_* 必带 pod_name,加该约束是 no-op);capacity 的 gpu_* 不用本护栏(整卡场景空闲卡应计入)。
    v3.6.180 relabel 未部署时已归属卡只有原生 pod 标签(无 pod_name)-> 该支为空 -> or 回退原生(亦空)-> 留白,符合预期。"""
    return lambda fs: fn(f'{fs},pod_name!=""')


# ---- 映射表:原生原始指标名 -> dcgm 等价 ----
GPU_DCGM_EQUIV = {
    # capacity 容量场景(卡/节点级,与 dcgm 同为卡级设备遥测,对得最干净)
    "gpu_core_utilization_percentage": _rename("DCGM_FI_DEV_GPU_UTIL"),
    "gpu_mem_usage": _rename("DCGM_FI_DEV_FB_USED"),
    "gpu_mem_each_card": _fb_total(),
    "gpu_power_usage": _rename("DCGM_FI_DEV_POWER_USAGE"),
    "gpu_temprature": _rename("DCGM_FI_DEV_GPU_TEMP"),  # exporter 原始拼写,勿改
    "gpu_count": _card_count(),  # 仅 anomaly_count 掉卡判定引用(不经 tpl 叶子)
    # tke_gpu 容器场景(整卡语义:dcgm 物理整卡 = 容器独占该卡 -> used 取卡级遥测,request 取整卡常量)。
    # 依赖 chart dcgm ServiceMonitor 自 v3.6.180 起把 pod->pod_name / container->container_name relabel,
    # 使 dcgm 容器归属维度与原生 container_* 对齐;namespace 由 dcgm pod-resources 映射原生带出。
    # 全部用 _attributed 包裹:只取已归属到 pod 的卡(详见 _attributed),否则空闲卡会漏进 namespace/cluster 汇总。
    # 注 1:container_gpu_utilization 与 container_core_utilization_percentage 同映射到 GPU_UTIL —— 整卡申请下
    #       "实际算力%"与"用量占申请%"重合,非笔误。
    # 注 2:显存单位沿用 capacity(#11125/#11111)同一口径(FB_* 视为与原生 elastic 同单位);tke_gpu.py 里
    #       "原始数据为MB"为旧注释,FB_* 实为 MiB,二者差约 4.86%,与 capacity 取舍一致,不在本表单独换算。
    # 注 3:多卡容器下百分比列(core/mem util%)按 sum 跨卡相加可能 >100%,与原生跨容器 sum 同源行为(非本次回归);
    #       1 卡/容器(整卡常见场景)精确正确。
    "container_gpu_utilization": _attributed(_rename("DCGM_FI_DEV_GPU_UTIL")),
    "container_gpu_memory_total": _attributed(_rename("DCGM_FI_DEV_FB_USED")),
    "container_core_utilization_percentage": _attributed(_rename("DCGM_FI_DEV_GPU_UTIL")),
    "container_mem_utilization_percentage": _attributed(_mem_ratio()),
    "container_request_gpu_memory": _attributed(_fb_total()),
    "container_request_gpu_utilization": _attributed(_const_oncard(100)),
}


def gpu_or(metric_name, filter_string):
    """叶子级双源合并:GPU 指标 -> (原生 or dcgm等价);非 GPU 指标原样返回。"""
    native = f"{metric_name}{{{filter_string}}}"
    equiv = GPU_DCGM_EQUIV.get(metric_name)
    if equiv is None:
        return native
    return f"({native} or {equiv(filter_string)})"
