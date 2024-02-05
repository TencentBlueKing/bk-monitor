/* eslint-disable @typescript-eslint/no-misused-promises */
/* eslint-disable no-param-reassign */
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
/* eslint-disable no-nested-ternary */
// import { Component as tsc } from 'vue-tsx-support'
import { Component, Provide, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Route } from 'vue-router';
import { Component as tsc } from 'vue-tsx-support';

import { getMainlineObjectTopo } from '../../../monitor-api/modules/commons';
import { getGraphQueryConfig } from '../../../monitor-api/modules/data_explorer';
import { getFunctions } from '../../../monitor-api/modules/grafana';
import {
  createFavorite,
  createFavoriteGroup,
  destroyFavorite,
  destroyFavoriteGroup,
  listByGroupFavorite,
  updateFavorite,
  updateFavoriteGroup
} from '../../../monitor-api/modules/model';
import {
  getMetricListV2,
  getScenarioList,
  promqlToQueryConfig,
  queryConfigToPromql
} from '../../../monitor-api/modules/strategies';
import { monitorDrag } from '../../../monitor-common/utils/drag-directive';
import { copyText, Debounce, deepClone, getUrlParam, random } from '../../../monitor-common/utils/utils';
import PromqlEditor from '../../../monitor-ui/promql-editor/promql-editor';
import { EmptyStatusType } from '../../components/empty-status/types';
import MetricSelector from '../../components/metric-selector/metric-selector';
import { IIpV6Value, INodeType } from '../../components/monitor-ip-selector/typing';
import { transformValueToMonitor } from '../../components/monitor-ip-selector/utils';
import NotifyBox from '../../components/notify-box/notify-box';
import type { TimeRangeType } from '../../components/time-range/time-range';
import {
  DEFAULT_TIME_RANGE,
  handleTransformToTimestamp,
  timestampTransformStr
} from '../../components/time-range/utils';
import { getDefautTimezone, updateTimezone } from '../../i18n/dayjs';
import { MetricDetail, MetricType } from '../../pages/strategy-config/strategy-config-set-new/typings';
import LogRetrieval from '../log-retrieval/log-retrieval.vue';
import PanelHeader from '../monitor-k8s/components/panel-header/panel-header';
import { PanelToolsType } from '../monitor-k8s/typings';
import StrategyIpv6 from '../strategy-config/strategy-ipv6/strategy-ipv6';

import DataRetrievalItem from './data-retrieval-item/data-retrieval-item';
import DataRetrievalView from './data-retrieval-view/data-retrieval-view';
import EventRetrieval from './event-retrieval/event-retrieval';
import ExpressionItem from './expression-item/expression-item';
import AddCollectDialog from './favorite-container/add-collect-dialog';
import FavoriteIndex from './favorite-container/collect-index';
import HandleBtn from './handle-btn/handle-btn';
import { IIndexListItem } from './index-list/index-list';
import {
  DataRetrievalPromqlItem,
  DataRetrievalQueryItem,
  EventRetrievalViewType,
  IDataRetrieval,
  IDataRetrievalItem,
  IDataRetrievalView,
  IFavList,
  IFilterCondition,
  TEditMode
} from './typings';

import './data-retrieval.scss';

const { i18n } = window;
const NAME_CHAR = 'abcdefghijklmnopqrstuvwxyz';

Component.registerHooks(['beforeRouteEnter']);
@Component({
  directives: {
    monitorDrag
  }
})
export default class DataRetrieval extends tsc<{}> {
  /** 指标方法数据 */
  @ProvideReactive('metricFunctions') metricFunctions = [];
  // 控制是否显示 收藏 和 展开检索栏 仅展示视图图表
  @ProvideReactive('onlyShowView') onlyShowView = false;
  // 是否展示复位
  @ProvideReactive('showRestore') showRestore = false;
  @Ref('favPopover') favPopoverRef: Popover;
  @Ref() eventRetrievalRef: EventRetrieval;
  @Ref('favoriteIndex') favoriteIndexRef: FavoriteIndex;

  /** 页面loading */
  loading = false;

  /** 自动查询开关 */
  autoQuery = true;
  /** 首次进入提示 */
  isShowTips = true;

  /** 本地查询项/表达式数据 */
  localValue: IDataRetrieval.ILocalValue[] = [];
  curLocalValueIndex = 0;

  /** 查询结果 */
  queryResult: any[] = [];
  /** 查询结果 - 用作图表渲染 */
  filterQueryResult: any[] = [];

  /** 查询项操作数据 去除了'source'  */
  allOptions: IDataRetrieval.IOption[] = ['enable', 'copy', 'delete'];
  expandedData: Array<string> = [];
  optionIconName: { [key in IDataRetrieval.IOption] } = {
    source: 'icon-mc-sorce',
    enable: 'icon-mc-visual',
    copy: 'icon-mc-copy',
    delete: 'icon-mc-delete-line'
  };

  /** 控制指标选择器 */
  isShowMetricSelector = false;
  metricSelectorTargetId = null;
  metricSelectorMetricId = null;

  /** 指标回显数据 */
  metricData: any[] = [];
  /** 监控对象 */
  curMonitorType = 'os';

  /** 日志检索页面展示控制 */
  logShow = false;

  /** 侧栏展示控制 */
  toggleSet = true;

  /** 左侧栏宽度 */
  leftDefaultWidth = 420;
  isShowLeft = true;
  leftWidth = 420;

  /** 收藏列表宽度 */
  favoriteDefaultWidth = 240;
  isShowFavorite = false;
  favoriteWidth = 240;

  /** tab数据 */
  tabList: IDataRetrieval.ITabList[] = [
    { id: 'monitor', name: i18n.t('route-指标检索') },
    { id: 'log', name: i18n.t('route-日志检索') },
    { id: 'event', name: i18n.t('route-事件检索') }
  ];
  /** 默认选中的数据检索 */
  tabActive: IDataRetrieval.tabId = 'monitor';
  /** 页面初始化数据是否准备完成 */
  initDataIsReady: { [key in IDataRetrieval.tabId]: boolean } = {
    monitor: false,
    log: false,
    event: false
  };
  /** 收藏列表数据 */
  favList: { [key in IDataRetrieval.tabId]: any[] } = {
    monitor: [],
    log: [],
    event: []
  };
  // 所有收藏的收藏名
  favStrList: string[];

  /** 监控对象数据 */
  scenarioList = [];

  /** 收藏列表 */
  favoritesList: IFavList.favGroupList[] = [];
  favCheckedValue: IFavList.favList = null;

  /** 对比配置数据 */
  compareValue: IDataRetrievalView.ICompareValue = {
    compare: {
      type: 'none',
      value: true
    },
    tools: {
      refleshInterval: -1,
      timeRange: DEFAULT_TIME_RANGE,
      timezone: getDefautTimezone()
    }
  };

  /** 监控目标选择器数据 */
  target: IDataRetrieval.ITarget = {
    show: false,
    objectType: 'HOST',
    targetType: 'INSTANCE',
    value: [],
    desc: '',
    mainlineObjectTopoList: []
  };

  /** 收藏描述 */
  favDescInput = '';

  /** 查询时间 */
  queryTimeRange = 0;

  /** 页面loading delay 避免自动查询开启时频繁出现闪现的loading */
  delayLoading = false;

  /** 拖拽数据 */
  dragData: { from: number; to: number } = {
    from: null,
    to: null
  };

  /** 表达式输入缓存 用作输入diff */
  expCache = '';

  /** 标记主动触发查询 */
  isHandleQuery = false;

  /** 强制刷新监听 */
  refleshNumber = 0;

  /** 总控制开关是否是PromQL模式 */
  isPromQLType = false;

  /** 是否展示新增收藏弹窗 */
  isShowAddFavoriteDialog = false;

  /** 收藏弹窗打开时的查询语句参数 */
  favoriteKeywordsData = null;

  /** 编辑收藏弹窗时展示的收藏数据 */
  editFavoriteData: IFavList.favList = null;

  /** 是否是替换收藏的config参数 */
  isUpdateFavoriteConfig = true;

  /** 收藏查询中*/
  favoriteLoading = false;

  /** 是否是带有收藏id的初始化*/
  isHaveFavoriteInit = false;

  /** 事件检索 */

  /** 事件检索字段列表 */
  // eventFieldList: FieldValue[] = []
  /** 事件检索查询图表的指标数据 */
  eventMetricParams: IFilterCondition.VarParams = null;
  /** 事件检索过滤条件 */
  eventWhere: IFilterCondition.localValue[] = [];
  /** 事件检索汇聚周期 */
  eventInterval: EventRetrievalViewType.intervalType = 'auto';
  /** 收藏回显数据 */
  eventQueryConfig: IFilterCondition.VarParams = null;
  /** 事件记录条数 */
  eventCount = 0;
  /** 图表选择的时间范围 */
  eventChartTimeRange: EventRetrievalViewType.IEvent['onTimeRangeChange'] = null;
  /** 图表标题 */
  eventChartTitle = '';
  // 重新计算的数据周期
  reviewInterval = 0;
  // 左侧是否出现滚动
  isExpandAll = true;
  /* 当前模式(PromQL/UI) */
  editMode: TEditMode = 'UI';
  /* promql模式下展开收起状态 */
  promqlExpandedData = [];
  promqlData: DataRetrievalPromqlItem[] = [];
  /* 缓存上一次查询的参数 防止自动查询过于频繁 */
  promqlDataCache: DataRetrievalPromqlItem[] = [];
  metricSelectorShow = false;
  /** 检索收藏功能指引 */
  needUseCollectGuide = false;
  emptyStatus: EmptyStatusType = 'empty';
  /** 事件检索下钻的值 */
  drillKeywords = '';
  // 事件检索图表框选范围需更新到此组件
  eventSelectTimeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时间范围缓存用于复位功能
  cacheTimeRange = [];

  // 是否开启（框选/复位）全部操作
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
  @Debounce(200)
  @Provide('handleChartDataZoom')
  handleChartDataZoom(value: TimeRangeType) {
    if (JSON.stringify(this.compareValue.tools.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.compareValue.tools.timeRange));
      this.compareValue.tools.timeRange = value;
      this.showRestore = true;
      this.handleQueryProxy();
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.compareValue.tools.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
    this.handleQueryProxy();
  }

  @Watch('canQuery')
  canQueryChange(val: boolean) {
    if (val) this.emptyStatus = 'search-empty';
    else this.emptyStatus = 'empty';
  }

  @Watch('loading')
  loadingChange(val: boolean) {
    setTimeout(() => (this.delayLoading = val ? this.loading : false), 200);
  }

  @Watch('queryResult')
  queryResultChange() {
    this.handleFilterQueryResult();
  }

  @Watch('$route.name', { immediate: true })
  routeChange(routeName) {
    switch (routeName) {
      case 'data-retrieval':
        this.tabActive = 'monitor';
        break;
      case 'log-retrieval':
        this.logShow = true;
        this.tabActive = 'log';
        break;
      case 'event-retrieval':
        this.tabActive = 'event';
        this.emptyStatus = 'search-empty';
        break;
    }
  }

  get bizId(): string {
    return this.$store.getters.bizId;
  }

  /** 查询按钮点击状态 */
  get canQuery(): boolean {
    return this.editMode === 'UI'
      ? this.localValue.some((item: DataRetrievalQueryItem) => item.isMetric && !item.isNullMetric)
      : this.promqlData.some(item => !!item.code);
  }

  // 是否可以添加多指标
  get canAddStrategy(): boolean {
    const metricList = this.localValue.filter(item => item.isMetric) as DataRetrievalQueryItem[];
    const leng = metricList.length;
    if (!leng) return false;
    if (leng === 1) return true;
    return metricList.every(item => item.canSetMulitpeMetric);
  }

  /** 收藏列表 */
  get curFavList() {
    return this.favList[this.tabActive];
  }

  /** 左侧总宽度 */
  get allLeftWidth() {
    return this.leftWidth + this.favoriteWidth;
  }

  /** 收藏索引 */
  get favoriteSearchType() {
    return this.tabActive === 'event' ? 'event' : 'metric';
  }

  /**
   * 索引列表数据
   */
  get indexLists(): IIndexListItem[] {
    const indexList: IIndexListItem[] = [];
    if (this.filterQueryResult.length < 2) return [];
    this.filterQueryResult.forEach(item => {
      const leng = item.targets.length;
      if (leng && item.group && item.index) {
        // 存在分组
        const group = indexList.find(group => group.id === item.group);
        const child = {
          id: `${item.group}-${item.index}`,
          name: item.index
        };
        if (group) {
          group.children.push(child);
        } else {
          indexList.push({
            id: item.group,
            name: item.group,
            children: [child]
          });
        }
      } else if (leng && item.group && !item.index) {
        indexList.push({
          id: item.group,
          name: item.group
        });
      } else if (leng && !item.group && item.index) {
        indexList.push({
          id: item.index,
          name: item.index
        });
      }
    });
    /** 只有一个组情况下 平铺数据 */
    if (indexList.length === 1 && indexList[0].children) return indexList[0].children;
    return indexList;
  }
  /** 指标监控对象数据 */
  get scenarioAllList() {
    const list = deepClone(this.scenarioList);
    const res = list.reduce((total, cur) => {
      const child = cur.children || [];
      total = total.concat(child);
      return total;
    }, []);
    return res;
  }

  get isFavoriteNewSearch() {
    return this.favCheckedValue === null;
  }

  get selectFavoriteName() {
    return this.favCheckedValue?.name || '--';
  }

