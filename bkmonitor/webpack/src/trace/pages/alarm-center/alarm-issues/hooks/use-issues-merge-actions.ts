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

import { type Ref, computed } from 'vue';

import { useI18n } from 'vue-i18n';

import type { IssueItem } from '../typing';

/** useIssuesMergeActions 入参类型 */
interface UseIssuesMergeActionsOptions {
  /** 表格数据 */
  data: Ref<IssueItem[]>;
  /** 当前选中的行 key 数组 */
  selectedRowKeys: Ref<string[]>;
}

/**
 * @description Issues 合并/拆分操作 hook
 * 封装 Issue 合并/拆分操作的状态判定与事件处理，消除多消费端重复代码。
 * - 合并：基于批量选择，提供禁用判定、tooltip 提示及点击处理
 * - 拆分：基于行级操作，提供点击处理
 *
 * 注意：hasSelection 不由此 hook 暴露 —— 它是 toolbar 级别通用状态（批量操作/导出共用），
 * 各消费端保留一行 `computed(() => selectedRowKeys.value.length > 0)` 即可。
 * 若后续需要由 hook 统一提供，需评估与消费端本地 hasSelection 的来源冲突。
 *
 * @param {UseIssuesMergeActionsOptions} options - 依赖注入
 * @returns 合并/拆分相关的计算属性与事件处理
 */
export function useIssuesMergeActions(options: UseIssuesMergeActionsOptions) {
  const { data, selectedRowKeys } = options;
  const { t } = useI18n();

  /** 选中行中主 Issue 的数量 */
  const mainIssueCount = computed(() => {
    const selectedSet = new Set(selectedRowKeys.value);
    return data.value.filter(item => selectedSet.has(item.id) && item.merge_status?.role === 'main').length;
  });

  /** 合并按钮是否禁用 */
  const mergeDisabled = computed(() => {
    const hasSelection = selectedRowKeys.value.length > 0;
    if (!hasSelection || selectedRowKeys.value.length < 2) return true;
    return mainIssueCount.value > 1;
  });

  /** 合并按钮禁用时的 tooltip 提示 */
  const mergeDisabledTip = computed(() => {
    const hasSelection = selectedRowKeys.value.length > 0;
    if (!hasSelection) return t('请先选择 Issue');
    if (selectedRowKeys.value.length < 2) return t('请至少选择 2 个 Issue');
    if (mainIssueCount.value > 1) return t('主 Issue 不支持再并入其他主 Issue');
    return '';
  });

  /**
   * @description 处理合并按钮点击。
   * 当前为 console.log 占位 —— 待合并弹框实现后，需评估是否需要在 hook 内部
   * 维护弹框可见性等状态。data + selectedRowKeys 已足够构建弹框参数，
   * 后续可直接在此函数内打开合并弹框或触发合并流程。
   */
  const handleIssuesMergeClick = () => {
    console.log('merge dialog', selectedRowKeys.value);
  };

  /**
   * @description 处理拆分按钮点击。
   * 当前为 console.log 占位 —— 待拆分弹框实现后，需评估是否需要在 hook 内部
   * 维护弹框可见性等状态。row 参数已包含构建拆分弹框所需的全部信息，
   * 后续可直接在此函数内打开拆分弹框或触发拆分流程。
   * @param {IssueItem} row - 被拆分的 Issue 行数据
   */
  const handleIssuesSplitClick = (row: IssueItem) => {
    console.log('split dialog', row.id);
  };

  return {
    mergeDisabled,
    mergeDisabledTip,
    handleIssuesMergeClick,
    handleIssuesSplitClick,
  };
}
