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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
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

import { type Ref, shallowRef, watch } from 'vue';

import { fetchRecentAssignees } from '../services/issues-operations';

import type { IssueIdentifier } from '../typing';

/** useRecentAssignees 配置选项 */
interface UseRecentAssigneesOptions {
  /** 外部受控的弹窗显隐状态 */
  isShow: Ref<boolean>;
  /** 关联的 Issue 标识数据，用于提取 bk_biz_ids */
  issuesData: Ref<IssueIdentifier[]>;
  /** 统计最近 N 天内的指派记录，范围 1~30，默认 7 */
  recentDays?: number;
}

/**
 * @description 最近指派负责人数据管理 hook。
 *   弹窗打开时自动获取，关闭时自动清空。
 * @param {UseRecentAssigneesOptions} options - 配置选项
 * @returns {{ recentUserIds }} 最近指派的负责人用户名列表
 */
export const useRecentAssignees = (options: UseRecentAssigneesOptions) => {
  const { isShow, issuesData, recentDays = 7 } = options;

  /** 最近指派的负责人用户名列表 */
  const recentUserIds = shallowRef<string[]>([]);

  /**
   * @description 加载最近指派的负责人列表
   * @returns {Promise<void>}
   */
  const loadRecentAssignees = async () => {
    if (!issuesData.value?.length) {
      recentUserIds.value = [];
      return;
    }
    const bkBizIds = [...new Set(issuesData.value.map(item => item.bk_biz_id))];
    recentUserIds.value = await fetchRecentAssignees({
      bk_biz_ids: bkBizIds,
      recent_days: recentDays,
    });
  };

  // 弹窗打开时获取数据，关闭时清空
  watch(isShow, val => {
    if (val) {
      loadRecentAssignees();
    } else {
      recentUserIds.value = [];
    }
  });

  return {
    recentUserIds,
  };
};