  /** 判断事件检索和指标检索收藏参数是否有修改 */
  get isFavoriteUpdate() {
    if (this.favCheckedValue === null || this.loading) return false;
    const favConfig = this.favCheckedValue.config;
    if (this.favoriteSearchType === 'event') {
      const curQueryConfig = this.eventRetrievalRef.currentGroupByVarPramas;
      const { queryConfig: favQueryConfig } = favConfig;
      return JSON.stringify(curQueryConfig) !== JSON.stringify(favQueryConfig);
    }
    if (this.editMode === 'UI') {
      const favParams = this.getComparedLocalParams(favConfig.localValue);
      const localParams = this.getComparedLocalParams(this.localValue);
      return JSON.stringify(favParams) !== JSON.stringify(localParams);
    }
    const favParams = this.getComparedPromQLParams(favConfig.promqlData);
    const localParams = this.getComparedPromQLParams(this.promqlData);
    return JSON.stringify(favParams) !== JSON.stringify(localParams);
  }

  /* 当前是否允许转为promql */
  get canToPromql() {
    if (this.editMode === 'UI') {
      return this.localValue
        .filter(item => !!item.metric_id)
        .every(item => ['custom', 'bk_monitor'].includes(item.data_source_label));
    }
    return true;
  }

  beforeRouteEnter(to: Route, from: Route, next: Function) {
    next((vm: DataRetrieval) => {
      const { targets, type } = vm.$route.query.targets ? vm.$route.query : vm.$route.params;
      let targetsList = [];
      if (targets) {
        try {
          targetsList = JSON.parse(decodeURIComponent(targets as string));
        } catch (error) {
          console.log('route query:', error);
        }
        if (type === 'event') {
          // 跳转事件检索路由参数会多带一个type=event
          vm.handleRouteQueryDataOfEvent(targetsList, type);
        } else if (targets && from.name !== 'view-detail') {
          // 跳转数据检索
          const fromRouteName: IDataRetrieval.fromRouteNameType = targetsList?.find?.(
            item => item?.data?.query_configs?.find?.(set => !!set.metrics)
          )
            ? 'performance-detail'
            : 'grafana';
          vm.handleRouteQueryData(targetsList, fromRouteName);
        }
      } else {
        const metricId = vm.$route.query.metric_id || vm.$route.params.metric_id;
        metricId?.length && this.handleRouterOfMetricId(metricId.toString());
      }
    });
  }

  created() {
    this.handleSetNeedRetrievalMenu();
    this.autoQuery = (localStorage.getItem('bk_monitor_auto_query_enable') || 'true') === 'true';
    this.isShowTips = (localStorage.getItem('bk_monitor_data_retrieval_show_tips') || 'true') === 'true';
    this.isHaveFavoriteInit = !!this.$route.query?.favorite_id;
    const isShowFavorite =
      (localStorage.getItem('bk_monitor_data_favorite_show') || 'false') === 'true' || this.isHaveFavoriteInit;
    this.isShowLeft = (localStorage.getItem('bk_monitor_search_left_show') || 'true') === 'true';
    this.editMode = localStorage.getItem('bk_monitor_edit_mode_str') === 'PromQL' ? 'PromQL' : 'UI';
    this.handleFavoriteHiddenAndShow(isShowFavorite);
    this.getApiData();
    this.handleAddQuery();
    this.handleAddCode();
  }

  mounted() {
    // this.isShowTips && this.autoQueryPopoverRef?.showHandler();
    window.addEventListener('message', this.handleMessage, false);
  }

  beforeDestroy() {
    window.removeEventListener('message', this.handleMessage, false);
  }
  /** 非路由组件无法触发 BeforeRouteEnter 钩子 在其父组件触发后跳用此方法 */
  handleBeforeRouteEnter(to: Route, from: Route) {
    const {
      targets,
      type,
      from: fromTime,
      to: toTime,
      timezone
    } = this.$route.query.targets ? this.$route.query : this.$route.params;
    let targetsList = [];
    if (fromTime && toTime) this.compareValue.tools.timeRange = [fromTime as string, toTime as string];
    this.compareValue.tools.timezone = getDefautTimezone();
    if (timezone) {
      this.compareValue.tools.timezone = timezone as string;
      updateTimezone(timezone as string);
    }
    if (targets) {
      try {
        targetsList = JSON.parse(decodeURIComponent(targets as string));
      } catch (error) {
        console.log('route query:', error);
      }
      if (type === 'event') {
        // 跳转事件检索路由参数会多带一个type=event
        this.handleRouteQueryDataOfEvent(targetsList, type);
      } else if (targets && from.name !== 'view-detail') {
        // 跳转数据检索
        const fromRouteName: IDataRetrieval.fromRouteNameType = targetsList?.find?.(
          item => item?.data?.query_configs?.find?.(set => !!set.metrics)
        )
          ? 'performance-detail'
          : 'grafana';
        this.handleRouteQueryData(targetsList, fromRouteName, fromTime as string, toTime as string);
      }
    } else {
      const metricId = this.$route.query.metric_id || this.$route.params.metric_id;
      metricId?.length && this.handleRouterOfMetricId(metricId.toString());
    }
  }

  /* 通过metric_id跳转过来 */
  async handleRouterOfMetricId(metricId: string) {
    this.loading = true;
    const metricList = await getMetricListV2({
      conditions: [{ key: 'metric_id', value: metricId }]
    })
      .then(data => data.metric_list || [])
      .catch(() => []);
    if (metricList.length) {
      const metricData = new MetricDetail(metricList[0]);
      this.handleAddMetricData(metricData as DataRetrievalQueryItem);
    }
    this.loading = true;
  }

  /**
   * @description: 日志检索点击指标检索派发message
   * @param {MessageEvent} evt
   * @return {*}
   */
  handleMessage(evt: MessageEvent) {
    const eventKey = evt.data;
    const tapActiveMap = {
      'datarieval-click': 'monitor',
      'event-click': 'event'
    };
    if (tapActiveMap[eventKey]) {
      this.logShow = false;
      this.tabActive = tapActiveMap[eventKey] ?? 'monitor';
    }
  }

  /** 获取刷新功能应该调用的请求数据接口 */
  @Provide('refreshQueryFn')
  refreshQueryFn() {
    // 事件检索返回eventRetrievalRef组件内部的handleEventQuery查询函数
    if (this.tabActive === 'event') this.eventRetrievalRef.handleEventQuery();
    // 指标检索返回handleQuery查询函数
    if (this.tabActive === 'monitor') this.handleQuery();
  }

  /**
   * @description: 基础功能的数据请求
   */
  getApiData() {
    if (this.initDataIsReady[this.tabActive]) return;
    this.loading = true;
    let promiseList: Promise<void>[] = []; // 收藏列表
    // 数据检索初始化所需数据接口
    if (this.tabActive === 'monitor') {
      promiseList = [
        this.getScenarioList(), // 监控对象数据
        this.handleGetMetricFunctions(), //  函数列表
        this.getMainlineObjectTopo() // 获取监控目标名字数据
      ];
    } else if (this.tabActive === 'event') {
      // 事件检索初始化所需数据接口
      promiseList = [];
    }
    return Promise.all(promiseList)
      .then(res => {
        this.initDataIsReady[this.tabActive] = true;
        return res;
      })
      .catch(err => {
        console.error(err);
        this.initDataIsReady[this.tabActive] = false;
      })
      .finally(() => (this.loading = false));
  }

  /**
   * @description: 获取收藏列表
   */
  async getListByGroupFavorite() {
    this.favoriteLoading = true;
    const order_type = localStorage.getItem('bk_monitor_favorite_sort_type') || 'asc'; // 获取收藏排序
    const param = { type: this.favoriteSearchType, order_type };
    return await listByGroupFavorite(param)
      .then(res => {
        this.favoriteIndexRef && (this.favoriteIndexRef.emptyStatusType = 'empty');
        const provideFavorite = res[0];
        const publicFavorite = res[res.length - 1];
        const sortFavoriteList = res.slice(1, res.length - 1).sort((a, b) => a.name.localeCompare(b.name));
        const sortAfterList = [provideFavorite, ...sortFavoriteList, publicFavorite];
        this.favList[this.tabActive] = sortAfterList;
        this.favStrList = res.reduce((pre, cur) => {
          // 获取所有收藏的名字新增时判断是否重命名
          pre = pre.concat(cur.favorites.map(item => item.name));
          return pre;
        }, []);
        if (this.isHaveFavoriteInit) {
          // 判断是否是分享初始化
          const urlFavoriteID = this.$route.query.favorite_id;
          for (const gItem of res) {
            const favorite = gItem.favorites.find(item => String(item.id) === urlFavoriteID);
            if (!!favorite) {
              this.handleSelectFavProxy(favorite);
              break;
            }
          }
        }
      })
      .catch(err => {
        console.warn(err);
        this.favoriteIndexRef && (this.favoriteIndexRef.emptyStatusType = '500');
        this.favList[this.tabActive] = [];
      })
      .finally(() => {
        // 获取收藏列表后 若当前不是新检索 则判断当前收藏是否已删除 若删除则变为新检索
        if (this.favCheckedValue !== null) {
          let isFindCheckValue = false; // 是否从列表中找到匹配当前收藏的id
          for (const gItem of this.favList[this.tabActive]) {
            const findFavorites = gItem.favorites.find(item => item.id === this.favCheckedValue.id);
            if (!!findFavorites) {
              isFindCheckValue = true; // 找到 中断循环
              break;
            }
          }
          if (!isFindCheckValue) {
            // 未找到 清空当前收藏 变为新检索
            this.favCheckedValue = null;
            this.favoriteSearchType === 'event' ? this.eventRetrievalRef?.handleClearQuery() : this.handleClearAll();
          }
        }
        // 如果是分享收藏初始化 则清空url的query参数
        if (this.isHaveFavoriteInit) this.$router.push({ name: this.$route.name });
        this.favoriteLoading = false;
        this.isHaveFavoriteInit = false;
      });
  }

  /**
   * @description: 获取监控目标名字数据
   */
  async getMainlineObjectTopo() {
    const list = await getMainlineObjectTopo().catch(() => []);
    this.target.mainlineObjectTopoList = list;
    this.target.desc = this.gettargetDes();
  }

  /**
   * @description: 获取指标函数列表
   */
  async handleGetMetricFunctions() {
    this.metricFunctions = await getFunctions().catch(() => []);
  }

  /** 图表查询结果 过滤隐藏的查询 */
  handleFilterQueryResult() {
    const hiddenAliasList = [];
    this.localValue.forEach(item => {
      !item.enable && hiddenAliasList.push(item.alias);
    });
    let isExist = false;
    const result = this.queryResult.map(item => {
      const targets = item.targets.filter(set => !hiddenAliasList.includes(set.source));
      !!targets?.length && (isExist = !!targets?.length);
      return {
        ...item,
        targets
      };
    });
    this.filterQueryResult = isExist ? result : [];
  }

  /**
   * @description: 操作配置
   * @param {IDataRetrieval} type 类型
   */
  itemOptions(localValItem: IDataRetrieval.ILocalValue): IDataRetrieval.IOption[] {
    // 数据检索prom转换开启
    return this.allOptions.filter(item => (localValItem.isMetric ? true : item !== 'source'));
    // return this.allOptions.filter(item => item !== 'source')
  }

  /**
   * @description: 获取监控对象数据
   */
  getScenarioList() {
    return getScenarioList().then(data => {
      this.scenarioList = data;
    });
  }

  /**
   * @description: 左侧隐藏
   */
  handleLeftHiddenAndShow(val: boolean) {
    this.isShowLeft = val;
    localStorage.setItem('bk_monitor_search_left_show', `${val}`);
  }

  /**
   * @description: tab切换方法
   * @param {IDataRetrieval} id
   */
  handleTabChange(id: IDataRetrieval.tabId) {
    if (id === 'log') {
      this.logShow = true;
      return;
    }
    this.tabActive = id;
    this.getApiData();
  }

  /**
   * @description: 查询项/表达式 操作方法
   * @param {Event} evt 点击事件
   * @param {IDataRetrieval} opt 操作key
   * @param {IDataRetrieval} item localValue item
   * @param {number} index localValue 索引
   */
  handleOptionProxy(evt: Event, opt: IDataRetrieval.IOption, item: IDataRetrieval.ILocalValue, index: number) {
    evt.stopPropagation();
    const fnMap: { [key in IDataRetrieval.IOption]: Function } = {
      source: () => this.handleSwitchSource(item as DataRetrievalQueryItem, index),
      enable: () => this.handleSwitchEnable(item),
      copy: () => this.handleCopyItem(item),
      delete: () => this.handleDeleteItem(index)
    };
    fnMap[opt]?.();
  }
  /* promql 模式下 */
  handleSourceCodeOptionProxy(evt: Event, opt: IDataRetrieval.IOption, item: DataRetrievalPromqlItem, index: number) {
    evt.stopPropagation();
    if (opt === 'copy') {
      const tempItem = deepClone(item) as DataRetrievalPromqlItem;
      tempItem.key = random(8);
      tempItem.alias = this.getCurItemAlias(this.promqlData as any);
      this.promqlData.push(new DataRetrievalPromqlItem(tempItem));
      this.promqlExpandedData.push(tempItem.key);
    } else if (opt === 'delete') {
      if (this.promqlData.length > 1) {
        this.promqlData.splice(index, 1);
      }
    } else if (opt === 'enable') {
      item.enable = !item.enable;
    }
    this.handleQueryProxy();
  }

  /**
   * @description: 源码切换操作
   * @param {IDataRetrieval} item
   * @param {number} index
   */
  async handleSwitchSource(item: DataRetrievalQueryItem, index: number) {
    const newVal = !item.showSource;
    item.switchToUI = !newVal;
    if (newVal) {
      const res = await this.handleQeueryConfigsToPromsql(item);
      if (res) {
        item.showSource = newVal;
      }
    } else {
      const promqlEditorRef = this.$refs[`promql-editor-${index}`] as any;
      const error = promqlEditorRef.getLinterStatus();
      if (!error) {
        if (item.sourceCode === item.sourceCodeCache || !item.sourceCode) {
          item.showSource = false;
          return;
        }
        item.loading = true;
        await this.handlePromqlQuery(item, index);
        item.loading = false;
      }
    }
  }
  /**
   * @description: 切换查询项/表达式是否生效
   * @param {IDataRetrieval} item
   * @param {number} index
   */
  handleSwitchEnable(item: IDataRetrieval.ILocalValue) {
    item.enable = !item.enable;
    // 不存在则请求接口查询
    const isExist = this.handleCheckExit(item.alias);
    if (isExist) {
      this.handleFilterQueryResult();
    } else {
      this.handleQueryProxy();
    }
  }

