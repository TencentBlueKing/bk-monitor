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
  watch,
} from 'vue';
import type { PropType } from 'vue';

import { type SortInfo, type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import EmptyStatus, { type EmptyStatusOperationType } from 'trace/components/empty-status/empty-status';
import TableSkeleton from 'trace/components/skeleton/table-skeleton';
import { formatTime } from 'trace/utils/utils';
import { useI18n } from 'vue-i18n';

import EventTableExpandContent from './event-table-expand-content';
import { DimensionsTypeEnum, eventChartMap, SourceTypeEnum } from './typing';

// #if IS_APM_MONITOR
import hostSvgUrl from '../../../../../../../monitor-common/svg/svg/host.svg?url';
import bcsSvgUrl from '../../../../../../../monitor-common/svg/svg/bcs.svg?url';
import landunSvgUrl from '../../../../../../../monitor-common/svg/svg/landun.svg?url';
import defaultSvgUrl from '../../../../../../../monitor-common/svg/svg/default.svg?url';

const escapeForSingleQuotedString = (value: string) => value.replace(/\\/g, '\\\\').replace(/'/g, "\\'");

const SourceIconSvgMap = {
  [SourceTypeEnum.BCS]: escapeForSingleQuotedString(bcsSvgUrl),
  [SourceTypeEnum.BKCI]: escapeForSingleQuotedString(landunSvgUrl),
  [SourceTypeEnum.HOST]: escapeForSingleQuotedString(hostSvgUrl),
  [SourceTypeEnum.DEFAULT]: escapeForSingleQuotedString(defaultSvgUrl),
};
// #endif

import './event-table.scss';

export const tableColumnKey = {
  TIME: 'time',
  SOURCE: 'source',
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
        (params: { limit: number; offset: number; sort: string[] }) => Promise<{
          data: unknown[];
          total: number;
        }>
      >,
      default: () => null,
    },
    /** 筛选条件变化时刷新表格 */
    refreshKey: {
      type: String,
      default: '',
    },
    /** 当前是否处于筛选状态，用于区分空态与搜索无结果 */
    isFiltered: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['clearFilter'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const loadingRef = useTemplateRef('scrollRef');
    const loading = shallowRef(false);
    const scrollLoading = shallowRef(false);
    const columns = shallowRef<TdPrimaryTableProps['columns']>([
      {
        colKey: tableColumnKey.TIME,
        title: window.i18n.t('时间'),
        width: 200,
        // sorter: true,
        ellipsis: false,
        cell: (_h, { row }) => {
          return (
            <span class='time-col-content'>
              <span
                class={[
                  'icon-monitor icon-mc-arrow-right table-expand-icon',
                  { 'rotate-90': expandedRowKeys.value.includes(row.key) },
                ]}
              />
              <span class='time-value'>{formatTime(+row[tableColumnKey.TIME].value)}</span>
            </span>
          );
        },
      },
      {
        colKey: tableColumnKey.SOURCE,
        title: window.i18n.t('事件来源'),
        width: 160,
        ellipsis: false,
        cell: (_h, { row }) => {
          const item = row[tableColumnKey.SOURCE];
          const { alias, value } = item;
          return (
            <span class='source-item'>
              {SourceIconMap[SourceTypeEnum.BCS] ? (
                window.source_app !== 'apm' ? (
                  <span class={`source-icon icon-monitor ${SourceIconMap[value]}`} />
                ) : (
                  <span
                    style={{
                      backgroundImage: SourceIconSvgMap[item.value]
                        ? `url('${SourceIconSvgMap[item.value]}')`
                        : undefined,
                    }}
                    class={`source-icon icon-monitor ${SourceIconMap[value]}`}
                  />
                )
              ) : undefined}
              <span
                class='common-table-ellipsis'
                v-overflow-tips={{
                  placement: 'top',
                }}
              >
                {' '}
                {alias}
              </span>
            </span>
          );
        },
      },
      {
        colKey: tableColumnKey.EVENT_NAME,
        title: window.i18n.t('事件名'),
        width: 160,
        ellipsis: false,
        cell: (_h, { row }) => {
          const alias = row[tableColumnKey.EVENT_NAME]?.alias || row.origin_data?.[tableColumnKey.EVENT_NAME];
          return (
            <span
              class='common-table-ellipsis'
              v-overflow-tips={{
                placement: 'top',
              }}
            >
              {alias}
            </span>
          );
        },
      },
      {
        colKey: tableColumnKey.CONTENT,
        title: window.i18n.t('内容'),
        ellipsis: false,
        minWidth: 150,
        cell: (_h, { row }) => {
          const cItem = row[tableColumnKey.CONTENT];
          const { alias, detail } = cItem;
          return (
            <div
              class='event-content-col'
              v-bk-tooltips={{
                extCls: 'alarm-center-detail-panel-alarm-relation-event-table-popover-wrap',
                delay: 300,
                content: (
                  <div class='alarm-center-detail-panel-alarm-relation-event-table-event-content-popover'>
                    <div class='explore-content-popover-title'>{t('内容')} :</div>
                    <div class='explore-content-popover-main'>
                      {Object.values(detail).map((item: any, index) => {
                        return (
                          <div
                            key={index}
                            class='explore-content-popover-main-item'
                          >
                            <span class='content-item-key'>{item?.label}</span>
                            <span class='content-item-colon'>:</span>
                            {item?.type === 'link' && item?.url ? (
                              <a
                                class='content-item-value-link'
                                href={item.url}
                                rel='noreferrer'
                                target='_blank'
                              >
                                {item?.alias || '--'}
                              </a>
                            ) : (
                              <span class='content-item-value'>{item?.alias || '--'}</span>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                ),
              }}
            >
              <span class='content-label'>{t('事件内容')}:</span>
              <span class='content-value explore-overflow-tip-col'>{alias}</span>
            </div>
          );
        },
      },
      {
        colKey: tableColumnKey.TARGET,
        title: window.i18n.t('目标'),
        width: 190,
        ellipsis: false,
        cell: (_h, { row }) => {
          const item = row[tableColumnKey.TARGET];
          if (!item.url) {
            const alias = row[tableColumnKey.TARGET]?.alias || row.origin_data?.[tableColumnKey.TARGET];
            return (
              <span
                class='explore-overflow-tip-col'
                v-bk-tooltips={{
                  content: alias || '--',
                  delay: 300,
                }}
              >
                {alias || '--'}
              </span>
            );
          }
          return (
            <div class='event-link-col'>
              <a
                class='explore-overflow-tip-col'
                v-bk-tooltips={{
                  delay: 300,
                  extCls: 'alarm-center-detail-panel-alarm-relation-event-table-popover-wrap',
                  content: <div class='explore-target-popover'>{`点击前往: ${item.scenario || '--'}`}</div>,
                }}
                href={item.url}
                rel='noreferrer'
                target='_blank'
              >
                {item.alias}
              </a>
            </div>
          );
        },
      },
    ]);
    const tableData = shallowReactive({
      offset: 0,
      limit: 30,
      data: [],
    });
    const expandIcon = shallowRef<TdPrimaryTableProps['expandIcon']>((_h, { _row }): any => {
      return <span class='icon-monitor icon-mc-arrow-right table-expand-icon' />;
    });
    const expandedRowKeys = shallowRef([]);
    const expandedRow = shallowRef<TdPrimaryTableProps['expandedRow']>((_h, { row }): any => {
      return <EventTableExpandContent data={row} />;
    });
    const sort = shallowRef<SortInfo>(null);
    const isEnd = shallowRef(false);
    const observer = shallowRef<IntersectionObserver>();

    const handleExpandChange = (keys: (number | string)[]) => {
      expandedRowKeys.value = keys;
    };

    const resetData = () => {
      tableData.offset = 0;
      tableData.data = [];
      isEnd.value = false;
    };

    const handleLoad = async () => {
      if (isEnd.value || loading.value || scrollLoading.value) {
        return;
      }
      tableData.offset = tableData.data.length;
      if (tableData.offset) {
        scrollLoading.value = true;
      } else {
        loading.value = true;
      }
      const res = await props.getTableData({
        offset: tableData.offset,
        limit: tableData.limit,
        sort: sort.value ? [`${sort.value.descending ? '-' : ''}${sort.value.sortBy}`] : [],
      });
      tableData.data = [...tableData.data, ...res.data];
      isEnd.value = res.data.length < tableData.limit;
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

    const handleSortChange = (value: SortInfo) => {
      sort.value = value;
      resetData();
      handleLoad();
    };

    const handleOperation = (type: EmptyStatusOperationType) => {
      if (type === 'clear-filter') {
        emit('clearFilter');
      }
    };

    watch(
      () => props.refreshKey,
      (val, oldVal) => {
        if (!val || val === oldVal) return;
        resetData();
        handleLoad();
      }
    );

    onMounted(init);
    onBeforeUnmount(() => {
      observer.value?.disconnect();
    });

    return {
      columns,
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
      handleOperation,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event-table'>
        {this.loading ? (
          <TableSkeleton type={1} />
        ) : (
          <PrimaryTable
            class='relation-event-table'
            rowClassName={({ row }) =>
              `row-event-status-${eventChartMap[row.type.value || DimensionsTypeEnum.DEFAULT]}`
            }
            columns={this.columns}
            data={this.tableData.data}
            expandedRow={this.expandedRow}
            expandedRowKeys={this.expandedRowKeys}
            expandIcon={false}
            expandOnRowClick={true}
            horizontalScrollAffixedBottom={true}
            needCustomScroll={false}
            resizable={true}
            rowKey={'key'}
            size={'small'}
            sort={this.sort}
            onExpandChange={this.handleExpandChange}
            onSortChange={this.handleSortChange as any}
          >
            {{
              empty: () => (
                <EmptyStatus
                  type={this.isFiltered ? 'search-empty' : 'empty'}
                  onOperation={this.handleOperation}
                />
              ),
            }}
          </PrimaryTable>
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
