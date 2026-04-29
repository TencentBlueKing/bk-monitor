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

import { computed } from 'vue';
import type { MaybeRef } from 'vue';

import { get } from '@vueuse/core';
import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { IDataSamplingItem } from '../components/data-state/mock';

/** useSamplingColumns 参数 */
export interface UseSamplingColumnsParams {
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
 * @description 封装数据采样表格列配置
 * @param {UseSamplingColumnsParams} params - 参数对象
 * @returns {{ columns: import('vue').ComputedRef<unknown[]> }} 表格列配置
 */
export const useSamplingColumns = (params: UseSamplingColumnsParams) => {
  const { samplingList, collapseRowIndexes, handleCollapse, copyEmit, viewDetailEmit } = params;
  const { t } = useI18n();

  const columns = computed(() => [
    {
      colKey: 'index',
      title: t('序号'),
      width: 80,
      cellRenderer: (_row, _column, { getRowId }) => {
        const rowIndex = get(samplingList).findIndex(item => getRowId(item) === getRowId(_row));
        return <span>{rowIndex + 1}</span>;
      },
    },
    {
      colKey: 'raw_log',
      title: t('原始数据'),
      cellRenderer: (row, _column, _renderCtx) => {
        const rowIndex = get(samplingList).indexOf(row);
        const isExpanded = get(collapseRowIndexes).includes(rowIndex);
        return (
          <div class={['text-log-wrap', { 'is-expanded': isExpanded }]}>
            <div class='text-log'>
              <span
                class='collapse-btn'
                onClick={() => handleCollapse(rowIndex)}
              >
                {isExpanded ? t('收起') : t('展开全部')}
              </span>
              <span
                class='log-text'
                onClick={() => viewDetailEmit(row.raw_log)}
              >
                {JSON.stringify(row.raw_log)}
              </span>
            </div>
          </div>
        );
      },
    },
    {
      colKey: 'sampling_time',
      title: t('采样时间'),
      width: 200,
    },
    {
      colKey: 'operations',
      title: t('操作'),
      width: 180,
      cellRenderer: row => {
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
        );
      },
    },
  ]);

  return { columns };
};

export type UseSamplingColumnsReturnType = ReturnType<typeof useSamplingColumns>;
