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
  onMounted,
  onUnmounted,
  shallowReactive,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import EmptyStatus from 'trace/components/empty-status/empty-status';
import TableSkeleton from 'trace/components/skeleton/table-skeleton';
import { useI18n } from 'vue-i18n';
import JsonPretty from 'vue-json-pretty';

import './log-table.scss';
import 'vue-json-pretty/lib/styles.css';
export default defineComponent({
  name: 'LogTable',
  props: {
    refreshKey: {
      type: String,
      default: null,
    },
    getData: {
      type: Function as PropType<(params: { limit: number; offset: number }) => Promise<any>>,
      default: () => Promise.resolve({}),
    },
  },
  emits: {
    scroll: (_params: { limit: number; offset: number }) => true,
  },
  setup(props) {
    const { t } = useI18n();
    const loadingRef = useTemplateRef('scrollRef');
    const loading = shallowRef(false);
    const scrollLoading = shallowRef(false);
    const isEnd = shallowRef(false);
    const columns = shallowRef<TdPrimaryTableProps['columns']>([
      {
        colKey: 'date',
        title: '时间',
        width: 200,
      },
      {
        colKey: 'log',
        title: '日志内容',
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
      },
    ]);
    const tableData = shallowReactive({
      data: [],
      total: 0,
      columns: [],
      limit: 30,
      offset: 0,
    });

    const expandedRowKeys = shallowRef([]);
    const expandedRow = shallowRef<TdPrimaryTableProps['expandedRow']>((_h, { row }): any => {
      return (
        <div class='table-expand-content'>
          <span
            class='icon-monitor icon-mc-copy'
            onClick={() => handleCopy(row.source)}
          />
          <JsonPretty data={row.source} />
        </div>
      );
    });
    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h, { _row }): any => {
      return <span class='icon-monitor icon-mc-arrow-right table-expand-icon' />;
    });

    const observer = shallowRef<IntersectionObserver>();

    const resetTableData = () => {
      tableData.data = [];
      tableData.total = 0;
      tableData.columns = [];
      tableData.limit = 30;
      tableData.offset = 0;
    };
    const handleLoadData = async () => {
      if (isEnd.value || scrollLoading.value) {
        return;
      }
      if (tableData.offset) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }

      const res = await props.getData({
        limit: tableData.limit,
        offset: tableData.offset,
      });
      tableData.data = res?.data || [];
      tableData.total = res?.total || 0;
      tableData.columns = res?.columns || [];
      isEnd.value = tableData.data.length < tableData.limit + tableData.offset;
      scrollLoading.value = false;
      loading.value = false;
      tableData.offset = tableData.data.length;
    };

    watch(
      () => props.refreshKey,
      val => {
        loading.value = true;
        if (val) {
          resetTableData();
          handleLoadData();
        }
      },
      { immediate: true }
    );

    onMounted(() => {
      observer.value = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            handleScroll();
          }
        }
      });
      observer.value.observe(loadingRef.value as HTMLDivElement);
    });
    onUnmounted(() => {
      observer.value.disconnect();
    });

    function handleScroll() {
      handleLoadData();
    }

    function handleExpandChange(keys: (number | string)[]) {
      expandedRowKeys.value = keys;
    }

    function handleCopy(value: Record<string, any>) {
      copyText(JSON.stringify(value), msg => {
        Message({
          message: msg,
          theme: 'error',
        });
        return;
      });
      Message({
        message: t('复制成功'),
        theme: 'success',
      });
    }

    return {
      columns,
      expandedRowKeys,
      expandIcon,
      expandedRow,
      isEnd,
      tableData,
      loading,
      scrollLoading,
      t,
      handleExpandChange,
    };
  },
  render() {
    return (
      <div class='panel-log-log-table'>
        {this.loading ? (
          <TableSkeleton type={4} />
        ) : (
          <PrimaryTable
            class='panel-log-log-table'
            columns={this.columns}
            data={this.tableData.data}
            expandedRow={this.expandedRow}
            expandedRowKeys={this.expandedRowKeys}
            expandIcon={this.expandIcon}
            expandOnRowClick={true}
            resizable={true}
            rowKey={'index'}
            size={'small'}
            onExpandChange={this.handleExpandChange}
          >
            {{
              empty: () => <EmptyStatus type={'empty'} />,
            }}
          </PrimaryTable>
        )}
        <div
          ref='scrollRef'
          style={{ display: this.tableData.data.length ? 'flex' : 'none' }}
          class='panel-log-log-table-scroll-loading'
        >
          <span>{this.isEnd ? this.$t('到底了') : this.$t('正加载更多内容…')}</span>
        </div>
      </div>
    );
  },
});
