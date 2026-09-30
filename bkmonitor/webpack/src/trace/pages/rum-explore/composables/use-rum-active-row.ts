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
 * THE WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { type MaybeRef, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';

/** 高亮行 hook 配置项 */
export interface IUseRumActiveRowOptions {
  /** 高亮行锁定：为 true 时忽略表格回传的行变化（events 抽屉展开期间点行不切换高亮） */
  locked?: MaybeRef<boolean>;
}

/**
 * @description 主表高亮行 key 管理（对应 RumExploreTable 的 activeRowKey）。行点击 / 键盘高亮由表格回传，
 * events 列点击由抽屉入口指定，两者写入同一个受控数据源，供表格行高亮与 events 抽屉、后续 span 详情侧弹联动。
 * @param {MaybeRef<number | string>} resetSignal 结果集重置信号，变化时清除高亮行
 * @param {IUseRumActiveRowOptions} options 配置项，见 IUseRumActiveRowOptions
 * @returns {object} 高亮行状态与操作：activeRowKey / setActiveRowKey / handleActiveRowChange
 */
export function useRumActiveRow(resetSignal: MaybeRef<number | string>, options: IUseRumActiveRowOptions = {}) {
  const { locked } = options;
  /** 当前高亮行 key，空串表示无高亮行 */
  const activeRowKey = shallowRef('');

  /**
   * @description 指定高亮行（events 列点击等由页面主动触发的场景）
   * @param {string} key 行 key，即该行的 span_id
   * @returns {void}
   */
  function setActiveRowKey(key: string) {
    activeRowKey.value = key || '';
  }

  /**
   * @description 表格回传的行高亮变化：锁定期间（如 events 抽屉展开）忽略，点行不切换高亮
   * @param {Array<number | string>} rowKeys 表格当前高亮的行 key 列表，取首个作为单一高亮行
   * @returns {void}
   */
  function handleActiveRowChange(rowKeys: Array<number | string>) {
    if (get(locked)) return;
    setActiveRowKey(rowKeys?.[0] as string);
  }

  /** 新检索后清除高亮行：结果集被替换后旧 key 已不在列表中，与 events 抽屉的自动收起同源同信号 */
  watch(
    () => get(resetSignal),
    () => setActiveRowKey('')
  );

  return {
    activeRowKey,
    setActiveRowKey,
    handleActiveRowChange,
  };
}