  /** 检查该查询项的结果是否存在 */
  handleCheckExit(alias) {
    let isExist = false;
    this.queryResult.forEach(item => {
      const targets = item.targets.filter(set => set.source === alias);
      !!targets?.length && (isExist = !!targets?.length);
    });
    return isExist;
  }
  /**
   * @description: 克隆操作
   * @param {IDataRetrieval} item
   * @param {number} index
   */
  handleCopyItem(item: IDataRetrieval.ILocalValue) {
    const tempItem = deepClone(item) as IDataRetrieval.ILocalValue;
    tempItem.key = random(8);
    tempItem.alias = this.getCurItemAlias();
    this.localValue.push(tempItem);
    this.expandedData.push(tempItem.key);
    this.handleQueryProxy();
  }
  /**
   * @description: 删除操作
   * @param {number} index
   */
  handleDeleteItem(index: number) {
    const item = this.localValue[index];
    if (item.isMetric) {
      const child = item as DataRetrievalQueryItem;
      if (this.localValue.length === 1 && child.isNullMetric) return;
    }
    this.localValue.splice(index, 1);
    if (!this.localValue.length) {
      this.handleAddQuery();
    }
    this.handleQueryProxy();
  }

  /**
   * @description: 生成查询项/表达式名称
   * @param {number} index
   * @return {string}
   */
  createItemName(index: number): string {
    const len = NAME_CHAR.length;
    if (index < len) {
      return NAME_CHAR[index];
    }
    const n = Math.floor(index / len);
    const i = index % len;
    return NAME_CHAR.slice(0, n) + NAME_CHAR[i];
  }
  /**
   * @description: 计算当前alias
   */
  getCurItemAlias(list = this.localValue): string {
    const aliasList = list.map(item => item.alias);
    const allList = NAME_CHAR.split('');
    let index = 0;
    while (aliasList.includes(allList[index])) {
      index += 1;
    }
    return this.createItemName(index < allList.length ? index : this.localValue.length);
  }

  /**
   * @description: 查询项/表达式 值更新
   * @param {IDataRetrievalItem} data 新值
   * @param {number} index localValue 索引
   * @param {IDataRetrieval} item localValue item
   */
  handleQueryItemValueChange(data: IDataRetrievalItem.onChange, index: number) {
    this.localValue[index].errMsg = '';
    const tempKey = data.value.key;
    const val = new DataRetrievalQueryItem(data.value);
    val.key = tempKey;
    this.$set(this.localValue, index, val as DataRetrievalQueryItem);
    this.handleQueryProxy();
  }

  /**
   * 表达式值变更
   * @param data 表达式数据
   * @param index 索引
   */
  handleExpressionValueChange(data: IDataRetrieval.IExpressionItem, index: number) {
    this.$set(this.localValue, index, data as IDataRetrieval.IExpressionItem);
    this.handleQueryProxy();
  }

  /**
   * @description: 清除指标信息
   * @param {number} index 索引
   */
  handleClearMetric(index: number) {
    const item = new DataRetrievalQueryItem();
    const oldItem = this.localValue[index];
    item.alias = oldItem.alias;
    item.key = oldItem.key;
    this.$set(this.localValue, index, item);
    this.expandedData.push(item.key);
    this.handleQueryProxy();
  }

  /**
   * @description: 控制指标选择器显隐
   * @param {boolean} val
   */
  handleShowMetricSelector(val: boolean, index?: number) {
    if (val) {
      const curItem = this.localValue[index] as DataRetrievalQueryItem;
      this.metricData = !!curItem.metric_id ? [curItem] : [];
      this.curLocalValueIndex = index;
      this.metricSelectorMetricId = curItem.metric_id;
    }
    this.metricSelectorTargetId = `#_metric_item_index_${index}`;
    this.isShowMetricSelector = val;
  }
  /**
   * @description: 指标选择器返回值
   * @param {*} data 指标数据
   */
  handleAddMetricData(data: DataRetrievalQueryItem) {
    const item = new DataRetrievalQueryItem(data);
    const oldItem = this.localValue[this.curLocalValueIndex] as DataRetrievalQueryItem;
    item.alias = oldItem.alias;
    item.enable = true;
    /** 当切换指标时保留原有查询条件（非空指标） */
    if (!oldItem.isNullMetric) {
      item.agg_condition = oldItem.agg_condition; // 条件
      item.agg_dimension = oldItem.agg_dimension.filter(dim => item.agg_dimension.includes(dim)); // 维度
      item.agg_interval = oldItem.agg_interval; // 汇聚周期
      item.agg_method = oldItem.agg_method; // 汇聚方法
      oldItem.canSetFunction && item.canSetFunction && (item.functions = oldItem.functions); // 函数
    } else {
      item.agg_dimension = []; // 添加指标不带默认维度值
    }
    this.$set(this.localValue, this.curLocalValueIndex, item);
    this.expandedData.push(item.key);
    this.handleQueryProxy();
  }

  /**
   * @description: 新增一条空的查询条件
   */
  handleAddQuery() {
    const item = new DataRetrievalQueryItem();
    item.alias = this.getCurItemAlias();
    this.localValue.push(item);
    this.expandedData.push(item.key);
  }
  /* promql模式下新建一条空的查询项 */
  handleAddCode() {
    const item = new DataRetrievalPromqlItem();
    item.alias = this.getCurItemAlias(this.promqlData as any);
    this.promqlData.push(item);
    this.promqlExpandedData.push(item.key);
  }
  /**
   * @description: 添加一条表达式
   */
  handleAddExpression() {
    const key = random(8);
    this.expandedData.push(key);
    this.localValue.push({
      key,
      alias: this.getCurItemAlias(),
      isMetric: false,
      enable: true,
      value: '',
      functions: []
    });
  }

  /**
   * @description: 清空查询
   */
  handleClearAll() {
    this.localValue = [];
    this.target.value = [];
    this.target.desc = '';
    this.filterQueryResult = [];
    this.promqlData = [];
    this.promqlExpandedData = [];
    this.handleAddQuery();
    this.handleAddCode();
  }

  /**
   * @description: 对比操作栏值更新
   * @param {IDataRetrievalView} data
   */
  handleCompareChange(data: IDataRetrievalView.ICompareComChange) {
    this.compareValue = data;
    if (!['interval'].includes(data.type)) {
      this.handleQueryProxy();
    }
  }

  handleCompareValueChange(data: PanelToolsType.Compare) {
    this.compareValue.compare = data;
    this.handleQueryProxy();
  }

  /**
   * @description: 变更时间范围
   * @param {PanelHeaderType} timeRange
   */
  handleToolsTimeRangeChange(timeRange: TimeRangeType) {
    this.compareValue.tools.timeRange = timeRange;
    this.handleQueryProxy();
  }
  /**
   * @description: 变更时区
   * @param {string} timezone
   */
  handleTimezoneChange(timezone: string) {
    this.compareValue.tools.timezone = timezone;
    this.handleQueryProxy();
  }
  /**
   * @description: 合并视图
   * @param {boolean} val
   */
  handleSplitChange(val: boolean) {
    this.compareValue.compare.value = val;
    this.handleQueryProxy();
  }

  /**
   * @description: 打开目标选择器
   */
  handleShowTargetSelector() {
    this.target.show = true;
  }
  /**
   * @description: 目标类型值更新
   * @param {string} type 目标类型
   */
  handleTargetTypeChange(type: IDataRetrieval.TargetType) {
    this.target.targetType = type;
  }

  /**
   * @description: 保存选中目标
   * @param {*} data 目标数据
   */
  handleTargetChange(data: { value: IIpV6Value; nodeType: INodeType }) {
    const value = transformValueToMonitor(data.value, data.nodeType);
    this.target.value = value;
    this.target.targetType = data.nodeType;
    this.target.desc = this.gettargetDes();
    this.handleQueryProxy();
  }

  /**
   * @description: 获取监控目标描述
   */
  gettargetDes(): string {
    const cloneTarget = JSON.parse(JSON.stringify(this.target.value || []));
    const nameList = this.target.mainlineObjectTopoList;
    let targetDes = '';
    if (!cloneTarget.length) return targetDes;
    // 动态选择目标
    if ('bk_obj_id' in cloneTarget[0]) {
      let list = cloneTarget.map(item => {
        item.name = nameList.find(set => set.bk_obj_id === item.bk_obj_id).bk_obj_name;
        return item;
      });
      // 统计数量
      list = list.map(item => {
        const count = list.reduce((pre, set) => {
          if (item.bk_obj_id === set.bk_obj_id) pre += 1;
          return pre;
        }, 0);
        item.count = count;
        return item;
      });
      // 去重
      const temp = [];
      list = list
        .map(item => {
          if (!temp.includes(item.name)) {
            temp.push(item.name);
            return {
              name: item.name,
              count: item.count
            };
          }
          return null;
        })
        .filter(item => item);
      const str = list.map(item => `${item.count} ${item.name}`).join('、');
      targetDes = this.$t('已选择 {n}', { n: str }) as string;
    } else {
      // 静态目标
      targetDes = this.$t('已选择 {n} 个主机', { n: cloneTarget.length }) as string;
    }
    return targetDes;
  }

  /**
   * @description: 处理兼容老的收藏数据格式
   * @param {any} data
   */
  async handleSelectFavProxy(data: any) {
    const { config } = data;
    this.updateFavCheckValue(data, undefined);
    // 事件检索收藏处理
    if (this.tabActive === 'event') return this.handleSelectEventFav(data);
    /* promql 模式 */
    if (config.promqlData) return this.handleSelectPromqlFav(config);
    if (config.localValue) return this.handleSelectFav(config, data);
    // 老数据结构兼容处理
    if (!config.queryConfigs) return console.error('Data format error');
    const promiseList = config.queryConfigs.map((item, index) => {
      const metricFieldsMap = {
        metricField: 'metric_field',
        resultTableId: 'result_table_id',
        dataSourceLabel: 'data_source_label',
        dataTypeLabel: 'dataTypeLabel'
      };
      const params = {
        page: 1,
        page_size: 1,
        conditions: Object.keys(metricFieldsMap).map(field => ({
          key: metricFieldsMap[field],
          value: item[field]
        })),
        search_value: '',
        tag: ''
      };
      return getMetricListV2(params)
        .then(res => {
          const metricData = res?.metric_list?.[0] || {};
          const alias = this.createItemName(index);
          return new DataRetrievalQueryItem({
            ...metricData,
            alias,
            enable: !item.hidden,
            agg_condition: item.where || [],
            agg_dimension: item.groupBy || [],
            agg_interval: item.interval,
            agg_method: item.method,
            functions: item.functions || []
          });
        })
        .catch(err => {
          console.log(err);
          return [];
        });
    });
    // 指标数据
    this.localValue = await Promise.all(promiseList);
    this.expandedData = this.localValue.map(item => item.key);
    // 操作栏对比数据
    const { tools } = data;
    if (tools?.timeRange && !Array.isArray(tools?.timeRange)) {
      tools.TimeRange = DEFAULT_TIME_RANGE;
    }
    data.tools && (this.compareValue.tools = data.tools);
    const compareMap: { [key in IDataRetrievalView.compareType]: Function } = {
      none: ({ type, split }: { type: IDataRetrievalView.compareType; split: boolean }) => ({ type, value: split }),
      target: ({ type }: { type: IDataRetrievalView.compareType }) => ({ type }),
      time: ({ type, timeOffset }: { type: IDataRetrievalView.compareType; timeOffset: string[] }) => ({
        type,
        value: timeOffset
      }),
      metric: ({ type }: { type: IDataRetrievalView.compareType }) => ({ type })
    };
    this.compareValue.compare = compareMap[data.compareConfig?.type]?.(data.compareConfig) || {
      type: 'none',
      value: true
    };
    // 监控目标
    this.target.value = config.target;
    this.target.targetType = config.targetType;
    this.target.desc = this.gettargetDes();
    // 刷新查询结果
    this.queryResult = [];
    this.handleQuery();
  }

  /**
   * @description: 选中收藏数据
   * @param {IDataRetrieval} data
   * @return {*}
   */
  async handleSelectFav(data: any, favData: any) {
    this.editMode = 'UI';
    this.loading = true;
    localStorage.setItem('bk_monitor_edit_mode_str', this.editMode);
    this.updateFavCheckValue(favData, undefined);
    const metricDataList = data.localValue.filter(item => item.isMetric);
    const { metric_list: metricList = [] } = await getMetricListV2({
      page: 1,
      page_size: data.localValue.length,
      conditions: [{ key: 'metric_id', value: metricDataList.map(item => item.metric_id) }]
    }).catch(err => {
      console.log(err);
      return { metric_list: [] };
    });
    const result = data.localValue.map((item, index) => {
      const alias = this.createItemName(index);
      if (item.isMetric) {
        const metricData = metricList.find(metric => metric.metric_id === item.metric_id);
        return new DataRetrievalQueryItem({
          ...(metricData || {}),
          alias,
          enable: item.enable,
          agg_condition: item.agg_condition || [],
          agg_dimension: item.agg_dimension || [],
          agg_interval: item.agg_interval,
          agg_method: item.agg_method,
          functions: item.functions,
          dimensions: item.dimensions
        });
      }
      item.alias = alias;
      return item;
    });
    this.localValue = deepClone(result as IDataRetrieval.ILocalValue[]);
    this.target = deepClone(data.target);
    const compareValue = deepClone(data.compareValue);
    if (compareValue) {
      if (!Array.isArray(compareValue.tools.timeRange)) compareValue.tools.timeRange = DEFAULT_TIME_RANGE;
    }
    this.compareValue = compareValue;

    const keys = this.localValue.map(item => item.key);
    this.expandedData.push(...keys);
    this.queryResult = [];
    this.handleQuery();
  }

