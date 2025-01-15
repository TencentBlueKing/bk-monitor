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
import { computed, defineComponent, ref } from 'vue';

import { Select, Table } from 'bkui-vue';
import random from 'lodash/random';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import './flame-filter-list.scss';

const usFormat = getValueFormat('µs');

export type FilterKey = 'kind' | 'name' | 'servce' | 'source';

/**
 * 定义 FilterValueItem 接口，表示过滤器的值的项
 */
export interface IFilterValueItem {
  P95: number; // P95 值
  avg_duration: number; // 平均持续时间
  count: number; // 计数
  max_duration: number; // 最大持续时间
  min_duration: number; // 最小持续时间
  sum_duration: number; // 总持续时间
}
/**
 * 定义 FilterValueKey 类型，表示过滤器的值的键
 */
export type FilterValueKey = keyof IFilterValueItem;

/**
 * 定义 FilterData 接口，表示过滤器的数据
 */
export interface IFilterData {
  aggregation_key: FilterKey; // 聚合键
  display_name: string; // 显示名称
  items: {
    key: string; // 键
    display_name: string; // 显示名称
    values: IFilterValueItem; // 值
  }[];
}

export interface IFilterColumnItem<D> {
  id: D;
  name: string;
}
const FilterValueColumn = [
  {
    id: 'avg_duration',
    name: window.i18n.t('平均耗时'),
  },
  {
    id: 'P95',
    name: 'P95',
  },
  {
    id: 'count',
    name: window.i18n.t('调用次数'),
  },
  {
    id: 'max_duration',
    name: window.i18n.t('最大耗时'),
  },
  {
    id: 'min_duration',
    name: window.i18n.t('最小耗时'),
  },
  {
    id: 'sum_duration',
    name: window.i18n.t('总耗时'),
  },
];
export default defineComponent({
  name: 'FlameFilterList',
  props: {
    /**
     * 数据列表
     */
    data: {
      type: Array as () => IFilterData[],
      required: true,
    },
    /**
     * 最大高度
     */
    maxHeight: {
      type: Number,
      default: 300,
    },
  },
  setup(props) {
    const columnKey = ref<FilterKey>('name'); // 默认选中第一列
    const columnValueKey = ref<FilterValueKey>('avg_duration'); // 默认选中第一列
    // 表格数据
    const tableData = computed(() => {
      const data = props.data.find(item => item.aggregation_key === columnKey.value)?.items;
      if (!data) return [];
      return data.map(item => {
        let value: number | string = item.values[columnValueKey.value];
        if (value && columnValueKey.value.match(/(_duration|P9)/)) {
          const { text, suffix } = usFormat(value);
          value = `${text}${suffix}`;
        }
        return {
          ...item,
          ...item.values,
          value: value ?? '--',
          raw: item.values[columnValueKey.value],
        };
      });
    });
    /**
     *
     * @param value 选择的列
     * @description 选择列
     */
    function handleSelectLabelChange(value: FilterKey) {
      columnKey.value = value;
    }
    function handleColumnValueChange(value: FilterValueKey) {
      columnValueKey.value = value;
    }
    return {
      columnKey,
      columnValueKey,
      tableData,
      handleSelectLabelChange,
      handleColumnValueChange,
    };
  },
  render() {
    if (!this.data?.length) return <div />;
    const columns = [
      {
        label: () => (
          <div class='col-label'>
            <Select
              behavior='simplicity'
              clearable={false}
              modelValue={this.columnKey}
              size='small'
              onChange={this.handleSelectLabelChange}
            >
              {this.data.map(item => (
                <Select.Option
                  key={item.aggregation_key}
                  label={item.display_name}
                  value={item.aggregation_key}
                />
              ))}
            </Select>
          </div>
        ),
        field: 'display_name',
        sort: false,
      },
      {
        label: () => (
          <div class='col-value'>
            <Select
              behavior='simplicity'
              clearable={false}
              modelValue={this.columnValueKey}
              size='small'
              onChange={this.handleColumnValueChange}
              onClick={e => e.stopPropagation()}
            >
              {FilterValueColumn.map(item => (
                <Select.Option
                  key={item.id}
                  label={item.name}
                  value={item.id}
                />
              ))}
            </Select>
          </div>
        ),
        field: 'value',
        sort: {
          value: 'asc',
          sortFn: (a, b) => {
            return a.raw - b.raw;
          },
        },
        align: 'right',
      },
    ];
    return (
      <div>
        <Table
          class='flame-filter-list'
          columns={columns}
          data={this.tableData || []}
          maxHeight={this.maxHeight}
          rowKey={random(10).toString()}
          showOverflowTooltip={true}
        />
      </div>
    );
  },
});
