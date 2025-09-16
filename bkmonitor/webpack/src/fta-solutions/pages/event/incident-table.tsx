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

import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';

import { random } from '../../../monitor-common/utils/utils';
import { transformLogUrlQuery } from '../../../monitor-pc/utils';
import { TableClickCurrentExpand } from '../../common/table-expand-plugins';
import { handleToAlertList } from './event-detail/action-detail';

import type { TType as TSliderType } from './event-detail/event-detail-slider';
// import { getStatusInfo } from './event-detail/type';
import type { eventPanelType, IEventItem, IPagination, SearchType } from './typings/event';
import type { TranslateResult } from 'vue-i18n';

import './incident-table.scss';

export interface IShowDetail {
  activeTab?: string;
  bizId: number;
  id: string;
  type: TSliderType;
}

interface IColumnItem {
  checked: boolean;
  disabled: boolean;
  id: string;
  name: string | TranslateResult;
  props?: {
    fixed?: 'left' | 'right';
    formatter?: (value: any) => any;
    minWidth?: number | string;
    resizable?: boolean;
    sortable?: 'curstom' | boolean;
    width?: number | string;
  };
}

interface IEventStatusMap {
  bgColor: string;
  color: string;
  icon: string;
  name: string | TranslateResult;
}
interface IEventTableEvent {
  onAlarmDispatch?: IIncidentItem;
  onAlertConfirm?: IIncidentItem;
  onBatchSet: string;
  onChatGroup?: IIncidentItem;
  onLimitChange: number;
  onManualProcess?: IIncidentItem;
  onPageChange: number;
  onQuickShield?: IIncidentItem;
  onSelectChange: string[];
  onShowDetail?: { id: string; type: TSliderType };
  onSortChange: string;
}
interface IEventTableProps {
  bizIds: number[];
  doLayout: eventPanelType;
  loading?: boolean;
  pagination: IPagination;
  searchType: SearchType;
  selectedList?: string[];
  tableData: IIncidentItem[];
}
interface IIncidentItem extends IEventItem {
  incident_reason?: string;
  level?: number;
}

const incidentKey = '__INCIDENT_EVENT_COLUMN__';

type TableSizeType = 'large' | 'medium' | 'small';
@Component({
  // components: { Popover, Pagination, Checkbox }
})
export default class IncidentTable extends tsc<IEventTableProps, IEventTableEvent> {
  @Prop({ required: true }) tableData: IIncidentItem[];
  @Prop({ required: true }) pagination: IPagination;
  @Prop({ default: false }) loading: boolean;
  @Prop({ default: () => [] }) bizIds: number[];
  @Prop({ type: String }) doLayout: eventPanelType;
  @Prop({ required: true, type: String }) searchType: SearchType;
  @Prop({ type: Array, default: () => [] }) selectedList: string[];

  @Ref('table') tableRef: any;
  @Ref('moreItems') moreItemsRef: HTMLDivElement;

  eventStatusMap: Record<string, IEventStatusMap> = {};
  actionStatusColorMap: Record<string, string> = {
    running: '#A3C4FD',
    success: '#8DD3B5',
    failure: '#F59E9E',
    skipped: '#FED694',
    shield: '#CBCDD2',
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
    name: string | TranslateResult;
  }[];
  /* 状态栏更多操作按钮 */
  popoperOperateInstance: any = null;
  popoperOperateIndex = -1;
  opetateRow = null;
  enableCreateChatGroup = false;
  /** table 行定位色功能类实例 */
  tableClickCurrentInstance = new TableClickCurrentExpand();