  /* 选中Prmql的收藏数据 */
  handleSelectPromqlFav(data) {
    this.editMode = 'PromQL';
    localStorage.setItem('bk_monitor_edit_mode_str', this.editMode);
    this.promqlData = data.promqlData.map(item => new DataRetrievalPromqlItem(item));
    const keys = this.promqlData.map(item => item.key);
    this.promqlExpandedData = keys;
    this.handleQuery();
  }

  /**
   * @description: 点击收藏按钮 显示收藏弹窗
   * @param {Boolean} isDirectUpdate: 是否直接替换当前收藏
   */
  handleClickAddOrUpdateFav(isDirectUpdate = false) {
    this.isUpdateFavoriteConfig = true;
    if (isDirectUpdate) {
      const submitValue = {
        value: this.favCheckedValue,
        hideCallback: () => {},
        isEdit: true
      };
      this.handleSubmitFavorite(submitValue);
      return;
    }
    this.handleClickEditFav();
  }

  handleClickEditFav() {
    this.isUpdateFavoriteConfig = true;
    this.editFavoriteData = deepClone(this.favCheckedValue);
    this.getFavoriteDialogKeywords();
    this.isShowAddFavoriteDialog = true;
  }

  /** 收藏列表操作 */
  handleFavoriteOperate(operate: string, value?: any) {
    switch (operate) {
      case 'click-favorite': // 点击收藏
        this.handleSelectFavProxy(value);
        break;
      case 'add-group': // 新建分組
        createFavoriteGroup({
          bk_biz_id: this.bizId,
          type: this.favoriteSearchType,
          name: value
        }).then(() => this.getListByGroupFavorite());
        break;
      case 'reset-group-name': // 重命名
        updateFavoriteGroup(value.group_id, {
          bk_biz_id: this.bizId,
          type: this.favoriteSearchType,
          name: value.group_new_name
        }).then(() => this.getListByGroupFavorite());
        break;
      case 'move-favorite': // 移动收藏
      case 'remove-group': // 从组中移除收藏（移动至未分组）
        updateFavorite(value.id, {
          ...value,
          type: this.favoriteSearchType
        }).then(() => this.getListByGroupFavorite());
        break;
      case 'edit-favorite': // 编辑收藏
        this.editFavoriteData = value;
        this.getFavoriteDialogKeywords(value.config);
        this.isShowAddFavoriteDialog = true;
        break;
      case 'delete-favorite': // 删除收藏
        this.$bkInfo({
          subTitle: this.$t('当前收藏名为{name}是否删除?', { name: value.name }),
          type: 'warning',
          confirmFn: async () => {
            destroyFavorite(value.id, { type: this.favoriteSearchType }).then(() => this.getListByGroupFavorite());
          }
        });
        break;
      case 'dismiss-group': // 解散分组
        this.$bkInfo({
          title: this.$t('当前分组为{name}是否解散?', { name: value.name }),
          subTitle: `${this.$t('解散分组后，原分组内的收藏将移至未分组中。')}`,
          type: 'warning',
          confirmFn: async () => {
            destroyFavoriteGroup(value.id, { type: this.favoriteSearchType }).then(() => this.getListByGroupFavorite());
          }
        });
        break;
      case 'share': {
        // 分享
        const href = `${location.origin}${location.pathname}?bizId=${this.bizId}#${this.$route.path}`;
        copyText(`${href}?favorite_id=${value.id}`, msg => {
          this.$bkMessage({
            message: msg,
            theme: 'error'
          });
          return;
        });
        this.$bkMessage({
          message: this.$t('复制成功'),
          theme: 'success'
        });
        break;
      }
      case 'drag-move-end': // 移动组
        // updateGroupOrderFavoriteGroup({
        //   bk_biz_id: this.bizId,
        //   type: this.favoriteSearchType,
        //   order: value
        // }).catch(err => console.warn(err));
        break;
      case 'create-copy':
        {
          const { group_id, name, id } = value;
          const copyName = `${name} ${this.$t('副本')}`;
          if (this.favStrList.includes(copyName)) {
            this.$bkMessage({
              message: this.$t('已存在该副本'),
              theme: 'warning'
            });
            return;
          }
          this.isUpdateFavoriteConfig = false;
          this.editFavoriteData = value;
          const copyBaseParams = { group_id, name: copyName, id };
          const submitValue = {
            value: copyBaseParams,
            hideCallback: () => {},
            isEdit: false
          };
          this.handleSubmitFavorite(submitValue);
        }
        break;
      case 'request-query-history':
        this.getListByGroupFavorite();
        break;
      case 'new-search':
        this.favCheckedValue = null;
        this.favoriteSearchType === 'event' ? this.eventRetrievalRef?.handleClearQuery() : this.handleClearAll();
        break;
    }
  }

  /** 获取对比的UI模式的参数 */
  getComparedLocalParams(comparedUIParams = []) {
    return comparedUIParams.map(item =>
      item.isMetric
        ? {
            metric_id: item?.metric_id,
            agg_method: item?.agg_method,
            agg_interval: item?.agg_interval,
            agg_dimension: item?.agg_dimension,
            agg_condition: item?.agg_condition,
            functions: item?.functions
          }
        : {
            value: item?.value,
            functions: item?.functions
          }
    );
  }

  /** 获取对比的PromQL模式的参数 */
  getComparedPromQLParams(comparedQLParams = []) {
    return comparedQLParams.map(item => ({
      step: item?.step,
      code: item?.code
    }));
  }

  /** 弹窗dialog新增或编辑收藏 */
  async handleSubmitFavorite({ value, hideCallback, isEdit }) {
    const type = this.tabActive === 'event' ? 'event' : 'metric';
    const { group_id, name, id } = value;
    let config;
    // 若是当前是编辑收藏, 且非更新收藏config的情况下 不改变config
    if (this.isUpdateFavoriteConfig) {
      if (this.tabActive === 'event') {
        config = {
          queryConfig: deepClone(this.eventRetrievalRef.currentGroupByVarPramas),
          compareValue: deepClone(this.compareValue)
        };
      } else {
        if (this.editMode === 'PromQL') {
          config = {
            promqlData: this.promqlData
          };
        } else {
          config = {
            localValue: this.localValue,
            target: this.target,
            compareValue: this.compareValue
          };
        }
      }
    } else {
      config = this.editFavoriteData.config;
    }
    const data = {
      bk_biz_id: this.bizId,
      group_id,
      name,
      type,
      config
    };
    if (!isEdit) {
      // 新增收藏
      const res = await createFavorite(data);
      hideCallback();
      this.handleFavoriteHiddenAndShow(true);
      this.editFavoriteData = null;
      this.isUpdateFavoriteConfig = true;
      await this.getListByGroupFavorite();
      this.handleSelectFavProxy(res); // 更新点击的收藏
    } else {
      // 编辑或替换收藏
      updateFavorite(id, data)
        .then(res => {
          hideCallback();
          this.handleSelectFavProxy(res); // 更新点击的收藏
        })
        .finally(() => {
          this.editFavoriteData = null;
          this.isUpdateFavoriteConfig = true;
          this.getListByGroupFavorite();
        });
    }
  }

  /**
   * @desc: 当点击收藏弹窗时显示的查询语句数据
   * @param {Any} replaceData 点击非当前收藏编辑时缓存的替换config数据（不改变config）
   */
  getFavoriteDialogKeywords(replaceData?: any) {
    let currentFavoriteKeywordsData: any;
    if (!!replaceData) {
      currentFavoriteKeywordsData = replaceData;
    } else {
      if (this.tabActive === 'event') {
        currentFavoriteKeywordsData = {
          queryConfig: deepClone(this.eventRetrievalRef.currentGroupByVarPramas),
          compareValue: deepClone(this.compareValue)
        };
      } else {
        if (this.editMode === 'PromQL') {
          currentFavoriteKeywordsData = {
            promqlData: this.promqlData
          };
        } else {
          currentFavoriteKeywordsData = {
            localValue: this.localValue,
            target: this.target,
            compareValue: this.compareValue
          };
        }
      }
    }
    this.favoriteKeywordsData = currentFavoriteKeywordsData;
  }

  // 收藏 检索 展示或隐藏
  handleClickResultIcon(str: string) {
    if (str === 'favorite') this.handleFavoriteHiddenAndShow(!this.isShowFavorite);
    if (str === 'search') this.handleLeftHiddenAndShow(!this.isShowLeft);
  }

  /**
   * @description: 收藏列表隐藏
   */
  handleFavoriteHiddenAndShow(val: boolean) {
    this.isShowFavorite = val;
    if (!val) this.favCheckedValue = null;
    localStorage.setItem('bk_monitor_data_favorite_show', `${val}`);
  }

  /**
   * @description: 将promql源码转换保证与ui保持一致
   * @param {*}
   * @return {*}
   */
  async handlePromqlToQueryConfig() {
    const promiseList = this.localValue.map((item, index) => {
      if (!item.isMetric) {
        return undefined;
      }
      const metricItem = item as DataRetrievalQueryItem;
      if (metricItem.consistency || metricItem.sourceCodeError) return undefined;
      const params = {
        promql: metricItem.sourceCode,
        step: 1
      };
      // 转换promsql语法
      return promqlToQueryConfig(params)
        .then(async res => {
          const newData = await this.updateMetricDataFromPromqlRes(metricItem, res.query_configs[0]);
          this.$set(this.localValue, index, newData);
          return newData;
        })
        .catch(err => {
          console.error(err);
        });
    });
    return Promise.all(promiseList);
  }

  /**
   * @description: 控制是否自动查询
   */
  handleQueryProxy() {
    // this.updateFavCheckValue();
    if (this.autoQuery) this.handleQuery();
  }

  /**
   * @description: 查询操作
   */
  async handleQuery() {
    this.isHandleQuery = true;
    this.loading = true;
    // await this.handlePromqlToQueryConfig().catch((err) => {
    //   this.loading = false
    //   console.error(err)
    // })
    let params = this.getQueryParams();
    // 过滤无效查询
    if (!params) {
      this.loading = false;
      this.queryResult = [];
      this.isHandleQuery = false;
      return;
    }
    const queryStartTime = +new Date();
    // 如果是只展示视图，需要将 compare_config.split 设置为 true
    if (this.onlyShowView) {
      params = {
        ...params,
        compare_config: {
          ...params.compare_config,
          split: false
        }
      };
    }
    getGraphQueryConfig(params)
      .then(data => {
        this.queryTimeRange = +new Date() - queryStartTime;
        this.queryResult = data.panels;
        this.emptyStatus = 'search-empty';
      })
      .catch(() => {
        this.queryResult = [];
        this.emptyStatus = '500';
      })
      .finally(() => (this.loading = false));
    this.isHandleQuery = false;
  }

  /**
   * @description: 处理查询所需参数
   */
  getQueryParams() {
    let queryConfigs = this.getQueryConfgs();
    // PromQL 模式下是没有 queryConfigs 。
    // 如果 localStorage 中的 bk_monitor_edit_mode_str 已经缓存的是 PromQL 就该手动的切换为 UI 模式。
    if (!queryConfigs.length) {
      // 原先是通过简单的判断 queryConfigs 数组是否存在来控制是否继续执行下面代码。现通过多加一层判断以适配上述问题。
      if (this.editMode === 'PromQL') {
        // 由于切换了 editMode 还需要重新 getQueryConfgs 一次。保证以通过 PromQL 模式进入页面的流程一致。
        queryConfigs = this.getQueryConfgs();
        if (!queryConfigs.length) return null;
      } else {
        return null;
      }
    }
    // const timeRange = handleTimeRange(this.compareValue.tools.timeRange);
    const [startTime, endTime] = handleTransformToTimestamp(this.compareValue.tools.timeRange);
    const expressions: Record<string, string> = this.getExpressions();
    const params = {
      query_configs: queryConfigs, // 查询项
      expressions, // 表达式
      functions: this.getFunctions(expressions), // 表达式的函数
      compare_config: this.getCompare(), // 操作栏对比配置
      target: this.getTargets(), // 监控目标
      start_time: startTime, // 起始时间
      end_time: endTime // 终止时间
    };
    return params;
  }

  /**
   * @description: 获取查询项参数
   * @param {*} allowNullWhere 允许返回空值的where
   * @param {DataRetrievalQueryItem} item 返回单条query_configs
   * @return {*}
   */
  getQueryConfgs(allowNullWhere = false, item: DataRetrievalQueryItem = null): IDataRetrieval.queryConfigsParams[] {
    /** 隐藏指标不影响表达式的查询 */
    if (this.editMode === 'UI') {
      const expressionList = this.localValue.reduce((total, cur) => {
        if (!cur.isMetric && cur.enable) total.push((cur as IDataRetrieval.IExpressionItem).value);
        return total;
      }, []);
      const tempList = item
        ? [item]
        : (this.localValue.filter(
            (item: DataRetrievalQueryItem) => item.isMetric && !item.isNullMetric && !item.sourceCodeError
          ) as DataRetrievalQueryItem[]);
      const queryList = tempList.map(item => {
        if (item.enable || expressionList.some(set => set.indexOf(item.alias) > -1)) {
          const {
            alias,
            agg_method: method,
            metric_field: metric,
            agg_interval: interval,
            result_table_id: table,
            data_type_label: dataTypeLabel,
            data_source_label: dataSourceLabel,
            agg_condition: where,
            agg_dimension: groupBy,
            functions,
            index_set_id: indexSetId,
            data_label
          } = item;
          const queryConfigItem: IDataRetrieval.queryConfigsParams = {
            metric,
            method,
            alias,
            interval,
            table,
            data_source_label: dataSourceLabel,
            data_type_label: dataTypeLabel,
            group_by: groupBy,
            where: (allowNullWhere ? where : where.filter(item => item.value.length)).filter(item => item.key),
            functions
          };
          indexSetId && (queryConfigItem.index_set_id = indexSetId);
          data_label && (queryConfigItem.data_label = data_label);
          return queryConfigItem;
        }
        return null;
      });
      return queryList.filter(item => !!item);
    }
    if (this.editMode === 'PromQL') {
      const promqlQuery = [];
      this.promqlData.forEach(promqlItem => {
        if (!!promqlItem.code && promqlItem.enable) {
          promqlQuery.push({
            data_source_label: 'prometheus',
            data_type_label: 'time_series',
            promql: promqlItem.code,
            interval: promqlItem.step || 'auto',
            alias: promqlItem.alias
          });
        }
      });
      return promqlQuery;
    }
  }

