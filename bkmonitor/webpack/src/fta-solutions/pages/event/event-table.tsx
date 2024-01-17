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
import dayjs from 'dayjs';

import { checkAllowedByActionIds } from '../../../monitor-api/modules/iam';
import { random } from '../../../monitor-common/utils/utils';
import authorityStore from '../../../monitor-pc/store/modules/authority';
import { transformLogUrlQuery } from '../../../monitor-pc/utils';

import { handleToAlertList } from './event-detail/action-detail';
import { TType as TSliderType } from './event-detail/event-detail-slider';
import { getStatusInfo } from './event-detail/type';
import { eventPanelType, IEventItem, IPagination, SearchType } from './typings/event';

import './event-table.scss';

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
@Component
export default class EventTable extends tsc<IEventTableProps, IEventTableEvent> {
  @Prop({ required: true }) tableData: IEventItem[];
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
  /* 关注人禁用操作 */
  followerDisabled = false;
  get tableColumnMap() {
    return this.alertColumns.reduce((pre, cur) => {
      if (cur.disabled || cur.checked) {
        pre[cur.id] = true;
      }
      return pre;
    }, {});
  }
  /**
   * @description: 处理记录列表字段
   * @param {*}
   * @return {*}
   */
  get actionColumns(): IColumnItem[] {
    let storeColumnList: any = localStorage.getItem(actionStoreKey) || '';
    try {
      storeColumnList = JSON.parse(storeColumnList) || [];
    } catch {
      storeColumnList = [];
    }
    return (
      [
        {
          id: 'id',
          name: 'ID',
          checked: true,
          disabled: true,
          props: {
            width: 160,
            minWidth: 160
          }
        },
        {
          id: 'create_time',
          name: this.$t('开始时间'),
          checked: true,
          disabled: false,
          props: {
            width: 150,
            minWidth: 150,
            sortable: 'curstom',
            formatter: (row: IEventItem) => this.formatterTime(row.create_time)
          }
        },
        {
          id: 'action_name',
          name: this.$t('套餐名称'),
          checked: true,
          disabled: true,
          props: {
            width: 180,
            minWidth: 180,
            sortable: 'curstom',
            showOverflowTooltip: true
          }
        },
        {
          id: 'action_plugin_type_display',
          name: this.$t('套餐类型'),
          checked: false,
          disabled: false,
          props: {
            width: 100,
            sortable: 'curstom'
          }
        },
        {
          id: 'operate_target_string',
          name: this.$t('执行对象'),
          checked: false,
          disabled: false,
          props: {
            width: 120,
            showOverflowTooltip: true
          }
        },
        {
          id: 'operator',
          name: this.$t('负责人'),
          checked: true,
          disabled: false,
          props: {
            width: 220,
            minWidth: 220,
            formatter: (row: IEventItem) =>
              // 去重
              row?.operator
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
          id: 'alert_count',
          name: this.$t('触发告警数'),
          checked: true,
          disabled: true,
          props: {
            width: 120,
            minWidth: 120
            // sortable: 'curstom'
          }
        },
        {
          id: 'converge_count',
          name: this.$t('防御告警数'),
          checked: true,
          disabled: true,
          props: {
            width: 120,
            minWidth: 120
          }
        },
        {
          id: 'end_time',
          name: this.$t('结束时间'),
          checked: false,
          disabled: false,
          props: {
            width: 150,
            minWidth: 150,
            sortable: 'curstom',
            formatter: (row: IEventItem) => this.formatterTime(row.end_time)
          }
        },
        {
          id: 'duration',
          name: this.$t('处理时长'),
          checked: false,
          disabled: false,
          props: {
            width: 80,
            minWidth: 80,
            sortable: 'curstom'
          }
        },
        {
          id: 'status',
          name: this.$t('执行状态'),
          checked: true,
          disabled: true,
          props: {
            width: 100,
            sortable: 'curstom',
            formatter: (row: IEventItem) => {
              const statusInfo = getStatusInfo(row.status, row.failure_type);
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
          id: 'content',
          name: this.$t('具体内容'),
          checked: true,
          disabled: false,
          props: {
            showOverflowTooltip: true,
            formatter: (row: IEventItem) => row.content.text || '--'
          }
        }
      ] as IColumnItem[]
    )
      .filter(Boolean)
      .map(item => ({
        ...item,
        checked: storeColumnList?.length ? storeColumnList.includes(item.id) : item.checked
      }));
  }
  // 告警列表字段
  get alertColumns(): IColumnItem[] {
    let storeColumnList: any = localStorage.getItem(alertStoreKey) || '';
    try {
      storeColumnList = JSON.parse(storeColumnList) || [];
    } catch {
      storeColumnList = [];
    }
    return (
      [
        {
          id: 'id',
          name: this.$t('告警ID'),
          disabled: true,
          checked: true,
          props: {
            width: 140,
            fixed: 'left',
            resizable: true
          }
        },
        this.bizIds.length > 1 || this.bizIds?.[0] === -1
          ? {
              id: 'bizName',
              name: this.$t('空间名'),
              disabled: true,
              checked: true,
              props: {
                width: 100,
                fixed: 'left',
                resizable: true
              }
            }
          : undefined,
        {
          id: 'alert_name',
          name: this.$t('告警名称'),
          disabled: true,
          checked: true,
          props: {
            width: 160,
            fixed: 'left',
            resizable: true
          }
        },
        {
          id: 'plugin_display_name',
          name: this.$t('告警来源'),
          disabled: false,
          checked: false,
          props: {
            minWidth: 110
          }
        },
        {
          id: 'category_display',
          name: this.$t('分类'),
          disabled: false,
          checked: true,
          props: {
            minWidth: 160
          }
        },
        {
          id: 'metric',
          name: this.$t('告警指标'),
          disabled: false,
          checked: true,
          props: {
            minWidth: 180,
            sortable: 'curstom',
            formatter: (row: IEventItem) => {
              const isEmpt = !row?.metric_display?.length;
              if (isEmpt) return '--';
              const key = random(10);
              return (
                <div class='tag-column-wrap'>
                  <div
                    class='tag-column'
                    id={key}
                    v-bk-overflow-tips={{
                      allowHTML: true,
                      interactive: true
                    }}
                  >
                    {row.metric_display.map(item => (
                      <div
                        key={item.id}
                        class='tag-item set-item'
                      >
                        {item.name || item.id}
                      </div>
                    ))}
                  </div>
                </div>
              );
            }
          }
        },
        {
          id: 'event_count',
          name: this.$t('关联事件'),
          disabled: false,
          checked: true,
          props: {
            minWidth: 140
          }
        },
        {
          id: 'create_time',
          name: this.$t('创建时间'),
          disabled: false,
          checked: false,
          props: {
            minWidth: 150,
            formatter: (row: IEventItem) => this.formatterTime(row.create_time),
            sortable: 'curstom'
          }
        },
        {
          id: 'begin_time',
          name: this.$t('开始时间'),
          disabled: false,
          checked: false,
          props: {
            minWidth: 150,
            formatter: (row: IEventItem) => this.formatterTime(row.begin_time),
            sortable: 'curstom'
          }
        },
        {
          id: 'end_time',
          name: this.$t('结束时间'),
          disabled: false,
          checked: false,
          props: {
            minWidth: 150,
            formatter: (row: IEventItem) => this.formatterTime(row.end_time),
            sortable: 'curstom'
          }
        },
        {
          id: 'latest_time',
          name: this.$t('最新事件时间'),
          disabled: false,
          checked: false,
          props: {
            minWidth: 150,
            formatter: (row: IEventItem) => this.formatterTime(row.latest_time),
            sortable: 'curstom'
          }
        },
        {
          id: 'first_anomaly_time',
          name: this.$t('首次异常时间'),
          disabled: false,
          checked: false,
          props: {
            minWidth: 150,
            formatter: (row: IEventItem) => this.formatterTime(row.first_anomaly_time),
            sortable: 'curstom'
          }
        },
        {
          id: 'duration',
          name: this.$t('持续时间'),
          disabled: false,
          checked: false,
          props: {
            sortable: 'curstom'
          }
        },
        {
          id: 'description',
          name: this.$t('告警内容'),
          disabled: false,
          checked: true,
          props: {
            minWidth: 300,
            width: 300
          }
        },
        {
          id: 'tags',
          name: this.$t('维度'),
          disabled: false,
          checked: false,
          props: {
            width: 200,
            minWidth: 200,
            formatter: (row: IEventItem) =>
              row.tags?.map(item => <span class='tag-item'>{`${item.key}: ${item.value}`}</span>) || '--'
          }
        },
        {
          id: 'extend_info',
          name: this.$t('关联信息'),
          disabled: true,
          checked: false,
          props: {
            minWidth: 250,
            width: 250
          }
        },
        {
          id: 'appointee',
          name: this.$t('负责人'),
          disabled: false,
          checked: true,
          props: {
            width: 200,
            minWidth: 200,
            formatter: (row: IEventItem) =>
              row.appointee?.map(appointee => <span class='tag-item'>{appointee}</span>) || '--'
          }
        },
        {
          id: 'assignee',
          name: this.$t('通知人'),
          disabled: false,
          checked: true,
          props: {
            width: 200,
            minWidth: 200,
            formatter: (row: IEventItem) =>
              row.assignee?.map(assginne => <span class='tag-item'>{assginne}</span>) || '--'
          }
        },
        {
          id: 'follower',
          name: this.$t('关注人'),
          disabled: false,
          checked: true,
          props: {
            width: 200,
            minWidth: 200,
            formatter: (row: IEventItem) =>
              row.follower?.map(follower => <span class='tag-item'>{follower}</span>) || '--'
          }
        },
        // {
        //   id: 'severity',
        //   name: this.$t('告警级别'),
        //   disabled: true,
        //   checked: true
        // },
        {
          id: 'strategy_name',
          name: this.$t('策略名称'),
          disabled: false,
          checked: false,
          props: {
            formatter: (item: IEventItem) => (
              <span
                class={item.strategy_id ? 'cell-strategy' : ''}
                onClick={() => this.goToStrategy(item.strategy_id, item.bk_biz_id)}
              >
                {item.strategy_name || '--'}
              </span>
            )
          }
        },
        {
          id: 'labels',
          name: this.$t('策略标签'),
          disabled: false,
          checked: false,
          props: {
            width: 200,
            minWidth: 200,
            formatter: (row: IEventItem) => row.labels?.map(label => <span class='tag-item'>{label}</span>) || '--'
          }
        },
        {
          id: 'stage_display',
          name: this.$t('处理阶段'),
          disabled: false,
          checked: true,
          props: {
            fixed: 'right',
            resizable: true,
            minWidth: 110,
            formatter: (item: IEventItem) => (!item.stage_display ? '--' : item.stage_display)
          }
        },
        {
          id: 'status',
          name: this.$t('状态'),
          disabled: true,
          checked: true,
          props: {
            fixed: 'right',
            resizable: true,
            width: this.$store.getters.lang === 'en' ? 120 : 80,
            minWidth: this.$store.getters.lang === 'en' ? 140 : 110,
            sortable: 'curstom'
          }
        }
      ] as IColumnItem[]
    )
      .filter(Boolean)
      .map(item => ({
        ...item,
        checked: storeColumnList?.length ? storeColumnList.includes(item.id) : item.checked
      }));
  }
  get tableColumn() {
    return this.searchType === 'alert' ? this.alertColumns : this.actionColumns;
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
        name: this.$t('未恢复')
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

  /* 自动批量弹窗是需要自动选中指定数据 */
  @Watch('selectedList')
  handleSelectedList(v: string[]) {
    if (v.length && this.tableData.length) {
      if (!this.tableRef?.store?.states?.selection?.length) {
        if (this.tableRef) {
          const selection = [];
          this.tableData.forEach(item => {
            if (v.includes(item.id)) {
              selection.push(item);
            }
          });
          this.tableRef.store.states.selection = selection;
        }
      }
    }
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
  /**
   * @description: 设置表字段显示
   * @param {*} param1
   * @return {*}
   */
  handleSettingChange({ size, fields }) {
    this.tableSize = size;
    this.tableColumn.forEach(item => (item.checked = fields.some(field => field.id === item.id)));
    const storeKey = this.searchType === 'alert' ? alertStoreKey : actionStoreKey;
    localStorage.setItem(
      storeKey,
      JSON.stringify(this.tableColumn.filter(item => item.checked || item.disabled).map(item => item.id))
    );
    this.tableKey = random(10);
  }
  @Emit('selectChange')
  handleSelectChange(selectList: IEventItem[]) {
    this.selectedCount = selectList?.length || 0;
    this.followerDisabled = selectList.some(item => item.followerDisabled);
    return selectList.map(item => item.id);
  }
  /**
   * @description: 告警确认
   * @param {*}
   * @return {*}
   */
  @Emit('alertConfirm')
  handleAlertConfirm(v) {
    return v;
  }
  /**
   * @description: 快捷屏蔽
   * @param {*}
   * @return {*}
   */
  @Emit('quickShield')
  handleQuickShield(v) {
    return v;
  }
  @Emit('chatGroup')
  handleChatGroup(v) {
    return v;
  }
  @Emit('alarmDispatch')
  handleAlarmDispatch(v) {
    return v;
  }
  // @Emit('manualProcess')
  async handleManualProcess(v) {
    // 手动处理需要权限判断
    const MANAGE_RULE = 'manage_rule_v2';
    const manage_event_v2 = 'manage_event_v2';
    const data = await checkAllowedByActionIds({
      action_ids: [MANAGE_RULE, manage_event_v2],
      bk_biz_id: v.bk_biz_id
    }).catch(() => []);
    if (!data.length) {
      authorityStore.getAuthorityDetail(MANAGE_RULE);
      return;
    }
    if (data.some(item => item.is_allowed)) {
      this.$emit('manualProcess', v);
    } else {
      const arr = data.filter(item => !item.is_allowed);
      authorityStore.getAuthorityDetail(arr[0].action_id);
    }
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
    if (time.toString().length < 13) return dayjs.tz(time * 1000).format('YYYY-MM-DD HH:mm:ss');
    return dayjs.tz(time).format('YYYY-MM-DD HH:mm:ss');
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
   * @description: 清除已选
   * @param {*}
   * @return {*}
   */
  handleClearSelected() {
    this?.tableRef?.clearSelection?.();
    this.selectedCount = 0;
  }
  /**
   * @description: 批量
   * @param {*}
   * @return {*}
   */
  @Emit('batchSet')
  handleBatchSet(id: string) {
    return id;
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

  /* 告警确认文案 */
  askTipMsg(isAak, status, ackOperator, followerDisabled) {
    const statusNames = {
      RECOVERED: this.$t('告警已恢复'),
      CLOSED: this.$t('告警已关闭')
    };
    if (followerDisabled) {
      return this.$t('关注人禁用此操作');
    }
    if (!isAak) {
      return statusNames[status];
    }
    return `${ackOperator || ''}${this.$t('已确认')}`;
  }

  /* 状态栏更多按钮操作 */
  handleShowMoreOperate(e: Event, index: number) {
    this.popoperOperateIndex = index;
    this.opetateRow = this.tableData[index];
    if (!this.popoperOperateInstance) {
      this.popoperOperateInstance = this.$bkPopover(e.target, {
        content: this.moreItemsRef,
        arrow: false,
        trigger: 'click',
        placement: 'bottom',
        theme: 'light common-monitor',
        maxWidth: 520,
        duration: [200, 0],
        onHidden: () => {
          this.popoperOperateInstance.destroy();
          this.popoperOperateInstance = null;
          this.popoperOperateIndex = -1;
        }
      });
    }
    this.popoperOperateInstance?.show(100);
  }

  // 表格column设置
  handleGetColumns() {
    const columList = [];
    if (this.searchType === 'alert') {
      columList.push(
        <bk-table-column
          type='selection'
          width='50'
          minWidth='50'
          fixed='left'
        />
      );
    }
    return columList.concat(
      ...this.tableColumn.map(column => {
        if (!(column.disabled || column.checked)) return undefined;
        if (this.searchType === 'alert') {
          // 告警id
          if (column.id === 'id') {
            return (
              <bk-table-column
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
              <bk-table-column
                class-name='status-cell'
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({
                    row: { status, is_ack: isAck, ack_operator: ackOperator, followerDisabled },
                    $index,
                    row
                  }: {
                    row: IEventItem;
                    $index: number;
                  }) => (
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
                      <div
                        class='operate-panel'
                        v-en-class='en-lang'
                        style={{
                          display:
                            this.hoverRowIndex === $index || this.popoperOperateIndex === $index ? 'flex' : 'none'
                        }}
                      >
                        {this.enableCreateChatGroup ? (
                          <span
                            class='operate-panel-item icon-monitor icon-we-com'
                            on-click={() => this.handleChatGroup(row)}
                            v-bk-tooltips={{ content: this.$t('一键拉群'), delay: 200, appendTo: 'parent' }}
                          />
                        ) : (
                          ''
                        )}
                        <span
                          class={[
                            'operate-panel-item icon-monitor icon-duihao',
                            { 'is-disable': isAck || ['RECOVERED', 'CLOSED'].includes(status) || followerDisabled }
                          ]}
                          on-click={() =>
                            !isAck &&
                            !['RECOVERED', 'CLOSED'].includes(status) &&
                            !followerDisabled &&
                            this.handleAlertConfirm(row)
                          }
                          v-bk-tooltips={{
                            content:
                              isAck || ['RECOVERED', 'CLOSED'].includes(status) || followerDisabled
                                ? this.askTipMsg(isAck, status, ackOperator, followerDisabled)
                                : this.$t('告警确认'),
                            delay: 200,
                            appendTo: 'parent',
                            allowHTML: false
                          }}
                        />
                        <span
                          class={[
                            'operate-panel-item icon-monitor icon-chuli',
                            {
                              'is-disable': followerDisabled
                            }
                          ]}
                          // eslint-disable-next-line @typescript-eslint/no-misused-promises
                          onClick={() => !followerDisabled && this.handleManualProcess(row)}
                          v-bk-tooltips={{
                            content: followerDisabled ? this.$t('关注人禁用此操作') : this.$t('手动处理'),
                            delay: 200,
                            appendTo: 'parent'
                          }}
                        />
                        {/* <span class="operate-panel-item icon-monitor icon-mc-alarm-abnormal"/> */}
                        {/* <span
                        class="operate-panel-item icon-monitor icon-chuli"
                        on-click={() => this.handleManualProcess(row)}
                        v-bk-tooltips={{ content: this.$t('手动处理'), delay: 200, appendTo: 'parent' }}
                      /> */}
                        <span
                          class={['operate-more', { active: this.popoperOperateIndex === $index }]}
                          onClick={e => this.handleShowMoreOperate(e, $index)}
                        >
                          <span class='bk-icon icon-more'></span>
                        </span>
                      </div>
                    </div>
                  )
                }}
              />
            );
          }
          // 关联信息
          if (column.id === 'extend_info') {
            return (
              <bk-table-column
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
              <bk-table-column
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row }: { row: IEventItem }) =>
                    row.event_count > -1 ? (
                      <bk-button
                        onClick={() => this.handleClickEventCount(row)}
                        text={true}
                      >
                        {row.event_count}
                      </bk-button>
                    ) : (
                      '--'
                    )
                }}
              />
            );
          }
          if (column.id === 'description') {
            return (
              <bk-table-column
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
              <bk-table-column
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
              <bk-table-column
                key={`${this.searchType}_${column.id}`}
                label={column.name}
                prop={column.id}
                {...{ props: column.props }}
                scopedSlots={{
                  default: ({ row }: { row: IEventItem }) =>
                    row[column.id] > 0 ? (
                      <bk-button
                        onClick={() =>
                          this.handleClickActionCount(column.id === 'alert_count' ? 'trigger' : 'defense', row)
                        }
                        text={true}
                      >
                        {row[column.id]}
                      </bk-button>
                    ) : (
                      '0'
                    )
                }}
              />
            );
          }
          if (column.id === 'content') {
            return (
              <bk-table-column
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
          <bk-table-column
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
        <bk-table
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
          {this.selectedCount && (
            <div
              slot='prepend'
              class='table-prepend'
            >
              <i class='icon-monitor icon-hint prepend-icon'></i>
              <i18n
                path='已选择{count}条'
                tag='span'
              >
                <span
                  slot='count'
                  class='table-prepend-count'
                >
                  {this.selectedCount}
                </span>
              </i18n>
              {this.tableToolList.map(item => (
                <bk-button
                  key={item.id}
                  slot='count'
                  text={true}
                  theme='primary'
                  disabled={item.id === 'chat' ? false : this.followerDisabled}
                  class='table-prepend-clear'
                  onClick={() => !(item.id === 'chat' ? false : this.followerDisabled) && this.handleBatchSet(item.id)}
                >
                  {item.name}
                </bk-button>
              ))}
              <bk-button
                slot='count'
                text={true}
                theme='primary'
                class='table-prepend-clear'
                onClick={this.handleClearSelected}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          )}
          {this.handleGetColumns()}
          <bk-table-column
            type='setting'
            key={`${this.tableKey}_${this.searchType}`}
          >
            <bk-table-setting-content
              class='event-table-setting'
              fields={this.tableColumn}
              value-key='id'
              label-key='name'
              selected={this.tableColumn.filter(item => item.checked || item.disabled)}
              on-setting-change={this.handleSettingChange}
            />
          </bk-table-column>
        </bk-table>
        {this.getMoreOperate()}
      </div>
    );
  }

  getMoreOperate() {
    return (
      <div style={{ display: 'none' }}>
        <div
          class='event-table-options-more-items'
          ref='moreItems'
        >
          <div
            class={['more-item', { 'is-disable': this.opetateRow?.is_shielded || this.opetateRow?.followerDisabled }]}
            v-bk-tooltips={{
              content: (() => {
                if (this.opetateRow?.followerDisabled) {
                  return this.$t('关注人禁用此操作');
                }
                return this.opetateRow?.is_shielded
                  ? `${this.opetateRow.shield_operator?.[0] || ''}${this.$t('已屏蔽')}`
                  : '';
              })(),
              delay: 200,
              placements: ['left'],
              appendTo: () => document.body,
              allowHTML: false
            }}
            on-click={() =>
              !this.opetateRow?.is_shielded &&
              !this.opetateRow?.followerDisabled &&
              this.handleQuickShield(this.opetateRow)
            }
          >
            <span class='icon-monitor icon-mc-notice-shield'></span>
            <span>{window.i18n.t('快捷屏蔽')}</span>
          </div>

          <div
            class={['more-item', { 'is-disable': this.opetateRow?.followerDisabled }]}
            v-bk-tooltips={{
              content: this.opetateRow?.followerDisabled ? this.$t('关注人禁用此操作') : '',
              delay: 200,
              placements: ['left'],
              appendTo: () => document.body
            }}
            on-click={() => this.handleAlarmDispatch(this.opetateRow)}
          >
            <span class='icon-monitor icon-fenpai'></span>
            <span>{window.i18n.t('告警分派')}</span>
          </div>
        </div>
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