  /**
   * @description: 处理记录列表字段
   * @param {*}
   * @return {*}
   */
  get tableColumn(): IColumnItem[] {
    let storeColumnList: any = localStorage.getItem(incidentKey) || '';
    try {
      storeColumnList = JSON.parse(storeColumnList) || [];
    } catch {
      storeColumnList = [];
    }
    return (
      [
        {
          id: 'id',
          name: this.$t('故障ID'),
          checked: false,
          disabled: true,
          props: {
            width: 160,
            minWidth: 160,
            fixed: 'left',
          },
        },
        this.bizIds.length > 1 || [-1, -2].includes(this.bizIds?.[0])
          ? {
              id: 'bk_biz_name',
              name: this.$t('空间名'),
              disabled: true,
              checked: true,
              props: {
                width: 100,
                fixed: 'left',
                resizable: true,
              },
            }
          : undefined,
        {
          id: 'incident_name',
          name: this.$t('故障名称'),
          checked: true,
          disabled: true,
          props: {
            width: 260,
            minWidth: 180,
            fixed: 'left',
            // sortable: 'curstom',
            showOverflowTooltip: true,
          },
        },
        {
          id: 'status',
          name: this.$t('故障状态'),
          checked: true,
          disabled: true,
          props: {
            width: 110,
          },
        },
        {
          id: 'alert_count',
          name: this.$t('告警数量'),
          checked: true,
          disabled: true,
          props: {
            width: 100,
            minWidth: 100,
            sortable: 'curstom',
          },
        },
        {
          id: 'labels',
          name: this.$t('标签'),
          disabled: false,
          checked: true,
          props: {
            width: 120,
            minWidth: 120,
            formatter: (row: IIncidentItem) => {
              return (
                <div class='tag-column-wrap'>
                  <div class='tag-column'>
                    {row.labels ? (
                      <div>
                        <div class='tag-item set-item'>
                          {typeof row.labels[0] === 'string'
                            ? row.labels[0].replace(/\//g, '')
                            : row.labels[0]?.key
                              ? `${row.labels[0].key}: ${row.labels[0].value.replace(/\//g, '')}`
                              : '--'}
                        </div>
                        {row.labels.length > 1 && (
                          <bk-popover>
                            <div slot='content'>
                              {row.labels.map(item => (
                                <div
                                  key={item}
                                  style={'margin:0 -5px'}
                                >
                                  {item}
                                </div>
                              ))}
                            </div>
                            <div class='tag-item set-item'>+ {row.labels.length - 1}</div>
                          </bk-popover>
                        )}
                      </div>
                    ) : (
                      '--'
                    )}
                  </div>
                </div>
              );
            },
          },
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
            formatter: (row: IIncidentItem) => {
              return (
                <span>
                  {this.formatterTime(row.begin_time)} / <br />
                  {this.formatterTime(row.end_time)}
                </span>
              );
            },
          },
        },
        {
          id: 'incident_duration',
          name: this.$t('持续时间'),
          disabled: true,
          checked: false,
          props: {
            width: 100,
            minWidth: 100,
            // sortable: 'curstom',
            formatter: (row: IIncidentItem) => {
              return row.duration || '--';
            },
          },
        },
        {
          id: 'assignee',
          name: this.$t('负责人'),
          checked: true,
          disabled: false,
          props: {
            width: 150,
            minWidth: 150,
            formatter: (row: IIncidentItem) => {
              return (
                (row?.assignees || []).map(name => (
                  <bk-user-display-name
                    key={name}
                    class='tag-item'
                    user-id={name}
                  />
                )) || '--'
              );
            },
          },
        },
        {
          id: 'incident_reason',
          name: this.$t('故障原因'),
          checked: true,
          disabled: false,
          props: {
            width: 240,
            showOverflowTooltip: true,
            formatter: (row: IIncidentItem) => row.incident_reason || '--', // row.content.text || '--'
          },
        },
      ] as IColumnItem[]
    )
      .filter(Boolean)
      .map(item => ({
        ...item,
        checked: storeColumnList?.length ? storeColumnList.includes(item.id) : item.checked,
      }));
  }

  @Watch('tableData')
  handleTableDataChange() {
    this.tableClickCurrentInstance.resetRowCurrentIndex();
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
      abnormal: {
        color: '#EA3536',
        bgColor: '#FFEEEE',
        name: this.$t('未恢复'),
        icon: 'icon-mind-fill',
      },
      recovering: {
        color: '#FF9C01',
        bgColor: '#FFF3E1',
        name: this.$t('观察中'),
        icon: 'icon-mc-visual',
      },
      recovered: {
        color: '#1CAB88',
        bgColor: '#E8FFF5',
        name: this.$t('已恢复'),
        icon: 'icon-mc-check-fill',
      },
      closed: {
        color: '#979ba5',
        bgColor: '#F5F7FA',
        name: this.$t('已解决'),
        icon: 'icon-mc-solved',
      },
      ABNORMAL: {
        color: '#EA3536',
        bgColor: '#FEEBEA',
        name: this.$t('未恢复'),
        icon: 'icon-mind-fill',
      },
      RECOVERED: {
        color: '#14A568',
        bgColor: '#E4FAF0',
        name: this.$t('已恢复'),
        icon: '',
      },
      CLOSED: {
        color: '#63656E',
        bgColor: '#F0F1F5',
        name: this.$t('已失效'),
        icon: '',
      },
    };
    this.extendInfoMap = {
      log_search: this.$t('查看更多相关的日志'),
      custom_event: this.$t('查看更多相关的事件'),
      bkdata: this.$t('查看更多相关的数据'),
    };
    this.tableToolList = [
      {
        id: 'comfirm',
        name: this.$t('批量确认'),
      },
      {
        id: 'shield',
        name: this.$t('批量屏蔽'),
      },
      {
        id: 'dispatch',
        name: this.$t('批量分派'),
      },
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
      shield: this.$t('已屏蔽'),
    };

