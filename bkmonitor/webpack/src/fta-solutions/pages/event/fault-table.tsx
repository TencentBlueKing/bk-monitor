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

/* eslint-disable no-case-declarations */
import { TranslateResult } from 'vue-i18n';
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Button, Checkbox, Pagination, Popover, Table, TableColumn, TableSettingContent } from 'bk-magic-vue';
import moment from 'moment';

import { checkAllowedByActionIds } from '../../../monitor-api/modules/iam';
import { random } from '../../../monitor-common/utils/utils';
import authorityStore from '../../../monitor-pc/store/modules/authority';
import { transformLogUrlQuery } from '../../../monitor-pc/utils';

import { handleToAlertList } from './event-detail/action-detail';
import { TType as TSliderType } from './event-detail/event-detail-slider';
import { getStatusInfo } from './event-detail/type';
import { eventPanelType, IEventItem, IPagination, SearchType } from './typings/event';

import './fault-table.scss';

const alertStoreKey = '__ALERT_EVENT_COLUMN__';
const actionStoreKey = '__ACTION_EVENT_COLUMN__';
type TableSizeType = 'small' | 'medium' | 'large';
interface IEventTableProps {
  tableData: IEventItem[];
  pagination: IPagination;
  loading?: boolean;
  searchType: SearchType;
  bizIds: number[];
  doLayout: eventPanelType;
  selectedList?: string[];
}
interface IEventStatusMap {
  color: string;
  bgColor: string;
  name: string | TranslateResult;
}
interface IColumnItem {
  id: string;
  name: TranslateResult | string;
  disabled: boolean;
  checked: boolean;
  props?: {
    width?: number | string;
    fixed?: 'left' | 'right';
    minWidth?: number | string;
    resizable?: boolean;
    formatter?: Function;
    sortable?: boolean | 'curstom';
  };
}
interface IEventTableEvent {
  onPageChange: number;
  onLimitChange: number;
  onShowDetail?: { id: string; type: TSliderType };
  onSelectChange: string[];
  onAlertConfirm?: IEventItem;
  onQuickShield?: IEventItem;
  onSortChange: string;
  onBatchSet: string;
  onManualProcess?: IEventItem;
  onChatGroup?: IEventItem;
  onAlarmDispatch?: IEventItem;
}

export interface IShowDetail {
  id: string;
  bizId: number;
  type: TSliderType;
  activeTab?: string;
}
@Component({
  components: { Popover, Pagination, Checkbox }
})
export default class EventTable extends tsc<IEventTableProps, IEventTableEvent> {
  @Prop({ required: true }) tableData: IEventItem[];
  @Prop({ required: true }) pagination: IPagination;
  @Prop({ default: false }) loading: boolean;
  @Prop({ default: () => [] }) bizIds: number[];
  @Prop({ type: String }) doLayout: eventPanelType;
  @Prop({ required: true, type: String }) searchType: SearchType;
  @Prop({ type: Array, default: () => [] }) selectedList: string[];

  @Ref('table') tableRef: Table;
  @Ref('moreItems') moreItemsRef: HTMLDivElement;

