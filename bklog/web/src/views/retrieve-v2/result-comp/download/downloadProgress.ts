/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
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
 * 日志下载进度计算工具
 * 采用「10 秒轮询真实数据 + 前端每 1 秒模拟增长」的方案
 */

/** 基础增长量：10 秒增长 20000 条 */
const BASE_GROWTH = 20000;

/** 进度上限：模拟增长最多到 99% */
const PROGRESS_CEILING = 0.99;

/** 单位数组 */
const UNITS = ['', 'K', 'M', 'G'];

/**
 * 计算单任务进度，直接更新 task 上的 exported_count 和 progressPercent
 * 每秒增长量 = currentGrowth / 10
 * 注意：exported_count 不能超过 export_total_count * 0.99
 *
 * @param task - 带进度的任务对象（会被直接修改）
 */
export function calculateProgress(task: any) {
  if (!task.export_total_count || task.export_total_count <= 0) return;

  // 每秒增长量
  const growthPerSecond = Math.max((task.currentGrowth || BASE_GROWTH) / 10, 0);
  const maxExportedCount = Math.floor(task.export_total_count * PROGRESS_CEILING);

  // 增长 exported_count，但不超过 99% 上限
  task.exported_count = Math.min(
    Math.max(task.exported_count, 0) + growthPerSecond,
    maxExportedCount,
  );

  // 同步计算百分比
  task.progressPercent = calculateProgressPercent(task.exported_count, task.export_total_count);
}

/**
 * 轮询回来后修正增长量
 * 根据真实值与当前显示值的误差，修正下次增长量
 *
 * @param task - 带进度的任务对象（会被直接修改）
 * @param realExportedCount - 接口返回的真实已下载条数
 * @param baseGrowth - 基础增长量，默认 20000
 */
export function adjustGrowthAfterPoll(task: any, realExportedCount: number, baseGrowth = BASE_GROWTH) {
  // 计算误差：真实值 - 当前显示值
  const error = realExportedCount - task.exported_count;

  // 修正下次增长量 = 基础增长量 + 误差，确保不为负
  const nextGrowth = Math.max(baseGrowth + error, 0);
  task.currentGrowth = nextGrowth;

  // 确保不超过 99% 上限
  const maxExportedCount = Math.floor(task.export_total_count * PROGRESS_CEILING);
  if (task.exported_count > maxExportedCount) {
    task.exported_count = maxExportedCount;
  }

  // 同步计算百分比
  task.progressPercent = calculateProgressPercent(task.exported_count, task.export_total_count);
}

/**
 * 计算百分比进度
 *
 * @param exportedCount - 当前已下载条数
 * @param totalCount - 总条数
 * @returns 百分比整数（0-100）
 */
export function calculateProgressPercent(exportedCount: number, totalCount: number) {
  if (!totalCount || totalCount <= 0) return 0;
  return Math.floor((exportedCount / totalCount) * 100);
}

/**
 * 数字格式化（K/M/G）
 * 供使用方组装显示文本时使用
 *
 * @param num - 要格式化的数字
 * @returns 格式化后的字符串，如 "567M"
 */
export function formatNumber(num: number | null | undefined) {
  if (num === undefined || num === null) return '--';

  let unitIndex = 0;
  let value = num;

  while (value >= 1000 && unitIndex < UNITS.length - 1) {
    value /= 1000;
    unitIndex++;
  }

  value = Number(value.toFixed(1));

  // 四舍五入后达到1000，则升级单位
  if (value >= 1000 && unitIndex < UNITS.length - 1) {
    value = 1;
    unitIndex++;
  }

  return `${value}${UNITS[unitIndex]}`;
}
