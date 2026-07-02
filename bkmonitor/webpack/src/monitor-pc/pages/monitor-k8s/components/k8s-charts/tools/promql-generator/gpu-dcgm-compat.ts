/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

/**
 * GPU dcgm 双源兼容映射 —— 前端镜像。
 *
 * 唯一真值源在后端 `packages/monitor_web/k8s/core/gpu_compat.py`(表格/后端驱动查询走它);本模块是它的
 * 前端图表侧镜像,产出与后端逐字一致的双源 PromQL。**两处任一改动须同步**(指标映射、dcgm 表达式、互斥逻辑)。
 *
 * 设计:容量/容器 GPU 生成器保持 source-blind,只声明原生指标名;本表把每个原生指标名映射到 dcgm 等价表达式。
 * gpuOr() 在叶子处产出跨 schema 互斥的 `(原生 or ((dcgm) unless on() (原生)))`:迁移期一个集群可能同时跑
 * elastic/qGPU 与 dcgm-exporter,两者 label set 不同,裸 or 不互斥会被外层 sum 双算;unless on()(空 label 集
 * 匹配)做集群级互斥,本 filter 范围内只要有原生数据就整体抑制 dcgm 支,确保至多一支贡献。单源时与裸 or 等价。
 *
 * 与后端唯一差异:前端选择器可带 `$time_shift`(offset 占位符)后缀,经 suffix 参数注入每个选择器;capacity
 * 场景把 $time_shift 放在外层 last_over_time(...[$interval:] $time_shift) 子查询上,故 suffix 置空。
 */

/** 单个带可选后缀(如 ` $time_shift`)的 PromQL 选择器。 */
const sel = (metric: string, filter: string, suffix: string): string => `${metric}{${filter}}${suffix}`;

type DcgmBuilder = (filter: string, suffix: string) => string;

// dcgm 直接改名:dcgm 指标本身即原生语义(算力利用率 / 显存 / 温度 / 功耗)
const rename =
  (dcgm: string): DcgmBuilder =>
  (f, s) =>
    sel(dcgm, f, s);

// 整卡总显存 = USED + FREE + RESERVED(逐卡同标签相加,单位 MiB,与 elastic 一致)
const fbTotal = (): DcgmBuilder => (f, s) =>
  `(${sel('DCGM_FI_DEV_FB_USED', f, s)} + ${sel('DCGM_FI_DEV_FB_FREE', f, s)} + ${sel('DCGM_FI_DEV_FB_RESERVED', f, s)})`;

// 整卡数量:dcgm 无 gpu_count,用每卡一条的 GPU_UTIL 计数合成(仅 anomaly_count 掉卡判定引用)
const cardCount = (): DcgmBuilder => (f, s) => `count by (bcs_cluster_id, node) (${sel('DCGM_FI_DEV_GPU_UTIL', f, s)})`;

// 整卡显存使用率% = 卡已用 / 整卡总显存 * 100
const memRatio = (): DcgmBuilder => (f, s) =>
  `(${sel('DCGM_FI_DEV_FB_USED', f, s)} / (${sel('DCGM_FI_DEV_FB_USED', f, s)} + ${sel('DCGM_FI_DEV_FB_FREE', f, s)} + ${sel('DCGM_FI_DEV_FB_RESERVED', f, s)}) * 100)`;

// 整卡 request 常量:容器独占整卡 -> 申请算力恒为 value%(乘 0 锚定 GPU_UTIL,非 dcgm 集群该支为空)
const constOncard =
  (value: number): DcgmBuilder =>
  (f, s) =>
    `(${sel('DCGM_FI_DEV_GPU_UTIL', f, s)} * 0 + ${value})`;

// 容器场景护栏:dcgm 支补 pod_name!="",只取已归属到 pod 的卡(排除空闲卡漏进无 workload-join 的 namespace/cluster 汇总)
const attributed =
  (builder: DcgmBuilder): DcgmBuilder =>
  (f, s) =>
    builder(`${f},pod_name!=""`, s);

const GPU_DCGM_EQUIV: Record<string, DcgmBuilder> = {
  // capacity 容量场景(卡/节点级,与 dcgm 同为卡级设备遥测)
  gpu_core_utilization_percentage: rename('DCGM_FI_DEV_GPU_UTIL'),
  gpu_mem_usage: rename('DCGM_FI_DEV_FB_USED'),
  gpu_mem_each_card: fbTotal(),
  gpu_power_usage: rename('DCGM_FI_DEV_POWER_USAGE'),
  gpu_temprature: rename('DCGM_FI_DEV_GPU_TEMP'), // exporter 原始拼写,勿改
  gpu_count: cardCount(),
  // tke_gpu 容器场景(整卡语义:容器独占整卡 -> used 取卡级遥测,request 取整卡常量;全部 attributed 排空闲卡)
  container_gpu_utilization: attributed(rename('DCGM_FI_DEV_GPU_UTIL')),
  container_gpu_memory_total: attributed(rename('DCGM_FI_DEV_FB_USED')),
  container_core_utilization_percentage: attributed(rename('DCGM_FI_DEV_GPU_UTIL')),
  container_mem_utilization_percentage: attributed(memRatio()),
  container_request_gpu_memory: attributed(fbTotal()),
  container_request_gpu_utilization: attributed(constOncard(100)),
};

/**
 * 叶子级双源合并:GPU 指标 -> 跨 schema 互斥的 `(原生 or ((dcgm) unless on() (原生)))`;非 GPU 指标原样返回。
 * 与后端 gpu_compat.gpu_or 逐字对齐。
 * @param metric 原生指标名
 * @param filter PromQL 选择器内的过滤串(不含花括号)
 * @param suffix 选择器后缀(如 ` $time_shift`;capacity 场景置空,offset 由外层子查询承载)
 */
export function gpuOr(metric: string, filter: string, suffix = ''): string {
  const native = sel(metric, filter, suffix);
  const equiv = GPU_DCGM_EQUIV[metric];
  if (!equiv) return native;
  return `(${native} or ((${equiv(filter, suffix)}) unless on() (${native})))`;
}
