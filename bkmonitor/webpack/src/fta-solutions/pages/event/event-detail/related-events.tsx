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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import dayjs from 'dayjs';

import { eventTopN, searchEvent } from '../../../../monitor-api/modules/alert';
import { xssFilter } from '../../../../monitor-common/utils/xss';
import EmptyStatus from '../../../../monitor-pc/components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../../monitor-pc/components/empty-status/types';
import { getEventPaths } from '../../../../monitor-pc/utils/index';
import { commonAlertFieldMap } from '../event';
import FilterInput from '../filter-input';
import { FilterInputStatus, SearchType } from '../typings/event';

import { IDetail } from './type';

import './related-events.scss';

// 事件状态
const statusMap = {
  RECOVERED: window.i18n.tc('已恢复'),
  ABNORMAL: window.i18n.tc('未恢复'),
  CLOSED: window.i18n.tc('已关闭')
};

// 事件级别
const levelMap = {
  1: window.i18n.tc('致命'),
  2: window.i18n.tc('预警'),
  3: window.i18n.tc('提醒')
};

/* eslint-disable camelcase */
interface IRelatedEventsProps {
  show?: boolean;
  params?: IParams;
  alertId?: number | string;
  detail: IDetail;
}
interface IParams {
  end_time: number;
  start_time: number;
}

interface IColumnItem {
  id: string;
  name: string;
  disabled: boolean;
  checked: boolean;
  props?: {
    width?: number | string;
    fixed?: 'left' | 'right';
    minWidth?: number | string;
    resizable?: boolean;
    formatter?: Function;
    sortable?: boolean | 'custom';
    showOverflowTooltip?: boolean;
  };
}

interface IEventItem {
  // 关联事件列表字段
  alert_name?: string;
  anomaly_time?: number;
  assignee?: string[] | null;
  bk_biz_id?: number;
  bk_cloud_id?: number;
  bk_ingest_time?: number;
  bk_service_instance_id?: unknown;
  bk_topo_node?: string[];
  category?: string;
  category_display?: string;
  create_time?: number;
  data_type?: string;
  description?: string;
  event_id?: string;
  id?: string;
  ip?: string;
  metric?: string[];
  plugin_id?: string;
  severity?: number;
  status?: string;
  strategy_id?: number;
  tags?: { key: string; value: string }[] | null;
  target: string;
  target_type: string;
  time: number;
}