  eventStatusMap: Record<string, IEventStatusMap> = {};
  actionStatusColorMap: Record<string, string> = {
    running: '#A3C4FD',
    success: '#8DD3B5',
    failure: '#F59E9E',
    skipped: '#FED694',
    shield: '#CBCDD2'
  };
  actionStatusMap: Record<string, TranslateResult> = {};
  hoverRowIndex = -1;
  tableSize: TableSizeType = 'medium';
  tableKey: string = random(10);
  extendInfoMap: Record<string, TranslateResult>;
  popoperInstance: any = null;
  selectedCount = 0;
  tableToolList: {
    id: string;
    name: TranslateResult | string;
  }[];
  /* 状态栏更多操作按钮 */
  popoperOperateInstance: any = null;
  popoperOperateIndex = -1;
  opetateRow = null;
  enableCreateChatGroup = false;
  /**
   * @description: 处理记录列表字段
   * @param {*}
   * @return {*}
   */
  get tableColumn(): IColumnItem[] {
    return (
      [
        {
          id: 'incident_id',
          name: 'ID',
          checked: false,
          disabled: true,
          props: {
            width: 160,
            minWidth: 160
          }
        },
        {
          id: 'incident_name',
          name: this.$t('故障名称'),
          checked: true,
          disabled: true,
          props: {
            width: 180,
            minWidth: 180,
            // sortable: 'curstom',
            showOverflowTooltip: true
          }
        },
        {
          id: 'status',
          name: this.$t('故障状态'),
          checked: true,
          disabled: true,
          props: {
            width: 130,
            // sortable: 'curstom',
            formatter: (row: IEventItem) => {
              const statusInfo = getStatusInfo(row.status, row.level);
              return (
                <span
                  v-bk-overflow-tips
                  class={['action-status', statusInfo.status]}
                >
                  {statusInfo.text || '--'}
                </span>
              );
            }
          }
        },
        {
          id: 'alert_count',
          name: this.$t('告警数量'),
          checked: true,
          disabled: true,
          props: {
            width: 120,
            minWidth: 120
            // sortable: 'curstom'
          }
        },
        {
          id: 'labels',
          name: this.$t('标签'),
          disabled: false,
          checked: true,
          props: {
            width: 200,
            minWidth: 200,
            formatter: (row: IEventItem) =>
              row.labels?.map(item => <span class='tag-item'>{item.key ? `${item.key}: ${item.value}` : item}</span>) ||
              '--'
          }
        },
        {
          id: 'end_time',
          name: this.$t('开始时间 / 结束时间'),
          checked: true,
          disabled: false,
          props: {
            width: 174,
            minWidth: 150,
            // sortable: 'curstom',
            formatter: (row: IEventItem) => {
              console.log(row);
              return (
                <span>
                  {this.formatterTime(row.begin_time)}/<br></br>
                  {this.formatterTime(row.end_time)}
                </span>
              );
            }
          }
        },
        {
          id: 'duration',
          name: this.$t('持续时间'),
          disabled: true,
          checked: false,
          props: {
            // sortable: 'curstom'
          }
        },
        {
          id: 'assignee',
          name: this.$t('负责人'),
          checked: true,
          disabled: false,
          props: {
            width: 220,
            minWidth: 220,
            formatter: (row: IEventItem) =>
              // 去重
              row?.assignee
                ?.filter((value, index, self) => {
                  return self.indexOf(value) === index;
                })
                ?.map(name => (
                  <span
                    key={name}
                    class='tag-item'
                  >
                    {name}
                  </span>
                )) || '--'
          }
        },
        {
          id: 'incident_reason',
          name: this.$t('故障原因'),
          checked: true,
          disabled: false,
          props: {
            showOverflowTooltip: true,
            formatter: (row: IEventItem) => row.description // row.content.text || '--'
          }
        }
      ] as IColumnItem[]
    ).filter(Boolean);
  }
  @Watch('doLayout')
  handleDolayoutChange(v: eventPanelType) {
    v === 'list' && this.tableRef?.doLayout?.();
  }
  /**
   * @description: 初始化
   * @param {*}
   * @return {*}
   */
  created() {
    this.eventStatusMap = {
      ABNORMAL: {
        color: '#EA3536',
        bgColor: '#FEEBEA',
        name: this.$t('未恢复'),
        icon: 'icon-mind-fill'
      },
      RECOVERED: {
        color: '#14A568',
        bgColor: '#E4FAF0',
        name: this.$t('已恢复')
      },
      CLOSED: {
        color: '#63656E',
        bgColor: '#F0F1F5',
        name: this.$t('已关闭')
      }
    };
    this.extendInfoMap = {
      log_search: this.$t('查看更多相关的日志'),
      custom_event: this.$t('查看更多相关的事件'),
      bkdata: this.$t('查看更多相关的数据')
    };
    this.tableToolList = [
      {
        id: 'comfirm',
        name: this.$t('批量确认')
      },
      {
        id: 'shield',
        name: this.$t('批量屏蔽')
      },
      {
        id: 'dispatch',
        name: this.$t('批量分派')
      }
      // {
      //   id: 'custom',
      //   name: this.$t('批量手动处理')
      // }
    ];
    this.actionStatusMap = {
      running: this.$t('执行中'),
      success: this.$t('成功'),
      failure: this.$t('失败'),
      skipped: this.$t('已收敛'),
      shield: this.$t('已屏蔽')
    };

    // 是否支持一键拉群 todo
    this.enableCreateChatGroup = window.enable_create_chat_group || false;
    if (this.enableCreateChatGroup) {
      this.tableToolList.push({
        id: 'chat',
        name: this.$t('一键拉群')
      });
    }
  }
  beforeDestroy() {
    this.handlePopoverHide();
  }

