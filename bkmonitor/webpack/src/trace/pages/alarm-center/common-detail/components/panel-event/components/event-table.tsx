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

import { type SortInfo, type TdPrimaryTableProps, PrimaryTable } from '@blueking/tdesign-ui';
import { Button, Checkbox } from 'bkui-vue';
import EmptyStatus, { type EmptyStatusOperationType } from 'trace/components/empty-status/empty-status';
import TableSkeleton from 'trace/components/skeleton/table-skeleton';
import { formatTime } from 'trace/utils/utils';
import { useI18n } from 'vue-i18n';

import EventTableExpandContent from './event-table-expand-content';
import { DimensionsTypeEnum, eventChartMap, SourceTypeEnum } from './typing';

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
        (params: { limit: number; offset: number; sort: string[]; sources: string[] }) => Promise<{
          data: unknown[];
          total: number;
        }>
      >,
      default: () => null,
    },
    getDataCount: {
      type: Function as PropType<
        (params?: { sources: string[] }) => Promise<{
          list: {
            alias: string;
            total: number;
            value: string;
          }[];
          total: number;
        }>
      >,
      default: () => null,
    },
  },
  emits: ['goEvent'],
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
                <span class={`source-icon icon-monitor ${SourceIconMap[value]}`} />
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
    const isAllSourceType = shallowRef(false);
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
      {
        label: window.i18n.t('业务上报'),
        value: SourceTypeEnum.DEFAULT,
        count: 0,
        icon: SourceIconMap[SourceTypeEnum.DEFAULT],
      },
    ]);
    const isEnd = shallowRef(false);
    const observer = shallowRef<IntersectionObserver>();

    const handleExpandChange = (keys: (number | string)[]) => {
      console.log(keys);
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
        sources: sourceType.value,
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

    const handleGoEvent = () => {
      emit('goEvent');
    };

    const handleSourceTypeChange = (value: (typeof SourceTypeEnum)[keyof typeof SourceTypeEnum][]) => {
      sourceType.value = value;
      isAllSourceType.value = sourceTypeOptions.value.length - 1 === value.length;
      resetData();
      handleLoad();
    };

    const handleChangeAllSourceType = (value: boolean) => {
      isAllSourceType.value = value;
      if (value) {
        sourceType.value = sourceTypeOptions.value
          .filter(item => item.value !== SourceTypeEnum.ALL)
          .map(item => item.value);
      } else {
        sourceType.value = [];
      }
      resetData();
      handleLoad();
    };

    const handleOperation = (type: EmptyStatusOperationType) => {
      if (type === 'clear-filter') {
        handleSourceTypeChange([]);
      }
    };

    onMounted(() => {
      init();
      props
        .getDataCount({
          sources: sourceTypeOptions.value.map(item => item.value).filter(item => item !== SourceTypeEnum.ALL),
        })
        .then(res => {
          const result = [];
          for (const option of sourceTypeOptions.value) {
            if (option.value === SourceTypeEnum.ALL) {
              option.count = res.total;
            } else {
              const item = res.list.find(i => i.value === option.value);
              option.count = item?.total || 0;
            }
            result.push(option);
          }
          sourceTypeOptions.value = result;
        });
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
      isAllSourceType,
      handleSortChange,
      handleExpandChange,
      t,
      handleGoEvent,
      handleSourceTypeChange,
      handleChangeAllSourceType,
      handleOperation,
    };
  },
  render() {
    const allItem = this.sourceTypeOptions.find(item => item.value === SourceTypeEnum.ALL);
    return (
      <div class='alarm-center-detail-panel-alarm-relation-event-table'>
        <div class='header-operate'>
          <span style='margin-right: 8px;'>{window.i18n.t('事件来源')}:</span>
          <Checkbox
            class='mr-24'
            modelValue={this.isAllSourceType}
            onChange={this.handleChangeAllSourceType}
          >
            <span class='source-item'>
              {allItem.icon ? <span class={`source-icon icon-monitor ${allItem.icon}`} /> : undefined}
              <span>{allItem.label}</span>
              <span>&nbsp;({allItem.count})</span>
            </span>
          </Checkbox>
          <Checkbox.Group
            class='header-operate-item'
            modelValue={this.sourceType}
            onChange={this.handleSourceTypeChange}
          >
            {{
              default: () => {
                return this.sourceTypeOptions
                  .filter(item => item.value !== SourceTypeEnum.ALL)
                  .map(item => (
                    <Checkbox
                      key={item.value}
                      label={item.value}
                    >
                      <span class='source-item'>
                        {item.icon ? <span class={`source-icon icon-monitor ${item.icon}`} /> : undefined}
                        <span>{item.label}</span>
                        <span>&nbsp;({item.count})</span>
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
                  type={this.sourceType.length ? 'search-empty' : 'empty'}
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
