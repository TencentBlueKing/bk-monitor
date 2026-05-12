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
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { onBeforeUnmount, shallowRef, watch } from 'vue';
import type { MaybeRef } from 'vue';

import { get } from '@vueuse/core';
import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { isEllipsisActiveMultiLine } from '../../../trace-explore/components/trace-explore-table/utils/dom-helper';
import type { BaseTableColumn } from '../../../trace-explore/components/trace-explore-table/typing';
import type { IDataSamplingItem } from '../../typings';
import type { SlotReturnValue } from 'tdesign-vue-next';

/** useSamplingColumnsRenderer 入参：采样表格交互处理函数 */
export interface SamplingColumnsRendererCtx {
  /** 已展开行索引集合 */
  collapseRowIndexes: MaybeRef<number[]>;
  /** 采样数据列表 */
  samplingList: MaybeRef<IDataSamplingItem[]>;
  /** 复制日志事件触发 */
  copyEmit: (log: IDataSamplingItem['raw_log']) => void;
  /** 切换展开/收起 */
  handleCollapse: (index: number) => void;
  /** 查看详情事件触发 */
  viewDetailEmit: (log: IDataSamplingItem['raw_log']) => void;
}

/**
 * @description 数据采样表格列渲染器 hook，负责将静态列配置与各列的自定义渲染逻辑合并
 * @param {SamplingColumnsRendererCtx} rendererCtx - 交互处理函数（展开/收起、复制、查看详情）
 * @returns {{ transformColumns: (columns: BaseTableColumn[]) => BaseTableColumn[] }} 列转换函数
 */