  /**
   * @description: 展示处理记录及告警详情
   * @param {*}
   * @return {*}
   */
  @Emit('showDetail')
  handleShowDetail(item: IEventItem, activeTab = ''): IShowDetail {
    const typeMap = {
      alert: 'eventDetail',
      action: 'handleDetail'
    };
    return {
      id: item.id,
      bizId: item.bk_biz_id,
      type: typeMap[this.searchType],
      activeTab
    };
  }
  /**
   * @description: 分页
   * @param {*}
   * @return {*}
   */
  @Emit('pageChange')
  handlePageChange(page: number) {
    return page;
  }
  @Emit('limitChange')
  handlePageLimitChange(limit: number) {
    return limit;
  }

  @Emit('selectChange')
  handleSelectChange(selectList: IEventItem[]) {
    this.selectedCount = selectList?.length || 0;
    return selectList.map(item => item.id);
  }

  @Emit('alarmDispatch')
  handleAlarmDispatch(v) {
    return v;
  }
  /**
   * @description: 关联信息跳转
   * @param {Record} extendInfo
   * @param {*} any
   * @param {string} bizId
   * @return {*}
   */
  handleGotoMore(extendInfo: Record<string, any>, bizId: string) {
    const origin = process.env.NODE_ENV === 'development' ? process.env.proxyUrl : location.origin;
    switch (extendInfo.type) {
      // 监控主机监控详情
      case 'host':
        const detailId =
          extendInfo.bk_host_id ??
          `${extendInfo.ip}-${extendInfo.bk_cloud_id === undefined ? 0 : extendInfo.bk_cloud_id}`;
        window.open(
          `${origin}${location.pathname.toString().replace('fta/', '')}?bizId=${bizId}#/performance/detail/${detailId}`,
          '__blank'
        );
        return;
      // 监控数据检索
      case 'bkdata':
        const targets = [{ data: { query_configs: extendInfo.query_configs } }];
        window.open(
          `${origin}${location.pathname
            .toString()
            .replace('fta/', '')}?bizId=${bizId}#/data-retrieval/?targets=${JSON.stringify(targets)}`,
          '__blank'
        );
        return;
      // 日志检索
      case 'log_search':
        const retrieveParams = {
          // 检索参数
          bizId,
          keyword: extendInfo.query_string, // 搜索关键字
          addition: extendInfo.agg_condition || []
        };
        const queryStr = transformLogUrlQuery(retrieveParams);
        const url = `${this.$store.getters.bkLogSearchUrl}#/retrieve/${extendInfo.index_set_id}${queryStr}`;
        window.open(url);
        return;
      // 监控自定义事件
      case 'custom_event':
        const id = extendInfo.bk_event_group_id;
        window.open(
          `${origin}${location.pathname
            .toString()
            .replace('fta/', '')}?bizId=${bizId}#/custom-escalation-detail/event/${id}`,
          '__blank'
        );
        return;
    }
  }
  /** 关联信息提示信息 */
  handleExtendInfoEnter(e, info) {
    let tplStr = '--';
    switch (info.type) {
      case 'host':
        tplStr = `<div class="extend-content">${this.$t('主机名:')}${info.hostname || '--'}</div>
            <div class="extend-content">
              <span class="extend-content-message">${this.$t('节点信息:')}${info.topo_info || '--'}</span>
            </div>
          `;
        break;
      case 'log_search':
      case 'custom_event':
      case 'bkdata':
        tplStr = `<span class="extend-content-link">
            ${this.extendInfoMap[info.type] || '--'}
          </span>`;
        break;
      default:
        break;
    }
    this.handlePopoverShow(e, tplStr);
  }
  /**
   * @description: 关联信息组件
   * @param {Record} extendInfo
   * @param {*} string
   * @param {string} bizId
   * @return {*}
   */
  getExtendInfoColumn(extendInfo: Record<string, string>, bizId: string) {
    switch (extendInfo.type) {
      case 'host':
        return [
          <div class='extend-content'>{`${this.$t('主机名:')}${extendInfo.hostname || '--'}`}</div>,
          <div class='extend-content'>
            <span class='extend-content-message'>{`${this.$t('节点信息:')}${extendInfo.topo_info || '--'}`}</span>
            <span
              class='extend-content-link link-more'
              onClick={() => this.handleGotoMore(extendInfo, bizId)}
            >
              {this.$t('更多')}
            </span>
          </div>
        ];
      case 'log_search':
      case 'custom_event':
      case 'bkdata':
        return (
          <span
            class='extend-content-link'
            onClick={() => this.handleGotoMore(extendInfo, bizId)}
          >
            {this.extendInfoMap[extendInfo.type] || '--'}
          </span>
        );
    }
    return '--';
  }
  // 跳转关联事件
  handleClickEventCount(item: IEventItem) {
    this.handleShowDetail(item, 'relatedEvents');
  }
  /**
   * @description: 跳转到告警列表
   * @param {string} id
   * @return {*}
   */
  handleClickActionCount(type: 'trigger' | 'defense', row: IEventItem) {
    // const data = { queryString: `action_id : ${id}`, timeRange }
    const { id, create_time: createTime, end_time: endTime } = row;
    handleToAlertList(
      type,
      {
        create_time: createTime,
        end_time: endTime,
        id
      },
      row.bk_biz_id || this.$store.getters.bizId
    );
  }
  // 时间格式化
  formatterTime(time: number | string): string {
    if (!time) return '--';
    if (typeof time !== 'number') return time;
    if (time.toString().length < 13) return moment(time * 1000).format('YYYY-MM-DD HH:mm:ss');
    return moment(time).format('YYYY-MM-DD HH:mm:ss');
  }