@Component({
  name: 'RelatedEvents'
})
export default class RelatedEvents extends tsc<IRelatedEventsProps> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: [Number, String], default: 0 }) alertId: number | string;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Prop({ type: Object, default: () => ({}) }) params: IParams;
  @Ref('eventTabel') eventTabelRef;

  data = {
    events: [],
    total: 0
  };
  pagination = {
    current: 1,
    count: 0,
    limit: 10
  };

  tableColumns: IColumnItem[] = []; // 表格字段

  isLoading = true;

  queryString = '';
  searchType: SearchType = 'event';
  filterInputStatus: FilterInputStatus = 'success';
  tablePopover = null;
  filterValueMap = {};
  emptyStatusType: EmptyStatusType = 'empty';

  created() {
    this.tableColumns = [
      {
        id: 'id',
        name: this.$tc('平台事件ID'),
        checked: true,
        disabled: true,
        props: {
          width: 150,
          minWidth: 120,
          formatter: (row: IEventItem) => (
            <span
              v-bk-tooltips={{ content: row.id, placements: ['top-start'], allowHTML: false }}
              class={`event-status status-${row.severity}`}
            >
              {row.id}
            </span>
          )
        }
      },
      {
        id: 'time',
        name: window.i18n.tc('时间'),
        checked: true,
        disabled: false,
        props: {
          minWidth: 130,
          sortable: 'custom',
          formatter: (row: IEventItem) => <span>{dayjs.tz(row.time * 1000).format('YYYY-MM-DD HH:mm')}</span>
        }
      },
      {
        id: 'alert_name',
        name: window.i18n.tc('告警名称'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130
        }
      },
      {
        id: 'category',
        name: window.i18n.tc('分类'),
        checked: true,
        disabled: false,
        props: {
          sortable: 'custom',
          minWidth: 130,
          formatter: (row: IEventItem) => row.category_display
        }
      },
      {
        id: 'description',
        name: window.i18n.tc('告警内容'),
        checked: true,
        disabled: false,
        props: {
          minWidth: 200,
          showOverflowTooltip: true
        }
      },
      {
        id: 'assignee',
        name: window.i18n.tc('负责人'),
        checked: true,
        disabled: false,
        props: {
          minWidth: 130,
          sortable: 'custom',
          formatter: (row: IEventItem) => <span>{row?.assignee?.join(',') || '--'}</span>
        }
      },
      {
        id: 'tag',
        name: window.i18n.tc('维度'),
        checked: true,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) => {
            const tags = row.tags || [];
            return tags.length ? (
              <span
                v-bk-tooltips={{
                  content: tags
                    .map(item => `<span>${xssFilter(item.key)}：${xssFilter(item.value)}</span><br/>`)
                    .join(''),
                  allowHTML: true
                }}
                class='tags-items'
              >
                {tags.slice(0, 2).map(item => [<span class='tags-item'>{`${item.key}: ${item.value}`}</span>, <br />])}
              </span>
            ) : (
              '--'
            );
          }
        }
      },
      {
        id: 'event_id',
        name: window.i18n.tc('事件ID'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130
        }
      },
      {
        id: 'anomaly_time',
        name: window.i18n.tc('异常时间'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) => dayjs.tz(row.anomaly_time * 1000).format('YYYY-MM-DD HH:mm:ss')
        }
      },
      {
        id: 'status',
        name: window.i18n.tc('事件状态'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) => statusMap[row.status]
        }
      },
      {
        id: 'bk_biz_id',
        name: window.i18n.tc('空间ID'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) =>
            this.$store.getters.bizList.find(item => item.id === row?.bk_biz_id)?.space_id || row?.bk_biz_id
        }
      },
      {
        id: 'strategy_id',
        name: window.i18n.tc('策略ID'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130
        }
      },
      {
        id: 'severity',
        name: window.i18n.tc('事件级别'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) => levelMap[row.severity]
        }
      },
      {
        id: 'plugin_id',
        name: window.i18n.tc('插件ID'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130
        }
      },
      {
        id: 'metric',
        name: window.i18n.tc('指标项'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) => row.metric?.join('; ') || '--'
        }
      },
      {
        id: 'target_type',
        name: window.i18n.tc('目标类型'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) => row.target_type || '--'
        }
      },
      {
        id: 'target',
        name: window.i18n.tc('事件目标'),
        checked: false,
        disabled: false,
        props: {
          minWidth: 130,
          formatter: (row: IEventItem) => row.target || '--'
        }
      }
    ];
  }

  @Watch('show')
  handleShow(v) {
    if (v) {
      this.queryString = '';
      if (this.params.start_time !== 0) {
        this.queryString = `time: [${this.params.start_time} TO ${this.params.end_time}]`;
      }
      this.getData();
    }
  }
  /**
   * @description: 获取列表数据
   * @param {string} sort
   * @return {*}
   */
  async getData(sort: string[] = []) {
    this.isLoading = true;
    const params = {
      bk_biz_id: this.detail.bk_biz_id,
      alert_id: this.alertId,
      query_string: this.queryString,
      start_time: this.detail.begin_time,
      end_time: this.detail.end_time,
      page: this.pagination.current,
      page_size: this.pagination.limit,
      record_history: true,
      ordering: sort
    };
    this.getEventTopN(params);
    this.data = await searchEvent(params, { needRes: true })
      .then(res => {
        this.filterInputStatus = 'success';
        return (
          res.data || {
            events: [],
            total: 0
          }
        );
      })
      .catch(res => {
        this.filterInputStatus = res?.data?.code === 3324003 ? 'error' : 'success';
        return {
          events: [],
          total: 0
        };
      })
      .finally(() => {
        this.isLoading = false;
      });
    this.pagination.count = this.data.total;
    this.isLoading = false;
  }
  /**
   * @description: 搜索候选值
   * @param {*} params
   * @return {*}
   */
  getEventTopN(params) {
    const fields = [
      'plugin_id',
      'alert_name',
      'assignee',
      'strategy_id',
      'metric',
      'target_type',
      'target',
      'category'
    ];
    const valueMap = {};
    eventTopN({ ...params, fields, size: 10 }).then(data => {
      data.fields.forEach(field => {
        valueMap[field.field] = field.buckets.map(({ id, name }) => ({ id, name }));
      });
      Object.keys(commonAlertFieldMap).forEach(key => {
        valueMap[key] = commonAlertFieldMap[key];
      });
      this.filterValueMap = valueMap;
    });
  }

  /**
   * @description: 分页
   * @param {number} page
   * @return {*}
   */
  handlePageChange(page: number) {
    this.eventTabelRef.clearSort();
    this.pagination.current = page;
    this.getData();
  }

  handlePageLimitChange(limit: number) {
    this.eventTabelRef.clearSort();
    this.pagination.limit = limit;
    this.getData();
  }

  /**
   * @description: 搜索
   * @param {string} v
   * @return {*}
   */
  handleQueryStringChange(v: string) {
    const isChange = v !== this.queryString;
    if (isChange) {
      this.emptyStatusType = isChange ? 'search-empty' : 'empty';
      this.queryString = v;
      this.pagination.current = 1;
      this.getData();
    }
  }
  /**
   * @description: 排序
   * @param {object} obj
   * @return {*}
   */
  handleSortChange(obj: { column: any; prop: string; order: string }) {
    let sort = [];
    const sortType = ['ascending', 'descending'];
    if (sortType[0] === obj.order) {
      sort.push(`${obj.prop}`);
    } else if (sortType[1] === obj.order) {
      sort.push(`-${obj.prop}`);
    } else {
      sort = [];
    }
    this.getData(sort);
  }

  // 移入
  handleRowEnter(event, tip) {
    this.handleRowLeave();
    this.tablePopover =
      this.tablePopover ||
      this.$bkPopover(event.target, { content: tip, arrow: true, boundary: 'window', placement: 'top' });
    this.tablePopover?.show(100);
  }
  // 移出
  handleRowLeave() {
    this.tablePopover?.destroy();
    this.tablePopover = null;
  }

  /**
   * @description: 表格展开数据
   * @param {*} child
   * @return {*}
   */
  getChildSlotsComponent(child) {
    const arrayTip = (arr: Array<string>) => arr?.map(item => `<div>${item}</div>`).join('') || '';
    const { bizList } = this.$store.getters;
    const spaceId = bizList.find(item => item.bk_biz_id === child.bk_biz_id)?.space_id || child.bk_biz_id;
    const topItems = [
      {
        children: [
          { title: this.$t('事件ID'), content: `${child.event_id}` },
          { title: this.$t('异常时间'), content: dayjs.tz(child.anomaly_time * 1000).format('YYYY-MM-DD HH:mm:ss') }
        ]
      },
      {
        children: [
          { title: this.$t('告警名称'), content: child.alert_name },
          { title: this.$t('事件状态'), content: `${statusMap[child.status]}` }
        ]
      },
      {
        children: [
          { title: this.$t('分类'), content: child.category_display },
          { title: this.$t('空间ID'), content: spaceId }
        ]
      },
      {
        children: [
          { title: this.$t('告警内容'), content: child.description },
          { title: this.$t('策略ID'), content: child.strategy_id || '--' }
        ]
      },
      {
        children: [
          { title: this.$t('负责人'), content: child?.assignee?.join(',') || '--' },
          { title: this.$t('平台事件ID'), content: child.id }
        ]
      },
      {
        children: [
          { title: this.$t('事件级别'), content: `${levelMap[child.severity]}` },
          { title: this.$t('插件ID'), content: child.plugin_id }
        ]
      },
      {
        children: [
          { title: this.$t('事件时间'), content: dayjs.tz(child.time * 1000).format('YYYY-MM-DD HH:mm:ss') },
          {
            title: <span>{this.$t('维度')}</span>,
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
                    disabled: (child.tags?.length || 0) <= 4
                  }}
                >
                  {(child.tags.slice(0, 4) || []).map((item, index) => (
                    <div
                      class='content-kv-item'
                      key={index}
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
            )
          }
        ]
      }
    ];
    const bottomItems = [
      {
        title: this.$t('指标项'),
        content: child.metric?.join('; ') || '--',
        extCls: 'metric-items',
        tip: arrayTip(child.metric) || ''
      },
      { title: this.$t('目标类型'), content: child.target_type || '--' },
      { title: this.$t('事件目标'), content: child.target || '--' }
    ];
    return (
      <div class='detail-form'>
        <div class='detail-form-top'>
          {topItems.map(child => (
            <div class='top-form-item'>
              {child.children.map(item => (
                <div class='item-col'>
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
              class='item-col'
              key={index}
            >
              <div class='item-label'>{item.title}</div>
              <div
                class={['item-content', item?.extCls]}
                onMouseover={e => item.tip && this.handleRowEnter(e, item.tip)}
                onMouseout={this.handleRowLeave}
              >
                {item.content}
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  /**
   * @description: 表格
   * @param {*}
   * @return {*}
   */
  getTableComponent() {
    const childSlots = {
      default: props => this.getChildSlotsComponent(props.row)
    };

    const handleRowClick = (row, event) => {
      const path = getEventPaths(event);
      const expandDom = path.find(item => item.className.includes('bk-table-row'));
      expandDom.firstChild.querySelector('.bk-table-expand-icon').click();
    };

    return (
      <bk-table
        {...{
          props: {
            data: this.data.events,
            size: 'large'
          }
        }}
        outer-border={false}
        header-border={false}
        header-cell-style={{ background: '#f5f6fa' }}
        pagination={this.pagination}
        ref='eventTabel'
        class='related-events-table'
        on-row-click={handleRowClick}
        on-page-change={this.handlePageChange}
        on-page-limit-change={this.handlePageLimitChange}
        on-sort-change={this.handleSortChange}
      >
        <EmptyStatus
          type={this.emptyStatusType}
          slot='empty'
          onOperation={this.handleOperation}
        />
        <bk-table-column
          type='expand'
          width={30}
          scopedSlots={childSlots}
        ></bk-table-column>
        {this.tableColumns.map(column => {
          if (!(column.disabled || column.checked)) return undefined;
          return (
            <bk-table-column
              key={`${column.id}`}
              label={column.name}
              prop={column.id}
              formatter={row => (!row[column.id] && row[column.id] !== 0 ? '--' : row[column.id])}
              {...{ props: column.props }}
            />
          );
        })}
      </bk-table>
    );
  }

  handleCheckColChange(item) {
    const filter = this.tableColumns.find(f => f.id === item.id);
    filter.checked = !item.checked;
  }

  /**
   * @description: 筛选弹窗
   * @param {*}
   * @return {*}
   */
  getRelatedeventsSettingComponent() {
    return (
      <div class='relatedevents-filter-btn'>
        <bk-popover
          placement='bottom-end'
          width='515'
          theme='light strategy-setting'
          trigger='click'
          offset='0, 10'
        >
          <div class='filter-btn'>
            <span class='icon-monitor icon-menu-set'></span>
          </div>
          <div
            slot='content'
            class='relatedevents-tool-popover'
          >
            <div class='tool-popover-title'>{this.$t('字段显示设置')}</div>
            <ul class='tool-popover-content'>
              {this.tableColumns.map(item => (
                <li
                  key={item.id}
                  class='tool-popover-content-item'
                >
                  <bk-checkbox
                    value={item.checked}
                    on-change={() => this.handleCheckColChange(item)}
                    disabled={item.disabled}
                  >
                    {item.name}
                  </bk-checkbox>
                </li>
              ))}
            </ul>
          </div>
        </bk-popover>
      </div>
    );
  }

  handleOperation(val: EmptyStatusOperationType) {
    if (val === 'clear-filter') this.queryString = '';
    this.getData();
  }

  render() {
    return (
      <div
        class={['event-detail-relatedevents', { displaynone: !this.show }]}
        v-bkloading={{ isLoading: this.isLoading }}
      >
        <FilterInput
          value={this.queryString}
          searchType={this.searchType}
          inputStatus={this.filterInputStatus}
          valueMap={this.filterValueMap}
          isFillId={true}
          on-change={this.handleQueryStringChange}
          on-clear={this.handleQueryStringChange}
        ></FilterInput>
        <div class='events-table-container'>
          {this.getRelatedeventsSettingComponent()}
          {this.getTableComponent()}
        </div>
      </div>
    );
  }
}
