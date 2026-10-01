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
import { type MaybeRef, shallowRef, watch } from 'vue';

import { get } from '@vueuse/core';

import type { IRumSpanRecord } from '../typings';

/** 打开抽屉的触发目标：被点击的 events 列键与该行数据 */
export interface IRumEventsTarget {
  colKey: string;
  row: IRumSpanRecord;
}

/** 抽屉 hook 配置项 */
export interface IUseRumEventsDrawerOptions {
  /** 抽屉收起时的回调（手动关闭与自动收起都会触发），供页面层同步清除联动状态 */
  onClose?: () => void;
}

/**
 * @description events 抽屉状态管理（对应 RumEventsDrawer）。状态放在页面层而非表格内：抽屉贴结果面板底部、不随检索视图滚动，而表格在滚动容器内；触发源只有主表 events.* 列，抽屉内部亦只展示 events.* 字段。
 * @param {MaybeRef<number | string>} resetSignal 结果集重置信号，变化时自动收起抽屉
 * @param {IUseRumEventsDrawerOptions} options 配置项，见 IUseRumEventsDrawerOptions
 * @returns {object} 抽屉状态与操作：row / colKey / show / handleEventsCellClick / closeDrawer
 */
export function useRumEventsDrawer(resetSignal: MaybeRef<number | string>, options: IUseRumEventsDrawerOptions = {}) {
  const { onClose } = options;
  /** 触发抽屉的行数据，null 表示尚未打开过（决定抽屉是否挂载） */
  const row = shallowRef<IRumSpanRecord>(null);
  /** 当前列键，抽屉中该列整列高亮，与 row 成对赋值 */
  const colKey = shallowRef('');
  /** 抽屉显隐，与 row 分开控制：关闭只置显隐，数据保留到下次打开，否则离场动画期间内容会闪成空态 */
  const show = shallowRef(false);

  /**
   * @description 打开抽屉：记录被点击单元格的行数据与列键，并置为显示
   * @param {IRumEventsTarget} target 被点击的 events 单元格（列键 + 行数据）
   * @returns {void}
   */
  function handleEventsCellClick(target: IRumEventsTarget) {
    row.value = target.row;
    colKey.value = target.colKey;
    show.value = true;
  }

  /**
   * @description 关闭抽屉：只置显隐为 false，行数据保留以规避离场动画期间的空态闪烁；同时回调通知页面层
   * @returns {void}
   */
  function closeDrawer() {
    show.value = false;
    onClose?.();
  }

  /**
   * 新检索后收起抽屉：resetSignal 在查询条件 / 排序 / 时间范围 / 刷新变化时重新生成，
   * 换应用与换视角同样会改写 commonParams，故一个信号即可覆盖全部「结果集被替换」的场景。
   */
  watch(() => get(resetSignal), closeDrawer);

  return {
    row,
    colKey,
    show,
    handleEventsCellClick,
    closeDrawer,
  };
}
