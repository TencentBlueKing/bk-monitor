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

import { type PropType, defineComponent, onMounted, shallowRef, useTemplateRef } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import EmptyStatus from 'trace/components/empty-status/empty-status';
import { useI18n } from 'vue-i18n';
import JsonPretty from 'vue-json-pretty';

import './log-table.scss';
import 'vue-json-pretty/lib/styles.css';
export default defineComponent({
  name: 'LogTable',
  props: {
    tableData: {
      type: Object as PropType<{
        columns: any[];
        data: any[];
        limit: number;
        offset: number;
        total: number;
      }>,
      default: () => ({
        data: [],
        total: 0,
        columns: [],
        limit: 30,
        offset: 0,
      }),
    },
    scrollLoading: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    scroll: (_params: { limit: number; offset: number }) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const loadingRef = useTemplateRef('scrollLoading');
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
      return <span class='icon-monitor icon-mc-arrow-right' />;
    });

    onMounted(() => {
      init();
    });

    function init() {
      const observer = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            handleScroll();
          }
        }
      });
      observer.observe(loadingRef.value as any);
    }

    function handleScroll() {
      isEnd.value = props.tableData.data.length < props.tableData.limit + props.tableData.offset;
      if (!props.tableData.data.length || isEnd.value) {
        return;
      }
      emit('scroll', {
        limit: props.tableData.limit,
        offset: props.tableData.data.length,
      });
    }

    function handleExpandChange(keys: (number | string)[]) {
      console.log(keys);
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
      t,
      handleExpandChange,
    };
  },
  render() {
    return (
      <div class='panel-log-log-table'>
        <PrimaryTable
          class='panel-log-log-table'
          columns={this.columns}
          data={this.tableData.data}
          expandedRow={this.expandedRow}
          expandedRowKeys={this.expandedRowKeys}
          expandIcon={this.expandIcon}
          expandOnRowClick={true}
          rowKey={'index'}
          size={'small'}
          onExpandChange={this.handleExpandChange}
        >
          {{
            empty: () => <EmptyStatus type={'empty'} />,
          }}
        </PrimaryTable>
        <div
          ref='scrollLoading'
          style={{ display: this.tableData.data.length ? 'flex' : 'none' }}
          class='panel-log-log-table-scroll-loading'
        >
          <span>{this.isEnd ? this.$t('到底了') : this.$t('正加载更多内容…')}</span>
        </div>
      </div>
    );
  },
});
