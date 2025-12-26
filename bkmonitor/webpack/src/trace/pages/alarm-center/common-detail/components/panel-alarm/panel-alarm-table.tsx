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
import { defineComponent, reactive, shallowRef } from 'vue';

import { type TableSort, PrimaryTable } from '@blueking/tdesign-ui';
import dayjs from 'dayjs';
import { xssFilter } from 'monitor-common/utils';
import { useI18n } from 'vue-i18n';

import { useAppStore } from '@/store/modules/app';

import './panel-alarm-table.scss';

// 事件状态
const statusMap = {
  RECOVERED: window.i18n.t('已恢复'),
  ABNORMAL: window.i18n.t('未恢复'),
  CLOSED: window.i18n.t('已失效'),
};

// 事件级别
const levelMap = {
  1: window.i18n.t('致命'),
  2: window.i18n.t('预警'),
  3: window.i18n.t('提醒'),
};
export default defineComponent({
  name: 'PanelAlarmTable',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['sortChange'],
  setup(_, { emit }) {
    const appStore = useAppStore();
    const { t } = useI18n();
    /** 当前展开的行 */
    const expandedRowKeys = shallowRef([]);
    /** 列配置 */
    const columns = [
      {
        colKey: 'id',
        title: t('平台事件ID'),
        width: 180,
        minWidth: 150,
        cell: (_h, { row }) => (
          <div class='event-id'>
            <span
              class={[
                'icon-monitor icon-mc-arrow-right table-expand-icon',
                { 'rotate-90': expandedRowKeys.value.includes(row.id) },
              ]}
            />
            <span
              class={`event-status status-${row.severity}`}
              v-overflow-tips={{ content: row.id, placements: ['top'], allowHTML: false }}
            >
              {row.id}
            </span>
          </div>
        ),
      },
      {
        colKey: 'time',
        title: t('时间'),
        minWidth: 130,
        sorter: true,
        cell: (_h, { row }) => <span class='cell'>{dayjs.tz(row.time * 1000).format('YYYY-MM-DD HH:mm')}</span>,
      },
      {
        colKey: 'alert_name',
        title: t('告警名称'),
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{row.alert_name}</span>,
      },
      {
        colKey: 'category',
        title: t('分类'),
        sorter: true,
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{row.category_display}</span>,
      },
      {
        colKey: 'description',
        title: t('告警内容'),
        minWidth: 200,
        cell: (_h, { row }) => (
          <span
            class='cell'
            v-bk-tooltips={{ content: row.description, extCls: 'mw400' }}
          >
            {row.description}
          </span>
        ),
      },
      {
        colKey: 'assignee',
        title: t('负责人'),
        sorter: true,
        minWidth: 130,
        cell: (_h, { row }) => (
          <span class='cell'>
            {row?.assignee?.length
              ? row?.assignee.map((v, index, arr) => [
                  <bk-user-display-title
                    key={`user-display-${v}`}
                    user-id={v}
                  />,
                  index !== arr.length - 1 ? <span key={`span-colon-${v}`}>{','}</span> : null,
                ])
              : '--'}
          </span>
        ),
      },
      {
        colKey: 'tag',
        title: t('维度'),
        minWidth: 130,
        cell: (_h, { row }) => {
          const tags = row.tags || [];
          return tags.length ? (
            <span class='cell'>
              <span
                class='tags-items'
                v-bk-tooltips={{
                  content: () => (
                    <div>
                      {tags.map(item => (
                        <div key={`${item.key}_${item.value}`}>
                          {xssFilter(item.key)}：{xssFilter(item.value)}
                        </div>
                      ))}
                    </div>
                  ),
                }}
              >
                {tags.slice(0, 2).map(item => (
                  <div
                    key={`${item.key}_${item.value}`}
                    class='tags-item'
                  >{`${item.key}: ${item.value}`}</div>
                ))}
              </span>
            </span>
          ) : (
            '--'
          );
        },
      },
      {
        colKey: 'event_id',
        title: t('事件ID'),
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{row.event_id}</span>,
      },
      {
        colKey: 'anomaly_time',
        title: t('异常时间'),
        minWidth: 130,
        cell: (_h, { row }) => (
          <span class='cell'>{dayjs.tz(row.anomaly_time * 1000).format('YYYY-MM-DD HH:mm:ss')}</span>
        ),
      },
      {
        colKey: 'status',
        title: t('事件状态'),
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{statusMap[row.status]}</span>,
      },
      {
        colKey: 'bk_biz_id',
        title: t('空间ID'),
        minWidth: 130,
        cell: (_h, { row }) => (
          <span class='cell'>
            {appStore.bizList.find(item => item.id === row?.bk_biz_id)?.space_id || row?.bk_biz_id}
          </span>
        ),
      },
      {
        colKey: 'strategy_id',
        title: t('策略ID'),
        minWidth: 130,
      },
      {
        colKey: 'severity',
        title: t('事件级别'),
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{levelMap[row.severity]}</span>,
      },
      {
        colKey: 'plugin_id',
        title: t('插件ID'),
        minWidth: 130,
      },
      {
        colKey: 'metric',
        title: t('指标项'),
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{row.metric?.join('; ') || '--'}</span>,
      },
      {
        colKey: 'target_type',
        title: t('目标类型'),
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{row.target_type || '--'}</span>,
      },
      {
        colKey: 'target',
        title: t('事件目标'),
        minWidth: 130,
        cell: (_h, { row }) => <span class='cell'>{row.target || '--'}</span>,
      },
    ];

    const tableSettings = reactive({
      hasCheckAll: false,
      checked: ['id', 'time', 'category', 'description', 'assignee', 'tag'],
      fields: columns.map(item => ({
        field: item.colKey,
        label: item.title,
      })),
      disabled: ['id'],
    });

    /** 表格行展开 */
    const handleExpandChange = keys => {
      expandedRowKeys.value = keys;
    };

    /** 排序功能 */
    const handleSortChange = (sortEvent: TableSort) => {
      if (Array.isArray(sortEvent)) {
        // 处理数组形式的排序
        const sortStrings = sortEvent
          .filter(item => item?.sortBy)
          .map(item => `${item.descending ? '-' : ''}${item.sortBy}`);
        emit('sortChange', sortStrings);
        return;
      }

      let sort = '';
      if (sortEvent?.sortBy) {
        sort = `${sortEvent.descending ? '-' : ''}${sortEvent.sortBy}`;
      }
      emit('sortChange', sort ? [sort] : []);
    };

    const getChildSlotsComponent = child => {
      const arrayTip = (arr: Array<string>) => arr?.map(item => `<div>${item}</div>`).join('') || '';
      const { bizList } = appStore;
      const spaceId = bizList.find(item => item.bk_biz_id === child.bk_biz_id)?.space_id || child.bk_biz_id;
      const topItems = [
        {
          children: [
            { title: t('事件ID'), content: `${child.event_id}` },
            { title: t('异常时间'), content: dayjs.tz(child.anomaly_time * 1000).format('YYYY-MM-DD HH:mm:ss') },
          ],
        },
        {
          children: [
            { title: t('告警名称'), content: child.alert_name },
            { title: t('事件状态'), content: `${statusMap[child.status]}` },
          ],
        },
        {
          children: [
            { title: t('分类'), content: child.category_display },
            { title: t('空间ID'), content: spaceId },
          ],
        },
        {
          children: [
            { title: t('告警内容'), content: child.description },
            { title: t('策略ID'), content: child.strategy_id || '--' },
          ],
        },
        {
          children: [
            {
              title: t('负责人'),
              content: child?.assignee?.length
                ? child?.assignee.map((v, index, arr) => [
                    <bk-user-display-name
                      key={`user-display-${v}`}
                      user-id={v}
                    />,
                    index !== arr.length - 1 ? <span key={`span-colon-${v}`}>{','}</span> : null,
                  ])
                : '--',
            },
            { title: t('平台事件ID'), content: child.id },
          ],
        },
        {
          children: [
            { title: t('事件级别'), content: `${levelMap[child.severity]}` },
            { title: t('插件ID'), content: child.plugin_id },
          ],
        },
        {
          children: [
            { title: t('事件时间'), content: dayjs.tz(child.time * 1000).format('YYYY-MM-DD HH:mm:ss') },
            {
              title: <span>{t('维度')}</span>,
              content: child.tags?.length ? (
                <div class='item-content-kv'>
                  <div
                    class='item-content-kv-tip'
                    v-bk-tooltips={{
                      content:
                        child.tags
                          ?.map(item => `<span>${xssFilter(item.key)}：${xssFilter(item.value)}</span><br/>`)
                          ?.join('') || '',
                      allowHTML: true,
                      disabled: (child.tags?.length || 0) <= 4,
                    }}
                  >
                    {(child.tags.slice(0, 4) || []).map((item, index) => (
                      <div
                        key={index}
                        class='content-kv-item'
                      >
                        <span class='kv-item-key'>{`${item.key}`}：</span>
                        <span class='kv-item-value'>
                          {`${item.value}`}
                          {index === 3 && child.tags.length > 4 ? '   ...' : undefined}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                '--'
              ),
            },
          ],
        },
      ];
      const bottomItems = [
        {
          title: t('指标项'),
          content: child.metric?.join('; ') || '--',
          extCls: 'metric-items',
          tip: arrayTip(child.metric) || '',
        },
        { title: t('目标类型'), content: child.target_type || '--' },
        { title: t('事件目标'), content: child.target || '--' },
      ];
      return (
        <div class='detail-form'>
          <div class='detail-form-top'>
            {topItems.map((child, index) => (
              <div
                key={index}
                class='top-form-item'
              >
                {child.children.map(item => (
                  <div
                    key={item.title}
                    class='item-col'
                  >
                    <div class='item-label'>{item.title}</div>
                    <div class='item-content'>{item.content}</div>
                  </div>
                ))}
              </div>
            ))}
          </div>
          <div class='detail-form-bottom'>
            {bottomItems.map((item, index) => (
              <div
                key={index}
                class='item-col'
              >
                <div class='item-label'>{item.title}</div>
                <div
                  class={['item-content', item?.extCls]}
                  // onMouseout={this.handleRowLeave}
                  // onMouseover={e => item.tip && this.handleRowEnter(e, item.tip)}
                >
                  {item.content}
                </div>
              </div>
            ))}
          </div>
        </div>
      );
    };

    return {
      tableSettings,
      columns,
      expandedRowKeys,
      handleExpandChange,
      handleSortChange,
      getChildSlotsComponent,
    };
  },
  render() {
    return (
      <PrimaryTable
        class='panel-alarm-table'
        v-slots={{
          empty: this.$slots.empty,
          expandedRow: ({ row }) => {
            return this.getChildSlotsComponent(row);
          },
        }}
        bkUiSettings={this.tableSettings}
        bordered={false}
        columns={this.columns}
        data={this.data}
        expandedRowKeys={this.expandedRowKeys}
        expandIcon={false}
        expandOnRowClick={true}
        loading={this.loading}
        maxHeight={600}
        needCustomScroll={false}
        rowClassName='panel-alarm-table-row'
        rowKey={'id'}
        resizable
        onExpandChange={this.handleExpandChange}
        onSortChange={this.handleSortChange}
      />
    );
  },
});