  /**
   * @description: 更新查询项表达式的别名数据
   */
  handleUpdateAlias() {
    this.localValue.forEach((item, index) => {
      item.alias = this.createItemName(index);
    });
  }

  /**
   * @description: 处理表达式参数
   */
  getExpressions(): Record<string, string> {
    const tempList = this.localValue.filter(item => !item.isMetric) as IDataRetrieval.IExpressionItem[];
    const resObj: Record<string, string> = {};
    tempList.forEach(item => {
      if (item.enable && item.value.trim()) resObj[item.alias] = item.value?.toLocaleLowerCase?.();
    });
    return resObj;
  }

  /**
   * 处理表达式的函数选项
   * @param expressions 表达式
   */
  getFunctions(expressions: Record<string, string>) {
    const tempList = this.localValue.filter(item => !item.isMetric) as IDataRetrieval.IExpressionItem[];
    return tempList.reduce((total, item) => {
      if (item.enable && item.value.trim() && expressions[item.alias]) {
        total[item.alias] = item.functions;
      }
      return total;
    }, {});
  }

  /**
   * @description: 获取监控目标参数
   */
  getTargets() {
    const targetFieldMap: { [key in IDataRetrieval.TargetType]: string } = {
      INSTANCE: 'ip',
      TOPO: 'host_topo_node',
      SERVICE_TEMPLATE: 'host_template_node',
      SET_TEMPLATE: 'host_template_node'
    };
    const value =
      this.target.targetType === 'INSTANCE'
        ? this.target.value.map((item: any) => ({
            ip: item.ip,
            bk_cloud_id: item.bk_cloud_id,
            bk_host_id: item.bk_host_id,
            bk_supplier_id: item.bk_supplier_id
          }))
        : this.target.value.map((item: any) => ({
            bk_inst_id: item.bk_inst_id,
            bk_obj_id: item.bk_obj_id
          }));
    // 监控目标格式转换
    const targets = [
      [
        {
          field: targetFieldMap[this.target.targetType],
          method: 'eq',
          value
        }
      ]
    ];
    if (this.editMode === 'PromQL') {
      return [];
    }
    return targets;
  }

  /**
   * @description: 获取对比参数
   */
  getCompare() {
    type type = IDataRetrievalView.compareType;
    const compareMap: { [key in type]: Function } = {
      none: ({ type, value }: { type: type; value: boolean }) => ({ type, split: value }),
      target: ({ type }: { type: type }) => ({ type }),
      time: ({ type, value }: { type: type; value: string[] }) => ({ type, time_offset: value }),
      metric: ({ type }: { type: type }) => ({ type })
    };
    const { compare } = this.compareValue;
    compareMap[compare.type]?.(compare);
    if (this.editMode === 'PromQL') {
      const { type, value } = this.compareValue.compare;
      return { type: 'none', split: type === 'none' ? value : true };
    }
    return compareMap[compare.type]?.(compare) || { type: 'none', split: true };
  }

  /**
   * @description: 切换自动查询开关
   * @param {boolean} val
   */
  handleAutoQueryChange(val?: boolean) {
    this.autoQuery = !!val;
    this.handleIseeCache();
    localStorage.setItem('bk_monitor_auto_query_enable', `${this.autoQuery}`);
  }
  handleAutoQueryOfEventChange(val?: boolean) {
    this.autoQuery = !!val;
    localStorage.setItem('bk_monitor_auto_query_enable', `${this.autoQuery}`);
  }

  /**
   * @description: 处理跳转到事件检索的路由数据
   * @param {*} targetsList 事件检索的数据
   * @param {*} type tab的选中状态
   */
  handleRouteQueryDataOfEvent(targetsList, type) {
    this.tabActive = type;
    const [
      {
        data: {
          query_configs: [
            {
              data_type_label,
              data_source_label,
              result_table_id,
              where,
              query_string: queryString,
              group_by: groupBy,
              method,
              metric_field,
              filter_dict: filterDict
            }
          ]
        }
      }
    ] = targetsList;
    this.eventQueryConfig = {
      data_type_label,
      data_source_label,
      result_table_id,
      where: where || [],
      query_string: queryString || '',
      group_by: groupBy || [],
      filter_dict: filterDict || {},
      method,
      metric_field
    };
  }

  /**
   * @description: 处理grafana跳转参数
   * @param {any} targets 路由targets参数
   * @return {*}
   */
  async handleRouteQueryData(
    targets: any,
    fromRouteName: IDataRetrieval.fromRouteNameType = 'grafana',
    from?: string,
    to?: string
  ) {
    const promqlData = this.getRoutePromqlData(targets);
    if (promqlData.length) {
      this.handleRoutePromqlData(promqlData, from, to);
      this.handleQuery();
      return;
    }
    // 如果 URL 中 targets 含有 mode 且为 ui ，或不含 mode 时默认为 ui 模式
    if (['ui'].includes(targets?.[0]?.data?.mode || 'ui')) {
      this.editMode = 'UI';
      localStorage.setItem('bk_monitor_edit_mode_str', this.editMode);
      this.localValue = [];
      const localValue = [];
      this.compareValue.tools.timeRange = from && to ? [from, to] : DEFAULT_TIME_RANGE;
      const promiseListAll = targets.map(item => {
        const promiseList = item.data.query_configs.map(
          query =>
            new Promise(resolve => {
              let metricFields = [
                'metric_field',
                'result_table_id',
                'data_source_label',
                'data_type_label',
                'data_label'
              ];
              /** 是否带有原始指标 */
              const hasOriginMetricData = !!query.originMetricData?.metricField;
              if (fromRouteName === 'performance-detail' && !hasOriginMetricData) {
                metricFields = ['metrics[0].field', 'table', 'data_source_label', 'data_type_label', 'data_label'];
              }
              /** 带有原指标信息的数据 */
              const metricFieldsValIds = ['metricField', 'resultTableId', 'dataSourceLabel', 'dataTypeLabel'];
              getMetricListV2({
                bk_biz_id: this.bizId,
                page: 1,
                page_size: 1,
                conditions: metricFields.map((field, index) => {
                  const res = {
                    key: field,
                    value: hasOriginMetricData ? query.originMetricData[metricFieldsValIds[index]] : query[field]
                  };
                  if (field === 'metrics[0].field') {
                    res.key = 'metric_field';
                    res.value = query.metrics[0].field;
                  }
                  if (field === 'table') {
                    res.key = 'result_table_id';
                  }
                  return res;
                }),
                search_value: '',
                tag: ''
              })
                .then(res => resolve(res))
                .catch(err => {
                  console.log(err);
                  resolve(null);
                });
            })
        );
        return Promise.all(promiseList);
      });
      const queryResultList = (await Promise.all(promiseListAll)) as any;
      /** 是否为多指标 */
      const isMultipleMetric = queryResultList.flat(1).length > 1;
      queryResultList.forEach((item, index) => {
        let { expression = '' } = targets[index].data;
        const { expressionList = [], functions = [] } = targets[index].data;
        item.forEach((metricRes, i) => {
          const metricData = metricRes?.metric_list?.[0] || {};
          const aliasIndex = localValue.length;
          const curQuery = targets[index].data.query_configs[i];
          let totalWhere = curQuery.where;
          const filterKeys = Object.keys(curQuery.filter_dict || {});
          if (filterKeys.length) {
            const where = [];
            filterKeys.forEach(key => {
              const filterVal = curQuery.filter_dict[key];
              if (key === 'variables' && !!filterVal) {
                where.push(
                  ...Object.entries(filterVal).map(item => {
                    const [key, value] = item;
                    return {
                      key,
                      condition: 'and',
                      method: 'eq',
                      value: Array.isArray(value) ? value : [value]
                    };
                  })
                );
              } else if (key === 'targets' && !!filterVal) {
                /** 目标主机、主机对比数据将添加到where */
                const firstItem = filterVal?.[0];
                if (!!firstItem) {
                  const res = Object.entries(firstItem).map(item => {
                    const [key] = item;
                    return {
                      key,
                      condition: 'and',
                      method: 'eq',
                      value: filterVal.reduce((total, obj) => {
                        const val = `${obj[key]}`;
                        !total.includes(val) && total.push(val);
                        return total;
                      }, [])
                    };
                  });
                  where.push(...res);
                }
              } else if (key !== 'bk_biz_id') {
                where.push({
                  key,
                  condition: 'and',
                  method: 'eq',
                  value: Array.isArray(filterVal) ? filterVal : [filterVal]
                });
              }
            });
            totalWhere = totalWhere.concat(where);
          }
          let { method } = curQuery;
          method = curQuery?.metrics?.find(set => set.method)?.method || method || 'AVG';
          // 添加查询项
          localValue.push(
            new DataRetrievalQueryItem({
              ...metricData,
              agg_condition: (totalWhere?.filter(item => item.key !== 'bk_biz_id') || []).map(set => ({
                ...set,
                dimensionName: (() => {
                  const temp = set?.dimensionName || set?.dimension_name;
                  if (temp) {
                    return temp;
                  }
                  const dimensions = JSON.parse(JSON.stringify(metricData?.dimensions || []));
                  const dimensionName = dimensions.find(d => d.id === set.key)?.name;
                  return dimensionName || set.key;
                })()
              })),
              agg_dimension: curQuery.group_by || [],
              agg_interval: this.handleInterval(curQuery.interval, curQuery.interval_unit?.toLocaleLowerCase?.()),
              agg_method: method,
              functions: curQuery.functions,
              enable: curQuery.display,
              filter_dict: curQuery.filter_dict
            })
          );
          // 更新表达值的别名信息
          !!curQuery.refId && (expression = expression.replace(curQuery.refId, this.createItemName(aliasIndex)));
        });
        /** 去除单指标时重复的表达式a查询 */
        if (expression) {
          // display为grafana的隐藏展示参数 如果为单指标跳转不展示表达式的图
          const enable = isMultipleMetric ? targets[index].data.display ?? true : false;
          const expItem: IDataRetrieval.IExpressionItem = {
            alias: '',
            enable,
            isMetric: false,
            key: random(8),
            value: expression.toLocaleLowerCase?.(),
            functions
          };
          // 添加表达式
          localValue.push(expItem);
        }
        /** 多表达式带有functions */
        if (!!expressionList.length) {
          expressionList.forEach(exp => {
            const expItem: IDataRetrieval.IExpressionItem = {
              alias: '',
              enable: exp.active,
              isMetric: false,
              key: random(8),
              value: exp.expression,
              functions: exp.functions
            };
            // 添加表达式
            localValue.push(expItem);
          });
        }
      });
      this.localValue = this.handleFilterExpression(localValue);
      this.handleDefaultCompareValue();
      this.handleUpdateAlias();
      this.target.value = [];
      this.handleQuery();
      this.expandedData.push(...this.localValue.map(item => item.key));
    }
  }

  getRoutePromqlData(targets: any) {
    const promqlData = [];
    if (['code', 'source'].includes(targets?.[0]?.data?.mode)) {
      targets.forEach(t => {
        const temp = {
          code: t.data.source,
          alias: t.data.promqlAlias,
          step: t.data.step
        };
        promqlData.push(new DataRetrievalPromqlItem(temp as any));
      });
      return promqlData;
    }
    if (targets?.[0]?.data?.query_configs?.[0]?.data_source_label === 'prometheus') {
      targets[0].data.query_configs.forEach(q => {
        const temp = {
          code: q.promql,
          step: q.interval || q.agg_interval || 'auto'
        };
        promqlData.push(new DataRetrievalPromqlItem(temp as any));
      });
      return promqlData;
    }
    return promqlData;
  }
  handleRoutePromqlData(promqlData: any[], from?: string, to?: string) {
    const result = [];
    const resultKey = [];
    promqlData.forEach(item => {
      const tempItem = deepClone(item);
      tempItem.key = random(8);
      tempItem.alias = item.alias || this.getCurItemAlias(result as any);
      result.push(tempItem);
      resultKey.push(tempItem.key);
    });
    this.editMode = 'PromQL';
    localStorage.setItem('bk_monitor_edit_mode_str', this.editMode);
    this.compareValue.tools.timeRange = from && to ? [from, to] : DEFAULT_TIME_RANGE;
    this.promqlData = result;
    this.promqlExpandedData = resultKey;
  }

  /**
   * 过滤表达式
   * @param localValue
   */
  handleFilterExpression(localValue: IDataRetrieval.ILocalValue[]): IDataRetrieval.ILocalValue[] {
    return localValue.filter(item => {
      if (!item.isMetric) {
        const val = (item as IDataRetrieval.IExpressionItem).value;
        /** 清除一个字母的无效表达式 */
        return val.length > 1;
      }
      return true;
    });
  }

