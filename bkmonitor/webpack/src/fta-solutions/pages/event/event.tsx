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

import { Component, InjectReactive, Mixins, Prop, Ref, Watch } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import dayjs from 'dayjs';
import difference from 'lodash/difference';
import intersection from 'lodash/intersection';
import {
  actionDateHistogram,
  actionTopN,
  alertDateHistogram,
  alertTopN,
  listAlertTags,
  searchAction,
  searchAlert,
  validateQueryString,
} from 'monitor-api/modules/alert';
import { checkAllowed } from 'monitor-api/modules/iam';
import {
  incidentList,
  incidentOverview,
  incidentTopN,
  incidentValidateQueryString,
} from 'monitor-api/modules/incident';
import { promqlToQueryConfig } from 'monitor-api/modules/strategies';
import { commonPageSizeSet, commonPageSizeGet, LANGUAGE_COOKIE_KEY, docCookies } from 'monitor-common/utils';
import { random } from 'monitor-common/utils/utils';
// 20231205 代码还原，先保留原有部分
import SpaceSelect from 'monitor-pc/components/space-select/space-select';
import { DEFAULT_TIME_RANGE, handleTransformToTimestamp } from 'monitor-pc/components/time-range/utils';
import { destroyTimezone, getDefaultTimezone, updateTimezone } from 'monitor-pc/i18n/dayjs';
import * as eventAuth from 'monitor-pc/pages/event-center/authority-map';
import DashboardTools from 'monitor-pc/pages/monitor-k8s/components/dashboard-tools';
import SplitPanel from 'monitor-pc/pages/monitor-k8s/components/split-panel';
import { SPLIT_MAX_WIDTH, SPLIT_MIN_WIDTH } from 'monitor-pc/pages/monitor-k8s/typings';
import { setLocalStoreRoute } from 'monitor-pc/router/router-config';
import authorityMixinCreate from 'monitor-ui/mixins/authorityMixin';

import ChatGroup from '../../components/chat-group/chat-group';
import TableSkeleton from '../../components/skeleton/table-skeleton';
import EventStoreModule from '../../store/modules/event';
import Group, { type IGroupData } from '../integrated/group';
import AlertAnalyze from './alert-analyze';
import EmptyTable from './empty-table';
import EventChart from './event-chart';
import AlarmConfirm from './event-detail/alarm-confirm';
import AlarmDispatch from './event-detail/alarm-dispatch';

// import EventDetailSlider from './event-detail/event-detail-slider';
import ManualDebugStatus from './event-detail/manual-debug-status';
import ManualProcess from './event-detail/manual-process';
import QuickShield from './event-detail/quick-shield';
import EventTable, { type IShowDetail } from './event-table';
import FilterInput from './filter-input';
import IncidentTable from './incident-table';
import MonitorDrag from './monitor-drag';
import AdvancedFilterSkeleton from './skeleton/advanced-filter-skeleton';
import {
  type AnlyzeField,
  EBatchAction,
  type FilterInputStatus,
  type IChatGroupDialogOptions,
  type ICommonItem,
  type ICommonTreeItem,
  type IEventItem,
  type SearchType,
  type eventPanelType,
} from './typings/event';
import { INIT_COMMON_FILTER_DATA, getOperatorDisabled } from './utils';

import type { TType as TSliderType } from './event-detail/event-detail-slider';

// import { showAccessRequest } from 'monitor-pc/components/access-request-dialog';
import type { EmptyStatusOperationType, EmptyStatusType } from 'monitor-pc/components/empty-status/types';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';
import type { TranslateResult } from 'vue-i18n';

import './event.scss';
// 有权限的业务id
const authorityBizId = -1;
// 有数据的业务id
const hasDataBizId = -2;
const grammaticalErrorCode = 3324003;
const alertAnalyzeStorageKey = '__ALERT_ANALYZE_STORAGE_KEY__';
const actionAnalyzeStorageKey = '__ACTION_ANALYZE_STORAGE_KEY__';
const incidentAnalyzeStorageKey = '__INCIDENT_ANALYZE_STORAGE_KEY__';
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
  'ipv6',
];
const allActionFieldList = [
  'action_name',
  'action_plugin_type',
  'operator',
  'duration',
  'strategy_name',
  'operate_target_string',
];
const allIncidentFieldList = ['status', 'level', 'assignees', 'handlers', 'labels'];
const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';
export const commonAlertFieldMap = {
  status: [
    {
      id: isEn ? 'ABNORMAL' : '未恢复',
      name: window.i18n.tc('未恢复'),
    },
    {
      id: isEn ? 'RECOVERED' : '已恢复',
      name: window.i18n.tc('已恢复'),
    },
    {
      id: isEn ? 'CLOSED' : '已失效',
      name: window.i18n.tc('已失效'),
    },
  ],
  severity: [
    {
      id: isEn ? 1 : '致命',
      name: window.i18n.tc('致命'),
    },
    {
      id: isEn ? 2 : '预警',
      name: window.i18n.tc('预警'),
    },
    {
      id: isEn ? 3 : '提醒',
      name: window.i18n.tc('提醒'),
    },
  ],
  stage: [
    {
      id: isEn ? 'is_handled' : '已通知',
      name: window.i18n.tc('已通知'),
    },
    {
      id: isEn ? 'is_ack' : '已确认',
      name: window.i18n.tc('已确认'),
    },
    {
      id: isEn ? 'is_shielded' : '已屏蔽',
      name: window.i18n.tc('已屏蔽'),
    },
    {
      id: isEn ? 'is_blocked' : '已流控',
      name: window.i18n.tc('已流控'),
    },
  ],
};
const commonActionFieldMap = {
  status: [
    {
      id: isEn ? 'RUNNING' : '执行中',
      name: window.i18n.tc('执行中'),
    },
    {
      id: isEn ? 'SUCCESS' : '成功',
      name: window.i18n.tc('成功'),
    },
    {
      id: isEn ? 'FAILURE' : '失败',
      name: window.i18n.tc('失败'),
    },
  ],
};

