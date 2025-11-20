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
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  shallowReactive,
  shallowRef,
  useTemplateRef,
} from 'vue';
import type { PropType } from 'vue';

import { type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Checkbox } from 'bkui-vue';
import dayjs from 'dayjs';
import TableSkeleton from 'trace/components/skeleton/table-skeleton';
import { useI18n } from 'vue-i18n';

import EventTableExpandContent from './event-table-expand-content';

import './event-table.scss';

export const SourceTypeEnum = {
  ALL: 'ALL',
  /** Kubernetes/BCS */
  BCS: 'BCS',
  /** BKCI/蓝盾 */
  BKCI: 'BKCI',
  /** 其他类型事件来源 */
  DEFAULT: 'DEFAULT',
  /** 系统/主机 */
  HOST: 'HOST',
} as const;
export const tableColumnKey = {
  TIME: 'time',
  SOURCE_TYPE: 'source_type',
  EVENT_NAME: 'event_name',
  CONTENT: 'event.content',
  TARGET: 'target',
};

const SourceIconMap = {
  [SourceTypeEnum.BCS]: 'icon-explore-bcs',
  [SourceTypeEnum.BKCI]: 'icon-explore-landun',
  [SourceTypeEnum.HOST]: 'icon-explore-host',
  [SourceTypeEnum.DEFAULT]: 'icon-explore-default',
};

