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

import {
  type PropType,
  defineComponent,
  nextTick,
  onMounted,
  onUnmounted,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { type TableSort, type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { debounce } from 'lodash';
import TableSkeleton from 'trace/components/skeleton/table-skeleton';
import { useI18n } from 'vue-i18n';

import { useTable } from './hooks/use-table';
import LogException from './log-exception';

import type { TClickMenuOpt } from './typing';

import './log-table-new.scss';

export default defineComponent({
  name: 'LogTableNew',
  props: {
    displayFields: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    getTableData: {
      type: Function,
      default: () => {},
    },
    getFieldsData: {
      type: Function,
      default: () => {},
    },
    refreshKey: {
      type: String,
      default: '',
    },
    headerAffixedTop: {
      type: Object as PropType<TdPrimaryTableProps['headerAffixedTop']>,
      default: () => null,
    },
  },
  emits: {
    clickMenu: (_opt: TClickMenuOpt) => true,
    removeField: (_fieldName: string) => true,
    addField: (_fieldName: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const wrapRef = useTemplateRef<HTMLDivElement>('wrap');
    const wrapWidth = shallowRef(800);
    const loading = shallowRef(false);
    const {
      tableData,
      tableColumns,
      expandedRow,
      originLogData,
      fieldsDataToColumns,
      setFieldsData,
      setWrapWidth,
      setDefaultFieldWidth,
    } = useTable({
      onClickMenu: opt => {
        emit('clickMenu', opt);
      },
      onRemoveField: fieldName => {
        emit('removeField', fieldName);
      },
      onAddField: fieldName => {
        emit('addField', fieldName);
      },
    });
    const offset = shallowRef(0);
    const limit = shallowRef(30);
    const fieldsData = shallowRef(null);
    const expandedRowKeys = shallowRef([]);
    const isEnd = shallowRef(false);
    const sortInfo = shallowRef(null);
    const scrollLoading = shallowRef(false);
    const observer = shallowRef<IntersectionObserver>();
    const resizeObserver = shallowRef<ResizeObserver>();

    watch(
      () => props.refreshKey,
      async val => {
        loading.value = true;
        if (val) {
          handleScroll(true);
        }
      },
      { immediate: true }
    );

    watch(
      () => props.displayFields,
      val => {
        if (val.length) {
          setTableColumns();
        }
      }
    );

    const setTableColumns = async () => {
      fieldsData.value = await getFieldsData();
      setFieldsData(fieldsData.value);
      fieldsDataToColumns(fieldsData.value?.fields || [], props.displayFields);
    };

    const getTableData = async () => {
      const res = await props.getTableData({
        offset: offset.value,
        size: limit.value,
        sortList: sortInfo.value ? [[sortInfo.value.sortBy, sortInfo.value.descending ? 'desc' : 'asc']] : [],
      });
      return res;
    };

    const getFieldsData = async () => {
      const res = await props.getFieldsData();
      return res;
    };

    const handleExpandChange = (keys: (number | string)[]) => {
      expandedRowKeys.value = keys;
    };

    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h): any => {
      return <span class='icon-monitor icon-mc-arrow-right table-expand-icon' />;
    });

    const handleScroll = async (isInit = false) => {
      if (isInit) {
        offset.value = 0;
        tableData.value = [];
        originLogData.value = [];
        isEnd.value = false;
        scrollLoading.value = false;
        loading.value = false;
      }
      if (isEnd.value || scrollLoading.value) {
        return;
      }
      if (offset.value) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }
      if (isInit) {
        await setTableColumns();
      }
      const data = await getTableData();
      tableData.value = [...tableData.value, ...(data?.list || [])];
      originLogData.value = [...originLogData.value, ...(data?.origin_log_list || [])];
      isEnd.value = tableData.value.length < limit.value + offset.value;
      scrollLoading.value = false;
      loading.value = false;
      offset.value = tableData.value.length;
      nextTick(() => {
        if (isInit) {
          setDefaultFieldWidth();
        }
        const loadingEl = wrapRef.value.querySelector('.scroll-loading___observer');
        if (loadingEl) {
          observer.value?.unobserve?.(loadingEl);
          observer.value.observe(loadingEl);
        }
      });
    };

    const handleSortChange = (sort: TableSort) => {
      sortInfo.value = sort;
      handleScroll(true);
    };

    onMounted(() => {
      if (wrapRef.value) {
        wrapWidth.value = wrapRef.value.offsetWidth;
        const debounceSetWrapWidth = debounce(() => {
          wrapWidth.value = wrapRef.value.offsetWidth;
          setWrapWidth(wrapWidth.value);
        }, 200);
        resizeObserver.value = new ResizeObserver(() => {
          debounceSetWrapWidth();
        });
        resizeObserver.value.observe(wrapRef.value);
        setWrapWidth(wrapWidth.value);
        observer.value = new IntersectionObserver(entries => {
          for (const entry of entries) {
            if (entry.isIntersecting) {
              handleScroll();
            }
          }
        });
      }
    });

    onUnmounted(() => {
      observer.value.disconnect();
      resizeObserver.value.disconnect();
    });

    return {
      tableData,
      fieldsData,
      tableColumns,
      loading,
      offset,
      expandedRowKeys,
      expandedRow,
      expandIcon,
      wrapWidth,
      isEnd,
      sortInfo,
      t,
      handleExpandChange,
      handleSortChange,
    };
  },
  render() {
    const customAsyncLoadingFn = () => {
      return (
        <div
          ref='scrollRef'
          style={{
            width: `${this.wrapWidth}px`,
            position: 'sticky',
            left: 0,
          }}
          class='scroll-loading scroll-loading___observer'
        >
          <span>{this.isEnd ? this.t('到底了') : this.t('正加载更多内容…')}</span>
        </div>
      );
    };
    return (
      <div
        ref='wrap'
        class='alarm-detail-log-table-new'
      >
        {this.loading ? (
          <TableSkeleton />
        ) : this.tableData.length ? (
          <PrimaryTable
            class={'panel-log-log-table'}
            columns={[
              ...this.tableColumns,
              {
                width: '32px',
                minWidth: '32px',
                fixed: 'right',
                align: 'center',
                resizable: false,
                thClassName: '__table-custom-setting-col__',
                colKey: '__col_setting__',
                title: () => this.$slots.settingBtn?.(),
                cell: () => undefined,
              },
            ]}
            rowspanAndColspan={({ colIndex }) => {
              return {
                rowspan: 1,
                colspan: colIndex === this.tableColumns.length ? 2 : 1,
              };
            }}
            asyncLoading={(this.tableData.length ? customAsyncLoadingFn : false) as any}
            data={this.tableData}
            expandedRow={this.expandedRow}
            expandedRowKeys={this.expandedRowKeys}
            expandIcon={this.expandIcon}
            expandOnRowClick={true}
            headerAffixedTop={this.headerAffixedTop}
            horizontalScrollAffixedBottom={this.headerAffixedTop}
            hover={true}
            // needCustomScroll={false}
            resizable={true}
            rowKey={'__id__'}
            size={'small'}
            sort={this.sortInfo}
            tableLayout='fixed'
            onExpandChange={this.handleExpandChange}
            onSortChange={this.handleSortChange}
          />
        ) : (
          <LogException />
        )}
      </div>
    );
  },
});