  handleDescEnter(e: MouseEvent, dimensions, description) {
    this.handlePopoverShow(
      e,
      [
        `<div class="dimension-desc">${this.$t('维度信息')}：${
          dimensions?.map?.(item => `${item.display_key || item.key}(${item.display_value || item.value})`).join('-') ||
          '--'
        }</div>`,
        `<div class="description-desc">${this.$t('告警内容')}：${description || '--'}</div>`
      ]
        .filter(Boolean)
        .join('')
    );
  }
  /**
   * @description: 展开
   * @param {MouseEvent} e
   * @param {string} content
   * @return {*}
   */
  handlePopoverShow(e: MouseEvent, content: string) {
    this.popoperInstance = this.$bkPopover(e.target, {
      content,
      maxWidth: 320,
      arrow: true,
      boundary: 'window'
    });
    this.popoperInstance?.show?.(100);
  }

  /**
   * @description: 清除popover
   * @param {*}
   * @return {*}
   */
  handlePopoverHide() {
    this.popoperInstance?.hide?.(0);
    this.popoperInstance?.destroy?.();
    this.popoperInstance = null;
  }

  /**
   * @description: 排序
   * @param {*}
   * @return {*}
   */
  @Emit('sortChange')
  handleSortChange({ prop, order }) {
    let key = prop;
    if (prop === 'action_plugin_type_display') {
      key = 'action_plugin_type';
    }
    if (order === 'ascending') return key;
    if (order === 'descending') return `-${key}`;
    return '';
  }