const commonIncidentFieldMap = {
  status: [
    {
      id: isEn ? 'ABNORMAL' : '未恢复',
      name: window.i18n.tc('未恢复'),
    },
    {
      id: isEn ? 'RECOVERING' : '观察中',
      name: window.i18n.tc('观察中'),
    },
    {
      id: isEn ? 'RECOVERED' : '已恢复',
      name: window.i18n.tc('已恢复'),
    },
    {
      id: isEn ? 'CLOSED' : '已解决',
      name: window.i18n.tc('已解决'),
    },
  ],
  level: [
    {
      id: isEn ? 'ERROR' : '致命',
      name: window.i18n.tc('致命'),
    },
    {
      id: isEn ? 'INFO' : '预警',
      name: window.i18n.tc('预警'),
    },
    {
      id: isEn ? 'WARN' : '提醒',
      name: window.i18n.tc('提醒'),
    },
  ],
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
  MY_ASSIGNEE: {
    color: '#979BA5',
    icon: 'icon-inform-circle',
  },
  MY_FOLLOW: {
    color: '#FF9C01',
    icon: 'icon-mc-note',
  },
  MY_APPOINTEE: {
    color: '#699DF4',
    icon: 'icon-mc-user-one',
  },
  MY_ASSIGNEE_INCIDENT: {
    color: '#699DF4',
    icon: 'icon-mc-user-one',
  },
  MY_HANDLER_INCIDENT: {
    color: '#979BA5',
    icon: 'icon-chulitaocan',
  },
  MY_HANDLER: {
    color: '#979BA5',
    icon: 'icon-inform-circle',
  },
  NOT_SHIELDED_ABNORMAL: {
    color: '#EA3636',
    icon: 'icon-mind-fill',
  },
  SHIELDED_ABNORMAL: {
    color: '#C4C6CC',
    icon: 'icon-menu-shield',
  },
  RECOVERED: {
    color: '#2DCB56',
    icon: 'icon-mc-check-fill',
  },
  success: {
    color: '#2DCB56',
    icon: 'icon-mc-check-fill',
  },
  failure: {
    color: '#EA3636',
    icon: 'icon-mc-close-fill',
  },
  abnormal: {
    color: '#EA3636',
    icon: 'icon-mind-fill',
  },
  recovered: {
    color: '#2DCB56',
    icon: 'icon-mc-check-fill',
  },
  recovering: {
    color: '#FFB848',
    icon: 'icon-mc-visual',
  },
  closed: {
    color: '#989CA7',
    icon: 'icon-mc-solved',
  },
};
@Component({
  name: 'Event',
  components: {
    EventDetailSlider: () => import('./event-detail/event-detail-slider'),
  },
})
class Event extends Mixins(authorityMixinCreate(eventAuth)) {
  // 监控左侧栏是否收缩配置 自愈默认未收缩
  @Prop({ default: false, type: Boolean }) readonly toggleSet: boolean;
  // 是否是分屏模式下的事件展示
  @Prop({ default: false, type: Boolean }) readonly isSplitEventPanel: boolean;
  @Prop({ default: () => ({}), type: Object }) readonly defaultParams: Record<string, any>;

  // 图表的数据时间间隔
  @InjectReactive('timeRange') readonly panelTimeRange!: number;
  // 图表刷新间隔
  @InjectReactive('refreshInterval') readonly panleRefleshInterval!: number;
  // 立即刷新图表
  @InjectReactive('refreshImmediate') readonly panelRefleshImmediate: string;

  @Ref('filterInput') filterInputRef: FilterInput;
  commonFilterData: ICommonTreeItem[] = INIT_COMMON_FILTER_DATA;
  commonFilterLoading = true;
  /* 默认事件范围为近24小时 */
  timeRange: TimeRangeType = ['now-7d', 'now'] || DEFAULT_TIME_RANGE;
  /* 时区 */
  timezone: string = getDefaultTimezone();
  refreshInterval = 5 * 60 * 1000;
  refleshInstance = null;
  allowedBizList = [];
  bizIds = [this.$store.getters.bizId];
  // 左侧过滤
  advancedFilterData = [];
  advancedFilterDefaultOpen = [];
  advancedFilterLoading = false;
  condition: Record<string, string | string[]> = {};
  activeFilterName = '';
  activeFilterId = '';
  searchType: SearchType = 'alert';
  filterScrollTop = 0;

