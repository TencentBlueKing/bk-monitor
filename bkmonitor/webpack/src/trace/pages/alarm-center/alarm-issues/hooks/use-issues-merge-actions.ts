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

import { type Ref, computed, shallowRef } from 'vue';

import { useI18n } from 'vue-i18n';

import type { SidesliderType } from '../issues-merge-split/issues-merge-split-sideslider';
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

  // ===================== 合并/拆分侧栏状态 =====================

  /** 侧栏是否可见 */
  const mergeSplitShow = shallowRef(false);

  /** 侧栏类型 */
  const mergeSplitType = shallowRef<SidesliderType>('merge');

  /** 侧栏传入的 Issue 列表 */
  const mergeSplitIssues = shallowRef<IssueItem[]>([]);

  // ===================== 合并按钮禁用判定 =====================

  /** 选中行中主 Issue 的数量 */
  const mainIssueCount = computed(() => {
    const selectedSet = new Set(selectedRowKeys.value);
    return data.value.filter(item => selectedSet.has(item.id) && item.merge_status?.role === 'main').length;
  });

  /** 选中行中是否包含不同空间的 Issue */
  const hasMultipleSpaces = computed(() => {
    const selectedSet = new Set(selectedRowKeys.value);
    const bizIds = new Set(data.value.filter(item => selectedSet.has(item.id)).map(item => item.bk_biz_id));
    return bizIds.size > 1;
  });

  /** 合并按钮是否禁用 */
  const mergeDisabled = computed(() => {
    const hasSelection = selectedRowKeys.value.length > 0;
    if (!hasSelection || selectedRowKeys.value.length < 2) return true;
    if (hasMultipleSpaces.value) return true;
    return mainIssueCount.value > 1;
  });

  /** 合并按钮禁用时的 tooltip 提示 */
  const mergeDisabledTip = computed(() => {
    const hasSelection = selectedRowKeys.value.length > 0;
    if (!hasSelection) return t('请先选择 Issue');
    if (selectedRowKeys.value.length < 2) return t('请至少选择 2 个 Issue');
    if (hasMultipleSpaces.value) return t('不支持跨空间合并 Issue');
    if (mainIssueCount.value > 1) return t('主 Issue 不支持再并入其他主 Issue');
    return '';
  });

  /**
   * @description 处理合并按钮点击。
   * 将选中行对应的 Issue 数据填入侧栏，以 merge 模式打开。
   */
  const handleIssuesMergeClick = () => {
    const selectedSet = new Set(selectedRowKeys.value);
    mergeSplitIssues.value = data.value.filter(item => selectedSet.has(item.id));
    mergeSplitType.value = 'merge';
    mergeSplitShow.value = true;
  };

  /**
   * @description 处理拆分按钮点击。
   * 将目标行 Issue 数据填入侧栏，以 split 模式打开。
   * @param {IssueItem} row - 被拆分的 Issue 行数据
   */
  const handleIssuesSplitClick = (row: IssueItem) => {
    mergeSplitIssues.value = [row];
    mergeSplitType.value = 'split';
    mergeSplitShow.value = true;
  };

  /**
   * @description 处理侧栏显示状态变更（v-model:show 回调）
   * @param {boolean} isShow - 目标显示状态
   */
  const handleMergeSplitShowChange = (isShow: boolean) => {
    mergeSplitShow.value = isShow;
    if (!isShow) {
      mergeSplitIssues.value = [];
    }
  };

  return {
    mergeDisabled,
    mergeDisabledTip,
    mergeSplitShow,
    mergeSplitType,
    mergeSplitIssues,
    handleIssuesMergeClick,
    handleIssuesSplitClick,
    handleMergeSplitShowChange,
  };
}