export default defineComponent({
  name: 'EventTable',
  props: {
    getTableData: {
      type: Function as PropType<
        (params: { page: number; pageSize: number }) => Promise<{
          data: unknown[];
          total: number;
        }>
      >,
      default: () => null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const loadingRef = useTemplateRef('scrollRef');
    const loading = shallowRef(false);
    const scrollLoading = shallowRef(false);
    const columns = shallowRef<TdPrimaryTableProps['columns']>([
      {
        colKey: tableColumnKey.TIME,
        title: window.i18n.t('时间'),
        width: 150,
        sorter: true,
        cell: (_h, { row }) => {
          return dayjs.tz(row.time * 1000).format('YYYY-MM-DD HH:mm');
        },
      },
      {
        colKey: tableColumnKey.SOURCE_TYPE,
        title: window.i18n.t('事件来源'),
        width: 160,
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { _row }) => {
          return (
            <span class='source-item'>
              {SourceIconMap[SourceTypeEnum.BCS] ? (
                <span class={`source-icon icon-monitor ${SourceIconMap[SourceTypeEnum.BCS]}`} />
              ) : undefined}
              <span>{window.i18n.t('容器')}</span>
            </span>
          );
        },
      },
      {
        colKey: tableColumnKey.EVENT_NAME,
        title: window.i18n.t('事件名'),
        width: 160,
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return row.alert_name;
        },
      },
      {
        colKey: tableColumnKey.CONTENT,
        title: window.i18n.t('内容'),
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        minWidth: 150,
        cell: (_h, { row }) => {
          return row.description;
        },
      },
      {
        colKey: tableColumnKey.TARGET,
        title: window.i18n.t('目标'),
        width: 190,
        ellipsis: {
          theme: 'light',
          placement: 'bottom',
        },
        cell: (_h, { row }) => {
          return row.target || '--';
        },
      },
    ]);
    const tableData = shallowReactive({
      page: 0,
      pageSize: 10,
      data: [],
      total: 0,
    });
    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h, { _row }): any => {
      return <span class='icon-monitor icon-mc-arrow-right table-expand-icon' />;
    });
    const expandedRowKeys = shallowRef([]);
    const expandedRow = shallowRef<TdPrimaryTableProps['expandedRow']>((_h, { row }): any => {
      return <EventTableExpandContent data={row} />;
    });
    const sort = shallowRef<TdPrimaryTableProps['sort']>(null);
    const sourceType = shallowRef([]);
    const sourceTypeOptions = shallowRef([
      {
        label: window.i18n.t('全部'),
        value: SourceTypeEnum.ALL,
        count: 0,
        icon: '',
      },
      {
        label: window.i18n.t('容器'),
        value: SourceTypeEnum.BCS,
        count: 0,
        icon: SourceIconMap[SourceTypeEnum.BCS],
      },
      {
        label: window.i18n.t('蓝盾'),
        value: SourceTypeEnum.BKCI,
        count: 0,
        icon: SourceIconMap[SourceTypeEnum.BKCI],
      },
      {
        label: window.i18n.t('主机'),
        value: SourceTypeEnum.HOST,
        count: 0,
        icon: SourceIconMap[SourceTypeEnum.HOST],
      },
    ]);
    const isEnd = shallowRef(false);
    const observer = shallowRef<IntersectionObserver>();

    const handleExpandChange = (keys: (number | string)[]) => {
      console.log(keys);
      expandedRowKeys.value = keys;
    };

    const handleLoad = async () => {
      if (isEnd.value || loading.value || scrollLoading.value) {
        return;
      }
      if (tableData.page) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }
      tableData.page += 1;
      const res = await props.getTableData({
        page: tableData.page,
        pageSize: tableData.pageSize,
      });
      tableData.data = [...tableData.data, ...res.data];
      tableData.total = res.total;
      isEnd.value = tableData.data.length < tableData.page * tableData.pageSize;
      scrollLoading.value = false;
      loading.value = false;
    };
    const init = async () => {
      await handleLoad();
      await nextTick();
      observer.value = new IntersectionObserver(entries => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            if (tableData.data.length) {
              handleLoad();
            }
          }
        }
      });
      observer.value.observe(loadingRef.value as HTMLElement);
    };

    const handleSortChange = (value: TdPrimaryTableProps['sort']) => {
      sort.value = value;
    };

    const handleGoEvent = () => {};

    onMounted(() => {
      init();
    });
    onBeforeUnmount(() => {
      observer.value?.disconnect();
    });

    return {
      columns,
      sourceType,
      sourceTypeOptions,
      expandIcon,
      expandedRow,
      expandedRowKeys,
      isEnd,
      tableData,
      sort,
      loading,
      handleSortChange,
      handleExpandChange,
      t,
      handleGoEvent,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event-table'>
        <div class='header-operate'>
          <span style='margin-right: 8px;'>{window.i18n.t('事件来源')}:</span>
          <Checkbox.Group class='header-operate-item'>
            {{
              default: () => {
                return this.sourceTypeOptions.map(item => (
                  <Checkbox
                    key={item.value}
                    label={item.value}
                  >
                    <span class='source-item'>
                      {item.icon ? <span class={`source-icon icon-monitor ${item.icon}`} /> : undefined}
                      <span>{item.label}</span>
                    </span>
                  </Checkbox>
                ));
              },
            }}
          </Checkbox.Group>
          <Button
            style='margin-left: 16px;'
            theme='primary'
            text
            onClick={this.handleGoEvent}
          >
            <span>{this.t('更多事件')}</span>
            <span
              style='margin-left: 5px; font-size: 12px;'
              class='icon-monitor icon-fenxiang'
            />
          </Button>
        </div>
        {this.loading ? (
          <TableSkeleton type={1} />
        ) : (
          <PrimaryTable
            class='relation-event-table'
            columns={this.columns}
            data={this.tableData.data}
            expandedRow={this.expandedRow}
            expandedRowKeys={this.expandedRowKeys}
            expandIcon={this.expandIcon}
            expandOnRowClick={true}
            resizable={true}
            rowClassName={({ row }) => `row-event-status-${row.severity}`}
            rowKey={'event_id'}
            size={'small'}
            sort={this.sort}
            onExpandChange={this.handleExpandChange}
            onSortChange={this.handleSortChange}
          />
        )}
        <div
          ref='scrollRef'
          style={{ display: this.tableData.data.length ? 'flex' : 'none' }}
          class='panel-event-table-scroll-loading'
        >
          <span>{this.isEnd ? this.$t('到底了') : this.$t('正加载更多内容…')}</span>
        </div>
      </div>
    );
  },
});
