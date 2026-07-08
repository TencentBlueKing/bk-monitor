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

import { type PropType, computed, defineComponent, shallowRef, toRef } from 'vue';

import { useI18n } from 'vue-i18n';

import CommonTable from '../../../../../../alarm-center/components/alarm-table/components/common-table/common-table';
import { SAMPLING_TABLE_COLUMNS } from '../../../../../constants';
import { useSamplingColumnsRenderer } from '../../../../hooks/use-sampling-columns-renderer';

import type { IDataSamplingItem } from '../../../../../typings';

import './data-sampling-table.scss';

export default defineComponent({
  name: 'DataSamplingTable',
  props: {
    /** 采样数据列表 */
    samplingList: {
      type: Array as PropType<IDataSamplingItem[]>,
      default: () => [],
    },
    /** 数据加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    /** 复制原始日志 — 由父组件决定复制方式和反馈 */
    copy: (_log: IDataSamplingItem['raw_log']) => true,
    /** 查看上报数据详情 — 由父组件决定具体交互方式 */
    viewDetail: (_log: IDataSamplingItem['raw_log']) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    /** 已展开原始数据的行索引集合 */
    const collapseRowIndexes = shallowRef<number[]>([]);

    /**
     * @description 切换指定行原始数据的展开/收起状态
     * @param {number} index - 行索引
     * @returns {void}
     */
    const handleCollapse = (index: number): void => {
      const isOpen = collapseRowIndexes.value.includes(index);
      collapseRowIndexes.value = isOpen
        ? collapseRowIndexes.value.filter(item => item !== index)
        : [...collapseRowIndexes.value, index];
    };

    /** 列渲染器：将静态列配置与各列 cellRenderer 合并 */
    const { transformColumns } = useSamplingColumnsRenderer({
      samplingList: toRef(props, 'samplingList'),
      collapseRowIndexes,
      handleCollapse,
      copyEmit: (log: IDataSamplingItem['raw_log']) => emit('copy', log),
      viewDetailEmit: (log: IDataSamplingItem['raw_log']) => emit('viewDetail', log),
    });

    /** 合并静态配置与渲染配置后的完整列定义 */
    const columns = computed(() => transformColumns([...SAMPLING_TABLE_COLUMNS]));

    return {
      t,
      collapseRowIndexes,
      columns,
    };
  },
  render() {
    return (
      <div class='data-sampling-table-wrapper'>
        <CommonTable
          class='sampling-table'
          empty={{
            type: 'empty',
            emptyText: this.t('暂无数据'),
          }}
          autoFillSpace={!this.samplingList?.length}
          columns={this.columns}
          data={this.samplingList as unknown as Record<string, unknown>[]}
          loading={this.loading}
          rowKey='raw_log'
        />
      </div>
    );
  },
});