    // 是否支持一键拉群 todo
    this.enableCreateChatGroup = window.enable_create_chat_group || false;
    if (this.enableCreateChatGroup) {
      this.tableToolList.push({
        id: 'chat',
        name: this.$t('一键拉群'),
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
  handleShowDetail(item: IIncidentItem, activeTab = ''): IShowDetail {
    const typeMap = {
      alert: 'eventDetail',
      action: 'handleDetail',
    };
    return {
      id: item.id,
      bizId: item.bk_biz_id,
      type: typeMap[this.searchType],
      activeTab,
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
  handleSelectChange(selectList: IIncidentItem[]) {
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
    const id = extendInfo.bk_event_group_id;
    switch (extendInfo.type) {
      // 监控主机监控详情
      case 'host':
        // biome-ignore lint/correctness/noSwitchDeclarations: <explanation>
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
        // biome-ignore lint/correctness/noSwitchDeclarations: <explanation>
        const targets = [{ data: { query_configs: extendInfo.query_configs } }];
        window.open(
          `${origin}${location.pathname
            .toString()
            .replace(
              'fta/',
              ''
            )}?bizId=${bizId}#/data-retrieval/?targets=${encodeURIComponent(JSON.stringify(targets))}`,
          '__blank'
        );
        return;
      // 日志检索
      case 'log_search':
        // biome-ignore lint/correctness/noSwitchDeclarations: <explanation>
        const retrieveParams = {
          // 检索参数
          bizId,
          keyword: extendInfo.query_string, // 搜索关键字
          addition: extendInfo.agg_condition || [],
        };
        // biome-ignore lint/correctness/noSwitchDeclarations: <explanation>
        const queryStr = transformLogUrlQuery(retrieveParams);
        // biome-ignore lint/correctness/noSwitchDeclarations: <explanation>
        const url = `${this.$store.getters.bkLogSearchUrl}#/retrieve/${extendInfo.index_set_id}${queryStr}`;
        window.open(url);
        return;
      // 监控自定义事件
      case 'custom_event':
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
          <div
            key={extendInfo.hostname}
            class='extend-content'
          >{`${this.$t('主机名:')}${extendInfo.hostname || '--'}`}</div>,
          <div
            key={`${extendInfo.hostname}-info`}
            class='extend-content'
          >
            <span class='extend-content-message'>{`${this.$t('节点信息:')}${extendInfo.topo_info || '--'}`}</span>
            <span
              class='extend-content-link link-more'
              onClick={() => this.handleGotoMore(extendInfo, bizId)}
            >
              {this.$t('更多')}
            </span>
          </div>,
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
  handleClickEventCount(item: IIncidentItem) {
    this.handleShowDetail(item, 'FailureView');
  }
  /**
   * @description: 跳转到告警列表
   * @param {string} id
   * @return {*}
   */
  handleClickActionCount(type: 'defense' | 'trigger', row: IIncidentItem) {
    // const data = { queryString: `action_id : ${id}`, timeRange }
    const { id, create_time: createTime, end_time: endTime } = row;
    handleToAlertList(
      type,
      {
        create_time: createTime as number,
        end_time: endTime as number,
        id,
      },
      row.bk_biz_id || this.$store.getters.bizId
    );
  }
  // 时间格式化
  formatterTime(time: number | string): string {
    if (!time) return '--';
    if (typeof time !== 'number') return time;
    if (time.toString().length < 13) return dayjs(time * 1000).format('YYYY-MM-DD HH:mm:ss');
    return dayjs(time).format('YYYY-MM-DD HH:mm:ss');
  }

  handleDescEnter(e: MouseEvent, dimensions, description) {
    this.handlePopoverShow(
      e,
      [
        `<div class="dimension-desc">${this.$t('维度信息')}：${
          dimensions?.map?.(item => `${item.display_key || item.key}(${item.display_value || item.value})`).join('-') ||
          '--'
        }</div>`,
        `<div class="description-desc">${this.$t('告警内容')}：${description || '--'}</div>`,
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
      boundary: 'window',
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
    const { origin, pathname } = window.location;
    return (
      <bk-table-column
        key={`${this.searchType}_${column.id}`}
        label={column.name}
        prop={column.id}
        {...{ props: column.props }}
        scopedSlots={{
          default: ({ row }: { row: IIncidentItem }) => (
            <a
              class={`event-status status-${row.severity} id-column ${row.level}_id`}
              v-bk-overflow-tips
              href={`${origin}${pathname}?bizId=${row.bk_biz_id}#/trace/incident/detail/${row.id}`}
              onClick={e => {
                e.preventDefault();
                this.handleShowDetail(row);
              }}
            >
              {row.id}
            </a>
          ),
        }}
      />
    );
  }
  handleRenderDefaultColumn(column) {
    return (
      <bk-table-column
        key={`${this.searchType}_${column.id}`}
        formatter={row => (!row[column.id] && row[column.id] !== 0 ? '--' : row[column.id])}
        label={column.name}
        prop={column.id}
        {...{ props: column.props }}
      />
    );
  }
  handleRenderStatus(column) {
    return (
      <bk-table-column
        key={`${this.searchType}_${column.id}`}
        class-name='status-cell'
        label={column.name}
        prop={column.id}
        {...{ props: column.props }}
        scopedSlots={{
          default: ({ row: { status } }) => (
            <div class='status-column'>
              <span
                style={{
                  color: this.eventStatusMap?.[status]?.color,
                  backgroundColor: this.eventStatusMap?.[status]?.bgColor,
                }}
                class='status-label'
              >
                {this.eventStatusMap?.[status]?.icon ? (
                  <i
                    style={{ color: this.eventStatusMap?.[status]?.color }}
                    class={['icon-monitor item-icon', this.eventStatusMap?.[status]?.icon ?? '']}
                  />
                ) : (
                  ''
                )}
                <span
                  class={'status-label-status'}
                  v-bk-overflow-tips
                >
                  {' '}
                  {this.eventStatusMap?.[status]?.name || '--'}
                </span>
              </span>
            </div>
          ),
        }}
      />
    );
  }
  handleRenderAlarmCount(column) {
    return (
      <bk-table-column
        key={`${this.searchType}_${column.id}`}
        label={column.name}
        prop={column.id}
        {...{ props: column.props }}
        scopedSlots={{
          default: ({ row }: { row: IIncidentItem }) =>
            row.alert_count > -1 ? (
              <bk-button
                text={true}
                onClick={() => this.handleClickEventCount(row)}
              >
                {row.alert_count}
              </bk-button>
            ) : (
              '--'
            ),
        }}
      />
    );
  }
  /**
   * @description: 设置表字段显示
   * @param {*} param1
   * @return {*}
   */
  handleSettingChange({ size, fields }) {
    this.tableSize = size;
    for (const item of this.tableColumn) {
      item.checked = fields.some(field => field.id === item.id);
    }
    localStorage.setItem(
      incidentKey,
      JSON.stringify(this.tableColumn.filter(item => item.checked || item.disabled).map(item => item.id))
    );
    this.tableKey = random(10);
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
          case 'status':
            return this.handleRenderStatus(column);
          case 'alert_count':
            return this.handleRenderAlarmCount(column);
          default: {
            return this.handleRenderDefaultColumn(column);
          }
        }
      })
    );
  }
  render() {
    return (
      <div>
        <bk-table
          ref='table'
          class='event-table'
          v-bkloading={{ isLoading: this.loading, zIndex: 1000 }}
          data={this.tableData}
          header-border={false}
          outer-border={false}
          pagination={this.pagination}
          row-class-name={this.tableClickCurrentInstance.getClassNameByCurrentIndex()}
          size={this.tableSize}
          on-page-change={this.handlePageChange}
          on-page-limit-change={this.handlePageLimitChange}
          on-row-click={this.tableClickCurrentInstance.tableRowClick()}
          on-row-mouse-enter={index => {
            this.hoverRowIndex = index;
          }}
          on-row-mouse-leave={() => {
            this.hoverRowIndex = -1;
          }}
          on-selection-change={this.handleSelectChange}
          on-sort-change={this.handleSortChange}
        >
          {this.handleGetColumns()}
          <bk-table-column
            key={`${this.tableKey}_${this.searchType}`}
            type='setting'
          >
            <bk-table-setting-content
              class='event-table-setting'
              fields={this.tableColumn}
              label-key='name'
              selected={this.tableColumn.filter(item => item.checked || item.disabled)}
              value-key='id'
              on-setting-change={this.handleSettingChange}
            />
          </bk-table-column>
        </bk-table>
      </div>
    );
  }

  /** 跳转到策略详情 */
  goToStrategy(strategyId: number, bizId: number) {
    if (!strategyId) return;
    const id = `${strategyId}`;
    const { href } = this.$router.resolve({
      name: 'strategy-config-detail',
      params: { id },
    });

    window.open(`${location.origin}${location.pathname}?bizId=${bizId}/${href}`, '_blank');
  }
}