  /**
   * 转换周期为秒
   * @param interval 周期
   * @param unit 单位
   * @returns number 单位：秒 | auto
   */
  handleInterval(interval: string | number, unit: 's' | 'm' | 'h' = 's'): number | 'auto' {
    if (interval === 'auto') return interval;
    const intervalUnitMap: IDataRetrieval.IntervalUnitMap = {
      s: 1,
      m: 30,
      h: 3600,
      d: 86400,
      M: 2592000,
      y: 31104000
    };
    if (typeof interval === 'number') {
      return interval * intervalUnitMap[unit];
    }
    if (typeof interval === 'string') {
      const [, v, unit] = interval.toString().match(/(\d+)([s|h|w|m|d|M|y])$/);
      return +v * intervalUnitMap[unit];
    }
    return interval;
  }

  /**
   * @description: 对比数据恢复默认
   */
  handleDefaultCompareValue() {
    this.compareValue = {
      compare: {
        type: 'none',
        value: true
      },
      tools: {
        ...this.compareValue.tools,
        refleshInterval: -1
      }
    };
  }

  /**
   * @description: 操作按钮提示
   * @param {IDataRetrieval} opt
   * @param {IDataRetrieval} item
   * @return {string}
   */
  handleTitleTips(opt: IDataRetrieval.IOption, item: IDataRetrieval.ILocalValue): string {
    const metricItem = item as DataRetrievalQueryItem;
    const tipsMap: { [key in IDataRetrieval.IOption]: string } = {
      copy: `${this.$t('拷贝')}`,
      delete: `${this.$t('删除')}`,
      enable: `${this.$t(item.enable ? '隐藏' : '展示')}`,
      source: `${metricItem.showSource ? 'UI' : this.$t('源码')}`
    };
    return tipsMap[opt] || '';
  }

  /**
   * @description: 设置隐藏提示标记
   */
  handleIseeCache(val = false) {
    val && (this.isShowTips = false);
    localStorage.setItem('bk_monitor_data_retrieval_show_tips', 'false');
    // this.autoQueryPopoverRef?.hideHandler();
  }

  /**
   * @description: 更新收藏高亮提示数据
   */
  updateFavCheckValue(data?: any, type: 'time_series' | 'event' = 'time_series') {
    let config: any = {
      localValue: this.localValue,
      target: this.target,
      compareValue: this.compareValue
    };
    if (this.editMode === 'PromQL') {
      config = {
        promqlData: this.promqlData
      };
    }
    if (type === 'event') {
      config = {
        queryConfig: deepClone(this.eventRetrievalRef.currentGroupByVarPramas),
        compareValue: this.compareValue
      };
    }
    this.favCheckedValue = data || config;
  }

  /**
   * @description: 拖拽开始
   * @param {DragEvent} evt
   * @param {number} index
   */
  handleDragStart(evt: DragEvent, index: number) {
    this.dragData.from = index;
    evt.dataTransfer.effectAllowed = 'move';
  }
  /**
   * @description: 拖拽结束
   */
  handleDragend() {
    // 动画结束后关闭拖拽动画效果
    setTimeout(() => {
      this.dragData.from = null;
      this.dragData.to = null;
    }, 500);
  }
  /**
   * @description: 拖拽放入
   */
  handleDrop() {
    const { from, to } = this.dragData;
    if (from === to) return;
    const temp = this.localValue[from];
    this.localValue.splice(from, 1);
    this.localValue.splice(to, 0, temp);
  }
  /**
   * @description: 拖拽进入
   * @param {number} index
   */
  handleDragEnter(index: number) {
    this.dragData.to = index;
  }
  /**
   * @description: 拖拽经过
   * @param {DragEvent} evt
   */
  handleDragOver(evt: DragEvent) {
    evt.preventDefault();
  }

  /**
   * @description: 添加策略
   */
  handleAddStrategy() {
    let queryData = null;
    if (this.editMode === 'PromQL') {
      queryData = {
        mode: 'code',
        data: this.promqlData.map(item => ({
          promql: item.code,
          step: item.step
        }))
      };
    } else {
      const metricList = this.localValue.filter(item => item.isMetric) as DataRetrievalQueryItem[];
      const epxList = this.localValue.filter(item => !item.isMetric) as IDataRetrieval.IExpressionItem[];
      const queryConfigs = metricList.map(item => ({
        data_source_label: item.data_source_label,
        data_type_label: item.data_type_label,
        filter_dict: {},
        functions: item.functions,
        group_by: item.agg_dimension,
        index_set_id: item.index_set_id,
        interval: item.agg_interval,
        table: item.result_table_id,
        item: item.time_field,
        where: item.agg_condition,
        metrics: [{ alias: item.alias, field: item.metric_field, method: item.agg_method }]
      }));
      queryData = {
        expression: epxList?.[0]?.value?.toLocaleLowerCase?.(),
        query_configs: queryConfigs
      };
    }
    window.open(
      `${location.href.replace(location.hash, '#/strategy-config/add')}?data=${encodeURIComponent(
        JSON.stringify(queryData)
      )}`
    );
  }

  /**
   * @description: 源码值更新
   * @param {DataRetrievalQueryItem} item
   * @param {string} value
   * @return {*}
   */
  handlePromsqlChange(item: DataRetrievalQueryItem, value: string) {
    item.sourceCode = value;
    item.consistency = false;
  }
  /**
   * @description: promsql语法转query_configs配置
   * @param {DataRetrievalQueryItem} item
   * @param {number} index
   * @return {*}
   */
  async handlePromqlQuery(item: DataRetrievalQueryItem, index: number): Promise<boolean | undefined> {
    const params = {
      promql: item.sourceCode,
      step: 1
    };
    // 转换promsql语法
    const res = await promqlToQueryConfig(params).catch(err => {
      item.sourceCodeError = true;
      console.error(err);
    });
    res && (item.consistency = true);
    const isMutiple = res?.query_configs?.length > 1;
    if (isMutiple || !res) {
      isMutiple &&
        this.$bkMessage({
          theme: 'warning',
          message: this.$t('输入单个指标')
        });
      return;
    }
    const newData = await this.updateMetricDataFromPromqlRes(item, res.query_configs[0]);
    if (item.switchToUI) {
      newData.showSource = false;
      item.switchToUI = false;
    }
    this.$set(this.localValue, index, newData);
    this.handleQueryProxy();
    return true;
  }

  /**
   * @description: promql接口数据更新一条ui的配置数据
   * @param {DataRetrievalQueryItem} item
   * @param {any} result
   */
  async updateMetricDataFromPromqlRes(item: DataRetrievalQueryItem, result: any) {
    // 获取指标信息
    const { metric_list: metricList = [] } = await getMetricListV2({
      page: 1,
      page_size: 1,
      conditions: [{ key: 'metric_id', value: [result.metric_id] }]
    }).catch(err => {
      console.error(err);
    });
    const {
      agg_method,
      agg_condition,
      agg_dimension,
      agg_interval,
      functions,
      data_source_label,
      result_table_id,
      metric_field
    } = result;
    const resultTableIdList = result_table_id.split('.');
    const metircData = metricList[0] || {
      result_table_label_name: data_source_label,
      related_name: resultTableIdList[0],
      result_table_name: resultTableIdList[1],
      metric_field_name: metric_field
    };
    // 实例化一条指标
    const newData = new DataRetrievalQueryItem({
      ...metircData,
      sourceCodeIsNullMetric: !metricList[0],
      sourceCodeCache: item.sourceCode || '',
      key: item.key || random(8),
      enable: item.enable === undefined ? true : !!item.enable,
      sourceCode: item.sourceCode || '',
      showSource: item.showSource === undefined ? false : !!item.showSource,
      agg_method,
      agg_condition,
      agg_dimension,
      agg_interval,
      alias: item.alias || 'a',
      functions: functions || []
    });
    return newData;
  }

  /**
   * @description: promsql语法转query_configs配置
   * @param {DataRetrievalQueryItem} item
   * @param {number} index
   * @param {*} type
   */
  handlePromqlQueryProxy(
    item: DataRetrievalQueryItem,
    index: number,
    type: IDataRetrieval.promEventType
  ): Promise<boolean | undefined> {
    if (
      (item.sourceCodeCache === item.sourceCode && type === 'blur') ||
      !item.sourceCode ||
      this.isHandleQuery ||
      item.switchToUI
    )
      return;
    item.loading = true;
    return this.handlePromqlQuery(item, index).finally(() => {
      this.$nextTick(() => (item.loading = false));
    });
  }

  /**
   * @description: 处理promql的报错信息
   * @param {boolean} hasError
   * @param {IDataRetrieval} type
   * @param {DataRetrievalQueryItem} item
   * @param {number} index
   */
  handlePromqlError(
    hasError: boolean,
    type: IDataRetrieval.promEventType,
    item: DataRetrievalQueryItem,
    index: number
  ) {
    item.sourceCodeError = hasError;
    if (!this.autoQuery && type === 'blur') return;
    !hasError && this.handlePromqlQueryProxy(item, index, type);
  }

  /**
   * @description: query_configs语法转promsql语法
   * @param {DataRetrievalQueryItem} item
   */
  async handleQeueryConfigsToPromsql(item: DataRetrievalQueryItem): Promise<boolean | undefined> {
    if (item.sourceCodeIsNullMetric) return true;
    const queryConfigs = this.getQueryConfgs(undefined, item);
    if (!queryConfigs[0].metric) return true;
    item.loading = true;
    const params = {
      query_config_format: 'graph',
      expression: queryConfigs[0].alias || 'a',
      query_configs: queryConfigs
    };
    const res = await queryConfigToPromql(params)
      .catch(err => {
        console.error(err);
      })
      .finally(() => {
        setTimeout(() => {
          item.loading = false;
        }, 0);
      });
    if (!res) return;
    item.consistency = true;
    item.sourceCode = res.promql;
    item.sourceCodeCache = res.promql;
    return true;
  }

  /**
   * @description: promql编辑器聚焦
   * @param {DataRetrievalQueryItem} item
   */
  handlePromqlFocus(item: DataRetrievalQueryItem) {
    item.sourceCodeError = false;
  }

  /** 事件检索 */

  /**
   * @description: 事件检索查询 图表和表格
   * eventMetricParams 变更触发图表和table的数据刷新
   */
  handleEventQuery(params?: IFilterCondition.VarParams) {
    // 事件检索初始化时会检索一次 判断当前是否有数据ID 有则检索次数+1
    this.eventMetricParams = {
      method: 'SUM',
      ...(params || deepClone(this.eventRetrievalRef.currentGroupByVarPramas))
    };
  }

  /**
   * @description: 事件检索的过滤条件更新
   */
  eventWhereChange(list: IFilterCondition.localValue[]) {
    this.eventWhere = list;
  }

  /**
   * @description: 事件检索选中收藏
   * @param {any} data 收藏的配置
   */
  handleSelectEventFav(data: any) {
    this.updateFavCheckValue(data, 'event');
    this.eventQueryConfig = deepClone(data.config.queryConfig) as IFilterCondition.VarParams;
    // data.config.compareValue && (this.compareValue = deepClone(data.config.compareValue));
    if (data.config.compareValue) {
      const compareValue = deepClone(data.config.compareValue);
      if (!Array.isArray(compareValue.tools.timeRange)) compareValue.tools.timeRange = DEFAULT_TIME_RANGE;
      this.compareValue = compareValue;
    }
  }

  /**
   * @description: 事件检索汇聚周期
   * @param {*} interval
   */
  handleEventIntervalChange(interval: EventRetrievalViewType.intervalType) {
    this.eventInterval = interval;
  }

  /**
   * @description: 时间范围变更
   * @param {EventRetrievalViewType} timeRange
   */
  handleTimeRangeChange(timeRange: EventRetrievalViewType.IEvent['onTimeRangeChange']) {
    timeRange && (this.eventChartTimeRange = timeRange);
    if (!!timeRange) {
      const targetTime = timestampTransformStr(timeRange);
      this.eventSelectTimeRange = targetTime;
    }
  }
  /**
   * @description: 更新图表标题
   * @param {string} title
   */
  eventChartTitleChange(title: string) {
    this.eventChartTitle = title;
  }