  // 告警分析
  analyzeData = [];
  analyzeFields = ['alert_name', 'metric', 'bk_biz_id', 'duration', 'ip', 'ipv6', 'bk_cloud_id'];
  incidentFieldList = ['incident_name', 'status', 'level', 'assignees', 'handlers', 'labels'];
  // bk助手链接
  incidentWxCsLink = '';
  incidentEmptyData = {
    path: '',
    text: '',
  };
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
    'operate_target_string',
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
    limit: 10,
  };

  // 查询
  chartInterval: number | string = 'auto';
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
    bizId: +window.bk_biz_id,
  };
  dialog = {
    quickShield: {
      show: false,
      details: [
        {
          severity: 1,
          dimension: [],
          trigger: '',
          alertId: '',
          strategy: {
            id: '',
            name: '',
          },
        },
      ],
      ids: [],
      bizIds: [],
    },
    alarmConfirm: {
      show: false,
      ids: [],
      bizIds: [],
    },
    manualProcess: {
      show: false,
      alertIds: [],
      bizIds: [],
      debugKey: random(8),
      actionIds: [],
      mealInfo: null,
    },
    alarmDispatch: {
      show: false,
      bizIds: [],
      alertIds: [],
    },
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
    alertIds: [],
  };
  // 过滤业务已选择是否为空
  filterSelectIsEmpty = false;
  showPermissionTips = true;
  noDataType: EmptyStatusType = 'empty';
  noDataString: any = '';
  bussinessTips: TranslateResult = '';

  // 统计 未恢复告警的通知人 栏为空的人数。
  numOfEmptyAssignee = 0;

  // 缓存topn概览数据（用于添加字段是无需调用接口）
  topNOverviewData = {
    fieldList: [],
    count: 0,
  };
  listOpenId = '';

  get panelList(): IPanelItem[] {
    return this.searchType === 'action' ? this.actionPanelList : this.alertPanelList;
  }
  get curAnalyzeFields() {
    return this.searchType === 'alert' ? this.analyzeFields : this.analyzeActionFields;
  }

  get isIncident() {
    return this.searchType === 'incident';
  }

  // 是否拥有查询条件： 搜索条件或者高级筛选条件
  get hasSearchParams() {
    return !!(this.queryString || Object.values(this.condition).some(item => item.length));
  }
  /** 以父类为维度打平所有id,用于左侧菜单展开的判断 */
  get commonFilterDataIdMap() {
    const idMap = {};
    this.commonFilterData.forEach(item => {
      idMap[item.id] = [item.id].concat(item.children?.map?.(child => child.id) || []);
    });
    return idMap;
  }
  @Watch('panelTimeRange')
  // 数据时间间隔
  handlePanelTimeRangeChange(v: TimeRangeType) {
    this.handleTimeRangeChange(v);
  }
  @Watch('panelRefleshInterval')
  // 数据刷新间隔
  handlePanelRefleshIntervalChange(v: number) {
    this.handleRefreshChange(v);
  }
  @Watch('panelRefleshImmediate')
  // 立刻刷新
  handlePanelRefleshImmediateChange(v: string) {
    if (v) this.handleImmediateRefresh();
  }
  @Watch('defaultParams', { immediate: true })
  async handleDefaultParamsChange(v: Record<string, any>) {
    if (this.isSplitEventPanel) {
      this.routeStateKeyList = [];
      Object.keys(v).forEach(key => (this[key] = v[key]));
      await Promise.all([this.handleGetFilterData(), this.handleGetTableData(true)]);
      this.handleRefreshChange(this.refreshInterval);
    }
  }
  async created() {
    this.alertPanelList = [
      {
        id: 'list',
        name: this.$t('告警列表'),
      },
      {
        id: 'analyze',
        name: this.$t('告警分析'),
      },
    ];
    this.actionPanelList = [
      {
        id: 'list',
        name: this.$t('处理记录'),
      },
      {
        id: 'analyze',
        name: this.$t('记录分析'),
      },
    ];
    if (!localStorage.getItem(alertAnalyzeStorageKey)) {
      localStorage.setItem(alertAnalyzeStorageKey, JSON.stringify(this.analyzeFields));
    }
    if (!localStorage.getItem(actionAnalyzeStorageKey)) {
      localStorage.setItem(actionAnalyzeStorageKey, JSON.stringify(this.analyzeActionFields));
    }

    if (!localStorage.getItem(incidentAnalyzeStorageKey)) {
      localStorage.setItem(incidentAnalyzeStorageKey, JSON.stringify(this.incidentFieldList));
    }
    this.pagination.limit = commonPageSizeGet();
    // 监控环境下侧栏宽度变小
    this.setFilterDefaultWidth();
    this.incidentFieldList = this.handleGetAnalyzeField(incidentAnalyzeStorageKey, this.incidentFieldList);
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
          promql: params.promql,
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
      await Promise.all([vm.handleGetFilterData(), vm.handleGetTableData(true)]);
      vm.handleRefreshChange(vm.refreshInterval);
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
      } else {
        // 正常进入告警页情况下不打开详情，只有通过告警通知进入的才展开详情（带collectId）
        // 新版首页搜索跳转过来打开详情(带alertId)
        const needShowDetail =
          (!!vm.$route.query.collectId || !!vm.$route.query.alertId) && location.search.includes('specEvent');
        if (needShowDetail) {
          vm.handleFirstShowDetail();
        }
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
    (contentWrap as HTMLDivElement).addEventListener('scroll', this.handleDisableHover, false);
  }

  beforeDestroy() {
    this.routeStateKeyList = [];
    window.removeEventListener('popstate', this.handlePopstate);
    const { contentWrap } = this.$refs as any;
    (contentWrap as HTMLDivElement).removeEventListener('scroll', this.handleDisableHover, false);
    window.clearInterval(this.refleshInstance);
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
  handleDisableHover() {
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
      ...query,
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
        dayjs.tz(time).format('YYYY-MM-DD HH:mm:ss'),
      ];
    }
    /** 移动端带collectId跳转事件中心 */
    if (defaultData.collectId) {
      defaultData.queryString = defaultData.queryString
        ? `${defaultData.queryString} AND action_id : ${defaultData.collectId}`
        : `action_id : ${defaultData.collectId}`;
      /* 带collectId是事件范围设为近15天 */
      defaultData.timeRange = ['now-30d', 'now'];
    }

    /** 新版首页带alertId跳转事件中心 */
    if (defaultData.alertId) {
      defaultData.queryString = defaultData.queryString
        ? `${defaultData.queryString} AND id : ${defaultData.alertId}`
        : `id : ${defaultData.alertId}`;
    }

    /** 处理指标参数 */
    if (defaultData.metricId?.length) {
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
      this.handleRefreshChange(this.refreshInterval);
    }
  }
  /**
   * @description: 查询参数获取
   * @param {*} onlyOverview 是否overview
   * @param {*} commonParams 是否获取同用参数
   * @return {*}
   */
  handleGetSearchParams(onlyOverview = false, commonParams = false) {
    // 查询条件语法格式错误，清除查询条件
    if (this.filterInputStatus === 'error') {
      this.queryString = '';
    }
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
      end_time: endTime, // 结束时间
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
        record_history: !onlyOverview && isManualInput, // 是否保存收藏历史，默认 false
      };
    }
    return params;
  }
  /**
   * @description: 获取故障列表信息
   * @param {*}
   * @return {*}
   */
  async handleGetIncidentList(onlyOverview = false) {
    const params = {
      ...this.handleGetSearchParams(onlyOverview),
      // alert_ids: this.handleUrl2Params()?.alertIds || [] // 告警ID
      alert_ids: this.getUrlParamsItem('alertIds') || [], // 告警ID
    };
    const {
      aggs,
      incidents: list,
      overview,
      total,
      code,
      greyed_spaces,
      wx_cs_link,
    } = await incidentList(params, { needRes: true, needMessage: false })
      .then(res => {
        !onlyOverview && (this.filterInputStatus = 'success');
        return res.data || {};
      })
      .catch(({ error_details, message, code }) => {
        if (code !== grammaticalErrorCode) {
          this.$bkMessage(error_details || { message, theme: 'error' });
        }
        return {
          wx_cs_link: '',
          greyed_spaces: [],
          aggs: [],
          incidents: [],
          overview: [],
          total: 0,
          code,
        };
      });
    this.incidentWxCsLink = wx_cs_link;
    return {
      aggs,
      greyed_spaces,
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
                    href={item.content.url}
                    target='blank'
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
            // alert_count: item?.alert_id?.length || '-1',
            content,
            bizName: this.allowedBizList?.find(set => +set.id === +item.bk_biz_id)?.name || '--',
          };
        }) || [],
      overview,
      total,
      code,
    };
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
      alert_ids: this.getUrlParamsItem('alertIds') || [], // 告警ID
    };
    const {
      aggs,
      actions: list,
      overview,
      total,
      code,
    } = await searchAction(params, { needRes: true, needMessage: false })
      .then(res => {
        !onlyOverview && (this.filterInputStatus = 'success');
        return res.data || {};
      })
      .catch(({ error_details, message, code }) => {
        if (code !== grammaticalErrorCode) {
          this.$bkMessage(error_details || { message, theme: 'error' });
        }
        return {
          aggs: [],
          actions: [],
          overview: [],
          total: 0,
          code,
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
                    href={item.content.url}
                    target='blank'
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
            bizName: this.allowedBizList?.find(set => +set.id === +item.bk_biz_id)?.name || '--',
          };
        }) || [],
      overview,
      total,
      code,
    };
  }
  /**
   * @description: 获取故障列表信息
   * @param {*} onlyOverview 是否overview模式
   * @return {*}
   */
  async handleGetSearchFaultList(onlyOverview = false) {
    const {
      aggs,
      alerts: list,
      overview,
      total,
      code,
    } = await incidentOverview(this.handleGetSearchParams(onlyOverview), { needRes: true, needMessage: false })
      .then(res => {
        !onlyOverview && (this.filterInputStatus = 'success');
        return res.data || {};
      })
      .catch(({ code }) => {
        // if (code !== grammaticalErrorCode) {
        //   this.$bkMessage({ message, theme: 'error' });
        // }
        return {
          aggs: [],
          alerts: [],
          overview: [],
          total: 0,
          code,
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
        bizName: this.allowedBizList?.find(set => +set.id === +item.bk_biz_id)?.name || '--',
      })),
      overview,
      total,
      code,
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
      code,
    } = await searchAlert(this.handleGetSearchParams(onlyOverview), { needRes: true, needMessage: false })
      .then(res => {
        !onlyOverview && (this.filterInputStatus = 'success');
        return res.data || {};
      })
      .catch(({ error_details, message, code }) => {
        if (code !== grammaticalErrorCode) {
          this.$bkMessage(error_details || { message, theme: 'error' });
        }
        return {
          aggs: [],
          alerts: [],
          overview: [],
          total: 0,
          code,
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
        bizName: this.allowedBizList?.find(set => +set.id === +item.bk_biz_id)?.name || '--',
      })),
      overview,
      total: Math.min(total, 10000),
      code,
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
    } else if (this.searchType === 'incident') {
      // 故障
      allFieldList =
        this.bizIds.includes(-1) || this.bizIds.length > 1
          ? ['bk_biz_id', ...allIncidentFieldList]
          : allIncidentFieldList;
    }
    let analyzeFields = this.searchType === 'alert' ? this.analyzeFields : this.analyzeActionFields;
    if (this.searchType === 'incident') analyzeFields = this.incidentFieldList;
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
      // biome-ignore lint/complexity/noForEach: <explanation>
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
              percent: count ? Number((set.count / count).toFixed(4)) : 0,
            })),
          });
        }
      });
      // 特殊添加一个空选项给 通知人 ，注意：仅仅加个 空 值还不够，之后查询之前还要执行一次 replaceSpecialCondition
      // 去替换这里添加的 空值 ，使之最后替换成这样 'NOT 通知人 : *'
      if (valueMap.assignee) {
        valueMap.assignee.unshift({
          id: '""',
          name: this.$t('- 空 -'),
        });
      }
      if (tagList?.length) {
        valueMap.tags = tagList.map(item => ({ id: item.name, name: item.name }));
      }
      const mergeFieldMap = this.searchType === 'alert' ? commonAlertFieldMap : commonActionFieldMap;
      this.valueMap = Object.assign(valueMap, this.searchType === 'incident' ? commonIncidentFieldMap : mergeFieldMap);
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
      size: isDetail ? 100 : 10,
    };
    let fieldList = [];
    let count = 0;
    if (this.searchType === 'alert') {
      const { fields, doc_count } = await alertTopN(
        {
          ...topNParams,
          fields: !isDetail ? [...allFieldList] : [this.detailField],
        },
        { needCancel: true }
      ).catch(() => ({ doc_count: 0, fields: [] }));
      fieldList = fields;
      count = doc_count;
      if (!isDetail) {
        alertTopN(
          {
            ...topNParams,
            fields: (!isDetail ? [...(tagList || []).map(item => item.id)] : [this.detailField]).slice(0, 20),
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
    } else if (this.searchType === 'incident') {
      const { fields, doc_count } = await incidentTopN({ ...topNParams }, { needCancel: true }).catch(() => ({
        doc_count: 0,
        fields: [],
      }));
      fieldList = fields;
      count = doc_count;
    } else {
      const { fields, doc_count } = await actionTopN({ ...topNParams }, { needCancel: true }).catch(() => ({
        doc_count: 0,
        fields: [],
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
      ...this.handleGetSearchParams(false, true),
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
      for (const item of this.tableData) {
        item.event_count = data[item.id] || -1;
      }
    }
  }
  /**
   * @description: 获取左侧面板统计数据
   * @param {*}
   * @return {*}
   */
  async handleGetFilterData() {
    this.commonFilterLoading = true;
    const filterDataPromise = [
      this.handleGetSearchAlertList(true),
      this.handleGetSearchActionList(true),
      this.handleGetSearchFaultList(true),
    ];
    const [{ overview }, { overview: actionOverview }, faultOverviewData] = await Promise.all(filterDataPromise).catch(
      () => [{ overview: [] }, { overview: [] }, { overview: [] }]
    );
    const faultOverview = faultOverviewData?.overview ?? {};
    this.commonFilterData = [overview, { ...faultOverview }, { ...actionOverview }].filter(item => !!item && item.id);

    this.commonFilterLoading = false;
    if (!this.activeFilterId) {
      this.activeFilterId = overview.id;
      this.activeFilterName = overview.name;
    } else if (this.activeFilterId) {
      this.activeFilterName =
        [
          overview,
          actionOverview,
          faultOverview,
          ...(overview?.children || []),
          ...(actionOverview?.children || []),
          ...(faultOverview.children ? faultOverview.children : []),
        ].find(item => item.id === this.activeFilterId)?.name || '';
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
    const validateFn = this.searchType === 'incident' ? incidentValidateQueryString : validateQueryString;
    if (this.queryString?.length) {
      validate = await validateFn(
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
    this.listOpenId =
      Object.keys(this.commonFilterDataIdMap).find(key =>
        this.commonFilterDataIdMap[key].includes(this.activeFilterId)
      ) || this.listOpenId;

    this.tableLoading = true;
    if (refleshAgg) this.advancedFilterLoading = true;
    // await this.handleValidateQueryString()
    await this.$nextTick();
    const promiseList = [];
    if (this.searchType === 'alert') {
      promiseList.push(this.handleGetSearchAlertList());
    } else if (this.searchType === 'action') {
      promiseList.push(this.handleGetSearchActionList());
    } else if (this.searchType === 'incident') {
      promiseList.push(this.handleGetIncidentList());
    }

    if (this.activePanel === 'analyze') {
      needTopN && promiseList.push(this.handleGetSearchTopNList(false));
    } else {
      needTopN && (await this.handleGetSearchTopNList(false));
    }
    const [{ aggs, list, total, code, greyed_spaces }] = await Promise.all(promiseList);

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
    this.advancedFilterLoading = false;
    this.tableData =
      list.map(item => ({
        ...item,
        extend_info: this.relateInfos?.[item.id] || '',
        event_count: this.eventCounts?.[item.id] || '--',
        followerDisabled: this.searchType === 'alert' ? getOperatorDisabled(item.follower, item.assignee) : false,
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
        this.noDataType = this.hasSearchParams
          ? 'search-empty'
          : this.searchType === 'incident'
            ? 'incidentEmpty'
            : 'empty';
        /**
         * 故障错误信息展示
         * 1. 有权限空间/与我的故障 无数据则根据当前人员是否有开启灰度空间，有：展示当前有多少空间权限， 无：提示开启灰度
         * 2. 当前已开启灰度空间无数据，不处理
         * 3. 当前多选空间，存在未灰度空间，则将为灰度空间拼接提示展示
         */
        if (this.searchType === 'incident') {
          this.noDataString = '';
          if (this.bizIds?.some(id => [authorityBizId, hasDataBizId].includes(id))) {
            this.noDataString = !greyed_spaces?.length
              ? 'incidentRenderAssistant'
              : this.$t('你当前有 {0} 个空间权限，暂无您负责的故障', [window.space_list.length]);
            this.incidentEmptyData = {
              text: String(window.space_list.length),
              path: '你当前有 {count} 个空间权限，暂未开启灰度, 请联系 {link}',
            };
          } else {
            const diffBizIds = difference(this.bizIds, greyed_spaces);
            if (diffBizIds?.length) {
              const intersectionBizIds = intersection(this.bizIds, greyed_spaces);
              const spaces = this.$store.getters.bizList
                .filter(({ bk_biz_id }) => diffBizIds.includes(bk_biz_id))
                .map(({ name, space_id }) => `${name} (#${space_id})`);
              this.incidentEmptyData = {
                text: spaces.join(','),
                path: '{count} 空间未开启故障分析功能，请联系 {link}',
              };
              this.noDataType = intersectionBizIds.length === 0 ? 'incidentNotEnabled' : this.noDataType;
              this.noDataString = 'incidentRenderAssistant';
            }
          }
        } else {
          if (!this.bizIds?.some(id => [authorityBizId, hasDataBizId].includes(id))) {
            this.noDataString = this.$t('你当前有 {0} 个业务权限，暂无告警事件', [window.space_list.length]);
          } else {
            this.noDataString = '';
          }
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
          key,
        },
      };
      setTimeout(() => {
        if (this.$store.getters.paddingRoute?.name.includes('event-center')) {
          this.routeStateKeyList.length === 0 ? this.$router.replace(params) : this.$router.push(params);
          this.routeStateKeyList.push(key);
        }
      }, 100);
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
        bizId: firstData.bk_biz_id,
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
      timezone: getDefaultTimezone(),
      refreshInterval: 300000,
      activePanel: 'list',
      chartInterval: 'auto',
      condition: {},
      // advancedFilterDefaultOpen: [],
      bizIds: [this.$store.getters.bizId || window.cc_biz_id],
      batchAction: '',
    };
  }
  handleParam2Url() {
    const defaultRouteData = this.handleGetDefaultRouteData();
    const newData = {};
    // biome-ignore lint/complexity/noForEach: <explanation>
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
        // biome-ignore lint/suspicious/noAssignInExpressions: <explanation>
        key === 'to' && ([, newData[key]] = this.timeRange);
      } else if (key === 'timezone') {
        newData[key] = this.timezone;
      }
      return false;
    });
    return newData;
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
      status,
    } = this.handleGetSearchParams(false, true);
    const params = {
      bk_biz_ids,
      conditions, // 过滤条件，二维数组
      query_string,
      status,
      start_time: from ? dayjs.tz(from).unix() : startTime, // 开始时间
      end_time: to ? dayjs.tz(to).unix() : endTime, // 结束时间
      interval: this.chartInterval,
    };
    const promiseFn = this.searchType === 'action' ? actionDateHistogram : alertDateHistogram;
    const { unit, series, code } = await promiseFn(params, { needRes: true, needMessage: false })
      .then(res => res.data)
      .catch(({ code, message, error_details }) => {
        if (code !== grammaticalErrorCode) {
          this.$bkMessage(error_details || { message, theme: 'error' });
        }
        return {
          series: [],
          unit: '',
          code,
        };
      });
    if (from) {
      this.timeRange = [
        dayjs.tz(params.start_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
        dayjs.tz(params.end_time * 1000).format('YYYY-MM-DD HH:mm:ss'),
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
        .map(item => ({ ...item, name: item.display_name, stack: 'event-alram' })),
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
    /** 故障只有列表，所以切换到故障的时候，默认选中list */
    if (id === 'incident') {
      this.activePanel = 'list';
    }
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
    if (this.searchType === 'incident') {
      this.$router.push({
        name: 'incident-detail',
        params: {
          id,
        },
        query: {
          activeTab,
        },
      });
    } else {
      this.detailInfo.id = id;
      this.detailInfo.type = type;
      this.detailInfo.isShow = true;
      this.detailInfo.bizId = bizId;
      this.detailInfo.activeTab = activeTab;
    }
  }

  /**
   * @description: 刷新间隔改变时触发
   * @param {number} v 刷新周期
   * @return {*}
   */
  handleRefreshChange(v: number) {
    window.clearInterval(this.refleshInstance);
    this.refreshInterval = v;
    if (v <= 0) return;
    this.refleshInstance = setInterval(() => {
      this.chartKey = random(10);
      this.handleGetFilterData();
      this.handleGetTableData();
    }, this.refreshInterval);
  }
  /**
   * @description: 点击立刻刷新图标触发
   * @param {*}
   * @return {*}
   */
  handleImmediateRefresh() {
    this.chartKey = random(10);
    this.handleGetFilterData();
    this.handleGetTableData();
    this.refreshInterval > 0 && this.handleRefreshChange(this.refreshInterval);
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
    this.handleRefreshChange(this.refreshInterval);
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
    commonPageSizeSet(limit);
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
    let exportFn = this.searchType === 'action' ? EventStoreModule.exportActionData : EventStoreModule.exportAlertData;
    if (this.searchType === 'incident') {
      exportFn = EventStoreModule.exportIncidentData;
    }
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
        theme: 'warning',
      });
    };
    switch (id) {
      // 批量确认告警
      case 'confirm':
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
        for (const alertId of this.selectedList) {
          const detail = this.tableData.find(tableitem => tableitem.id === alertId);
          details.push({
            severity: detail.severity,
            dimension: detail.dimensions,
            trigger: detail.description,
            alertId: alertId,
            strategy: {
              id: detail.strategy_id,
              name: detail.strategy_name,
            },
          });
        }
        this.dialog.quickShield.details = details;
        this.batchUrlUpdate(EBatchAction.quickShield);
        break;
      }
      case 'chat': {
        let assignees = [];
        for (const item of this.selectedList) {
          const detail = this.tableData.find(tableitem => tableitem.id === item);
          assignees = detail.assignee?.map(val => {
            return !assignees.includes(val);
          });
        }
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
  batchUrlUpdate(type: '' | EBatchAction) {
    if (/(^action_id).+/g.test(this.queryString) || !type) {
      const key = random(10);
      const params = {
        name: this.$route.name,
        query: {
          ...this.handleParam2Url(),
          batchAction: type || undefined,
          key,
        },
      };
      this.$nextTick(() => {
        if (this.$route.name.includes('event-center')) {
          this.$router.replace(params);
          this.routeStateKeyList.push(key);
        }
      });
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
        dimension: v.dimensions,
        trigger: v.description,
        alertId: v.id,
        strategy: {
          id: v?.strategy_id as unknown as string,
          name: v?.strategy_name,
        },
      },
    ];
    // EventModuleStore.setDimensionList(v.dimensions || []);
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
      for (const item of this.tableData) {
        if (this.dialog.quickShield.ids.includes(item.id)) {
          item.is_shielded = true;
          item.shield_operator = [window.username || window.user_name];
        }
      }
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
  handleChartIntervalChange(v: number | string) {
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
  handleAdvanceFilterChange(conditionKey: number | string, id: string[]) {
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
      for (const item of this.tableData) {
        if (this.dialog.alarmConfirm.ids.includes(item.id)) {
          item.is_ack = true;
          item.ack_operator = window.username || window.user_name;
        }
      }
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
    for (const item of this.tableData) {
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
    }
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
    let key = this.searchType === 'alert' ? alertAnalyzeStorageKey : actionAnalyzeStorageKey;
    if (this.searchType === 'incident') {
      key = incidentAnalyzeStorageKey;
    }
    if (this.searchType === 'alert') {
      this.analyzeFields = v;
    } else if (this.searchType === 'incident') {
      this.incidentFieldList = v;
    } else {
      this.analyzeActionFields = v;
    }
    localStorage.setItem(key, JSON.stringify(v));
    await this.handleGetSearchTopNList(false, false);
    this.tableLoading = false;
  }
  /**
   * @description 跳转打开bk助手
   */
  handleToBkAssistant() {
    this.incidentWxCsLink && window.open(this.incidentWxCsLink, '__blank');
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
        'view_rule_v2',
      ],
      resources: bizList.map(id => ({ id, type: 'space' })),
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
        key='AlarmConfirm'
        bizIds={this.dialog.alarmConfirm.bizIds}
        ids={this.dialog.alarmConfirm.ids}
        show={this.dialog.alarmConfirm.show}
        on-change={this.alarmConfirmChange}
        onConfirm={this.handleConfirmAfter}
      />,
      <QuickShield
        key='QuickShield'
        authority={this.authority}
        bizIds={this.dialog.quickShield.bizIds}
        details={this.dialog.quickShield.details}
        handleShowAuthorityDetail={this.handleShowAuthorityDetail}
        ids={this.dialog.quickShield.ids}
        show={this.dialog.quickShield.show}
        on-change={this.quickShieldChange}
        on-succes={this.quickShieldSucces}
      />,
      <ManualProcess
        key='ManualProcess'
        alertIds={this.dialog.manualProcess.alertIds}
        bizIds={this.dialog.manualProcess.bizIds}
        show={this.dialog.manualProcess.show}
        onDebugStatus={this.handleDebugStatus}
        onMealInfo={this.handleMealInfo}
        onShowChange={this.manualProcessShowChange}
      />,
      <ManualDebugStatus
        key='ManualDebugStatus'
        actionIds={this.dialog.manualProcess.actionIds}
        bizIds={this.dialog.manualProcess.bizIds}
        debugKey={this.dialog.manualProcess.debugKey}
        mealInfo={this.dialog.manualProcess.mealInfo}
      />,
      <AlarmDispatch
        key='AlarmDispatch'
        alertIds={this.dialog.alarmDispatch.alertIds}
        bizIds={this.dialog.alarmDispatch.bizIds}
        show={this.dialog.alarmDispatch.show}
        onShow={this.handleAlarmDispatchShowChange}
        onSuccess={this.handleAlarmDispatchSuccess}
      />,
    ];
  }

  filterGroupSlot(item: IGroupData) {
    return (
      <bk-big-tree
        ref={`tree-${item.id}`}
        class={{ 'no-multi-level': !item.children.some(child => child.children?.length) }}
        scopedSlots={{
          default: ({ data }) => (
            <div class='condition-tree-item'>
              <span class={['item-name', `item-status-${data.id}`]}>{data.name}</span>
              <span class='item-count'>{data.count}</span>
            </div>
          ),
        }}
        data={item.children}
        default-checked-nodes={this.condition[item.id]}
        default-expand-all={true}
        options={{ nameKey: 'name', idKey: 'id', childrenKey: 'children' }}
        padding={30}
        show-checkbox={true}
        show-link-line={false}
        on-check-change={id => this.handleAdvanceFilterChange(item.id, id)}
      />
    );
  }
  filterListComponent(item: ICommonTreeItem) {
    const isOpen = this.commonFilterDataIdMap[item.id].includes(this.listOpenId);
    return [
      <div
        key={`${item.id}list-title`}
        class={['list-title', { 'item-active': item.id === this.activeFilterId }]}
        on-click={() => this.handleSelectActiveFilter(item.id as SearchType, item)}
      >
        <i
          class={['bk-icon', isOpen ? 'icon-down-shape' : 'icon-right-shape']}
          on-click={e => {
            e.stopPropagation();
            const status = this.listOpenId;
            this.listOpenId = status === item.id ? '' : item.id;
          }}
        />
        {item.name}
        {this.commonFilterLoading ? (
          <div class='count-skeleton skeleton-element' />
        ) : (
          <span class='item-count'>{item.count}</span>
        )}
      </div>,
      <ul
        key={item.id}
        class='set-list'
        v-show={isOpen}
      >
        {item?.children?.map?.(set =>
          filterIconMap[set.id] ? (
            <li
              key={set.id}
              class={['set-list-item', { 'item-active': set.id === this.activeFilterId }]}
              on-click={() => this.handleSelectActiveFilter(item.id as SearchType, set)}
            >
              <i
                style={{ color: filterIconMap[set.id].color }}
                class={`icon-monitor item-icon ${filterIconMap[set.id].icon}`}
              />
              {set.name}
              {this.commonFilterLoading ? (
                <div class='count-skeleton skeleton-element' />
              ) : (
                <span class='item-count'>{set.count}</span>
              )}
            </li>
          ) : undefined
        ) || undefined}
      </ul>,
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
      for (const [key, val] of Object.entries(this.condition)) {
        if (val.length) {
          this.condition[key] = [];
        }
      }
      this.noDataType = 'empty';
      this.handleGetTableData();
      return;
    }
  }
  renderList() {
    return this.searchType === 'incident' ? (
      <IncidentTable
        bizIds={this.bizIds}
        doLayout={this.activePanel}
        loading={this.tableLoading}
        pagination={this.pagination}
        searchType={this.searchType}
        selectedList={this.selectedList}
        tableData={this.tableData}
        onAlarmDispatch={this.handleAlarmDispatch}
        onAlertConfirm={this.handleAlertConfirm}
        onBatchSet={this.handleBatchAlert}
        onChatGroup={this.handleChatGroup}
        onLimitChange={this.handleTableLimitChange}
        onManualProcess={this.handleManualProcess}
        onPageChange={this.handleTabelPageChange}
        onQuickShield={this.handleQuickShield}
        onSelectChange={this.handleTableSelecChange}
        onShowDetail={this.handleShowDetail}
        onSortChange={this.handleSortChange}
      />
    ) : (
      <EventTable
        bizIds={this.bizIds}
        doLayout={this.activePanel}
        loading={this.tableLoading}
        pagination={this.pagination}
        searchType={this.searchType}
        selectedList={this.selectedList}
        tableData={this.tableData}
        onAlarmDispatch={this.handleAlarmDispatch}
        onAlertConfirm={this.handleAlertConfirm}
        onBatchSet={this.handleBatchAlert}
        onChatGroup={this.handleChatGroup}
        onLimitChange={this.handleTableLimitChange}
        onManualProcess={this.handleManualProcess}
        onPageChange={this.handleTabelPageChange}
        onQuickShield={this.handleQuickShield}
        onSelectChange={this.handleTableSelecChange}
        onShowDetail={this.handleShowDetail}
        onSortChange={this.handleSortChange}
      />
    );
  }
  render() {
    return (
      <div class='event-center-page'>
        <div
          style={{
            width: `${this.filterWidth}px`,
            flexBasis: `${this.filterWidth}px`,
            display: this.filterWidth > 200 ? 'flex' : 'none',
          }}
          class={`event-filter ${this.isSplitEventPanel ? 'hidden' : ''}`}
          onScroll={e => {
            this.filterScrollTop = (e.target as HTMLDivElement).scrollTop;
          }}
        >
          <div class='filter-list'>{this.commonFilterData?.map(item => this.filterListComponent(item))}</div>
          <div class='filter-search'>
            <div class='search-title'>{this.$t('高级筛选')}</div>
            {this.advancedFilterLoading ? (
              <AdvancedFilterSkeleton />
            ) : (
              <Group
                class='search-group'
                scopedSlots={{
                  default: ({ item }) => this.filterGroupSlot(item),
                }}
                data={this.advancedFilterData}
                defaultActiveName={this.advancedFilterDefaultOpen}
                theme='filter'
                onActiveChange={this.handleFilterActiveChange}
                onClear={item => this.clearCheckedFilter(item)}
              />
            )}
          </div>
          <MonitorDrag
            lineText={''}
            theme={'line'}
            toggleSet={this.toggleSet}
            top={this.filterScrollTop}
            on-move={this.handleDragFilter}
          />
          <div
            style={{
              left: `${this.filterWidth}px`,
            }}
            class='filter-line-trigger'
            onClick={() => (this.filterWidth = 0)}
          >
            <span class='icon-monitor icon-arrow-left' />
          </div>
        </div>
        <div
          style={{ maxWidth: `calc(100% - ${this.filterWidth}px - ${this.isSplitPanel ? this.splitPanelWidth : 0}px)` }}
          class='event-content'
        >
          <div class={`content-header ${this.isSplitEventPanel ? 'hidden' : ''}`}>
            <i
              style={{ display: this.filterWidth > 200 ? 'none' : 'flex' }}
              class='icon-monitor icon-double-up set-filter'
              on-click={this.setFilterDefaultWidth}
            />
            <span
              style={{ marginLeft: this.filterWidth > 200 ? '24px' : '0px' }}
              class='header-title'
            >
              {this.$t(this.activeFilterName)}
            </span>
            <DashboardTools
              class='header-tools'
              isSplitPanel={this.isSplitPanel}
              refreshInterval={this.refreshInterval}
              showListMenu={false}
              timeRange={this.timeRange}
              timezone={this.timezone}
              onFullscreenChange={this.handleFullscreen}
              onImmediateRefresh={this.handleImmediateRefresh}
              onRefreshChange={this.handleRefreshChange}
              onSplitPanelChange={this.handleSplitPanel}
              onTimeRangeChange={this.handleTimeRangeChange}
              onTimezoneChange={this.handleTimezoneChange}
            />
          </div>

          <div
            ref='contentWrap'
            class='content-wrap'
          >
            {this.searchType !== 'incident' && (
              <EventChart
                chartInterval={this.chartInterval}
                chartKey={this.chartKey}
                getSeriesData={this.handleGetAlertDateHistogram}
                searchType={this.searchType}
                onIntervalChange={this.handleChartIntervalChange}
              />
            )}
            <div class='content-wrap-filter'>
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
              {/* <div class='filter-select'>
                <SpaceSelect
                  class='mr-16'
                  value={this.bizIds}
                  spaceList={this.$store.getters.bizList}
                  hasAuthApply={true}
                  onApplyAuth={this.handleCheckAllowedByIds}
                  onChange={this.handleBizIdsChange}
                ></SpaceSelect>
              </div> */}
              <SpaceSelect
                class='mr-16'
                // currentSpace={this.$store.getters.bizId}
                hasAuthApply={true}
                isAutoSelectCurrentSpace={true}
                // needAlarmOption={!this.isIncident}
                needIncidentOption={this.isIncident}
                spaceList={this.$store.getters.bizList}
                value={this.bizIds}
                onApplyAuth={this.handleCheckAllowedByIds}
                onChange={this.handleBizIdsChange}
              />
              <FilterInput
                ref='filterInput'
                inputStatus={this.filterInputStatus}
                isFillId={true}
                searchType={this.searchType}
                value={this.queryString}
                valueMap={this.valueMap}
                onChange={this.handleQueryStringChange}
                onClear={this.handleQueryStringChange}
              />
              <div
                class={['tools-export', { disabled: !this.tableData.length }]}
                title={this.$tc('导出')}
                onClick={this.handleExportData}
              >
                <span class='icon-monitor icon-xiazai' />
              </div>
            </div>
            {`${this.bussinessTips}`.length > 0 && (
              <div class='permission-tips'>
                <bk-icon
                  class='permission-tips-icon'
                  type='exclamation-circle'
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
                  class='permission-tips-close'
                  type='close'
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
                    class='alert-text query-btn'
                    title='primary'
                    text
                    onClick={this.setQueryStringForCheckingEmptyAssignee}
                  >
                    <span style='display: inline-flex;'>{this.$t('button-查看')}</span>
                  </bk-button>
                </template>
              </bk-alert>
            )}
            <div
              ref='contentTable'
              class='content-table'
            >
              {this.searchType !== 'incident' && (
                <bk-tab
                  active={this.activePanel}
                  type='unborder-card'
                  on-tab-change={this.handleAlertTabChange}
                >
                  {this.panelList.map(item => (
                    <bk-tab-panel
                      key={item.id}
                      label={item.name}
                      name={item.id}
                    />
                  ))}
                </bk-tab>
              )}
              {!this.tableData.length ? (
                (() => {
                  if (this.tableLoading) {
                    return (
                      <div class='table-content'>
                        <TableSkeleton type={2} />
                      </div>
                    );
                  }
                  return (
                    <EmptyTable
                      // v-bkloading={{ isLoading: this.tableLoading, zIndex: 1000 }}
                      emptyType={this.noDataType}
                      handleOperation={this.handleOperation}
                      onApplyAuth={this.handleCheckAllowedByIds}
                    >
                      {this.noDataString && (
                        <span>
                          {this.noDataString === 'incidentRenderAssistant' ? (
                            <i18n
                              slot='title'
                              path={this.incidentEmptyData.path}
                            >
                              <span slot='count'>{this.incidentEmptyData.text}</span>
                              <span
                                class='bk-assistant-link'
                                slot='link'
                                onClick={this.handleToBkAssistant}
                              >
                                {this.$t('BK助手')}
                              </span>
                            </i18n>
                          ) : (
                            this.noDataString
                          )}{' '}
                        </span>
                      )}
                    </EmptyTable>
                  );
                })()
              ) : (
                <div class='table-content'>
                  <keep-alive>
                    {this.activePanel === 'list' ? (
                      (() => {
                        if (this.tableLoading) {
                          return <TableSkeleton type={2} />;
                        }
                        return this.renderList();
                      })()
                    ) : (
                      <AlertAnalyze
                        analyzeData={this.analyzeData}
                        analyzeFields={this.curAnalyzeFields}
                        analyzeTagList={this.analyzeTagList}
                        bizIds={this.bizIds}
                        clearSearch={this.handleOperation}
                        detailField={this.detailField}
                        detailFieldData={this.detailFieldData}
                        detailLoading={this.detailLoading}
                        hasSearchParams={this.hasSearchParams}
                        loading={this.tableLoading}
                        searchType={this.searchType}
                        onAppendQuery={this.handleAppendQuery}
                        onDetailFieldChange={this.handleDetailFieldChange}
                        // style={{ display: this.activePanel === 'analyze' ? 'flex' : 'none' }}
                        onFieldChange={this.handleFieldChange}
                      />
                    )}
                  </keep-alive>
                </div>
              )}
            </div>
          </div>
        </div>
        <div
          style={{
            width: `${this.splitPanelWidth}px`,
            display: this.splitPanelWidth > SPLIT_MIN_WIDTH && this.isSplitPanel ? 'flex' : 'none',
          }}
          class='split-panel-wrapper'
        >
          {this.isSplitPanel ? (
            <SplitPanel
              defaultRelated={'k8s'}
              splitMaxWidth={Math.max(this.splitPanelWidth + 300, SPLIT_MAX_WIDTH)}
              toggleSet={this.toggleSet}
              onDragMove={this.handleDragMove}
            />
          ) : undefined}
        </div>
        {this.detailInfo.isShow && (
          <event-detail-slider
            activeTab={this.detailInfo.activeTab}
            bizId={this.detailInfo.bizId}
            eventId={this.detailInfo.id}
            isShow={this.detailInfo.isShow}
            type={this.detailInfo.type}
            onShowChange={v => (this.detailInfo.isShow = v)}
          />
        )}
        {this.getOperateDialogComponent()}
        <ChatGroup
          alarmEventName={this.chatGroupDialog.alertName}
          alertIds={this.chatGroupDialog.alertIds}
          assignee={this.chatGroupDialog.assignee}
          show={this.chatGroupDialog.show}
          onShowChange={this.chatGroupShowChange}
        />
      </div>
    );
  }
}

export default ofType<IEventProps>().convert(Event);
