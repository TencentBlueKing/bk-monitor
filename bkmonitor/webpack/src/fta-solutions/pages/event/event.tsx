/* eslint-disable @typescript-eslint/no-misused-promises */
/* eslint-disable @typescript-eslint/naming-convention */
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
/* eslint-disable no-param-reassign */
import { TranslateResult } from 'vue-i18n';
import { Component, InjectReactive, Mixins, Prop, Provide, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';
import dayjs from 'dayjs';

import {
  actionDateHistogram,
  actionTopN,
  alertDateHistogram,
  alertTopN,
  listAlertTags,
  searchAction,
  searchAlert,
  validateQueryString
} from '../../../monitor-api/modules/alert';
import { listSpaces } from '../../../monitor-api/modules/commons';
import { bizWithAlertStatistics } from '../../../monitor-api/modules/home';
import { checkAllowed } from '../../../monitor-api/modules/iam';
import { promqlToQueryConfig } from '../../../monitor-api/modules/strategies';
import { docCookies, LANGUAGE_COOKIE_KEY } from '../../../monitor-common/utils';
import { random } from '../../../monitor-common/utils/utils';
// 20231205 代码还原，先保留原有部分
// import { showAccessRequest } from '../../../monitor-pc/components/access-request-dialog';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../monitor-pc/components/empty-status/types';
import SpaceSelect from '../../../monitor-pc/components/space-select/space-select';
import { type TimeRangeType } from '../../../monitor-pc/components/time-range/time-range';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from '../../../monitor-pc/components/time-range/utils';
import { destroyTimezone, getDefautTimezone, updateTimezone } from '../../../monitor-pc/i18n/dayjs';
import * as eventAuth from '../../../monitor-pc/pages/event-center/authority-map';
import DashboardTools from '../../../monitor-pc/pages/monitor-k8s/components/dashboard-tools';
import SplitPanel from '../../../monitor-pc/pages/monitor-k8s/components/split-panel';
import { SPLIT_MAX_WIDTH, SPLIT_MIN_WIDTH } from '../../../monitor-pc/pages/monitor-k8s/typings';
import { setLocalStoreRoute } from '../../../monitor-pc/router/router-config';
import authorityMixinCreate from '../../../monitor-ui/mixins/authorityMixin';
import ChatGroup from '../../components/chat-group/chat-group';
import EventStoreModule from '../../store/modules/event';
import Group, { IGroupData } from '../integrated/group';

import AlarmConfirm from './event-detail/alarm-confirm';
import AlarmDispatch from './event-detail/alarm-dispatch';
import EventDetailSlider, { TType as TSliderType } from './event-detail/event-detail-slider';
import ManualDebugStatus from './event-detail/manual-debug-status';
import ManualProcess from './event-detail/manual-process';
import QuickShield from './event-detail/quick-shield';
import {
  AnlyzeField,
  EBatchAction,
  eventPanelType,
  FilterInputStatus,
  IChatGroupDialogOptions,
  ICommonItem,
  ICommonTreeItem,
  IEventItem,
  SearchType
} from './typings/event';
import AlertAnalyze from './alert-analyze';
import EmptyTable from './empty-table';
import EventChart from './event-chart';
import EventTable, { IShowDetail } from './event-table';
import FilterInput from './filter-input';
import MonitorDrag from './monitor-drag';
import { getOperatorDisabled } from './utils';

import './event.scss';
// 有权限的业务id
const authorityBizId = -1;
// 有数据的业务id
const hasDataBizId = -2;
const grammaticalErrorCode = 3324003;
const alertAnalyzeStorageKey = '__ALERT_ANALYZE_STORAGE_KEY__';
const actionAnalyzeStorageKey = '__ACTION_ANALYZE_STORAGE_KEY__';
const allAnlyzeFieldList = [
  'alert_name',
  'metric',
  'duration',
  'ip',
  'bk_cloud_id',
  'strategy_id',
  'strategy_name',
  'assignee',
  'bk_service_instance_id',
  'appointee',
  'labels',
  'plugin_id',
  'ipv6'
];
const allActionFieldList = [
  'action_name',
  'action_plugin_type',
  'operator',
  'duration',
  'strategy_name',
  'operate_target_string'
];
const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';
export const commonAlertFieldMap = {
  status: [
    {
      id: isEn ? 'ABNORMAL' : '未恢复',
      name: window.i18n.tc('未恢复')
    },
    {
      id: isEn ? 'RECOVERED' : '已恢复',
      name: window.i18n.tc('已恢复')
    },
    {
      id: isEn ? 'CLOSED' : '已关闭',
      name: window.i18n.tc('已关闭')
    }
  ],
  severity: [
    {
      id: isEn ? 1 : '致命',
      name: window.i18n.tc('致命')
    },
    {
      id: isEn ? 2 : '预警',
      name: window.i18n.tc('预警')
    },
    {
      id: isEn ? 3 : '提醒',
      name: window.i18n.tc('提醒')
    }
  ]
};
const commonActionFieldMap = {
  status: [
    {
      id: isEn ? 'RUNNING' : '执行中',
      name: window.i18n.tc('执行中')
    },
    {
      id: isEn ? 'SUCCESS' : '成功',
      name: window.i18n.tc('成功')
    },
    {
      id: isEn ? 'FAILURE' : '失败',
      name: window.i18n.tc('失败')
    }
  ]
};
// 监控环境下侧栏初始宽度
const filterWidth = 240;
interface IPanelItem extends ICommonItem {
  id: eventPanelType;
}
interface IEventProps {
  toggleSet?: boolean;
  isSplitEventPanel?: boolean;
  defaultParams?: Record<string, any>;
}
Component.registerHooks(['beforeRouteEnter', 'beforeRouteLeave']);
const filterIconMap = {
  // MINE: {
  //   color: '#699DF4',
  //   icon: 'icon-mc-user-one'
  // },
  // MY_ASSIGNEE: {
  //   color: '#fff',
  //   icon: 'icon-inform-circle'
  // },
  MY_FOLLOW: {
    color: '#FF9C01',
    icon: 'icon-mc-note'
  },
  MY_APPOINTEE: {
    color: '#699DF4',
    icon: 'icon-mc-user-one'
  },
  NOT_SHIELDED_ABNORMAL: {
    color: '#EA3636',
    icon: 'icon-mind-fill'
  },
  SHIELDED_ABNORMAL: {
    color: '#C4C6CC',
    icon: 'icon-menu-shield'
  },
  RECOVERED: {
    color: '#2DCB56',
    icon: 'icon-mc-check-fill'
  },
  success: {
    color: '#2DCB56',
    icon: 'icon-mc-check-fill'
  },
  failure: {
    color: '#EA3636',
    icon: 'icon-mc-close-fill'
  }
};
@Component({
  name: 'Event'
})
class Event extends Mixins(authorityMixinCreate(eventAuth)) {
  @Provide('authority') authority;
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  // 监控左侧栏是否收缩配置 自愈默认未收缩
  @Prop({ default: false, type: Boolean }) readonly toggleSet: boolean;
  // 是否是分屏模式下的事件展示
  @Prop({ default: false, type: Boolean }) readonly isSplitEventPanel: boolean;
  @Prop({ default: () => ({}), type: Object }) readonly defaultParams: Record<string, any>;

  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly panelTimeRange!: number;
  // 图表刷新间隔
  @InjectReactive('refleshInterval') readonly panleRefleshInterval!: number;
  // 立即刷新图表
  @InjectReactive('refleshImmediate') readonly panelRefleshImmediate: string;

  @Ref('filterInput') filterInputRef: FilterInput;
  commonFilterData: ICommonTreeItem[] = [];
  /* 默认事件范围为近24小时 */
  timeRange: TimeRangeType = ['now-7d', 'now'] || DEFAULT_TIME_RANGE;
  /* 时区 */
  timezone: string = getDefautTimezone();
  refleshInterval = 5 * 60 * 1000;
  refleshInstance = null;
  allowedBizList = [];
  bizIds = [this.$store.getters.bizId];
  // 左侧过滤
  advancedFilterData = [];
  advancedFilterDefaultOpen = [];
  condition: Record<string, string[] | string> = {};
  activeFilterName = '';
  activeFilterId = '';
  searchType: SearchType = 'alert';

  // 告警分析
  analyzeData = [];
  analyzeFields = ['alert_name', 'metric', 'bk_biz_id', 'duration', 'ip', 'ipv6', 'bk_cloud_id'];
  analyzeTagList: ICommonItem[] = [];
  detailField = '';
  detailFieldData: any = {};
  detailLoading = false;
  // 处理记录分析
  analyzeActionFields = [
    'bk_biz_name',
    'action_name',
    'action_plugin_type',
    'operator',
    'duration',
    'strategy_name',
    'operate_target_string'
  ];

  // 表格
  alertPanelList: IPanelItem[] = [];
  actionPanelList: IPanelItem[] = [];
  activePanel: eventPanelType = 'list';
  tableData: IEventItem[] = [];
  tableLoading = false;
  selectedList: string[] = [];
  sortOrder = '';
  pagination = {
    current: 1,
    count: 1,
    limit: 10
  };

  // 查询
  chartInterval: string | number = 'auto';
  chartKey: string = random(10);
  alertChartMap: Record<string, number> = { ABNORMAL: 1, RECOVERED: 2, CLOSED: 3 };
  actionChartMap: Record<string, number> = { success: 1, failure: 2, running: 3, skipped: 4, shield: 5 };
  queryString = '';
  valueMap: Record<Partial<AnlyzeField>, ICommonItem[]> = null;

  filterWidth = 320;
  filterInputStatus: FilterInputStatus = 'success';
  // 侧栏详情信息
  detailInfo: { isShow: boolean; id: string; type: TSliderType; activeTab: string; bizId: number } = {
    isShow: false,
    id: '',
    type: 'eventDetail',
    activeTab: '',
    bizId: +window.bk_biz_id
  };
  dialog = {
    quickShield: {
      show: false,
      details: [
        {
          severity: 1,
          dimension: '',
          trigger: '',
          strategy: {
            id: '',
            name: ''
          }
        }
      ],
      ids: [],
      bizIds: []
    },
    alarmConfirm: {
      show: false,
      ids: [],
      bizIds: []
    },
    manualProcess: {
      show: false,
      alertIds: [],
      bizIds: [],
      debugKey: random(8),
      actionIds: [],
      mealInfo: null
    },
    alarmDispatch: {
      show: false,
      bizIds: [],
      alertIds: []
    }
  };
  routeStateKeyList: string[] = [];
  isRouteBack = false;

  disableHoverTimer = null;
  // 关联信息
  relateInfos: { [propName: string]: any } = {};
  // 关联事件数量
  eventCounts: { [propName: string]: number } = {};
  splitPanelWidth = 0;
  defaultPanelWidth = 0;
  isSplitPanel = false;
  /** 一键拉群弹窗 */
  chatGroupDialog: IChatGroupDialogOptions = {
    show: false,
    alertName: '',
    assignee: [],
    alertIds: []
  };

  // 过滤业务已选择是否为空
  filterSelectIsEmpty = false;
  showPermissionTips = true;
  noDataType: EmptyStatusType = 'empty';
  noDataString: any = '';
  bussinessTips: TranslateResult = '';
  allBizList = [];

  // 统计 未恢复告警的通知人 栏为空的人数。
  numOfEmptyAssignee = 0;

  // 缓存topn概览数据（用于添加字段是无需调用接口）
  topNOverviewData = {
    fieldList: [],
    count: 0
  };

  get panelList(): IPanelItem[] {
    return this.searchType === 'action' ? this.actionPanelList : this.alertPanelList;
  }
  get curAnalyzeFields() {
    return this.searchType === 'alert' ? this.analyzeFields : this.analyzeActionFields;
  }

  // 是否拥有查询条件： 搜索条件或者高级筛选条件
  get hasSearchParams() {
    return !!(this.queryString || Object.values(this.condition).some(item => item.length));
  }

  @Watch('panelTimeRange')
  // 数据时间间隔
  handlePanelTimeRangeChange(v: TimeRangeType) {
    this.handleTimeRangeChange(v);
  }
  @Watch('panelRefleshInterval')
  // 数据刷新间隔
  handlePanelRefleshIntervalChange(v: number) {
    this.handleRefleshChange(v);
  }
  @Watch('panelRefleshImmediate')
  // 立刻刷新
  handlePanelRefleshImmediateChange(v: string) {
    if (v) this.handleImmediateReflesh();
  }
  @Watch('defaultParams', { immediate: true })
  async handleDefaultParamsChange(v: Record<string, any>) {
    if (this.isSplitEventPanel) {
      this.routeStateKeyList = [];
      Object.keys(v).forEach(key => (this[key] = v[key]));
      await Promise.all([this.handleGetFilterData(), this.handleGetTableData(true)]);
      this.handleRefleshChange(this.refleshInterval);
    }
  }
  async created() {
    this.alertPanelList = [
      {
        id: 'list',
        name: this.$t('告警列表')
      },
      {
        id: 'analyze',
        name: this.$t('告警分析')
      }
    ];
    this.actionPanelList = [
      {
        id: 'list',
        name: this.$t('处理记录')
      },
      {
        id: 'analyze',
        name: this.$t('记录分析')
      }
    ];
    if (!localStorage.getItem(alertAnalyzeStorageKey)) {
      localStorage.setItem(alertAnalyzeStorageKey, JSON.stringify(this.analyzeFields));
    }
    if (!localStorage.getItem(actionAnalyzeStorageKey)) {
      localStorage.setItem(actionAnalyzeStorageKey, JSON.stringify(this.analyzeActionFields));
    }
    // 监控环境下侧栏宽度变小
    this.setFilterDefaultWidth();
    this.analyzeFields = this.handleGetAnalyzeField(alertAnalyzeStorageKey, this.analyzeFields);
    this.analyzeActionFields = this.handleGetAnalyzeField(actionAnalyzeStorageKey, this.analyzeActionFields);
    !this.isSplitEventPanel && window.addEventListener('popstate', this.handlePopstate);
  }

  beforeRouteEnter(to, from, next) {
    next(async (vm: Event) => {
      vm.routeStateKeyList = [];
      const params = vm.handleUrl2Params();
      Object.keys(params).forEach(key => {
        if (key === 'timezone') {
          updateTimezone(params[key]);
        }
        vm[key] = params[key];
      });
      if (vm.bizIds?.length) {
        vm.showPermissionTips = vm.bizIds
          .filter(id => ![authorityBizId, hasDataBizId].includes(+id))
          .some(id => !window.space_list.some(item => item.id === id));
      }
      if (params?.promql?.length) {
        const queryData = await promqlToQueryConfig({
          promql: params.promql
        }).catch(() => false);
        if (queryData?.query_configs?.length) {
          const { query_configs } = queryData;
          let queryString = '';
          const uniqueMap = {};
          query_configs.forEach((item, index) => {
            if (item.metric_id && !uniqueMap[item.metric_id]) {
              queryString += `${index > 0 ? ' OR ' : ''}${isEn ? 'metric' : '指标ID'}: "${item.metric_id}"`;
              uniqueMap[item.metric_id] = true;
            }
          });
          vm.queryString = queryString;
        }
      }
      // await vm.handleGetAllBizList();
      await Promise.all([vm.handleGetFilterData(), vm.handleGetTableData(true)]);
      vm.handleRefleshChange(vm.refleshInterval);
      // 正常进入告警页情况下不打开详情，只有通过告警通知进入的才展开详情
      const queryString = vm.$route.query;
      const paramString = vm.$route.params;
      const needShowDetail = /(^id).+/g.test(queryString.queryString as string);
      if ((Object.keys(queryString).length || Object.keys(paramString).length) && needShowDetail) {
        vm.handleFirstShowDetail();
      }
      // 批量弹窗 (batchAction=xxx并且queryString 包含action_id 搜索 则弹出弹窗)
      if (
        [EBatchAction.alarmConfirm, EBatchAction.quickShield].includes(params.batchAction) &&
        /(^action_id).+/g.test(params.queryString)
      ) {
        vm.selectedList = vm.tableData.map(t => t.id);
        const bizIds = [];
        vm.tableData.forEach(item => {
          if (vm.selectedList.includes(item.id) && !bizIds.includes(item.bk_biz_id)) {
            bizIds.push(item.bk_biz_id);
          }
        });
        vm.handleBatchAlert(params.batchAction);
      }
    });
  }
  beforeRouteLeave(to, from, next) {
    this.detailInfo.isShow = false;
    destroyTimezone();
    next();
  }

  async mounted() {
    const { contentWrap } = this.$refs as any;
    (contentWrap as HTMLDivElement).addEventListener('scroll', this.handleDisbaleHover, false);
  }

  beforeDestroy() {
    this.routeStateKeyList = [];
    window.removeEventListener('popstate', this.handlePopstate);
    const { contentWrap } = this.$refs as any;
    (contentWrap as HTMLDivElement).removeEventListener('scroll', this.handleDisbaleHover, false);
    window.clearInterval(this.refleshInstance);
  }
  async handleGetAllBizList() {
    const allBizList = await listSpaces({ show_all: true });
    // const allBizList = await businessListOption({ show_all: true });
    this.allBizList = allBizList.map(item => ({
      id: item.bk_biz_id,
      text: item.space_name,
      name: item.space_name
    }));
  }
  // 拼一个查询语句，然后查询 未恢复的且处理阶段都不满足 的异常通知人数据（显示是通知人为空）
  setQueryStringForCheckingEmptyAssignee() {
    let queryString = `${this.$t('通知人')} : "" AND ${this.$t('状态')} : 未恢复`;
    // 通过点击查看空通知人按钮进来的查询语句需要拼接到原先查询语句的后方
    // 需要判断原查询语句是否已经带有 查询通知人为空 的语句，防止重复拼接
    if (!this.queryString.includes(queryString)) {
      if (this.queryString.length) {
        queryString = `${this.queryString} AND ${queryString}`;
      }
    } else {
      queryString = this.queryString;
    }
    this.handleQueryStringChange(queryString);
  }
  handleDisbaleHover() {
    const { contentTable } = this.$refs as any;
    clearTimeout(this.disableHoverTimer);
    if (!contentTable.classList.contains('disable-hover')) {
      contentTable.classList.add('disable-hover');
    }

    this.disableHoverTimer = setTimeout(() => {
      contentTable.classList.remove('disable-hover');
    }, 500);
  }

  /** 获取路由某个参数参数 */
  getUrlParamsItem(key: string, queryStr?: string) {
    const queryDataString = queryStr || this.$route.params?.data || this.$route.query?.data;
    let queryData: Record<string, any> = {};
    if (queryDataString?.length) {
      try {
        queryData = JSON.parse(queryDataString.toString());
      } catch {
        queryData = {};
      }
    }
    return queryData[key] ?? null;
  }
  /**
   * @description: 获取路由query参数
   * @param {*}
   * @return {*}
   */
  handleGetRouteQueryParams(queryStr = ''): Record<string, any> {
    const queryDataString = queryStr || this.$route.params?.data || this.$route.query?.data;
    let queryData: Record<string, any> = {};
    if (queryDataString?.length) {
      try {
        queryData = JSON.parse(queryDataString.toString());
      } catch {
        queryData = {};
      }
    }
    const query = {};
    Object.keys(this.$route.query).forEach(key => {
      if (!['data', 'key'].includes(key)) {
        const val = this.$route.query[key];
        if (typeof val === 'string' && val.includes('{')) {
          try {
            query[key] = JSON.parse(val);
          } catch {
            query[key] = {};
          }
        } else if (key === 'bizIds') {
          query[key] = Array.isArray(val) ? val.map(id => +id) : [+(val || this.$store.getters.bizId || -1)];
        } else if (['from', 'to'].includes(key)) {
          key === 'from' && this.$set(this.timeRange, 0, val);
          key === 'to' && this.$set(this.timeRange, 1, val);
          query[key] = val;
        } else if (key === 'promql') {
          query[key] = decodeURIComponent((val as string) || '');
        } else {
          query[key] = val;
        }
      }
    });
    return {
      ...queryData,
      ...query
    };
  }

  handleUrl2Params(): any {
    const defaultData: any = { ...this.handleGetDefaultRouteData(), ...this.handleGetRouteQueryParams() };
    if (defaultData.actionId && defaultData.actionId.toString().length > 10) {
      defaultData.queryString = defaultData.queryString
        ? `${defaultData.queryString} AND action_id : ${defaultData.actionId}`
        : `action_id : ${defaultData.actionId}`;
      const time = +defaultData.actionId.toString().slice(0, 10) * 1000;
      defaultData.timeRange = [
        dayjs.tz(time).add(-30, 'd').format('YYYY-MM-DD HH:mm:ss'),
        dayjs.tz(time).format('YYYY-MM-DD HH:mm:ss')
      ];
    }
    /** 移动端带collectId跳转事件中心 */
    if (!!defaultData.collectId) {
      defaultData.queryString = defaultData.queryString
        ? `${defaultData.queryString} AND action_id : ${defaultData.collectId}`
        : `action_id : ${defaultData.collectId}`;
      /* 带collectId是事件范围设为近15天 */
      defaultData.timeRange = ['now-30d', 'now'];
    }
    /** 处理指标参数 */
    if (!!defaultData.metricId?.length) {
      const metricStr = `metric : (${defaultData.metricId.map(item => `"${item}"`).join(' OR ')})`;
      defaultData.queryString = defaultData.queryString ? `AND ${metricStr}` : metricStr;
    }
    return defaultData;
  }
  /**
   * @description: popstate事件触发 用于记录用户搜索操作历史
   * @param {*} event
   * @return {*}
   */
  async handlePopstate() {
    if (this.isSplitEventPanel) return;
    let params = this.handleUrl2Params();
    const index = this.routeStateKeyList.findIndex(key => key === this.$route.query.key);
    params = index === -1 ? this.handleGetDefaultRouteData() : params;
    if (this.$route.name === 'event-center') {
      Object.keys(params).forEach(key => (this[key] = params[key]));
      this.isRouteBack = true;
      this.chartKey = random(10);
      await Promise.all([this.handleGetFilterData(), this.handleGetTableData(true)]);
      this.isRouteBack = false;
      this.handleRefleshChange(this.refleshInterval);
    }
  }
  /**
   * @description: 查询参数获取
   * @param {*} onlyOverview 是否overview
   * @param {*} commonParams 是否获取同用参数
   * @return {*}
   */
  handleGetSearchParams(onlyOverview = false, commonParams = false) {
    // const { startTime, endTime } = this.handleGetTimeRange();
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    let params: any = {
      bk_biz_ids: this.bizIds.includes(hasDataBizId) ? [] : this.bizIds,
      status:
        !onlyOverview && this.activeFilterId && this.searchType !== this.activeFilterId ? [this.activeFilterId] : [],
      // 状态，可选 MINE, ABNORMAL, CLOSED, RECOVERED
      conditions: !onlyOverview
        ? Object.keys(this.condition)
            .map((key, index) =>
              Object.assign({ key, value: this.condition[key] }, index > 0 ? { condition: 'and' } : {})
            )
            .filter(item => item.value?.length)
        : [], // 过滤条件，二维数组
      // 在查询前，将 queryString 中查询 通知人 为空的语句进行替换。
      // 为什么不在 input 框（queryString）上替换，会有意料之外的bug，也符合操作直觉。
      query_string: !onlyOverview ? this.replaceSpecialCondition(this.queryString) : '', // 查询字符串
      start_time: startTime, // 开始时间
      end_time: endTime // 结束时间
    };
    const isManualInput = this.filterInputRef?.isManualInput; // 是否手动输入
    if (!commonParams) {
      params = {
        ...params,
        ordering: (() => {
          // 排序字段，字段前面加 "-" 代表倒序
          if (onlyOverview) {
            return [];
          }
          return this.sortOrder ? [this.sortOrder] : [];
        })(),
        page: this.pagination.current,
        page_size: onlyOverview ? 0 : this.pagination.limit,
        show_overview: onlyOverview, // 是否返回总览统计信息，默认 true
        show_aggs: !onlyOverview, // 是否返回聚合统计信息，默认 true
        record_history: !onlyOverview && isManualInput // 是否保存收藏历史，默认 false
      };
    }
    return params;
  }
  /**
   * @description: 获取处理记录列表信息
   * @param {*}
   * @return {*}
   */
  async handleGetSearchActionList(onlyOverview = false) {
    const params = {
      ...this.handleGetSearchParams(onlyOverview),
      // alert_ids: this.handleUrl2Params()?.alertIds || [] // 告警ID
      alert_ids: this.getUrlParamsItem('alertIds') || [] // 告警ID
    };
    const {
      aggs,
      actions: list,
      overview,
      total,
      code
    } = await searchAction(params, { needRes: true, needMessage: false })
      .then(res => {
        !onlyOverview && (this.filterInputStatus = 'success');
        return res.data || {};
      })
      .catch(({ message, code }) => {
        if (code !== grammaticalErrorCode) {
          this.$bkMessage({ message, theme: 'error' });
        }
        return {
          aggs: [],
          actions: [],
          overview: [],
          total: 0,
          code
        };
      });
    return {
      aggs,
      list:
        list?.map(item => {
          // 处理记录的具体内容不可直接转换成html
          const contentArr = item?.content?.text.split('$') || [];
          let content = () => <span>{item?.content?.text || '--'}</span>;
          if (contentArr[1]) {
            content = () => (
              <span>
                {contentArr[0]}
                {
                  <a
                    target='blank'
                    href={item.content.url}
                  >
                    {contentArr[1]}
                  </a>
                }
                {contentArr[2] || ''}
              </span>
            );
          }
          return {
            ...item,
            alert_count: item?.alert_id?.length || '-1',
            content,
            bizName: this.allowedBizList?.find(set => +set.id === +item.bk_biz_id)?.name || '--'
          };
        }) || [],
      overview,
      total,
      code
    };
  }

  /**
   * @description: 获取告警列表信息
   * @param {*} onlyOverview 是否overview模式
   * @return {*}
   */
  async handleGetSearchAlertList(onlyOverview = false) {
    const {
      aggs,
      alerts: list,
      overview,
      total,
      code
    } = await searchAlert(this.handleGetSearchParams(onlyOverview), { needRes: true, needMessage: false })
      .then(res => {
        !onlyOverview && (this.filterInputStatus = 'success');
        return res.data || {};
      })
      .catch(({ message, code }) => {
        if (code !== grammaticalErrorCode) {
          this.$bkMessage({ message, theme: 'error' });
        }
        return {
          aggs: [],
          alerts: [],
          overview: [],
          total: 0,
          code
        };
      });
    if (list?.length && !onlyOverview) {
      const ids = list.map(item => item.id);
      this.handleGetEventRelateInfo(ids);
      this.handleGetEventCount(ids);
    }
    return {
      aggs,
      list: list?.map(item => ({
        ...item,
        extend_info: '',
        event_count: '--',
        bizName: this.allowedBizList?.find(set => +set.id === +item.bk_biz_id)?.name || '--'
      })),
      overview,
      total,
      code
    };
  }

  /**
   * @description: 获取告警分析TopN数据
   * @param {*}
   * @return {*}
   */
  async handleGetSearchTopNList(isDetail = false, isInit = true) {
    // 告警分析才需要tags topn
    if (this.searchType === 'alert' && isInit && !isDetail) {
      await this.handleGetAlertTagList();
    }
    let allFieldList = [];
    // 告警分析
    if (this.searchType === 'alert') {
      allFieldList =
        this.bizIds.includes(-1) || this.bizIds.length > 1 ? ['bk_biz_id', ...allAnlyzeFieldList] : allAnlyzeFieldList;
    } else if (this.searchType === 'action') {
      // 处理记录
      allFieldList =
        this.bizIds.includes(-1) || this.bizIds.length > 1 ? ['bk_biz_id', ...allActionFieldList] : allActionFieldList;
    }
    const analyzeFields = this.searchType === 'alert' ? this.analyzeFields : this.analyzeActionFields;
    const topNFieldList =
      this.bizIds.includes(-1) || this.bizIds.length > 1
        ? ['bk_biz_id', ...analyzeFields.filter(id => id !== 'bk_biz_id')]
        : analyzeFields.filter(id => id !== 'bk_biz_id');
    const tagList = this.searchType === 'alert' ? this.analyzeTagList || [] : [];
    // const topNFunc = this.searchType === 'alert' ? alertTopN : actionTopN;
    // const { fields: fieldList, doc_count: count } = await topNFunc({
    //   ...this.handleGetSearchParams(false, true),
    //   fields: (!isDetail ? [...allFieldList, ...(tagList || []).map(item => item.id)] : [this.detailField])
    //     .slice(0, 50),
    //   size: isDetail ? 100 : 10
    // }, { needCancel: true }).catch(() => ({ doc_count: 0, fields: [] }));
    const setTopnDataFn = (fieldList, count) => {
      if (!isDetail) {
        this.topNOverviewData.fieldList = fieldList;
        this.topNOverviewData.count = count;
      }
      const valueMap: any = {};
      const list = [];
      (fieldList || []).forEach(item => {
        valueMap[item.field] =
          item.buckets.map(set => {
            if (tagList.some(tag => tag.id === item.field)) {
              return { id: set.id, name: `"${set.name}"` };
            }
            return { id: set.id, name: item.field === 'strategy_id' ? set.id : `"${set.name}"` };
          }) || [];
        if (topNFieldList.includes(item.field)) {
          list.push({
            ...item,
            buckets: (item.buckets || []).map(set => ({
              ...set,
              name: set.name,
              percent: count ? Number((set.count / count).toFixed(4)) : 0
            }))
          });
        }
      });
      // 特殊添加一个空选项给 通知人 ，注意：仅仅加个 空 值还不够，之后查询之前还要执行一次 replaceSpecialCondition
      // 去替换这里添加的 空值 ，使之最后替换成这样 'NOT 通知人 : *'
      if (valueMap.assignee) {
        valueMap.assignee.unshift({
          id: '""',
          name: this.$t('- 空 -')
        });
      }
      if (tagList?.length) {
        valueMap.tags = tagList.map(item => ({ id: item.name, name: item.name }));
      }
      this.valueMap = Object.assign(valueMap, this.searchType === 'alert' ? commonAlertFieldMap : commonActionFieldMap);
      if (!isDetail) {
        this.analyzeData = list;
      } else {
        this.detailFieldData = list.find(item => item.field === this.detailField) || {};
      }
    };
    if (!isInit) {
      setTopnDataFn(this.topNOverviewData.fieldList, this.topNOverviewData.count);
      return;
    }
    /*
      alertTopN接口分为两部分请求 (固定字段及带tags前缀的字段(带前缀的字段只取20个) )
    */
    const topNParams = {
      ...this.handleGetSearchParams(false, true),
      fields: !isDetail ? [...allFieldList, ...(tagList || []).map(item => item.id)] : [this.detailField],
      size: isDetail ? 100 : 10
    };
    let fieldList = [];
    let count = 0;
    if (this.searchType === 'alert') {
      const { fields, doc_count } = await alertTopN(
        {
          ...topNParams,
          fields: !isDetail ? [...allFieldList] : [this.detailField]
        },
        { needCancel: true }
      ).catch(() => ({ doc_count: 0, fields: [] }));
      fieldList = fields;
      count = doc_count;
      if (!isDetail) {
        alertTopN(
          {
            ...topNParams,
            fields: (!isDetail ? [...(tagList || []).map(item => item.id)] : [this.detailField]).slice(0, 20)
          },
          { needCancel: true }
        )
          .then(({ fields, doc_count }) => {
            fieldList = [...fieldList, ...fields];
            count = doc_count;
            setTopnDataFn(fieldList, count);
          })
          .catch(err => console.error(err));
      }
    } else {
      const { fields, doc_count } = await actionTopN({ ...topNParams }, { needCancel: true }).catch(() => ({
        doc_count: 0,
        fields: []
      }));
      fieldList = fields;
      count = doc_count;
    }
    setTopnDataFn(fieldList, count);
  }
  /**
   * @description: 获取告警分析告警tag列表数据
   * @param {*}
   * @return {*}
   */
  async handleGetAlertTagList() {
    const list = await listAlertTags({
      ...this.handleGetSearchParams(false, true)
    }).catch(() => []);
    this.analyzeTagList = list;
  }
  handleGetAnalyzeField(storageKey: string, defaultKey?: string[]) {
    const storeFields = localStorage.getItem(storageKey);
    let fields = defaultKey || [];
    try {
      fields = storeFields ? JSON.parse(storeFields) : fields;
    } catch {
      return fields;
    }
    return fields;
  }
  /**
   * @description: 获取当前告警关联信息
   * @param {string} ids 过滤的id列表
   * @return {*}
   */
  async handleGetEventRelateInfo(ids: string[]) {
    const data = await EventStoreModule.getAlertRelatedInfo({ ids });
    this.relateInfos = data;
    if (data) {
      this.tableData.forEach(item => {
        item.extend_info = data[item.id];
      });
    }
  }

  /**
   * @description: 获取告警关联事件数量
   * @param {string} ids 过滤的id列表
   * @return {*}
   */
  async handleGetEventCount(ids: string[]) {
    const data = await EventStoreModule.getAlertEventCount({ ids });
    this.eventCounts = data;
    if (data) {
      this.tableData.forEach(item => {
        item.event_count = data[item.id] || -1;
      });
    }
  }
  /**
   * @description: 获取左侧面板统计数据
   * @param {*}
   * @return {*}
   */
  async handleGetFilterData() {
    const [{ overview }, { overview: actionOverview }] = await Promise.all([
      this.handleGetSearchAlertList(true),
      this.handleGetSearchActionList(true)
    ]).catch(() => [{ overview: [] }, { overview: [] }]);
    this.commonFilterData = [overview, { ...actionOverview }];
    if (!this.activeFilterId) {
      this.activeFilterId = overview.id;
      this.activeFilterName = overview.name;
    } else if (this.activeFilterId) {
      this.activeFilterName =
        [overview, actionOverview, ...overview.children, ...actionOverview.children].find(
          item => item.id === this.activeFilterId
        )?.name || '';
      if (!this.activeFilterName) {
        this.activeFilterId = overview.id;
        this.activeFilterName = overview.name;
      }
    }
  }
  /**
   * @description: 校验查询语句语法
   * @param {*}
   */
  async handleValidateQueryString() {
    let validate = true;
    if (this.queryString?.length) {
      validate = await validateQueryString(
        { query_string: this.replaceSpecialCondition(this.queryString), search_type: this.searchType },
        { needMessage: false, needRes: true }
      )
        .then(res => res.result)
        .catch(() => false);
    }
    if (!validate) {
      this.filterInputStatus = 'error';
      this.tableLoading = false;
    }
    return validate;
  }
  // 将特殊的查询条件进行替换，使其符合后端的查询规则校验。
  // 在验证 queryString 和 告警列表 查询时会使用
  replaceSpecialCondition(qs: string) {
    // 由于验证 queryString 不允许使用单引号，为提升体验，这里单双引号的空串都会进行替换。
    const regExp = new RegExp(`${this.$t('通知人')}\\s*:\\s*(""|'')`, 'gi');
    return qs.replace(regExp, `NOT ${this.$t('通知人')} : *`);
  }
  /**
   * @description: 获取表格数据
   * @param {*} searchTypeChange alert 事件 | action 处理记录 是否变更
   * @param {*} refleshAgg 是否刷新左侧统计信息
   * @param {*} isPageChange 是否切换分页
   */
  async handleGetTableData(searchTypeChange = false, refleshAgg = true, needTopN = true) {
    this.tableLoading = true;
    // await this.handleValidateQueryString()
    if (!this.allowedBizList?.length) {
      await this.handleGetAllowedBizList();
    }
    await this.$nextTick();
    const promiseList = [];
    if (this.searchType === 'alert') {
      promiseList.push(this.handleGetSearchAlertList());
    } else if (this.searchType === 'action') {
      promiseList.push(this.handleGetSearchActionList());
    }
    if (this.activePanel === 'analyze') {
      needTopN && promiseList.push(this.handleGetSearchTopNList(false));
    } else {
      needTopN && (await this.handleGetSearchTopNList(false));
    }
    const [{ aggs, list, total, code }] = await Promise.all(promiseList);
    // 语法错误
    this.filterInputStatus = code !== grammaticalErrorCode ? 'success' : 'error';
    // 数据接口是否报错
    const isError = code && code !== grammaticalErrorCode;
    if (searchTypeChange) {
      if (
        !this.advancedFilterDefaultOpen?.length ||
        !this.advancedFilterDefaultOpen.every(id => aggs.some(set => set.id === id))
      ) {
        this.advancedFilterDefaultOpen = aggs?.length ? aggs.map(agg => agg.id) : [];
      }
    }
    if (refleshAgg) {
      this.advancedFilterData = aggs || [];
    }
    this.tableData =
      list.map(item => ({
        ...item,
        extend_info: this.relateInfos?.[item.id] || '',
        event_count: this.eventCounts?.[item.id] || '--',
        followerDisabled: this.searchType === 'alert' ? getOperatorDisabled(item.follower, item.assignee) : false
      })) || [];

    // 查找当前表格的 告警 标签是否有 通知人 为空的情况。BugID: 1010158081103484871
    this.numOfEmptyAssignee = this.tableData.filter(
      (item: IEventItem) => this.searchType === 'alert' && !item.assignee?.length && item.status === 'ABNORMAL'
    ).length;

    const ublist = this.allowedBizList.filter(item => item.noAuth && this.bizIds.includes(item.id));
    this.bussinessTips = '';
    if (!this.tableData.length) {
      if (ublist.length) {
        this.noDataType = '403';
        this.noDataString = this.$t('您没有该业务的权限，请先申请!');
      } else if (isError) {
        this.noDataType = '500';
        this.noDataString = '';
      } else {
        this.noDataType = this.hasSearchParams ? 'search-empty' : 'empty';
        if (!this.bizIds?.some(id => [authorityBizId, hasDataBizId].includes(id))) {
          this.noDataString = this.$t('你当前有 {0} 个业务权限，暂无告警事件', [window.space_list.length]);
        } else {
          this.noDataString = '';
        }
      }
    } else {
      if (ublist.length) {
        const hasDatalist = ublist.filter(item => item.hasData).map(item => item.name);
        const noBussinessList = ublist.filter(item => !item.hasData).map(item => item.name);
        let tips = '';
        if (hasDatalist.length) {
          tips += `${hasDatalist.join(',')} 业务仅能查看属于本人的告警，`;
        }
        if (noBussinessList.length) {
          tips += `${noBussinessList.join(',')} 业务无权限且无数据，`;
        }
        tips += '如需查看业务全部告警，可前往申请相关业务权限';
        this.bussinessTips = tips;
      }
    }
    this.pagination.count = total || 0;
    if (!this.isRouteBack && !this.isSplitEventPanel) {
      const key = random(10);
      const params = {
        name: this.$route.name,
        query: {
          ...this.handleParam2Url(),
          key
        }
      };
      this.routeStateKeyList.length === 0 ? this.$router.replace(params) : this.$router.push(params);
      this.routeStateKeyList.push(key);
    }
    this.tableLoading = false;
  }

  handleFirstShowDetail() {
    const [firstData] = this.tableData;
    if (firstData) {
      const params = {
        id: firstData.id,
        type: this.searchType === 'alert' ? ('eventDetail' as TSliderType) : ('handleDetail' as TSliderType),
        activeTab: '',
        bizId: firstData.bk_biz_id
      };
      this.handleShowDetail(params);
    }
  }

  handleGetDefaultRouteData() {
    return {
      queryString: '',
      searchType: 'alert',
      activeFilterId: 'alert',
      sortOrder: '',
      // timeRange: 3600000,
      from: 'now-30d',
      to: 'now',
      timezone: getDefautTimezone(),
      refleshInterval: 300000,
      activePanel: 'list',
      chartInterval: 'auto',
      condition: {},
      // advancedFilterDefaultOpen: [],
      bizIds: [this.$store.getters.bizId || window.cc_biz_id],
      batchAction: ''
    };
  }
  handleParam2Url() {
    const defaultRouteData = this.handleGetDefaultRouteData();
    const newData = {};
    Object.keys(defaultRouteData).forEach(key => {
      const item = defaultRouteData[key];
      if (item !== this[key]) {
        if (typeof this[key] === 'object') {
          if (Array.isArray(this[key]) && this[key].length === 0) {
            return false;
          }
          if (Object.keys(this[key]).length === 0) {
            return false;
          }
          if (!Array.isArray(this[key])) {
            newData[key] = JSON.stringify(this[key]);
            return;
          }
          if (key === 'activeFilter' && this[key].id === 'alert') {
            return false;
          }
        }
        newData[key] = this[key];
      }
      if (['from', 'to'].includes(key)) {
        key === 'from' && ([newData[key]] = this.timeRange);
        key === 'to' && ([, newData[key]] = this.timeRange);
      } else if (key === 'timezone') {
        newData[key] = this.timezone;
      }
      return false;
    });
    return newData;
  }
  /**
   * @description: 获取有权限的业务列表
   * @param {*}
   * @return {*}
   */
  async handleGetAllowedBizList() {
    const { business_list, business_with_alert, business_with_permission } = await bizWithAlertStatistics().catch(
      () => ({})
    );
    this.allBizList = business_list.map(item => ({
      id: item.bk_biz_id,
      name: `[${item.bk_biz_id}] ${item.bk_biz_name}`
    }));
    const data =
      business_with_permission.map(item => ({
        ...item,
        id: item.bk_biz_id,
        name: `[${item.bk_biz_id}] ${item.bk_biz_name}`,
        sort: this.bizIds.includes(item.id) ? 2 : 1
      })) || [];
    if (business_with_alert?.length) {
      business_with_alert.forEach(item => {
        data.push({
          name: `[${item.bk_biz_id}] ${item.bk_biz_name}`,
          id: item.bk_biz_id,
          noAuth: true,
          hasData: true,
          sort: 2
        });
      });
    }
    this.bizIds?.forEach(id => {
      const bizItem = this.allBizList.find(set => set.id === id);
      if (bizItem && !data.some(set => set.id === id)) {
        data.push({
          name: bizItem.name,
          id: bizItem.id,
          noAuth: true,
          sort: 2
        });
      }
    });
    if (data.length) {
      data.unshift({
        id: hasDataBizId,
        name: this.$t('-我有告警的空间-'),
        sort: 3
      });
      data.unshift({
        id: authorityBizId,
        name: this.$t('-我有权限的空间-'),
        sort: 3
      });
    }
    data.sort((a, b) => b.sort - a.sort);
    this.allowedBizList = data;
  }
  /**
   * @description: 获取趋势图表数据
   * @param {string} from
   * @param {string} to
   * @return {*}
   */
  async handleGetAlertDateHistogram(from?: string, to?: string) {
    const {
      bk_biz_ids,
      conditions,
      start_time: startTime,
      end_time: endTime,
      query_string,
      status
    } = this.handleGetSearchParams(false, true);
    const params = {
      bk_biz_ids,
      conditions, // 过滤条件，二维数组
      query_string,
      status,
      start_time: from ? dayjs.tz(from).unix() : startTime, // 开始时间
      end_time: to ? dayjs.tz(to).unix() : endTime, // 结束时间
      interval: this.chartInterval
    };
    const promiseFn = this.searchType === 'action' ? actionDateHistogram : alertDateHistogram;
    const { unit, series, code } = await promiseFn(params, { needRes: true, needMessage: false })
      .then(res => res.data)
      .catch(({ code, message }) => {
        if (code !== grammaticalErrorCode) {
          this.$bkMessage({ message, theme: 'error' });
        }
        return {
          series: [],
          unit: '',
          code
        };
      });
    if (from) {
      this.timeRange = [
        dayjs.tz(params.start_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
        dayjs.tz(params.end_time * 1000).format('YYYY-MM-DD HH:mm:ss')
      ];
      this.handleGetFilterData();
      this.pagination.current = 1;
      this.handleGetTableData();
    }
    const chartMap = this.searchType === 'action' ? this.actionChartMap : this.alertChartMap;
    this.filterInputStatus = code !== grammaticalErrorCode ? 'success' : 'error';
    return {
      unit,
      series: series
        .sort((a, b) => chartMap[a.name] - chartMap[b.name])
        .map(item => ({ ...item, name: item.display_name, stack: 'event-alram' }))
    };
  }
  /**
   * @description: 左侧过滤面板选中触发
   * @param {SearchType} id 数据类型 action | alert
   * @param {ICommonTreeItem} item 选中的数据id
   * @return {*}
   */
  handleSelectActiveFilter(id: SearchType, item: ICommonTreeItem) {
    if (this.tableLoading) return;
    const isTypeChange = this.searchType !== id;
    this.searchType = id;
    setLocalStoreRoute(this.searchType === 'action' ? 'event-action' : 'event-center');
    if (isTypeChange) {
      this.handleQueryStringChange('');
      this.sortOrder = '';
      this.condition = {};
    }
    this.activeFilterId = item.id;
    this.activeFilterName = item.name;
    this.pagination.current = 1;
    this.chartKey = random(10);
    this.handleGetTableData(isTypeChange);
    this.handleGetFilterData();
  }
  /**
   * @description: 拖动左侧面板触发
   * @param {number} v 拖动的宽度
   * @return {*}
   */
  handleDragFilter(v: number) {
    this.filterWidth = v;
  }
  /**
   * @description: 显示详情数据
   * @param {IShowDetail}
   * @return {*}
   */
  handleShowDetail({ id, type, activeTab, bizId }: IShowDetail) {
    this.detailInfo.id = id;
    this.detailInfo.type = type;
    this.detailInfo.isShow = true;
    this.detailInfo.bizId = bizId;
    this.detailInfo.activeTab = activeTab;
  }

  /**
   * @description: 刷新间隔改变时触发
   * @param {number} v 刷新周期
   * @return {*}
   */
  handleRefleshChange(v: number) {
    window.clearInterval(this.refleshInstance);
    this.refleshInterval = v;
    v > 0 &&
      (this.refleshInstance = setInterval(() => {
        this.chartKey = random(10);
        this.handleGetFilterData();
        this.handleGetTableData();
      }, this.refleshInterval));
  }
  /**
   * @description: 点击立刻刷新图标触发
   * @param {*}
   * @return {*}
   */
  handleImmediateReflesh() {
    this.chartKey = random(10);
    this.handleGetFilterData();
    this.handleGetTableData();
    this.refleshInterval > 0 && this.handleRefleshChange(this.refleshInterval);
  }
  /**
   * @description: 数据间隔改变时触发
   * @param {*} v 事件间隔
   * @return {*}
   */
  handleTimeRangeChange(v: TimeRangeType) {
    this.timeRange = v;
    this.chartKey = random(10);
    this.handleGetFilterData();
    this.pagination.current = 1;
    this.handleGetTableData();
  }
  /**
   *
   * @param v 时区
   * @description 时区改变时触发
   */
  handleTimezoneChange(v: string) {
    this.timezone = v;
    updateTimezone(v);
    this.chartKey = random(10);
    this.handleGetFilterData();
    this.handleGetTableData();
    this.handleRefleshChange(this.refleshInterval);
  }
  handleBizIdsChange(v: number[]) {
    this.bizIds = v;
    this.handleBizChange(v);
  }
  /**
   * @description: 业务变更时触发
   * @param {number} newV 业务id列表
   * @return {*}
   */
  handleBizChange(newV: number[]) {
    if (!newV.length || [authorityBizId, hasDataBizId].includes(newV[newV.length - 1])) {
      this.bizIds = [newV[newV.length - 1]];
    } else {
      this.bizIds = newV.filter(id => ![authorityBizId, hasDataBizId].includes(id));
    }
    this.bizIds = this.bizIds.filter(id => !!id);
    this.chartKey = random(10);
    this.handleGetFilterData();
    this.pagination.current = 1;
    this.handleGetTableData();
    // const list  = this.allowedBizList.map(item => ({
    //   ...item,
    //   sort: [authorityBizId, hasDataBizId].includes(item.id) ? 3 : (this.bizIds.includes(item.id) ? 2 : 1)
    // }));
    // this.allowedBizList = list.sort((a, b) => b.sort - a.sort);
    this.filterSelectIsEmpty = false;
  }

  /**
   * @description: 表格页变更时触发
   * @param {number} page 页数
   * @return {*}
   */
  async handleTabelPageChange(page: number) {
    this.pagination.current = page;
    await this.handleGetTableData(false, true, false);
  }

  /**
   * @description: 表格页面变更时触发
   * @param {number} limit 页码
   * @return {*}
   */
  async handleTableLimitChange(limit: number) {
    this.pagination.current = 1;
    this.pagination.limit = limit;
    await this.handleGetTableData(false, true, false);
  }

  /**
   * @description: 表格行数据选中时触发
   * @param {string} v 表格选中的事件id列表
   * @return {*}
   */
  handleTableSelecChange(v: string[]) {
    this.selectedList = v;
  }
  /**
   * @description: 表格排序触发
   * @param {string} v 排序字段名称
   * @return {*}
   */
  handleSortChange(v: string) {
    this.sortOrder = v;
    this.handleGetTableData(false, true, false);
  }
  /**
   * @description: 点击导出数据时触发
   * @param {*}
   * @return {*}
   */
  async handleExportData() {
    if (!this.tableData.length) {
      return;
    }
    const exportFn =
      this.searchType === 'action' ? EventStoreModule.exportActionData : EventStoreModule.exportAlertData;
    const data = await exportFn(this.handleGetSearchParams(false, true));
    if (data) {
      const { download_path: path, download_name: name } = data;
      let origin = path;
      if (path.indexOf('http') !== 0) {
        origin =
          process.env.NODE_ENV === 'development'
            ? `${process.env.proxyUrl}/media${path}`
            : `${window.location.origin}${window.site_url}media${path}`;
      }
      const element = document.createElement('a');
      element.setAttribute('href', `${origin}/${name}`);
      element.setAttribute('download', name);
      element.style.display = 'none';
      document.body.appendChild(element);
      element.click();
      document.body.removeChild(element);
    }
  }
  /**
   * @description: 批量操作触发
   * @param {*} item 操作内容
   * @return {*}
   */
  handleBatchAlert(id: string) {
    const bizIds = [];
    this.tableData.forEach(item => {
      if (this.selectedList.includes(item.id) && !bizIds.includes(item.bk_biz_id)) {
        bizIds.push(item.bk_biz_id);
      }
    });
    const isMoreThenOneOfBiz = bizIds.length > 1;
    const messsage = () => {
      this.$bkMessage({
        message: this.$t('当前不能跨业务批量操作'),
        theme: 'warning'
      });
    };
    switch (id) {
      // 批量确认告警
      case 'comfirm':
      case EBatchAction.alarmConfirm: {
        if (isMoreThenOneOfBiz) {
          messsage();
          return;
        }
        this.dialog.alarmConfirm.bizIds = bizIds;
        this.dialog.alarmConfirm.show = true;
        this.dialog.alarmConfirm.ids = this.selectedList;
        this.batchUrlUpdate(EBatchAction.alarmConfirm);
        break;
      }
      case 'shield': {
        if (isMoreThenOneOfBiz) {
          messsage();
          return;
        }
        this.dialog.quickShield.bizIds = bizIds;
        this.dialog.quickShield.show = true;
        this.dialog.quickShield.ids = this.selectedList;
        const details = [];
        this.selectedList.forEach(item => {
          const detail = this.tableData.find(tableitem => tableitem.id === item);
          details.push({
            severity: detail.severity,
            dimension: detail.dimension_message,
            trigger: detail.description,
            strategy: {
              id: detail.strategy_id,
              name: detail.strategy_name
            }
          });
        });
        this.dialog.quickShield.details = details;
        this.batchUrlUpdate(EBatchAction.quickShield);
        break;
      }
      case 'chat': {
        const assignees = [];
        this.selectedList.forEach(item => {
          const detail = this.tableData.find(tableitem => tableitem.id === item);
          detail.assignee?.forEach(val => {
            if (!assignees.includes(val)) {
              assignees.push(val);
            }
          });
        });
        this.chatGroupDialog.assignee = assignees;
        this.chatGroupDialog.alertIds.splice(0, this.chatGroupDialog.alertIds.length, ...this.selectedList);
        this.chatGroupShowChange(true);
        break;
      }
      case 'dispatch': {
        if (isMoreThenOneOfBiz) {
          messsage();
          return;
        }
        this.dialog.alarmDispatch.bizIds = bizIds;
        this.dialog.alarmDispatch.alertIds = this.selectedList;
        this.dialog.alarmDispatch.show = true;
        // this.batchUrlUpdate(id as EBatchAction);
      }
    }
  }
  /* 搜索条件包含action_id 且 打开批量搜索则更新url状态 */
  batchUrlUpdate(type: EBatchAction | '') {
    if (/(^action_id).+/g.test(this.queryString) || !type) {
      const key = random(10);
      const params = {
        name: this.$route.name,
        query: {
          ...this.handleParam2Url(),
          batchAction: type || undefined,
          key
        }
      };
      this.$router.replace(params);
      this.routeStateKeyList.push(key);
    }
  }

  /**
   * @description: 确认告警
   * @param {*} v 告警id
   * @return {*}
   */
  handleAlertConfirm(v: IEventItem) {
    this.dialog.alarmConfirm.ids = [v.id];
    this.dialog.alarmConfirm.bizIds = [v.bk_biz_id];
    this.dialog.alarmConfirm.show = true;
  }
  /**
   * @description: 屏蔽告警
   * @param {*} v
   * @return {*}
   */
  handleQuickShield(v: IEventItem) {
    this.dialog.quickShield.bizIds = [v.bk_biz_id];
    this.dialog.quickShield.show = true;
    this.dialog.quickShield.ids = [v.id];
    this.dialog.quickShield.details = [
      {
        severity: v.severity,
        dimension: v.dimension_message,
        trigger: v.description,
        strategy: {
          id: v?.strategy_id as unknown as string,
          name: v?.strategy_name
        }
      }
    ];
  }
  /**
   * @description: 手动处理
   * @param {*} v
   * @return {*}
   */
  handleManualProcess(v) {
    this.dialog.manualProcess.alertIds = [v.id] as any;
    this.dialog.manualProcess.bizIds = [v.bk_biz_id];
    this.manualProcessShowChange(true);
  }
  /**
   * @description: 一键拉群
   * @param {*} v
   * @return {*}
   */
  handleChatGroup(v) {
    const { id, assignee, alert_name } = v;
    this.chatGroupDialog.assignee = assignee || [];
    this.chatGroupDialog.alertName = alert_name;
    this.chatGroupDialog.alertIds.splice(0, this.chatGroupDialog.alertIds.length, id);
    this.chatGroupShowChange(true);
  }
  /**
   * @description: 一键拉群弹窗关闭/显示
   * @param {boolean} show
   * @return {*}
   */
  chatGroupShowChange(show: boolean) {
    this.chatGroupDialog.show = show;
  }
  /**
   * @description: 手动处理
   * @param {*} v
   * @return {*}
   */
  manualProcessShowChange(v: boolean) {
    this.dialog.manualProcess.show = v;
  }
  /* 手动处理轮询状态 */
  handleDebugStatus(actionIds: number[]) {
    this.dialog.manualProcess.actionIds = actionIds;
    this.dialog.manualProcess.debugKey = random(8);
  }
  handleMealInfo(mealInfo: { name: string }) {
    this.dialog.manualProcess.mealInfo = mealInfo;
  }
  /**
   * @description: 告警确认
   * @param {boolean} v
   * @return {*}
   */
  alarmConfirmChange(v: boolean) {
    this.dialog.alarmConfirm.show = v;
    if (!v) {
      this.batchUrlUpdate('');
    }
  }
  /**
   * @description: 快捷屏蔽
   * @param {boolean} v
   * @return {*}
   */
  quickShieldChange(v: boolean) {
    this.dialog.quickShield.show = v;
    if (!v) {
      this.batchUrlUpdate('');
    }
  }
  /**
   * @description: 屏蔽成功
   * @param {boolean} v
   * @return {*}
   */
  quickShieldSucces(v: boolean) {
    if (v) {
      this.tableData.forEach(item => {
        if (this.dialog.quickShield.ids.includes(item.id)) {
          item.is_shielded = true;
          item.shield_operator = [window.username || window.user_name];
        }
      });
    }
  }

  /* 告警分派 */
  handleAlarmDispatch(v: IEventItem) {
    this.dialog.alarmDispatch.bizIds = [v.bk_biz_id];
    this.dialog.alarmDispatch.alertIds = [v.id];
    this.dialog.alarmDispatch.show = true;
  }

  /**
   * @description: 趋势图周期变更时触发
   * @param {string} v 图表周期
   * @return {*}
   */
  handleChartIntervalChange(v: string | number) {
    this.chartInterval = v;
    this.chartKey = random(10);
  }

  /**
   * @description: 查询条件变更时触发搜索
   * @param {string} v 查询语句
   * @return {*}
   */
  async handleQueryStringChange(v: string) {
    const isChange = v !== this.queryString;
    if (isChange) {
      this.queryString = v;
      this.pagination.current = 1;
      const validate = await this.handleValidateQueryString();
      if (!validate) return;
      this.handleGetTableData();
      this.chartKey = random(10);
    }
  }
  handleFilterActiveChange(v: string[]) {
    this.advancedFilterDefaultOpen = v;
  }

  /**
   * @description: 高级帅选选中时触发
   * @param {string} conditionKey 条件key值
   * @param {string} id 选中id
   * @return {*}
   */
  handleAdvanceFilterChange(conditionKey: string | number, id: string[]) {
    this.condition[conditionKey] = id;
    this.pagination.current = 1;
    this.handleGetTableData(false);
    this.chartKey = random(10);
  }
  /**
   * @description: 清除左侧过滤面板数据
   * @param {*} item 清除的分类项
   * @return {*}
   */
  clearCheckedFilter(item) {
    if (this.condition[item.id]?.length) {
      (this.$refs[`tree-${item.id}`] as any)?.removeChecked({ emitEvent: false });
      this.condition[item.id] = [];
      this.pagination.current = 1;
      this.handleGetTableData(false);
    }
  }

  /**
   * @description: 确认告警后刷新数据
   * @param {boolean} v 是否确认
   * @return {*}
   */
  handleConfirmAfter(v: boolean) {
    if (v) {
      this.tableData.forEach(item => {
        if (this.dialog.alarmConfirm.ids.includes(item.id)) {
          item.is_ack = true;
          item.ack_operator = window.username || window.user_name;
        }
      });
    }
  }
  /* 告警分派弹窗 */
  handleAlarmDispatchShowChange(v: boolean) {
    this.dialog.alarmDispatch.show = v;
    // if (!v) {
    //   this.batchUrlUpdate('');
    // }
  }
  /* 分派成功 */
  handleAlarmDispatchSuccess(data: { ids: string[]; users: string[] }) {
    this.tableData.forEach(item => {
      if (data.ids.includes(item.id)) {
        if (item.appointee) {
          const usersSet = new Set();
          item.appointee.concat(data.users).forEach(u => {
            usersSet.add(u);
          });
          item.appointee = Array.from(usersSet) as string[];
        } else {
          item.appointee = data.users;
        }
      }
    });
  }
  /**
   * @description: 切换告警列表tab时触发
   * @param {eventPanelType} v tabId
   * @return {*}
   */
  handleAlertTabChange(v: eventPanelType) {
    this.activePanel = v;
    if (v === 'analyze') {
      !this.analyzeData?.length && this.handleGetSearchTopNList(false);
    } else {
      !this.tableData?.length && this.handleGetTableData();
    }
  }
  /**
   * @description: 告警分析字段切换后触发
   * @param {string} v 告警分析字段
   * @return {*}
   */
  async handleFieldChange(v: string[]) {
    this.tableLoading = true;
    const key = this.searchType === 'alert' ? alertAnalyzeStorageKey : actionAnalyzeStorageKey;
    if (this.searchType === 'alert') {
      this.analyzeFields = v;
    } else {
      this.analyzeActionFields = v;
    }
    localStorage.setItem(key, JSON.stringify(v));
    await this.handleGetSearchTopNList(false, false);
    this.tableLoading = false;
  }
  /**
   * @description: 告警分析查看详情时触发
   * @param {string} v 查看全部的字段
   * @return {*}
   */
  async handleDetailFieldChange(v: string) {
    this.detailField = v;
    this.detailFieldData = {};
    this.detailLoading = true;
    await this.handleGetSearchTopNList(true);
    this.detailLoading = false;
  }
  /**
   * @description: 告警分析特定字段时触发
   * @param {object} obj 子查询语句
   * @return {*}
   */
  async handleAppendQuery(obj: { type: 'add' | 'del'; queryString: string }) {
    let str = '';
    if (obj.type === 'add') {
      str = this.queryString ? `(${this.queryString}) AND ${obj.queryString}` : obj.queryString;
    } else if (obj.type === 'del') {
      str = this.queryString ? `(${this.queryString}) AND -${obj.queryString}` : `-${obj.queryString}`;
    }
    this.handleQueryStringChange(str);
  }
  // 设置全屏
  handleFullscreen() {
    if (!document.fullscreenElement) {
      this.$el.requestFullscreen();
    } else if (document.exitFullscreen) {
      document.exitFullscreen();
    }
  }
  // 分屏拖拽大小触发事件
  handleDragMove(v: number) {
    this.splitPanelWidth = v;
    this.isSplitPanel = v > 0;
  }
  handleSetDefaultSplitPanelWidth() {
    this.defaultPanelWidth = (this.$refs.contentWrap as HTMLDivElement).getBoundingClientRect().width / 2;
    this.splitPanelWidth = this.defaultPanelWidth;
  }
  // 是否分屏触发事件
  handleSplitPanel(v: boolean) {
    this.handleSetDefaultSplitPanelWidth();
    this.isSplitPanel = v;
    this.splitPanelWidth = v ? this.defaultPanelWidth : 0;
  }
  // 筛选侧栏宽度
  setFilterDefaultWidth() {
    if (this.isSplitEventPanel) {
      this.filterWidth = 0;
      return;
    }
    // 监控环境下侧栏宽度变小
    if (!this.$route.meta?.isFta) {
      this.filterWidth = filterWidth;
    } else {
      this.filterWidth = 320;
    }
  }

  // 监听选择器是否focus判断是否关闭选择面板
  handleToggleChange(status) {
    if (!status && !this.bizIds.length) {
      (this.$refs.selectRef as any).show();
      this.filterSelectIsEmpty = true;
    }
  }
  // 点击清除按钮时展开选择面板
  handleClearFilterSelect() {
    (this.$refs.selectRef as any).show();
  }

  /**
   * @description: 通过业务id 获取无权限申请url
   * @param {string} bizIds 业务id
   * @return {*}
   */
  async handleCheckAllowedByIds(bizIds?: string[]) {
    let bizList = bizIds;
    if (!bizIds?.length) {
      bizList = this.allowedBizList.filter(item => item.noAuth).map(item => item.id);
    }
    if (!bizList?.length) return;
    const applyObj = await checkAllowed({
      action_ids: [
        'view_business_v2',
        'manage_event_v2',
        'manage_downtime_v2',
        'view_event_v2',
        'view_host_v2',
        'view_rule_v2'
      ],
      resources: bizList.map(id => ({ id, type: 'space' }))
    });
    if (applyObj?.apply_url) {
      window.open(applyObj?.apply_url, random(10));
      // 20231205 代码还原，先保留原有部分
      // if (bizList.length > 1) {
      //   window.open(applyObj?.apply_url, random(10));
      // } else {
      //   showAccessRequest(applyObj?.apply_url, bizList[0]);
      // }
    }
  }

  getOperateDialogComponent() {
    return [
      <AlarmConfirm
        show={this.dialog.alarmConfirm.show}
        ids={this.dialog.alarmConfirm.ids}
        bizIds={this.dialog.alarmConfirm.bizIds}
        onConfirm={this.handleConfirmAfter}
        on-change={this.alarmConfirmChange}
      ></AlarmConfirm>,
      <QuickShield
        details={this.dialog.quickShield.details}
        ids={this.dialog.quickShield.ids}
        bizIds={this.dialog.quickShield.bizIds}
        show={this.dialog.quickShield.show}
        on-change={this.quickShieldChange}
        on-succes={this.quickShieldSucces}
      ></QuickShield>,
      <ManualProcess
        show={this.dialog.manualProcess.show}
        bizIds={this.dialog.manualProcess.bizIds}
        alertIds={this.dialog.manualProcess.alertIds}
        onShowChange={this.manualProcessShowChange}
        onDebugStatus={this.handleDebugStatus}
        onMealInfo={this.handleMealInfo}
      ></ManualProcess>,
      <ManualDebugStatus
        bizIds={this.dialog.manualProcess.bizIds}
        debugKey={this.dialog.manualProcess.debugKey}
        actionIds={this.dialog.manualProcess.actionIds}
        mealInfo={this.dialog.manualProcess.mealInfo}
      ></ManualDebugStatus>,
      <AlarmDispatch
        show={this.dialog.alarmDispatch.show}
        alertIds={this.dialog.alarmDispatch.alertIds}
        bizIds={this.dialog.alarmDispatch.bizIds}
        onShow={this.handleAlarmDispatchShowChange}
        onSuccess={this.handleAlarmDispatchSuccess}
      ></AlarmDispatch>
    ];
  }

  filterGroupSlot(item: IGroupData) {
    return (
      <bk-big-tree
        class={{ 'no-multi-level': !item.children.some(child => child.children?.length) }}
        ref={`tree-${item.id}`}
        options={{ nameKey: 'name', idKey: 'id', childrenKey: 'children' }}
        show-checkbox={true}
        data={item.children}
        default-expand-all={true}
        show-link-line={false}
        default-checked-nodes={this.condition[item.id]}
        padding={30}
        on-check-change={id => this.handleAdvanceFilterChange(item.id, id)}
        scopedSlots={{
          default: ({ data }) => (
            <div class='condition-tree-item'>
              <span class={['item-name', `item-status-${data.id}`]}>{data.name}</span>
              <span class='item-count'>{data.count}</span>
            </div>
          )
        }}
      ></bk-big-tree>
    );
  }
  filterListComponent(item: ICommonTreeItem) {
    return [
      <div
        class={['list-title', { 'item-active': item.id === this.activeFilterId }]}
        on-click={() => this.handleSelectActiveFilter(item.id as SearchType, item)}
      >
        {item.name}
        <span class='item-count'>{item.count}</span>
      </div>,
      <ul class='set-list'>
        {item?.children?.map?.(set =>
          filterIconMap[set.id] ? (
            <li
              class={['set-list-item', { 'item-active': set.id === this.activeFilterId }]}
              key={set.id}
              on-click={() => this.handleSelectActiveFilter(item.id as SearchType, set)}
            >
              <i
                class={`icon-monitor item-icon ${filterIconMap[set.id].icon}`}
                style={{ color: filterIconMap[set.id].color }}
              />
              {set.name}
              <span class='item-count'>{set.count}</span>
            </li>
          ) : undefined
        ) || undefined}
      </ul>
    ];
  }

  /**
   * 空状态操作
   * @param val 操作类型
   */
  handleOperation(val: EmptyStatusOperationType) {
    if (val === 'refresh') {
      this.handleGetTableData();
      return;
    }
    if (val === 'clear-filter') {
      this.queryString = '';
      Object.keys(this.condition).forEach(key => {
        if (this.condition[key].length) {
          this.condition[key] = [];
        }
      });
      this.noDataType = 'empty';
      this.handleGetTableData();
      return;
    }
  }

  render() {
    return (
      <div class='event-center-page'>
        <div
          class={`event-filter ${this.isSplitEventPanel ? 'hidden' : ''}`}
          style={{
            width: `${this.filterWidth}px`,
            flexBasis: `${this.filterWidth}px`,
            display: this.filterWidth > 200 ? 'flex' : 'none'
          }}
        >
          <div class='filter-list'>{this.commonFilterData?.map(item => this.filterListComponent(item))}</div>
          <div class='filter-search'>
            <div class='search-title'>{this.$t('高级筛选')}</div>
            <Group
              class='search-group'
              data={this.advancedFilterData}
              defaultActiveName={this.advancedFilterDefaultOpen}
              onActiveChange={this.handleFilterActiveChange}
              onClear={item => this.clearCheckedFilter(item)}
              scopedSlots={{
                default: ({ item }) => this.filterGroupSlot(item)
              }}
              theme='filter'
            />
          </div>
          <MonitorDrag
            theme={'line'}
            lineText={''}
            toggleSet={this.toggleSet}
            on-move={this.handleDragFilter}
          />
          <div
            class='filter-line-trigger'
            style={{
              left: `${this.filterWidth}px`
            }}
            onClick={() => (this.filterWidth = 0)}
          >
            <span class='icon-monitor icon-arrow-left'></span>
          </div>
        </div>
        <div
          class='event-content'
          style={{ maxWidth: `calc(100% - ${this.filterWidth}px - ${this.isSplitPanel ? this.splitPanelWidth : 0}px)` }}
        >
          <div class={`content-header ${this.isSplitEventPanel ? 'hidden' : ''}`}>
            <i
              class='icon-monitor icon-double-up set-filter'
              style={{ display: this.filterWidth > 200 ? 'none' : 'flex' }}
              on-click={this.setFilterDefaultWidth}
            />
            <span
              class='header-title'
              style={{ marginLeft: this.filterWidth > 200 ? '24px' : '0px' }}
            >
              {this.activeFilterName || this.$t('事件中心')}
            </span>
            <DashboardTools
              class='header-tools'
              isSplitPanel={this.isSplitPanel}
              refleshInterval={this.refleshInterval}
              showListMenu={false}
              timeRange={this.timeRange}
              timezone={this.timezone}
              onSplitPanelChange={this.handleSplitPanel}
              onFullscreenChange={this.handleFullscreen}
              onImmediateReflesh={this.handleImmediateReflesh}
              onRefleshChange={this.handleRefleshChange}
              onTimeRangeChange={this.handleTimeRangeChange}
              onTimezoneChange={this.handleTimezoneChange}
            />
          </div>
          <div
            class='content-wrap'
            ref='contentWrap'
          >
            <EventChart
              searchType={this.searchType}
              chartInterval={this.chartInterval}
              getSeriesData={this.handleGetAlertDateHistogram}
              chartKey={this.chartKey}
              onIntervalChange={this.handleChartIntervalChange}
            />
            <div class='content-wrap-filter'>
              <div
                class='business-screening-notes'
                v-en-style='width: 120px;'
              >
                {this.$t('空间筛选')}
              </div>
              {/* <bk-select
                class={`filter-select ${this.filterSelectIsEmpty ? 'empty-warning' : ''}`}
                v-model={this.bizIds}
                placeholder={this.$t('选择')}
                searchable
                multiple
                search-with-pinyin
                onClear={this.handleClearFilterSelect}
                onSelected={this.handleBizChange}
                onToggle={this.handleToggleChange}
                ref="selectRef"
              >
                {this.allowedBizList.map(item => (
                  <bk-option
                    disabled={!!item.noAuth && !item.hasData}
                    key={item.id}
                    id={item.id}
                    name={item.name}>
                    {item.name}
                    {
                      !!item.noAuth && !item.hasData
                        ? <bk-button style="color: #3a84ff;font-size: 12px;padding-right: 0px;"
                          class="bk-option-icon"
                          size="small"
                          text
                          theme="primary"
                          onClick={() => this.handleCheckAllowedByIds([item.id])}>
                          {this.$t('申请权限')}</bk-button>
                        : this.bizIds.includes(item.id) && <i class="bk-option-icon bk-icon icon-check-1"></i>
                    }
                  </bk-option>
                ))}
              </bk-select> */}
              <div class='filter-select'>
                <SpaceSelect
                  value={this.bizIds}
                  spaceList={this.$store.getters.bizList}
                  hasAuthApply={true}
                  onApplyAuth={this.handleCheckAllowedByIds}
                  onChange={this.handleBizIdsChange}
                ></SpaceSelect>
              </div>
              <FilterInput
                ref='filterInput'
                value={this.queryString}
                valueMap={this.valueMap}
                searchType={this.searchType}
                isFillId={true}
                inputStatus={this.filterInputStatus}
                onChange={this.handleQueryStringChange}
                onClear={this.handleQueryStringChange}
              />
              <div
                class={['tools-export', { disabled: !this.tableData.length }]}
                title={this.$tc('导出')}
                onClick={this.handleExportData}
              >
                <span class='icon-monitor icon-xiazai'></span>
              </div>
            </div>
            {`${this.bussinessTips}`.length > 0 && (
              <div class='permission-tips'>
                <bk-icon
                  type='exclamation-circle'
                  class='permission-tips-icon'
                />
                {this.bussinessTips}
                <bk-button
                  theme='primary'
                  text
                  onClick={() => this.handleCheckAllowedByIds()}
                >
                  {this.$t('申请权限')}
                </bk-button>
                <bk-icon
                  type='close'
                  class='permission-tips-close'
                  onClick={() => (this.showPermissionTips = false)}
                />
              </div>
            )}
            {this.numOfEmptyAssignee > 0 && (
              <bk-alert
                class='content-alert'
                type='error'
              >
                <template slot='title'>
                  <span class='alert-text'>
                    {this.$t('当前有 {0} 个未恢复告警的通知人是空的', [this.numOfEmptyAssignee])} ,
                  </span>

                  <bk-button
                    text
                    title='primary'
                    class='alert-text query-btn'
                    onClick={this.setQueryStringForCheckingEmptyAssignee}
                  >
                    <span style='display: inline-flex;'>{this.$t('button-查看')}</span>
                  </bk-button>
                </template>
              </bk-alert>
            )}
            <div
              class='content-table'
              ref='contentTable'
            >
              <bk-tab
                active={this.activePanel}
                on-tab-change={this.handleAlertTabChange}
                type='unborder-card'
              >
                {this.panelList.map(item => (
                  <bk-tab-panel
                    key={item.id}
                    name={item.id}
                    label={item.name}
                  />
                ))}
              </bk-tab>
              {!this.tableData.length ? (
                <EmptyTable
                  v-bkloading={{ isLoading: this.tableLoading, zIndex: 1000 }}
                  emptyType={this.noDataType}
                  onApplyAuth={this.handleCheckAllowedByIds}
                  handleOperation={this.handleOperation}
                >
                  {this.noDataString && <span>{this.noDataString} </span>}
                </EmptyTable>
              ) : (
                <div class='table-content'>
                  <keep-alive>
                    {this.activePanel === 'list' ? (
                      <EventTable
                        doLayout={this.activePanel}
                        bizIds={this.bizIds}
                        tableData={this.tableData}
                        pagination={this.pagination}
                        loading={this.tableLoading}
                        searchType={this.searchType}
                        selectedList={this.selectedList}
                        onBatchSet={this.handleBatchAlert}
                        onPageChange={this.handleTabelPageChange}
                        onLimitChange={this.handleTableLimitChange}
                        onShowDetail={this.handleShowDetail}
                        onSelectChange={this.handleTableSelecChange}
                        onAlertConfirm={this.handleAlertConfirm}
                        onQuickShield={this.handleQuickShield}
                        onSortChange={this.handleSortChange}
                        onManualProcess={this.handleManualProcess}
                        onChatGroup={this.handleChatGroup}
                        onAlarmDispatch={this.handleAlarmDispatch}
                      />
                    ) : (
                      <AlertAnalyze
                        bizIds={this.bizIds}
                        loading={this.tableLoading}
                        analyzeData={this.analyzeData}
                        analyzeFields={this.curAnalyzeFields}
                        analyzeTagList={this.analyzeTagList}
                        detailField={this.detailField}
                        detailFieldData={this.detailFieldData}
                        detailLoading={this.detailLoading}
                        searchType={this.searchType}
                        hasSearchParams={this.hasSearchParams}
                        clearSearch={this.handleOperation}
                        // style={{ display: this.activePanel === 'analyze' ? 'flex' : 'none' }}
                        onFieldChange={this.handleFieldChange}
                        onDetailFieldChange={this.handleDetailFieldChange}
                        onAppendQuery={this.handleAppendQuery}
                      />
                    )}
                  </keep-alive>
                </div>
              )}
            </div>
          </div>
        </div>
        <div
          class='split-panel-wrapper'
          style={{
            width: `${this.splitPanelWidth}px`,
            display: this.splitPanelWidth > SPLIT_MIN_WIDTH && this.isSplitPanel ? 'flex' : 'none'
          }}
        >
          {this.isSplitPanel ? (
            <SplitPanel
              splitMaxWidth={Math.max(this.splitPanelWidth + 300, SPLIT_MAX_WIDTH)}
              toggleSet={this.toggleSet}
              defaultRelated={'k8s'}
              onDragMove={this.handleDragMove}
            />
          ) : undefined}
        </div>
        <EventDetailSlider
          isShow={this.detailInfo.isShow}
          eventId={this.detailInfo.id}
          type={this.detailInfo.type}
          activeTab={this.detailInfo.activeTab}
          bizId={this.detailInfo.bizId}
          onShowChange={v => (this.detailInfo.isShow = v)}
        />
        {this.getOperateDialogComponent()}
        <ChatGroup
          show={this.chatGroupDialog.show}
          assignee={this.chatGroupDialog.assignee}
          alarmEventName={this.chatGroupDialog.alertName}
          alertIds={this.chatGroupDialog.alertIds}
          onShowChange={this.chatGroupShowChange}
        />
      </div>
    );
  }
}

export default ofType<IEventProps>().convert(Event);