  /**
   * @description: 事件查询添加策略
   * @param {IFilterCondition} queryConfig
   */
  handleAddEventStrategy(queryConfig: IFilterCondition.VarParams) {
    const { data_source_label, data_type_label, result_table_id, where, metric_field_cache } = queryConfig;
    const queryConfigs = [
      {
        data_source_label,
        data_type_label,
        filter_dict: {},
        functions: [],
        group_by: [],
        index_set_id: '',
        interval: this.eventInterval === 'auto' ? 60 : this.eventInterval,
        table: result_table_id,
        item: '',
        where,
        metrics: [{ alias: 'a', field: metric_field_cache, method: 'COUNT' }]
      }
    ];
    const queryData = {
      expression: 'a',
      query_configs: queryConfigs
    };
    window.open(
      `${location.href.replace(location.hash, '#/strategy-config/add')}?data=${encodeURIComponent(
        JSON.stringify(queryData)
      )}`
    );
  }
  // 切换业务
  handleChangeBizId(v: number) {
    window.cc_biz_id = v;
    window.bk_biz_id = v;
    window.space_uid = this.$store.getters.bizIdList.find(item => item.bk_biz_id === +v)?.space_uid;
    this.$store.commit('app/SET_BIZ_ID', v);
    const { navId } = this.$route.meta;
    // 所有页面的子路由在切换业务的时候都统一返回到父级页面
    if (navId !== this.$route.name) {
      const parentRoute = this.$router.options.routes.find(item => item.name === navId);
      if (parentRoute) {
        location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${parentRoute.path}`;
      } else {
        this.handleReload();
      }
    } else {
      this.handleReload();
    }
  }
  // 刷新页面
  handleReload() {
    const { needClearQuery } = this.$route.meta;
    // 清空query查询条件
    if (needClearQuery) {
      location.href = `${location.origin}${location.pathname}?bizId=${window.cc_biz_id}#${this.$route.path}`;
    } else {
      location.search = `?bizId=${window.cc_biz_id}`;
    }
  }
  handleExpandAll() {
    this.isExpandAll = !this.isExpandAll;
    if (this.editMode === 'UI') {
      this.expandedData = !this.isExpandAll ? [] : this.localValue.map(item => item.key);
    }
    if (this.editMode === 'PromQL') {
      this.promqlExpandedData = !this.isExpandAll ? [] : this.promqlData.map(item => item.key);
    }
  }

  // 点击 PromQL 和 UI 模式的切换按钮。
  async handleEditModeChange() {
    if (!this.canToPromql) {
      return;
    }
    /* ui 模式 与 promql 模式转换 */
    if (this.editMode === 'UI') {
      let isErr = false;
      let errMsg = '';
      const promqlData = [];
      const promiseList = [];
      const localValueFilter = this.localValue.filter((item: DataRetrievalQueryItem) => !!item.metric_id);
      localValueFilter.forEach((item: DataRetrievalQueryItem) => {
        const promiseItem = new Promise((resolve, reject) => {
          const queryConfigs = this.getQueryConfgs(undefined, item);
          const params = {
            query_config_format: 'graph',
            expression: queryConfigs[0].alias || 'a',
            query_configs: queryConfigs
          };
          queryConfigToPromql('', params, { needMessage: false })
            .then(res => {
              resolve(res.promql);
            })
            .catch(err => {
              isErr = true;
              errMsg = err.data.message || '';
              const localValueItem = this.localValue.find(l => l.key === item.key);
              localValueItem.errMsg = errMsg;
              reject(null);
            });
        });
        promiseList.push(promiseItem);
      });
      const dataList = await Promise.all(promiseList);
      /* 报错不提供转换 */
      if (isErr) return;
      dataList.forEach((sql, index) => {
        promqlData.push(
          new DataRetrievalPromqlItem({
            alias: this.createItemName(index),
            code: sql
          } as any)
        );
      });
      if (promqlData.length) {
        this.promqlData = promqlData;
        this.promqlExpandedData = promqlData.map(item => item.key);
      }
    } else if (this.editMode === 'PromQL') {
      let isErr = false;
      let errMsg = '';
      const metricQueryData = [];
      const promiseList = [];
      const promqlDataFilter = this.promqlData.filter(item => !!item.code);
      promqlDataFilter.forEach((item: DataRetrievalPromqlItem) => {
        const promiseItem = new Promise((resolve, reject) => {
          const params = {
            promql: item.code,
            step: item.step
          };
          promqlToQueryConfig('', params, { needMessage: false })
            .then(async res => {
              const newData = await this.updateMetricDataFromPromqlRes({} as any, res.query_configs[0]);
              const queryItem = new DataRetrievalQueryItem(newData);
              queryItem.alias = this.getCurItemAlias(metricQueryData);
              queryItem.enable = true;
              metricQueryData.push(queryItem);
              resolve(queryItem);
            })
            .catch(err => {
              isErr = true;
              errMsg = err.data.message || '';
              const promqlItem = this.promqlData.find(p => p.key === item.key);
              promqlItem.errMsg = errMsg;
              reject(err);
            });
        });
        promiseList.push(promiseItem);
      });
      await Promise.all(promiseList);
      if (isErr) return;
      if (metricQueryData.length) {
        this.localValue = metricQueryData;
        this.expandedData = this.localValue.map(item => item.key);
      }
    }
    this.editMode = this.editMode === 'PromQL' ? 'UI' : 'PromQL';
    localStorage.setItem('bk_monitor_edit_mode_str', this.editMode);
    this.handleQueryProxy();
  }

  handleSourceStepChange(value: string | number, index: number) {
    this.promqlData[index].step = value as any;
  }

  /* 输入promql code */
  handlePromqlDataCodeChange(value: string, index: number) {
    this.promqlData[index].code = value;
  }
  /* promql code 失焦 */
  handlePromqlDataBlur() {
    if (this.isNeedQueryOfAuto()) this.handleQueryProxy();
  }
  handlePromqlDataFocus(index: number) {
    this.promqlData[index].errMsg = '';
  }
  // /* todo */
  // handlePromqDataItemlError(hasError: boolean, index: number) {
  //   this.promqlData[index].sourceCodeError = hasError;
  // }
  /* step 失焦 */
  handleSourceStepBlur() {
    if (this.isNeedQueryOfAuto()) this.handleQueryProxy();
  }
  /* promql 模式下自动查询 判断 */
  isNeedQueryOfAuto() {
    const oldData = JSON.stringify(this.promqlDataCache.map(item => ({ ...item, key: '' })));
    const curData = JSON.stringify(this.promqlData.map(item => ({ ...item, key: '' })));
    this.promqlDataCache = deepClone(this.promqlData);
    return oldData !== curData;
  }
  handleMetricSelectShow(v: boolean) {
    this.metricSelectorShow = v;
  }
  handleSelectMetric(value) {
    const copyStr = value.promql_metric;
    copyText(copyStr, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  handlePromqlDataEnter() {
    if (this.isNeedQueryOfAuto()) this.handleQueryProxy();
  }

  handleGuideDone() {
    this.needUseCollectGuide = false;
  }

  handleEmptyStatusChange(val: EmptyStatusType) {
    this.emptyStatus = val;
  }

  // 检查 URL 查询语句中 控制是否显示 收藏 和 检索 侧边栏的按钮
  handleSetNeedRetrievalMenu() {
    this.onlyShowView = !!getUrlParam('onlyShowView');
    // 如果不显示 收藏 和 检索的侧边栏 按钮，都不显示它们对应的侧边栏。
    if (this.onlyShowView) {
      this.handleLeftHiddenAndShow(false);
      this.handleFavoriteHiddenAndShow(false);
    }
  }

  render() {
    // 查询项/表达式头部区域
    const titleSlot = (item: IDataRetrieval.ILocalValue, index: number) => (
      <div class='collapse-item-title'>
        <span class='title-left'>
          <i class={['bk-icon', 'icon-play-shape', { acitve: this.expandedData.includes(item.key) }]}></i>
          <span class='title-name'>{item.alias}</span>
          <span class='title-desc'>{item.isMetric ? this.$t('（查询项）') : this.$t('（表达式）')}</span>
        </span>
        <span class='title-center' />
        <span class='title-right'>
          {this.itemOptions(item).map(opt => {
            const metricItem = item as DataRetrievalQueryItem;
            const iconName =
              opt !== 'enable'
                ? this.optionIconName[opt]
                : item.enable
                  ? this.optionIconName[opt]
                  : 'icon-mc-invisible';
            const sourceAcitve = opt === 'source' && metricItem.showSource ? 'is-source' : '';
            /** 不支持多指标的不支持源码编辑 */
            const display =
              opt === 'source' && !metricItem.canSetMulitpeMetric && !metricItem.isNullMetric ? 'none' : 'initial';
            return (
              <i
                key={opt}
                v-bk-tooltips_top={this.handleTitleTips(opt, item)}
                class={['icon-monitor', iconName, sourceAcitve, display]}
                onClick={evt => evt.stopPropagation()}
                onMousedown={evt => this.handleOptionProxy(evt, opt, item, index)}
              />
            );
          })}
        </span>
      </div>
    );
    // 查询项/表达式内容区域
    const contentSlot = (item: IDataRetrieval.ILocalValue, index: number) => {
      const metricItem = item as DataRetrievalQueryItem;
      const expItem = item as IDataRetrieval.IExpressionItem;
      return (
        <div class={['collapse-item-content', { 'is-metric': item.isMetric }]}>
          {
            // eslint-disable-next-line no-nested-ternary
            item.isMetric ? (
              // 查询项配置
              metricItem.showSource ? (
                // 源码模式编辑
                <div class='source-mode-wrap'>
                  <div class={['source-mode', { 'is-error': metricItem.sourceCodeError }]}>
                    {metricItem.loading ? undefined : (
                      <PromqlEditor
                        ref={`promql-editor-${index}`}
                        class='promql-editor'
                        value={metricItem.sourceCode}
                        executeQuery={(hasError: boolean) =>
                          this.handlePromqlError(hasError, 'enter', metricItem, index)
                        }
                        onBlur={(val, hasError: boolean) => this.handlePromqlError(hasError, 'blur', metricItem, index)}
                        onFocus={() => this.handlePromqlFocus(metricItem)}
                        onChange={val => this.handlePromsqlChange(metricItem, val)}
                      />
                    )}
                  </div>
                </div>
              ) : (
                <DataRetrievalItem
                  key={metricItem.key}
                  value={metricItem}
                  index={index}
                  compareValue={this.compareValue}
                  scenarioList={this.scenarioList}
                  onLoadingChange={loading => (metricItem.loading = loading)}
                  onClearMetric={() => this.handleClearMetric(index)}
                  onShowMetricSelector={() => this.handleShowMetricSelector(true, index)}
                  onChange={data => this.handleQueryItemValueChange(data, index)}
                />
              )
            ) : (
              // 表达式输入
              <ExpressionItem
                value={expItem}
                onChange={data => this.handleExpressionValueChange(data, index)}
              />
            )
          }
          {!!item.errMsg ? <div class='err-msg'>{item.errMsg}</div> : undefined}
        </div>
      );
    };
    const titleTpl = () => (
      /* 标题 */
      <div class={['title-wrap']}>
        {/* <BizSelect
          class="biz-select"
          value={+this.bizId}
          bizList={this.bizList}
          minWidth={270}
          onChange={this.handleChangeBizId} /> */}
        <div class='title-main'>
          <div class='title-edit'>
            <span class='title-text'>{this.isFavoriteNewSearch ? this.$t('新检索') : this.selectFavoriteName}</span>
            {!this.isFavoriteNewSearch ? (
              <span
                class='edit icon-monitor icon-bianji'
                onClick={() => this.handleClickEditFav()}
              ></span>
            ) : undefined}
          </div>
          <div class='title-operate'>
            {this.tabActive === 'monitor' && (
              <span
                class={['edit-mode-btn', { 'mode-disable': !this.canToPromql }]}
                v-bk-tooltips={{
                  content: this.$t('目前仅支持{0}切换PromQL', [`${this.$t('监控采集指标')}、${this.$t('自定义指标')}`]),
                  disabled: this.canToPromql
                }}
                onClick={this.handleEditModeChange}
              >
                <span class='icon-monitor icon-switch'></span>
                <span>{this.editMode === 'PromQL' ? 'UI' : 'PromQL'}</span>
              </span>
            )}
            {this.tabActive === 'monitor' && (
              <i
                class='icon-monitor icon-mc-expand expand-icon'
                onClick={this.handleExpandAll}
                style={{ transform: this.isExpandAll ? 'rotate(0deg)' : 'rotate(-180deg)' }}
              ></i>
            )}
            {/* <bk-popover
              ref="autoQueryPopover"
              theme="light"
              trigger="click"
              placement="bottom">
              <i class="icon-monitor icon-menu-setting" onClick={() => this.handleIseeCache()}></i>
              <div slot="content" class="setting-pop-centent">
                <span class="text">{this.$t('是否开启自动查询')}</span>
                <bk-switcher
                  vModel={this.autoQuery}
                  class="switcher" size="small" theme="primary" onChange={this.handleAutoQueryChange}></bk-switcher>
                { this.isShowTips
                  ? <span class="i-see-btn" onClick={() => this.handleIseeCache(true)}>{this.$t('知道了!')}</span>
                  : undefined }
              </div>
            </bk-popover> */}
            {/* <span class="icon-monitor icon-double-down"
                  onClick={() => this.handleLeftHiddenAndShow(false)}></span> */}
          </div>
        </div>
        {this.editMode !== 'PromQL' && this.tabActive === 'monitor' && (
          <div class='target-add-btn'>
            <span
              class='target-add-btn-content'
              onClick={this.handleShowTargetSelector}
            >
              {this.target.desc ? this.target.desc : [<i class='icon-monitor icon-plus-line' />, this.$t('IP目标')]}
            </span>
          </div>
        )}
      </div>
    );
    const metricRetrieval = () => [
      <bk-collapse
        class='collapse-wrap collapse-wrap-data'
        vModel={this.expandedData}
      >
        <transition-group
          name={this.dragData.from !== null ? 'flip-list' : 'filp-list-none'}
          tag='ul'
        >
          {this.localValue.map((item, index) => (
            <li
              class='drag-item'
              key={item.key}
              draggable={true}
              onDragstart={evt => this.handleDragStart(evt, index)}
              onDragend={this.handleDragend}
              onDrop={this.handleDrop}
              onDragenter={() => this.handleDragEnter(index)}
              onDragover={evt => this.handleDragOver(evt)}
            >
              <bk-collapse-item
                v-bkloading={{ isLoading: (item as DataRetrievalQueryItem).loading }}
                class='collapse-item'
                name={item.key}
                scopedSlots={{
                  default: () => titleSlot(item, index),
                  content: () => contentSlot(item, index)
                }}
              ></bk-collapse-item>
            </li>
          ))}
        </transition-group>
      </bk-collapse>,
      <div class='query-add-btn-wrap'>
        <span
          class='query-add-btn'
          onClick={this.handleAddQuery}
        >
          <i class='icon-monitor icon-mc-add' />
          {this.$t('查询项')}
        </span>
        <span
          class='query-add-btn'
          onClick={this.handleAddExpression}
        >
          <i class='icon-monitor icon-mc-add' />
          {this.$t('表达式')}
        </span>
      </div>,
      <HandleBtn
        class='search-group'
        canQuery={this.canQuery && !this.loading}
        autoQuery={this.autoQuery}
        queryLoading={this.loading}
        isFavoriteUpdate={this.isFavoriteUpdate}
        favCheckedValue={this.favCheckedValue}
        onQueryTypeChange={this.handleAutoQueryChange}
        onQuery={this.handleQuery}
        onClear={this.handleClearAll}
        onAddFav={this.handleClickAddOrUpdateFav}
      />
    ];
    const promQLContent = () => (
      <div class='promql-data-content'>
        <div
          class='metric-copy-btn'
          id='data-retrieval-metric-copy-btn-select-id'
          onClick={() => this.handleMetricSelectShow(true)}
        >
          <span>{this.$t('指标选择')}</span>
          <span class='icon-monitor icon-arrow-down'></span>
        </div>
        <MetricSelector
          show={this.metricSelectorShow}
          type={MetricType.TimeSeries}
          targetId={'#data-retrieval-metric-copy-btn-select-id'}
          isPromql={true}
          onShowChange={(v: boolean) => this.handleMetricSelectShow(v)}
          onSelected={this.handleSelectMetric}
        ></MetricSelector>
        <bk-collapse
          class='collapse-wrap collapse-wrap-data'
          v-model={this.promqlExpandedData}
        >
          {this.promqlData.map((item, index) => (
            <li
              class='drag-item'
              key={item.key}
            >
              <bk-collapse-item
                class='collapse-item'
                name={item.key}
                scopedSlots={{
                  default: () => (
                    <div class='collapse-item-title'>
                      <span class='title-left'>
                        <i
                          class={['bk-icon', 'icon-play-shape', { acitve: this.promqlExpandedData.includes(item.key) }]}
                        ></i>
                        <span class='title-name'>{item.alias}</span>
                        <span class='title-desc'>{this.$t('（查询项）')}</span>
                      </span>
                      <span class='title-center' />
                      <span class='title-right'>
                        {this.allOptions.map(opt => {
                          const iconName =
                            opt !== 'enable'
                              ? this.optionIconName[opt]
                              : item.enable
                                ? this.optionIconName[opt]
                                : 'icon-mc-invisible';
                          return (
                            <i
                              key={opt}
                              class={['icon-monitor', iconName]}
                              v-bk-tooltips_top={this.handleTitleTips(opt, item as any)}
                              onClick={evt => evt.stopPropagation()}
                              onMousedown={evt => this.handleSourceCodeOptionProxy(evt, opt, item, index)}
                            />
                          );
                        })}
                      </span>
                    </div>
                  ),
                  content: () => (
                    <div class='collapse-item-content promql'>
                      <div class='source-mode-wrap'>
                        <div class={['source-mode source-mode-h80']}>
                          <PromqlEditor
                            ref={'promql-mode-editor'}
                            class='promql-editor'
                            value={item.code}
                            onChange={val => this.handlePromqlDataCodeChange(val, index)}
                            executeQuery={this.handlePromqlDataEnter}
                            onFocus={() => this.handlePromqlDataFocus(index)}
                            onBlur={(val, hasError: boolean) => this.handlePromqlDataBlur(hasError, index)}
                          />
                        </div>
                      </div>
                      <span class='step-content'>
                        <bk-input
                          class='step-input'
                          value={item.step}
                          onChange={value => this.handleSourceStepChange(value, index)}
                          onFocus={() => this.handlePromqlDataFocus(index)}
                          onBlur={this.handleSourceStepBlur}
                        >
                          <div
                            slot='prepend'
                            class='step-input-prepend'
                          >
                            <span>{'Step'}</span>
                            <span
                              class='icon-monitor icon-hint'
                              v-bk-tooltips={{
                                content: this.$t('数据步长'),
                                placements: ['top']
                              }}
                            ></span>
                          </div>
                        </bk-input>
                      </span>
                      {!!item.errMsg ? <div class='err-msg'>{item.errMsg}</div> : undefined}
                    </div>
                  )
                }}
              ></bk-collapse-item>
            </li>
          ))}
        </bk-collapse>
        <div class='query-add-btn-wrap'>
          <span
            class='query-add-btn'
            onClick={this.handleAddCode}
          >
            <i class='icon-monitor icon-mc-add' />
            {this.$t('查询项')}
          </span>
        </div>
        <HandleBtn
          class='search-group'
          canQuery={this.canQuery && !this.loading}
          autoQuery={this.autoQuery}
          queryLoading={this.loading}
          isFavoriteUpdate={this.isFavoriteUpdate}
          favCheckedValue={this.favCheckedValue}
          onQueryTypeChange={this.handleAutoQueryChange}
          onQuery={this.handleQuery}
          onClear={this.handleClearAll}
          onAddFav={this.handleClickAddOrUpdateFav}
        />
      </div>
    );
    return (
      <div class='data-retrieval-wrap'>
        {
          // 日志检索
          this.logShow ? (
            <LogRetrieval></LogRetrieval>
          ) : (
            <div class='data-retrieval-container'>
              {!this.onlyShowView && (
                <PanelHeader
                  timeRange={this.compareValue.tools?.timeRange}
                  timezone={this.compareValue.tools?.timezone}
                  refleshInterval={this.compareValue.tools.refleshInterval}
                  showDownSample={false}
                  eventSelectTimeRange={this.eventSelectTimeRange}
                  onTimeRangeChange={this.handleToolsTimeRangeChange}
                  onImmediateReflesh={() => (this.refleshNumber += 1)}
                  onTimezoneChange={this.handleTimezoneChange}
                >
                  {
                    // url 带有 onlyShowView=false 的时候，不显示该按钮
                    <div
                      slot='pre'
                      class='left-show-icon-container'
                    >
                      <div class='icon-container'>
                        <div
                          v-bk-tooltips={{
                            content: this.isShowFavorite ? this.$t('点击收起收藏') : this.$t('点击展开收藏'),
                            placements: ['bottom'],
                            delay: 200,
                            disabled: this.needUseCollectGuide
                          }}
                          class={[
                            'result-icon-box',
                            {
                              'light-icon': !this.isShowFavorite,
                              'disable-icon': this.needUseCollectGuide
                            }
                          ]}
                          onClick={() => this.handleClickResultIcon('favorite')}
                        >
                          <span class='bk-icon icon-star'></span>
                        </div>
                        <div
                          v-bk-tooltips={{
                            content: this.isShowLeft ? this.$t('点击收起检索') : this.$t('点击展开检索'),
                            placements: ['bottom'],
                            delay: 200
                          }}
                          class={['result-icon-box', { 'light-icon': !this.isShowLeft }]}
                          onClick={() => this.handleClickResultIcon('search')}
                        >
                          <span class='bk-icon icon-monitor icon-mc-search-favorites'></span>
                        </div>
                      </div>
                    </div>
                  }
                </PanelHeader>
              )}
              <div class='data-retrieval-main'>
                {/* 收藏列表 */}
                <div
                  class='favorite-list'
                  v-monitor-drag={{
                    minWidth: 200,
                    maxWidth: 500,
                    defaultWidth: this.favoriteDefaultWidth,
                    autoHidden: true,
                    theme: 'line',
                    isShow: this.isShowFavorite,
                    onHidden: () => this.handleFavoriteHiddenAndShow(false),
                    onWidthChange: width => (this.favoriteWidth = width)
                  }}
                >
                  <FavoriteIndex
                    ref='favoriteIndex'
                    favoriteSearchType={this.favoriteSearchType}
                    favoritesList={this.curFavList}
                    favoriteLoading={this.favoriteLoading}
                    favCheckedValue={this.favCheckedValue}
                    isShowFavorite={this.isShowFavorite}
                    onOperateChange={({ operate, value }) => this.handleFavoriteOperate(operate, value)}
                    onGetFavoritesList={this.getListByGroupFavorite}
                  ></FavoriteIndex>
                </div>
                {/* 监控数据检索 */}
                <div
                  class={['data-retrieval-left', { 'is-loading': this.loading }]}
                  v-monitor-drag={{
                    minWidth: 200,
                    maxWidth: 800,
                    defaultWidth: this.leftDefaultWidth,
                    autoHidden: true,
                    theme: 'dotted',
                    isShow: this.isShowLeft,
                    onHidden: () => this.handleLeftHiddenAndShow(false),
                    onWidthChange: width => (this.leftWidth = width)
                  }}
                >
                  {/* 检索切换按钮 */}
                  {/* <div class="left-tab-wrap">
                  {this.tabList.map(item => (
                    <div
                      key={item.id}
                      class={['left-tab-item', { active: item.id === this.tabActive }]}
                      onClick={() => this.handleTabChange(item.id)}
                    >
                      {item.name}
                    </div>
                  ))}
                </div> */}
                  <div class={['left-content-wrap', { 'is-event': this.tabActive === 'event' }]}>
                    {titleTpl()}
                    {
                      // 数据检索
                      this.tabActive === 'monitor'
                        ? (() => (this.editMode === 'PromQL' ? promQLContent() : metricRetrieval()))()
                        : undefined
                    }
                    {
                      // 事件检索
                      this.tabActive === 'event' ? (
                        <EventRetrieval
                          ref='eventRetrievalRef'
                          where={this.eventWhere}
                          autoQuery={this.autoQuery}
                          compareValue={this.compareValue}
                          favCheckedValue={this.favCheckedValue}
                          isFavoriteUpdate={this.isFavoriteUpdate}
                          queryConfig={this.eventQueryConfig}
                          eventInterval={this.eventInterval}
                          chartTimeRange={this.eventChartTimeRange}
                          drillKeywords={this.drillKeywords}
                          onAutoQueryChange={this.handleAutoQueryOfEventChange}
                          onChartTitleChange={this.eventChartTitleChange}
                          onCountChange={count => (this.eventCount = count)}
                          onQuery={this.handleEventQuery}
                          onAddFav={this.handleClickAddOrUpdateFav}
                          onWhereChange={this.eventWhereChange}
                          onEmptyStatusChange={this.handleEmptyStatusChange}
                        />
                      ) : undefined
                    }
                    {/* 按钮操作区 */}
                  </div>
                </div>
                {/* 右侧视图部分 */}
                <div
                  class='data-retrieval-right'
                  style={{ flex: 1, width: `calc(100% - ${this.allLeftWidth}px)` }}
                >
                  <DataRetrievalView
                    v-bkloading={{ isLoading: this.delayLoading, zIndex: 500 }}
                    leftShow={this.isShowLeft}
                    refleshNumber={this.refleshNumber}
                    compareValue={this.compareValue}
                    queryResult={this.filterQueryResult}
                    queryTimeRange={this.queryTimeRange}
                    canAddStrategy={this.canAddStrategy}
                    retrievalType={this.tabActive}
                    eventMetricParams={this.eventMetricParams}
                    eventCount={this.eventCount}
                    eventChartTitle={this.eventChartTitle}
                    indexList={this.indexLists}
                    needCompare={this.editMode !== 'PromQL'}
                    queryLoading={this.loading}
                    onTimeRangeChangeEvent={this.handleTimeRangeChange}
                    onShowLeft={this.handleLeftHiddenAndShow}
                    onCompareChange={this.handleCompareChange}
                    onTimeRangeChange={this.handleToolsTimeRangeChange}
                    onCompareValueChange={this.handleCompareValueChange}
                    onSplitChange={this.handleSplitChange}
                    eventChartInterval={this.eventInterval}
                    onEventIntervalChange={this.handleEventIntervalChange}
                    onAddEventStrategy={this.handleAddEventStrategy}
                    onAddStrategy={this.handleAddStrategy}
                    onDrillKeywordsSearch={val => (this.drillKeywords = val)}
                    emptyStatus={this.emptyStatus}
                  />
                </div>
                {/* 指标选择器 */}
                <MetricSelector
                  show={this.isShowMetricSelector}
                  targetId={this.metricSelectorTargetId}
                  metricId={this.metricSelectorMetricId}
                  type={MetricType.TimeSeries}
                  scenarioList={this.scenarioAllList}
                  onShowChange={val => (this.isShowMetricSelector = val)}
                  onSelected={this.handleAddMetricData}
                />
                {/* <MetricSelector
                show={this.metricSelector.show}
                targetId={this.metricSelectorTargetId}
                scenarioList={this.scenarioAllList}
                type={this.metricSelector.type as MetricType}
                onShowChange={val => this.metricSelector.show = val}
                onSelected={this.handleAddMetric}></MetricSelector> */}
                {/* <StrategyMetricCommon
                isShow={this.isShowMetricSelector}
                on-show-change={this.handleShowMetricSelector}
                scenarioList={this.scenarioList}
                monitorType={this.curMonitorType}
                metricData={this.metricData}
                on-add={this.handleAddMetricData}
                multiple={false}
              /> */}
                {/* 监控目标选择器 */}
                <StrategyIpv6
                  showDialog={this.target.show}
                  objectType={this.target.objectType}
                  nodeType={this.target.targetType}
                  checkedNodes={this.target.value}
                  onChange={this.handleTargetChange}
                  onCloseDialog={() => (this.target.show = false)}
                />
              </div>
              <AddCollectDialog
                v-model={this.isShowAddFavoriteDialog}
                keyword={this.favoriteKeywordsData}
                favoriteSearchType={this.favoriteSearchType}
                favStrList={this.favStrList}
                editFavoriteData={this.editFavoriteData}
                onSubmit={value => this.handleSubmitFavorite(value)}
                onCancel={() => (this.editFavoriteData = null)}
              />
            </div>
          )
        }
        {this.needUseCollectGuide && (
          <NotifyBox
            placement={'bottom'}
            hasBorder
            tipStyles={{
              top: '50px',
              left: '14px'
            }}
          >
            <div slot='title'>{this.$t('检索收藏功能支持分组和管理')}</div>
            <div slot='action'>
              <div
                class='action-text'
                onClick={this.handleGuideDone}
              >
                {this.$t('知道了!')}
              </div>
            </div>
          </NotifyBox>
        )}
      </div>
    );
  }
}