  handleRenderIdColumn(column) {
    return (
      <TableColumn
        key={`${this.searchType}_${column.id}`}
        label={column.name}
        prop={column.id}
        {...{ props: column.props }}
        scopedSlots={{
          default: ({ row }: { row: IEventItem }) => (
            <span
              class={`event-status status-${row.severity} id-column`}
              v-bk-overflow-tips
              onClick={() => this.handleShowDetail(row)}
            >
              {row.id}
            </span>
          )
        }}
      />
    );
  }
  handleRenderDefaultColumn(column) {
    return (
      <TableColumn
        key={`${this.searchType}_${column.id}`}
        label={column.name}
        prop={column.id}
        formatter={row => (!row[column.id] && row[column.id] !== 0 ? '--' : row[column.id])}
        {...{ props: column.props }}
      />
    );
  }
  handleRenderStatus(column) {
    return (
      <TableColumn
        class-name='status-cell'
        key={`${this.searchType}_${column.id}`}
        label={column.name}
        prop={column.id}
        {...{ props: column.props }}
        scopedSlots={{
          default: ({ row: { status } }) => (
            <div class='status-column'>
              <span
                class='status-label'
                style={{
                  color: this.eventStatusMap?.[status]?.color,
                  backgroundColor: this.eventStatusMap?.[status]?.bgColor
                }}
              >
                {this.eventStatusMap?.[status]?.icon ? (
                  <i
                    class={['icon-monitor item-icon', this.eventStatusMap?.[status]?.icon ?? '']}
                    style={{ color: this.eventStatusMap?.[status]?.color }}
                  ></i>
                ) : (
                  ''
                )}
                {this.eventStatusMap?.[status]?.name || '--'}
              </span>
            </div>
          )
        }}
      />
    );
  }
  handleRenderAlarmCount(column) {
    return (
      <TableColumn
        key={`${this.searchType}_${column.id}`}
        label={column.name}
        prop={column.id}
        {...{ props: column.props }}
        scopedSlots={{
          default: ({ row }: { row: IEventItem }) =>
            row.event_count > -1 ? (
              <Button
                onClick={() => this.handleClickEventCount(row)}
                text={true}
              >
                {row.event_count}
              </Button>
            ) : (
              '--'
            )
        }}
      />
    );
  }
  // 表格column设置
  handleGetColumns() {
    const columList = [];
    return columList.concat(
      ...this.tableColumn.map(column => {
        if (!(column.disabled || column.checked)) return undefined;

        switch (column.id) {
          case 'id':
            return this.handleRenderIdColumn(column);
            break;
          case 'status':
            return this.handleRenderStatus(column);
            break;
          case 'alert_count':
            return this.handleRenderAlarmCount(column);
            break;
          default: {
            return this.handleRenderDefaultColumn(column);
          }
        }

        if (this.searchType === 'alert') {
          // 告警id
          if (column.id === 'id') {
            return (
              <TableColumn
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row }: { row: IEventItem }) => (
                    <span
                      class={`event-status status-${row.severity} id-column`}
                      v-bk-overflow-tips
                      onClick={() => this.handleShowDetail(row)}
                    >
                      {row.id}
                    </span>
                  )
                }}
              />
            );
          }
          // 告警状态
          if (column.id === 'status') {
            return (
              <TableColumn
                class-name='status-cell'
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row: { status } }) => (
                    <div class='status-column'>
                      <span
                        class='status-label'
                        style={{
                          color: this.eventStatusMap?.[status]?.color,
                          backgroundColor: this.eventStatusMap?.[status]?.bgColor
                        }}
                      >
                        {this.eventStatusMap?.[status]?.name || '--'}
                      </span>
                    </div>
                  )
                }}
              />
            );
          }
          // 关联信息
          if (column.id === 'extend_info') {
            return (
              <TableColumn
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row: { extend_info: info, bk_biz_id: bizId } }: { row: IEventItem }) => (
                    <div
                      class='extend-column'
                      onMouseenter={e => this.handleExtendInfoEnter(e, info)}
                      onMouseleave={this.handlePopoverHide}
                    >
                      {info?.type ? this.getExtendInfoColumn(info, bizId.toString()) : '--'}
                    </div>
                  )
                }}
              />
            );
          }
          if (column.id === 'event_count') {
            return (
              <TableColumn
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row }: { row: IEventItem }) =>
                    row.event_count > -1 ? (
                      <Button
                        onClick={() => this.handleClickEventCount(row)}
                        text={true}
                      >
                        {row.event_count}
                      </Button>
                    ) : (
                      '--'
                    )
                }}
              />
            );
          }
          if (column.id === 'description') {
            return (
              <TableColumn
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row: { dimensions, description } }: { row: IEventItem; $index: number }) => (
                    <div
                      onMouseenter={e => this.handleDescEnter(e, dimensions, description)}
                      onMouseleave={this.handlePopoverHide}
                    >
                      {[
                        <div class='dimension-desc'>
                          {this.$t('维度信息')}：
                          {dimensions?.length
                            ? dimensions
                                .map(item => `${item.display_key || item.key}(${item.display_value || item.value})`)
                                .join('-')
                            : '--'}
                        </div>,
                        <div class='description-desc'>
                          {this.$t('告警内容')}：{description || '--'}
                        </div>
                      ]}
                    </div>
                  )
                }}
              />
            );
          }
        } else {
          if (column.id === 'id') {
            return (
              <TableColumn
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row }: { row: IEventItem }) => (
                    <span
                      class='event-status'
                      style={{ borderLeftColor: this.actionStatusColorMap[row.status] }}
                      onClick={() => this.handleShowDetail(row)}
                    >
                      {row.id}
                    </span>
                  )
                }}
              />
            );
          }
          if (column.id === 'alert_count' || column.id === 'converge_count') {
            return (
              <TableColumn
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row }: { row: IEventItem }) =>
                    row[column.id] > 0 ? (
                      <Button
                        onClick={() =>
                          this.handleClickActionCount(column.id === 'alert_count' ? 'trigger' : 'defense', row)
                        }
                        text={true}
                      >
                        {row[column.id]}
                      </Button>
                    ) : (
                      '0'
                    )
                }}
              />
            );
          }
          if (column.id === 'content') {
            return (
              <TableColumn
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row: { content } }: { row: IEventItem }) => (
                    <div class='col-content'>{content?.() || '--'}</div>
                  )
                }}
              />
            );
          }
        }
        return (
          <TableColumn
            key={`${this.searchType}_${column.id}`}
            label={column.name}
            prop={column.id}
            formatter={row => (!row[column.id] && row[column.id] !== 0 ? '--' : row[column.id])}
            {...{ props: column.props }}
          />
        );
      })
    );
  }
  render() {
    return (
      <div>
        <Table
          data={this.tableData}
          class='event-table'
          size={this.tableSize}
          outer-border={false}
          header-border={false}
          pagination={this.pagination}
          ref='table'
          v-bkloading={{ isLoading: this.loading, zIndex: 1000 }}
          on-sort-change={this.handleSortChange}
          on-row-mouse-enter={index => (this.hoverRowIndex = index)}
          on-row-mouse-leave={() => (this.hoverRowIndex = -1)}
          on-page-change={this.handlePageChange}
          on-page-limit-change={this.handlePageLimitChange}
          on-selection-change={this.handleSelectChange}
        >
          {this.handleGetColumns()}
        </Table>
      </div>
    );
  }

  /** 跳转到策略详情 */
  goToStrategy(strategyId: number, bizId: number) {
    if (!strategyId) return;
    const id = `${strategyId}`;
    const { href } = this.$router.resolve({
      name: 'strategy-config-detail',
      params: { id }
    });

    window.open(`${location.origin}${location.pathname}?bizId=${bizId}/${href}`, '_blank');
  }
}
