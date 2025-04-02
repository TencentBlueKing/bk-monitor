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

import { computed, defineComponent, reactive, ref, watch, type PropType } from 'vue';

import { Table } from '@blueking/table';
import { useMemoize } from '@vueuse/core';
import { Loading } from 'bkui-vue';
import { orderBy } from 'lodash';

import useRenderEmpty from '../../hooks/useRenderEmpty';

import type { Column } from 'bkui-vue/lib/table/props';
import type { VxeColumnProps } from 'vxe-pc-ui/types/components/column';
import type { VxeTableProps } from 'vxe-pc-ui/types/components/table';

type TableColumn = VxeColumnProps & Column;

import './index.scss';
import '@blueking/table/vue3/vue3.css';

interface TableProps {
  data: any[];
  virtualGt: number;
  virtualEnabled: boolean;
  localPage: boolean;
  columns: any[];
  tableStyle: Record<string, unknown>;
  search?: string;
}

type CustomTableProps = VxeTableProps & TableProps;
export default defineComponent({
  name: 'CustomTable',
  inheritAttrs: true,
  props: {
    tableStyle: {
      default: () => ({}),
      type: Object,
    },
    // 定义需要的 props，可以扩展 TableProps 的类型
    data: {
      type: Array as PropType<Record<string, any>[]>,
    },
    virtualGt: {
      default: 0,
      type: Number,
    },
    /** 开启虚拟滚动 */
    virtualEnabled: {
      type: Boolean,
      default: false,
    },
    // 是否开启本地分页等
    localPage: {
      type: Boolean,
      default: false,
    },
    autoResize: {
      type: Boolean,
      default: true,
    },
    columns: {
      required: true,
      type: Array as PropType<Column[]>,
    },
    search: {
      type: String,
      default: '',
    },
    // 其他需要的 props
  },
  emits: ['clear'],
  setup(props: CustomTableProps, { emit, slots, attrs, expose }) {
    const table = ref(null);
    const localPagination = ref({
      current: 1,
      limit: (attrs as any)?.pagination?.limit ?? 10,
    });
    const localSort = ref({
      order: '',
      orderBy: '',
    });
    const localFilters = ref({});
    const columnsData = ref([]);
    const keyword = ref([]);
    const { renderEmpty } = useRenderEmpty(keyword, () => emit('clear', ''));
    /** 简化表格虚拟滚动配置 */
    const virtualEnabledConfig = props.virtualEnabled
      ? {
          showOverflow: true,
          scrollY: {
            enabled: true,
            gt: props.virtualGt,
          },
          virtualYConfig: {
            enabled: true,
            gt: props.virtualGt,
          },
        }
      : {};

    // 行配置
    const rowConfig = computed(() => {
      const initConfig = { isHover: true };
      const attrRowConfig = (attrs as any)?.rowConfig ?? {};
      return { ...initConfig, ...attrRowConfig };
    });

    // 单元格配置
    const cellConfig = computed(() => {
      const initConfig = { height: 56 };
      const attrCellConfig = (attrs as any)?.cellConfig ?? {};
      return { ...initConfig, ...attrCellConfig };
    });

    /** 本地分页配置 */
    const localPageEvent = ref(
      props.localPage
        ? {
            onPageLimitChange: (limit: number) => {
              localPagination.value.limit = limit;
            },
            onPageValueChange: (value: number) => {
              localPagination.value.current = value;
            },
            onColumnSort: (order: { field: string; type: string }) => {
              const { field, type } = order;
              localSort.value = {
                order: type ? field : '',
                orderBy: type ?? '',
              };
            },
            onFilterChange: ({ filters }: { field: string; type: string; filters: any[] }) => {
              localFilters.value = filters.reduce((curr, { field, values }) => {
                curr[field] = reactive([...values]);
                return curr;
              }, {});
            },
          }
        : {}
    );

    const dataList = computed(() => {
      const list = props.data;
      if (localSort.value.order) {
        return orderBy(list, [localSort.value.order], [localSort.value.orderBy as 'asc' | 'desc']);
      }
      return list;
    });

    const pagination = computed(() => {
      if (props.virtualEnabled || !attrs?.pagination) {
        return {};
      }
      return {
        pagination: {
          ...((attrs as any)?.pagination ?? localPagination.value),
          count: (attrs as any)?.pagination?.count ?? dataList.value.length,
        },
      };
    });

    // 缓存计算结果
    const getMemoizedFilter = useMemoize(
      (field: string) => {
        // 排除当前字段的筛选条件
        const curFilterData = dataList.value.filter(row =>
          Object.entries(localFilters.value)
            .filter(([f]) => f !== field)
            .every(([field, value]) => {
              const col = columnsData.value.find((v: { field: string }) => v.field === field);
              return col?.filterMethod?.({ value, row }) ?? true;
            })
        );
        // 提取唯一值
        const results = [
          ...new Set(
            curFilterData.map(function (item: { [key: string]: number | number[] | string | string[] }) {
              return item[field];
            })
          ),
        ].map(value => ({
          text: value,
          label: value,
          value,
        }));
        return results;
      },
      {
        getKey: (field: string) => JSON.stringify(localFilters.value) + field,
      }
    );

    const getTableData = () => {
      return table.value?.getVxeTableInstance()?.getFullData?.() ?? [];
    };

    const reloadTableData = () => {
      table.value?.getVxeTableInstance()?.reloadData?.(dataList.value);
    };

    // Grid布局存在全选样式问题，判断是否全选
    const isAllCheckboxChecked = () => {
      return table.value?.getVxeTableInstance()?.getCheckboxRecords(true)?.length === dataList.value;
    };

    expose({ getTableData, reloadTableData, isAllCheckboxChecked, table });

    watch(
      () => props.columns,
      (value: TableColumn[]) => {
        columnsData.value = (value || []).map(v => {
          if (v.filter && props.localPage) {
            const results = {
              ...v,
              filter: Object.assign(v.filter, {
                list: getMemoizedFilter(v.field),
                filterFn: ({ value, row }: { value: string; row: { [key: string]: unknown } }): boolean => {
                  return Array.isArray(value) ? value.includes(row[v.field]) : row[v.field] === value;
                },
              }),
            };
            return results;
          }
          return v;
        });
      },
      {
        immediate: true,
      }
    );

    return () => (
      <div
        style={{ height: '100%', width: '100%' }}
        class={['bv-custom-table', { 'is-loading': attrs?.loading, 'is-no-check-all': !isAllCheckboxChecked() }]}
      >
        <Table
          ref={table}
          style={props.tableStyle}
          autoResize={props.autoResize}
          columns={columnsData.value}
          data={dataList.value}
          maxHeight='100%'
          {...virtualEnabledConfig}
          {...{
            ...attrs,
            ...pagination.value,
          }}
          {...localPageEvent.value}
          v-slots={{
            ...slots,
            loading: () => <Loading />,
            empty: () => slots?.empty?.() ?? renderEmpty(),
          }}
          cellConfig={cellConfig.value}
          rowConfig={rowConfig.value}
        />
      </div>
    );
  },
});