export const useSamplingColumnsRenderer = (rendererCtx: SamplingColumnsRendererCtx) => {
  const { samplingList, collapseRowIndexes, handleCollapse, copyEmit, viewDetailEmit } = rendererCtx;
  const { t } = useI18n();
  /** 内容区域发生实际溢出的行索引集合（垂直或水平方向） */
  const overflowRowIndexes = shallowRef<Set<number>>(new Set());
  /** text-log-main 元素与其 ResizeObserver + 行索引元数据映射 */
  const logMainResizeObserverMap = new Map<HTMLElement, { observer: ResizeObserver; rowIndex: number }>();

  /**
   * @description 通过行对象引用获取当前行索引，不依赖额外唯一键
   * @param {IDataSamplingItem} row - 当前行数据
   * @returns {number} 行索引；未命中返回 -1
   */
  const getSamplingRowIndex = (row: IDataSamplingItem): number => {
    return get(samplingList).indexOf(row);
  };

  /**
   * @description 序号列渲染（通过当前行在列表中的索引 + 1）
   * @param {IDataSamplingItem} row - 当前行数据
   * @param {unknown} _column - 列配置
   * @param {{ getRowId: (row: IDataSamplingItem) => string }} _renderCtx - 渲染上下文（参数占位）
   * @returns {SlotReturnValue} 序号列 JSX
   */
  const renderIndexCell = (
    row: IDataSamplingItem,
    _column: unknown,
    _renderCtx: { getRowId: (row: IDataSamplingItem) => string }
  ): SlotReturnValue => {
    const rowIndex = getSamplingRowIndex(row);
    return (<span>{rowIndex + 1}</span>) as unknown as SlotReturnValue;
  };

  /**
   * @description 更新指定行的溢出状态
   * @param {number} rowIndex - 当前行索引
   * @param {boolean} isOverflow - 是否发生溢出
   * @returns {void}
   */
  const setOverflowRowState = (rowIndex: number, isOverflow: boolean): void => {
    const nextOverflowRowIndexes = new Set(overflowRowIndexes.value);
    const hasOverflow = nextOverflowRowIndexes.has(rowIndex);
    if (isOverflow && !hasOverflow) {
      nextOverflowRowIndexes.add(rowIndex);
      overflowRowIndexes.value = nextOverflowRowIndexes;
      return;
    }
    if (!isOverflow && hasOverflow) {
      nextOverflowRowIndexes.delete(rowIndex);
      overflowRowIndexes.value = nextOverflowRowIndexes;
    }
  };

  /**
   * @description 检测 text-log-main 是否发生多行垂直溢出，并同步按钮显隐状态
   * @param {HTMLElement} element - text-log-main 容器元素
   * @param {number} rowIndex - 当前行索引
   * @returns {void}
   */
  const detectLogMainOverflow = (element: HTMLElement, rowIndex: number): void => {
    const { isEllipsisActive } = isEllipsisActiveMultiLine(element);
    setOverflowRowState(rowIndex, isEllipsisActive);
  };

  /**
   * @description 注册 text-log-main 元素并监听尺寸变化，动态更新溢出状态
   * @param {HTMLElement | null} element - text-log-main 容器元素
   * @param {number} rowIndex - 当前行索引
   * @returns {void}
   */
  const registerLogMainElement = (element: HTMLElement | null, rowIndex: number): void => {
    if (!element) {
      return;
    }

    detectLogMainOverflow(element, rowIndex);

    const observerMeta = logMainResizeObserverMap.get(element);
    if (observerMeta?.rowIndex === rowIndex) {
      return;
    }

    observerMeta?.observer.disconnect();

    const resizeObserver = new ResizeObserver(() => {
      detectLogMainOverflow(element, rowIndex);
    });

    resizeObserver.observe(element);
    logMainResizeObserverMap.set(element, {
      observer: resizeObserver,
      rowIndex,
    });
  };

  watch(
    () => get(samplingList),
    () => {
      overflowRowIndexes.value = new Set();
      for (const observerMeta of logMainResizeObserverMap.values()) {
        observerMeta.observer.disconnect();
      }
      logMainResizeObserverMap.clear();
    }
  );

  onBeforeUnmount(() => {
    for (const observerMeta of logMainResizeObserverMap.values()) {
      observerMeta.observer.disconnect();
    }
    logMainResizeObserverMap.clear();
  });

  /**
   * @description 原始数据列渲染（按实际溢出动态显示展开/收起按钮，点击文本查看详情）
   * @param {IDataSamplingItem} row - 当前行数据
   * @returns {SlotReturnValue} 原始数据列 JSX
   */
  const renderRawLogCell = (
    row: IDataSamplingItem,
    _column: unknown,
    _renderCtx: { getRowId: (row: IDataSamplingItem) => string }
  ): SlotReturnValue => {
    const rowIndex = getSamplingRowIndex(row);
    const isExpanded = rowIndex > -1 && get(collapseRowIndexes).includes(rowIndex);
    const shouldShowCollapseBtn = rowIndex > -1 && (isExpanded || overflowRowIndexes.value.has(rowIndex));

    return (
      <div class={['text-log-wrap', { 'is-expanded': isExpanded }]}>
        <div
          class='text-log-main'
          ref={element => {
            if (rowIndex > -1) {
              registerLogMainElement(element as HTMLElement | null, rowIndex);
            }
          }}
        >
          <span
            class='log-text'
            onClick={() => viewDetailEmit(row.raw_log)}
          >
            {JSON.stringify(row.raw_log)}
          </span>
        </div>
        {shouldShowCollapseBtn && (
          <span
            class='collapse-btn'
            onClick={() => handleCollapse(rowIndex)}
          >
            {isExpanded ? t('收起') : t('展开全部')}
          </span>
        )}
      </div>
    ) as unknown as SlotReturnValue;
  };

  /**
   * @description 操作列渲染（复制按钮 + 查看上报数据按钮）
   * @param {IDataSamplingItem} row - 当前行数据
   * @returns {SlotReturnValue} 操作列 JSX
   */
  const renderOperationCell = (row: IDataSamplingItem): SlotReturnValue => {
    const log = row.raw_log;
    return (
      <div class='operation-cell'>
        <Button
          class='operation-btn'
          theme='primary'
          text
          onClick={() => copyEmit(log)}
        >
          {t('复制')}
        </Button>
        <Button
          class='operation-btn'
          theme='primary'
          text
          onClick={() => viewDetailEmit(log)}
        >
          {t('查看上报数据')}
        </Button>
      </div>
    ) as unknown as SlotReturnValue;
  };

  /** 列渲染配置映射表：按 colKey 定义各列的 cellRenderer 等渲染配置 */
  const columnsRendererMap: Record<string, Partial<BaseTableColumn>> = {
    index: { cellRenderer: renderIndexCell },
    raw_log: { cellRenderer: renderRawLogCell },
    operations: { cellRenderer: renderOperationCell },
  };

  /**
   * @description 将外部静态列配置与 columnsRendererMap 中的渲染配置按 colKey 合并，生成完整列定义
   * @param {BaseTableColumn[]} columns - 外部传入的静态列配置
   * @returns {BaseTableColumn[]} 合并渲染配置后的完整列定义数组
   */
  const transformColumns = (columns: BaseTableColumn[]): BaseTableColumn[] => {
    return columns.map(col => {
      const renderer = columnsRendererMap[col.colKey as string];
      return renderer ? { ...col, ...renderer } : { ...col };
    });
  };

  return { transformColumns };
};

export type UseSamplingColumnsRendererReturnType = ReturnType<typeof useSamplingColumnsRenderer>;
