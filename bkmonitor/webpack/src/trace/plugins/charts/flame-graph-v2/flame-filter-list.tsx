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
import { computed, defineComponent, ref, shallowRef } from 'vue';

import { type SortInfo, type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import { Select } from 'bkui-vue';
import { getValueFormat } from 'monitor-ui/monitor-echarts/valueFormats';

import './flame-filter-list.scss';

const usFormat = getValueFormat('µs');

export type FilterKey = 'kind' | 'name' | 'servce' | 'source';

/**
 * 定义 FilterValueKey 类型，表示过滤器的值的键
 */
export type FilterValueKey = keyof IFilterValueItem;
export interface IFilterColumnItem<D> {
  id: D;
  name: string;
}

/**
 * 定义 FilterData 接口，表示过滤器的数据
 */
export interface IFilterData {
  aggregation_key: FilterKey; // 聚合键
  display_name: string; // 显示名称
  items: {
    display_name: string; // 显示名称
    key: string; // 键
    values: IFilterValueItem; // 值
  }[];
}

/**
 * 定义 FilterValueItem 接口，表示过滤器的值的项
 */
export interface IFilterValueItem {
  avg_duration: number; // 平均持续时间
  count: number; // 计数
  max_duration: number; // 最大持续时间
  min_duration: number; // 最小持续时间
  P95: number; // P95 值
  sum_duration: number; // 总持续时间
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
    const sortInfo = shallowRef<SortInfo>({
      sortBy: '', // 排序字段
      descending: false, // 是否降序
    });
    // 表格数据
    const tableData = computed(() => {
      const data = props.data.find(item => item.aggregation_key === columnKey.value)?.items;
      if (!data) return [];
      let list = [];
      const tableData = data.map(item => {
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
      if (sortInfo.value.sortBy) {
        list = tableData.slice().sort((a, b) => {
          const aVal = a.raw;
          const bVal = b.raw;
          return aVal === bVal ? 0 : aVal > bVal ? 1 : -1;
        });
        if (sortInfo.value.descending) {
          list.reverse();
        }
      } else {
        return tableData;
      }
      return list;
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
    function handleSortChange(info: TableSort) {
      sortInfo.value = info
        ? (info as SortInfo)
        : {
            sortBy: '', // 排序字段
            descending: false, // 是否降序
          };
    }
    return {
      columnKey,
      columnValueKey,
      tableData,
      handleSelectLabelChange,
      handleColumnValueChange,
      handleSortChange,
    };
  },
  render() {
    if (!this.data?.length) return <div />;
    return (
      <div>
        <PrimaryTable
          class='flame-filter-list'
          columns={[
            {
              sorter: false,
              colKey: 'display_name',
              ellipsis: {
                popperOptions: {
                  strategy: 'fixed',
                },
              },
              title: () => (
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
                        id={item.aggregation_key}
                        key={item.aggregation_key}
                        name={item.display_name}
                      />
                    ))}
                  </Select>
                </div>
              ),
            },
            {
              colKey: 'value',
              align: 'right',
              ellipsis: {
                popperOptions: {
                  strategy: 'fixed',
                },
              },
              title: () => (
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
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </Select>
                </div>
              ),
              sorter: true,
            },
          ]}
          data={this.tableData || []}
          maxHeight={this.maxHeight}
          resizable={true}
          rowKey='display_name'
          stripe={false}
          onSortChange={this.handleSortChange}
        >
          {/* <TableColumn
            width={'66%'}
            v-slots={{
              header: () => (
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
                        id={item.aggregation_key}
                        key={item.aggregation_key}
                        name={item.display_name}
                      />
                    ))}
                  </Select>
                </div>
              ),
            }}
            field='display_name'
            show-overflow='tooltip'
          />
          <TableColumn
            width={'33%'}
            v-slots={{
              header: () => (
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
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </Select>
                </div>
              ),
            }}
            align='right'
            field='value'
            headerClassName={'col-value-header'}
            sortable={true}
            sortBy={'raw'}
            sortType='number'
          /> */}
        </PrimaryTable>
      </div>
    );
  },
});
