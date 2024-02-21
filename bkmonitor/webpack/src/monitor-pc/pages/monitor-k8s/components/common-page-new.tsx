/* eslint-disable max-len */
/* eslint-disable no-nested-ternary */
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
import { Component, Emit, InjectReactive, Prop, Provide, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getSceneView, getSceneViewList } from '../../../../monitor-api/modules/scene_view';
import bus from '../../../../monitor-common/utils/event-bus';
import { deepClone, random } from '../../../../monitor-common/utils/utils';
import DashboardPanel from '../../../../monitor-ui/chart-plugins/components/dashboard-panel';
import { DEFAULT_INTERVAL, DEFAULT_METHOD } from '../../../../monitor-ui/chart-plugins/constants/dashbord';
import { BookMarkModel, DashboardMode, IPanelModel, IViewOptions } from '../../../../monitor-ui/chart-plugins/typings';
import { VariablesService } from '../../../../monitor-ui/chart-plugins/utils/variable';
import introduce from '../../../common/introduce';
import Collapse from '../../../components/collapse/collapse';
import GuidePage from '../../../components/guide-page/guide-page';
import { ASIDE_COLLAPSE_HEIGHT } from '../../../components/resize-layout/resize-layout';
import type { TimeRangeType } from '../../../components/time-range/time-range';
import { DEFAULT_TIME_RANGE } from '../../../components/time-range/utils';
import { CP_METHOD_LIST, PANEL_INTERVAL_LIST } from '../../../constant/constant';
import { getDefautTimezone, updateTimezone } from '../../../i18n/dayjs';
import { Storage } from '../../../utils';
import { IIndexListItem } from '../../data-retrieval/index-list/index-list';
// import { CHART_INTERVAL } from '../../../constant/constant';
import HostList from '../../performance/performance-detail/host-list/host-list';
import HostTree, { FilterDictType, TreeNodeItem } from '../../performance/performance-detail/host-tree/host-tree';
import SettingModal from '../../setting-modal';
import SettingsWrapper from '../settings/settings';
import {
  DASHBOARD_PANEL_COLUMN_KEY,
  IBookMark,
  IMenuId,
  IMenuItem,
  IOption,
  IQueryData,
  IQueryDataSearch,
  ISearchItem,
  ITabItem,
  ITableItem,
  METHOD_LIST,
  PanelToolsType,
  SearchType,
  SPLIT_MAX_WIDTH,
  SPLIT_MIN_WIDTH
} from '../typings';
import { SETTINGS_POP_ZINDEX } from '../utils';

import CommonList from './common-list/common-list';
import CommonListK8s from './common-list-k8s/common-list-k8s';
import CommonSelectTable from './common-select-table/common-select-table';
import CommonTree from './common-tree/common-tree';
import FilterVarSelectGroup from './filter-var-select/filter-var-select-group';
import FilterVarSelectSimple from './filter-var-select/filter-var-select-simple';
import GroupSelect from './group-select/group-select';
import CompareSelect from './panel-tools/compare-select';
import PanelTools from './panel-tools/panel-tools';
import ApmApiPanel from './select-panel/apm-api-panel';
import AlarmTools from './alarm-tools';
import CommonDetail, { INDEX_LIST_DEFAULT_CONFIG_KEY } from './common-detail';
import DashboardTools from './dashboard-tools';
import PageTitle from './page-title';
import SplitPanel from './split-panel';
import { getPanelData } from './utils';

import './common-page.scss';

export type SceneType = 'detail' | 'overview';

const DEFAULT_QUERY_DATA = {
  page: 1, // 切换tab 重置 1
  pageSize: 10,
  search: [], // 切换tab 清空列表自定义搜索的条件
  selectorSearch: [], // 切换tab 清空侧栏自定义的的搜索条件
  keyword: '', // 搜索关键字
  checkboxs: [], // 复选框过滤
  filter: '',
  sort: '',
  filterDict: {}
};

interface ICommonPageProps {
  // 场景id
  sceneId: string;
  // 场景类型
  sceneType: SceneType;
  // 默认viewoptions 视图变量等
  defaultViewOptions: IViewOptions;
  // 标题
  title?: string;
  // 是否展示分屏按钮
  isShowSplitPanel?: boolean;
  // 详情返回操作
  backToOverviewKey?: string;
  // tab切换是否转换为overview
  tab2SceneType?: boolean;
  // 表格搜索条件需要保留的字段
  toggleTabSearchFilterKeys?: string[];
  // 默认汇聚方法
  defalutMethod?: string;
}
interface ICommonPageEvent {
  onTitleChange: string;
  onPageTitleChange: (a: string, b?: Record<string, any>) => void;
  onTabChange: string;
  onTimeRangeChange: TimeRangeType;
  onSceneTypeChange: SceneType;
}
export const MIN_DASHBOARD_PANEL_WIDTH = '640';
export type ShowModeType = 'list' | 'dashboard' | 'default';
@Component({
  components: {
    /** 视图设置异步组件 */
    SettingsWrapper: () => import(/* webpackChunkName: "k8s-settings-wrapper" */ '../settings/settings')
  }
})
export default class CommonPageNew extends tsc<ICommonPageProps, ICommonPageEvent> {
  // 场景id
  @Prop({ default: 'host', type: String }) readonly sceneId: string;
  // 场景类型
  @Prop({ default: 'detail', type: String }) readonly sceneType: SceneType;
  // 默认viewoptions 视图变量等
  @Prop({ default: () => {}, type: Object }) readonly defaultViewOptions: IViewOptions;
  // 标题
  @Prop({ default: '', type: String }) readonly title: string; // 场景名称
  // 是否展示分屏按钮
  @Prop({ default: true, type: Boolean }) readonly isShowSplitPanel: boolean; // 是否需要分屏按钮
  // 详情返回列表的操作 更新该值更新数据
  @Prop({ default: '', type: String }) readonly backToOverviewKey: string; // 详情返回操作
  // tab切换是否转换为overview
  @Prop({ default: false, type: Boolean }) readonly tab2SceneType: boolean;
  // 切换tab时候表格的保留搜索条件的key值
  @Prop({ default: () => [], type: Array }) readonly toggleTabSearchFilterKeys: string[];
  // 默认汇聚方法
  @Prop({ default: '' }) readonly defalutMethod: string;

  // 监控左侧栏是否收缩配置 自愈默认未收缩
  @InjectReactive('toggleSet') toggleSet: boolean;
  @InjectReactive('readonly') readonly readonly: boolean;

  @Ref() settingsWrapRef: SettingsWrapper;
  @Ref() collapseRef: Collapse;
  @Ref() filterVarSelectGroupRef: FilterVarSelectGroup;
  @Ref() commonListRef: CommonList;

  /** 场景类型 */
  localSceneType: SceneType = 'overview';
  // 视图面板id
  dashboardId = '';
  // 视图tab 列表
  tabList: ITabItem[] = [];
  // 是否展示loading
  loading = false;
  // 当前场景数据模型 页签
  sceneData: BookMarkModel = null;
  // 变量是否已经获取完毕
  filtersReady = false;
  // 左侧选择栏是否获取完毕
  selectorReady = false;
  // 左侧选择栏是否刷新key值
  selectorPanelKey = random(10);
  // 是否分屏
  isSplitPanel = false;
  // 左侧栏是否显示
  isSelectPanelActive = true;
  // 重置拖拽锚点问题
  resetDragPosKey = random(10);
  // dashboard模式 list: 列表模式 chart: 图表模式(default)
  dashbordMode: DashboardMode = 'chart';
  // 右侧栏info panel active
  infoActive = true;
  // 分屏大小
  splitPanelWidth = 0;
  // 初始化分屏大小
  defaultPanelWidth = 0;
  /** 设置弹窗显示状态 */
  showSetting = false;
  /** 当前设置弹窗 */
  activeSettingId: string | number = '';
  /** 设置弹窗关闭时判断当前页签内容是否发生变更需要重新请求 */
  isPanelChange = false;
  // 搜索的值
  searchValue: ISearchItem[] | string[] = [];
  // 图表布局
  columns = 0;
  // 选中添加目标对比的主机
  compareHostList: IOption[] = [];
  /** 变量伸缩层 */
  filterActive = true;
  // 图表特殊配置项
  filterDict: Record<string, any> = {};
  // group by
  group_by: string[] = [];
  // 汇聚方法
  method = DEFAULT_METHOD;
  // 汇聚周期
  interval: string | number = 'auto';
  // 对比数据
  compares: Record<string, any> = {};
  // 默认对比数据
  filters: Record<string, any> = {};
  // 变量数据
  variables: Record<string, any> = {};
  /** groups筛选的维度值 */
  groups: string[] = [];
  // 是否刷新变量
  refleshVariablesKey: string = random(10);
  // 搜索后的配置panels
  localPanels: IPanelModel[] = [];
  // 初始化一个dashboard id 保证分屏和dashboard唯一
  dashboardPanelId: string = random(10);

  /** 选中节点或主机的title */
  currentTitle = '';

  /** filter的已选数量 */
  filterCount = 0;

  /** 侧栏的搜索条件 */
  selectorSearchCondition: IQueryDataSearch = [];

  /** 容器引导页 */
  showK8sGuidePage = false;

  // 查询条件
  queryString = '';
  /** 是否开启精准过滤 */
  isPreciseFilter = false;

  /** 视图设置页面是否为跳转到自动添加页面 */
  initAddSetting = false;
  // 展示模式 纯列表 list 纯视图 dashboar  列表和纯视图混合模式 default
  showMode: ShowModeType = 'default';
  // 是否折叠详情panel
  collapseInfo = false;
  // 时间范围缓存用于复位功能
  cacheTimeRange = [];
  // 特殊的目标字段配置
  get targetFields(): { [propName: string]: string } {
    const panel = this.sceneData?.selectorPanel;
    /* 是否存在fields */
    const fields = panel?.targets?.[0]?.fields ? panel.targets[0].fields : panel?.targets?.[0]?.field;
    return fields;
  }

  // 是否选中的是主机或者是服务实例
  get isCheckedHost() {
    // eslint-disable-next-line max-len
    return !!this.localViewOptions.filters?.bk_target_ip || this.isCheckInstance;
  }
  /** 对比工具的可选项 */
  get compareTypeMap(): PanelToolsType.CompareId[] {
    return (
      !this.readonly &&
      (this.isCheckedHost || !!this.sceneData?.options?.panel_tool?.need_compare_target
        ? ['none', 'target', 'time']
        : ['none', 'time'])
    );
  }

  /** 是否需要对比工具 */
  get isShowCompareTool(): boolean {
    return !!this.sceneData?.options?.panel_tool?.compare_select;
  }

  /** 汇聚周期选择 */
  get isEnableIntervalSelect() {
    return !!this.sceneData?.options?.panel_tool?.interval_select;
  }

  /** 是否开启布局选择 */
  get isEnableColumnsSelect() {
    return !!this.sceneData?.options?.panel_tool?.columns_toggle;
  }

  /* 是否选中了服务实例 */
  get isCheckInstance() {
    // eslint-disable-next-line max-len
    return (
      !!this.localViewOptions.filters?.[this.targetFields?.id] ||
      !!this.localViewOptions.filters?.bk_target_service_instance_id
    );
  }

  /** 是否开启汇聚方法选择 */
  get isEnableMethodSelect() {
    return this.sceneData?.options?.panel_tool?.method_select && !this.isCheckInstance;
  }

  /** 是否需要合并、分割视图开关 */
  get needSplitSwitch() {
    return !!this.sceneData?.options?.panel_tool?.split_switcher;
  }

  /** 是否展示面板的工具栏 */
  get isEnablePanelTool() {
    return (
      this.isEnableIntervalSelect || this.isShowCompareTool || this.isEnableColumnsSelect || this.isEnableMethodSelect
    );
  }

  // 组件内维护的viewoptions
  get localViewOptions(): IViewOptions {
    return {
      filters: this.filters,
      groups: this.groups,
      variables: this.variables,
      method: this.method,
      interval: this.interval,
      compares: this.compares
    };
  }

  /** 是否展示详情面板 */
  get enableDetail() {
    return (
      (!this.isOverview && !!this.sceneData?.options?.detail_panel && this.selectorReady) ||
      (this.isOverview && !!this.sceneData?.options?.overview_detail_panel && this.selectorReady)
    );
  }

  /** 告警、策略刷新数据的key */
  get alarmToolsKey() {
    return JSON.stringify(this.filters) + this.dashboardId;
  }

  /** 是否需要展示侧边栏 */
  get showSelectPanel() {
    return this.dashbordMode !== 'list';
  }

  get isOverview() {
    return this.localSceneType === 'overview';
  }
  /** 索引列表 */
  get indexList(): IIndexListItem[] {
    const panels = this.isPreciseFilter
      ? this.preciseFilteringPanels
      : this.handleGetLocalPanels(this.isOverview ? this.sceneData.overview_panels : this.sceneData.panels);
    if (this.sceneData?.options?.enable_index_list && !!panels.length) {
      let curTagChartId = '';
      const { mode } = this.sceneData;
      const list = panels.reduce((total, row) => {
        if (mode === 'auto') {
          // 主机
          const item = {
            id: row.id,
            name: row.title,
            children: row.panels?.map?.(panel => ({
              id: panel.id,
              name: panel.title
            }))
          };
          total.push(item);
        } else if (mode === 'custom') {
          // 自定义模式tag分组数据
          if (row.type === 'tag-chart') {
            curTagChartId = row.id as string;
            const item = {
              id: row.id,
              name: row.title,
              children: []
            };
            total.push(item);
          } else if (!!row.title) {
            const curGroup = total.find(group => group.id === curTagChartId);
            const child = {
              id: row.id,
              name: row.title
            };
            if (curGroup?.children) {
              curGroup.children.push(child);
            } else {
              total.push(child);
            }
          }
        }
        return total;
      }, []);
      if (list.length === 1 && !!list[0].children?.length) return list[0].children;
      return list;
    }
    return [];
  }
  /** 需要精准过滤的维度key 包含了 filters 和 groups 的key */
  get groupByKey() {
    return Object.entries(this.variables)
      .reduce((total, item) => {
        const [key, value] = item;
        if (value !== void 0) total.push(key);
        return total;
      }, [])
      .concat(this.viewOptions.group_by);
  }
  /**
   * 精准过滤的panels
   * panel不被过滤情况：没有显示精准过滤 或者 没有选中精准过滤
   * panel过滤的条件：panel没有dimensions || 维度key为空 || panel.dimensions存在于维度key中
   */
  get preciseFilteringPanels() {
    if (!this.sceneData?.isShowPreciseFilter || !this.isPreciseFilter) return this.localPanels;
    const fn = panels =>
      panels.reduce((total, item) => {
        const { type, dimensions } = item;
        if (type === 'row') {
          /** 分组 */
          // eslint-disable-next-line no-param-reassign
          item.panels = fn(item.panels);
          total.push(item);
        } else {
          const isPass =
            dimensions === undefined ||
            !this.groupByKey.length ||
            dimensions.some(key => this.groupByKey.includes(key));
          isPass && total.push(item);
        }
        return total;
      }, []);
    return fn(JSON.parse(JSON.stringify(this.localPanels)));
  }
  /** 当前tab的数据 */
  get currentTabData() {
    return this.tabList.find(item => item.id === this.dashboardId);
  }
  /** apm服务 */
  get isApmServiceOverview() {
    return this.sceneId === 'apm_service';
  }
  /** 是否需要额外的参数 */
  get hasOtherParams() {
    return !!this.currentTabData?.params;
  }
  /* 是否为单图模式 */
  get isSingleChart() {
    return (
      this.curPanelCount < 2 &&
      this.localPanels?.some(item => item.type !== 'graph') &&
      this.localPanels.length < 2 &&
      (this.localPanels?.[0].type === 'row' ? this.localPanels[0]?.panels?.some(item => item.type !== 'graph') : true)
    );
  }
  /** 是否含overviewPanels */
  get hasOverviewPanels() {
    return !!this.sceneData?.overview_panels;
  }
  /** 当前视图panelCount */
  get curPanelCount() {
    return this.sceneData?.updatePanels(this.localSceneType) || 0;
  }
  // 派发到子孙组件内的一些视图配置变量
  // 数据时间间隔
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  // 时区
  @ProvideReactive('timezone') timezone: string = getDefautTimezone();
  // 刷新间隔
  @ProvideReactive('refleshInterval') refleshInterval = -1;
  // 视图变量
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};
  // 是否立即刷新
  @ProvideReactive('refleshImmediate') refleshImmediate = '';
  // 对比的时间
  @ProvideReactive('timeOffset') timeOffset: string[] = [];
  // 对比类型
  @ProvideReactive('compareType') compareType: PanelToolsType.CompareId = 'none';
  // 场景数据
  @ProvideReactive('currentSceneData') currentSceneData: BookMarkModel = null;
  // 表格图表搜索条件数据
  @ProvideReactive('queryData') queryData: IQueryData = DEFAULT_QUERY_DATA;
  // 粒度
  @ProvideReactive('downSampleRange') downSampleRange: string | number = 'auto';
  /** 图表的告警状态接口是否需要加入$current_target作为请求参数 */
  @ProvideReactive('alertFilterable') alertFilterable = false;
  // 是否展示复位
  @ProvideReactive('showRestore') showRestore = false;
  // 是否开启（框选/复位）全部操作
  @Provide('enableSelectionRestoreAll') enableSelectionRestoreAll = true;
  // 侧栏搜索
  @Provide('handleUpdateQueryData')
  handleUpdateQueryData(queryData: IQueryData) {
    this.queryData = queryData;
    this.handleResetRouteQuery();
  }
  // 框选图表事件范围触发（触发后缓存之前的时间，且展示复位按钮）
  @Provide('handleChartDataZoom')
  handleChartDataZoom(value) {
    if (JSON.stringify(this.timeRange) !== JSON.stringify(value)) {
      this.cacheTimeRange = JSON.parse(JSON.stringify(this.timeRange));
      this.timeRange = value;
      this.showRestore = true;
    }
  }
  @Provide('handleRestoreEvent')
  handleRestoreEvent() {
    this.timeRange = JSON.parse(JSON.stringify(this.cacheTimeRange));
    this.showRestore = false;
  }
  mounted() {
    this.timezone = getDefautTimezone();
    this.initData();
    bus.$on('dashboardModeChange', this.handleDashboardModeChange);
    bus.$on('switch_scenes_type', this.handleLinkToDetail);
  }
  beforeDestroy() {
    bus.$off('dashboardModeChange', this.handleDashboardModeChange);
    bus.$off('switch_scenes_type');
  }
  @Watch('backToOverviewKey')
  backToOverviewKeyChange() {
    this.localSceneType = 'overview';
    this.handleResetRouteQuery();
    this.initData();
  }

  @Watch('sceneData.variables')
  showFilterChange(val) {
    if (!val.length) {
      this.handleFilterVarChange([]);
    }
  }

  async initData() {
    this.localSceneType = this.sceneType;
    this.loading = true;
    this.columns = +localStorage.getItem(DASHBOARD_PANEL_COLUMN_KEY) || 0;
    this.filtersReady = false;
    this.selectorReady = false;
    await this.$nextTick();
    this.handleSetDefaultParams();
    this.handleUpdateViewOptions();
    await this.getTabList(true);
    this.loading = false;
  }
  /**
   * @description: 初始化设置默认数据
   * @return {*}
   */
  handleSetDefaultParams() {
    const filters: Record<string, any> = {};
    const variables = {};
    this.defaultViewOptions?.filters &&
      Object.keys(this.defaultViewOptions.filters).forEach(key => {
        filters[key] = this.defaultViewOptions.filters[key];
      });
    this.defaultViewOptions?.variables &&
      Object.keys(this.defaultViewOptions.variables).forEach(key => {
        variables[key] = this.defaultViewOptions.variables[key];
      });
    this.groups = this.defaultViewOptions?.groups || [];
    Object.keys(this.$route.query || {}).forEach(key => {
      const val = this.$route.query[key];
      if (key.match(/^filter-/)) {
        let v = null;
        if (Array.isArray(val)) {
          v = val;
        } else {
          if (/^(\[|\{)/.test(val)) {
            v = JSON.parse(val);
          } else if (/^-?[1-9]?[0-9]*[1-9]+$/.test(val)) {
            v = +val;
          } else {
            v = val;
          }
        }
        filters[key.replace('filter-', '')] = v;
        /** 处理主机详情 (主机、节点、服务实例) 互为冲突的字段 */
        if (['bk_inst_id', 'bk_target_service_instance_id'].some(item => key.includes(item))) {
          delete filters.bk_target_cloud_id;
          delete filters.bk_target_ip;
        }
      } else if (key.match(/^var-/)) {
        variables[key.replace('var-', '')] = typeof val === 'string' && /^-?[1-9]?[0-9]*[1-9]+$/.test(val) ? +val : val;
      } else if (key.match(/^groups/)) {
        this.groups = Array.isArray(val) ? val : [val];
      } else if (!['key'].includes(key)) {
        if (typeof val === 'string' && /^-?[1-9]?[0-9]*[1-9]+$/.test(val)) {
          this[key] = +val;
        } else if (['from', 'to'].includes(key)) {
          // eslint-disable-next-line no-nested-ternary
          // this[key] = Array.isArray(val) ? val : isNaN(+val) ? val : +val;
          key === 'from' && (this.timeRange[0] = val as string);
          key === 'to' && (this.timeRange[1] = val as string);
        } else if (key === 'queryData') {
          try {
            const {
              page = 0,
              pageSize = 10,
              search = [],
              filter = '',
              keyword = '',
              sort = '',
              checkboxs = [],
              selectorSearch = [],
              filterDict = {}
            } = JSON.parse(decodeURIComponent(val as string));
            this.queryData = {
              page,
              pageSize,
              search,
              selectorSearch,
              filter,
              keyword,
              checkboxs,
              sort,
              filterDict
            };
          } catch (error) {
            console.log(error);
          }
        } else if (key === 'preciseFilter') {
          this.isPreciseFilter = val === 'true';
        } else if (key === 'sceneType') {
          this.localSceneType = val as SceneType;
        } else if (['timeOffset', 'compares'].includes(key)) {
          /** 目标对比、时间对比数据 */
          try {
            const value = JSON.parse(decodeURIComponent(val as string));
            key === 'compares' ? (this.compares = value) : (this.timeOffset = value);
            this.compareType = key === 'compares' ? 'target' : 'time';
          } catch (err) {
            console.log(err);
          }
        } else if (key === 'timezone') {
          if (val?.length) {
            this.timezone = val as string;
            updateTimezone(val as string);
          }
        } else {
          this[key] = val;
        }
      }
    });
    this.localSceneType = (this.$route.query.sceneType as any) ?? this.sceneType;
    this.method =
      this.defaultViewOptions.method || (this.$route.query.method as string) || this.defalutMethod || DEFAULT_METHOD;
    this.interval = this.defaultViewOptions.interval || (this.$route.query.interval as string) || DEFAULT_INTERVAL;
    this.filters = filters;
    this.variables = variables;
  }
  // 初始化默认分屏宽度
  handleSetDefaultSplitPanelWidth() {
    this.defaultPanelWidth = (this.$refs.dashboardPanelWrap as HTMLDivElement).getBoundingClientRect().width / 2;
    this.splitPanelWidth = this.defaultPanelWidth;
  }
  // 获取页签列表
  async getTabList(isInit?: boolean) {
    const params = {
      scene_id: this.sceneId,
      type: this.localSceneType
    };
    if (this.sceneId === 'apm_service') {
      // APM 服务视图需要增加参数区分类型 参数为 【filter-变量】
      const apmServiceParams = Object.keys(this.filters).reduce((pre, key) => {
        // eslint-disable-next-line no-param-reassign
        pre[`apm_${key}`] = this.filters[key];
        return pre;
      }, {});
      Object.assign(params, apmServiceParams);
    }
    const data = await getSceneViewList(params, { reject403: true }).catch(() => []);
    if (this.sceneId === 'kubernetes') {
      this.showK8sGuidePage = !data?.length;
      if (this.showK8sGuidePage) return;
    }
    /** 标题栏 */
    this.tabList = data;
    if (isInit) {
      let [{ id } = { id: '' }] = data;
      if (this.dashboardId) {
        id = this.dashboardId;
      }
      await this.handleTabChange(id);
    }
  }
  // 全屏设置
  async handleFullscreen() {
    this.resetDragPosKey = random(10);
  }
  // @Emit('tabChange')
  emitTabChange(val: string) {
    const tabName = this.tabList.find(tab => tab.id === val)?.name || '';
    this.$emit('tabChange', val, tabName);
  }
  @Emit('sceneTypeChange')
  emitLocalSceneTypeChange() {
    return this.localSceneType;
  }
  /**
   * 获取图表的配置
   * @param id
   * @param needLoading loading
   * @param isSelectItem 是否为选中侧栏操作
   */
  async handleTabChange(id: string, needLoading = true) {
    needLoading && (this.loading = true);
    this.dashboardId = id;
    this.handleGetPanelData(id, needLoading);
  }
  // 页签改变时
  async handleGetPanelData(v: string, needLoading = true) {
    needLoading && (this.loading = true);
    this.dashboardId = v;
    this.headerTitleChange(this.localSceneType === 'overview' ? '' : this.currentTitle || 'loading...');
    if (!this.isEnableMethodSelect) {
      this.method = this.defaultViewOptions.method || this.defalutMethod || DEFAULT_METHOD;
    }
    let params = {
      scene_id: this.sceneId,
      type: this.localSceneType,
      id: this.dashboardId
    };

    /** 注入侧栏的变量 或 apm自定义服务变量 */
    if (this.hasOtherParams || this.isApmServiceOverview) {
      const variablesService = new VariablesService(this.filters);
      params = {
        ...params,
        ...variablesService.transformVariables(this.currentTabData?.params || {})
      };
    }
    const data: IBookMark = await getSceneView(params).catch(() => ({ id: '', panels: [], name: '' }));
    const oldSelectPanel = this.sceneData?.options?.selector_panel?.targets
      ? JSON.stringify(this.sceneData.options.selector_panel.targets)
      : '';
    this.sceneData = new BookMarkModel(data || { id: '', panels: [], name: '' });
    let title = this.tabList.find(item => item.id === v)?.name;
    if (this.sceneData.selectorPanel) title += this.$t('列表');
    this.$emit('pageTitleChange', title, { dashboardId: this.dashboardId });
    this.currentSceneData = this.sceneData;
    const newSelectPanel = this.sceneData?.options?.selector_panel?.targets
      ? JSON.stringify(this.sceneData.options.selector_panel.targets)
      : '';
    // 部分dashboard没有列表模式
    if (this.dashbordMode === 'list' && !this.sceneData.list?.length) {
      this.dashbordMode = 'chart';
    }
    // 切换tab时初始化 sceneType
    const { overview_panels, panels: detail } = data;
    const rightSceneType =
      (this.localSceneType === 'detail' && detail?.length) || (this.localSceneType === 'overview' && overview_panels);
    if (!rightSceneType) {
      this.localSceneType = overview_panels ? 'overview' : 'detail';
    }
    //  切换tab时初始化 showMode
    if (!this.sceneData.selectorPanel && this.showMode === 'list') {
      this.showMode = 'dashboard';
    }
    // 判断左侧栏是否需要缓存
    this.selectorPanelKey = oldSelectPanel === newSelectPanel ? this.selectorPanelKey : random(10);
    const variables = {};
    this.sceneData.variables.forEach(item => {
      variables[item.fieldsKey] = this.variables[item.fieldsKey];
    });
    /* 少量图表的索引默认收起来 */
    if (this.sceneData?.panelCount <= 6) {
      const indexStorage = new Storage();
      const defaultIndexData = indexStorage.get(INDEX_LIST_DEFAULT_CONFIG_KEY);
      if (!defaultIndexData || !!defaultIndexData?.expand) {
        indexStorage.set(INDEX_LIST_DEFAULT_CONFIG_KEY, {
          height: ASIDE_COLLAPSE_HEIGHT,
          placement: defaultIndexData?.placement || 'bottom',
          expand: false
        });
      }
    }
    this.alertFilterable = this.sceneData.options?.alert_filterable;
    this.variables = variables;
    this.handleUpdateViewOptions();
    const panels =
      this.hasOverviewPanels && this.localSceneType === 'overview'
        ? this.sceneData.overview_panels
        : this.sceneData.panels;
    this.localPanels = this.handleGetLocalPanels(panels);
    this.selectorReady = !this.sceneData.fetchPanel && this.hasOverviewPanels && this.localSceneType === 'overview';
    this.filtersReady = !this.sceneData.variables?.length;
    this.searchValue = [];
    // if (this.selectorPanelPriority) this.refleshVariablesKey = random(8);
    needLoading && (this.loading = false);
    this.handleResizeCollapse();
    this.emitTabChange(v);
    this.emitLocalSceneTypeChange();
  }
  handleGetLocalPanels(panels) {
    const unGroupKey = '__UNGROUP__';
    /** 处理只有一个分组且为未分组时则不显示组名 */
    const rowPanels = panels.filter(item => item.type === 'row');
    if (rowPanels.length === 1 && rowPanels[0]?.id === unGroupKey) {
      const resultPanels = [];
      panels.forEach(item => {
        if (item.type === 'row') {
          resultPanels.push(...item.panels);
        } else {
          resultPanels.push(item);
        }
      });
      return resultPanels;
    }
    /* 当有多个分组且未分组为空的情况则不显示未分组 */
    if (panels.length > 1 && panels.some(item => item.id === unGroupKey)) {
      return panels.filter(item => (item.id === unGroupKey ? !!item.panels?.length : true));
    }
    return panels;
  }
  // 是否分屏触发事件
  handleSplitPanel(v: boolean) {
    this.handleSetDefaultSplitPanelWidth();
    this.isSplitPanel = v;
    this.splitPanelWidth = v ? this.defaultPanelWidth : 0;
    this.handleInfoActive(!v);
  }
  // 分屏拖拽大小触发事件
  handleDragMove(v: number) {
    this.splitPanelWidth = v;
    this.isSplitPanel = v > 0;
  }
  // goto page by name
  handleGotoPage(name: string) {
    this.$router.push({ name });
  }
  /**
   * @description: 选择设置菜单
   * @param {IMenuItem} menuItem
   */
  handleShowSettingModel(menuItem: IMenuItem) {
    if (menuItem.id === 'view-demo') {
      this.handleToDemo();
    } else {
      this.activeSettingId = menuItem.id;
      this.showSetting = true;
      this.initAddSetting = false;
    }
  }
  /**
   * 打开设置页签和设置变量页面
   * @param id
   */
  handleAddTab(id: IMenuId = 'edit-tab') {
    this.activeSettingId = id;
    this.showSetting = true;
    this.initAddSetting = true;
  }
  /* 粒度 */
  handleDownSampleRangeChange(v: number | string) {
    this.downSampleRange = v;
    this.handleResetRouteQuery();
  }
  /**
   * @description: 跳转demo业务
   */
  handleToDemo() {
    const demo = this.$store.getters.bizList.find(item => item.is_demo);
    if (demo?.id) {
      if (+this.$store.getters.bizId === +demo.id) {
        location.reload();
      } else {
        /** 切换为demo业务 */
        this.$store.commit('app/handleChangeBizId', {
          bizId: demo.id,
          ctx: this
        });
      }
    }
  }
  async handleMenuChange(item: IMenuItem) {
    let res = true;
    res = await this.handleBeforeCloseSettings();
    if (res) this.activeSettingId = item.id;
  }
  // 监控主框架 menu缩进设置
  async toggleSettingModel(isShow: boolean) {
    this.showSetting = isShow;
    if (this.isPanelChange) {
      await this.getTabList();
      if (!this.tabList.some(item => item.id === this.dashboardId)) {
        this.dashboardId = this.tabList[0].id.toString();
      }
      await this.handleTabChange(this.dashboardId);
      this.handleResizeCollapse();
      this.isPanelChange = false;
      this.filterVarSelectGroupRef?.handleCreatePromiseMap();
    }
  }
  /**
   * @description: 关闭设置前进行保存校验
   * @return 返回true为关闭，false则取消关闭设置
   */
  async handleBeforeCloseSettings(): Promise<boolean> {
    /** 编辑后存在差异 */
    if (this.settingsWrapRef?.hasDiff) {
      const res = await new Promise((resolve, reject) => {
        this.$bkInfo({
          zIndex: SETTINGS_POP_ZINDEX,
          title: this.$t('是否放弃本次操作？'),
          confirmFn: () => resolve(true),
          cancelFn: () => reject(false)
        });
      });
      return !!res;
    }
    return true;
  }
  // header上搜索值改变触发
  handleSearchChange(t: SearchType, v: ISearchItem[] | string[]) {
    if (this.sceneData.mode === 'custom') {
      const [item] = v as ISearchItem[];
      document.getElementById(`${item.id}__key__`)?.scrollIntoView?.();
      return;
    }
    if (!v?.length) {
      this.searchValue = v;
      this.localPanels = this.sceneData.panels;
      return;
    }
    if (t === 'key-value') {
      this.handleKeyValueSearch(v as ISearchItem[]);
    } else {
      const { panels } = this.sceneData;
      const list = [];
      panels.forEach(panel => {
        if (v.some(id => panel.id.toString() === id.toString())) {
          list.push({ ...panel });
        } else if (panel.panels?.length) {
          const panels = panel.panels.filter(item => v.some(id => item.id.toString() === id.toString()));
          panels.length &&
            list.push({
              ...panel,
              panels
            });
        }
      });
      this.localPanels = list;
    }
    this.searchValue = v;
  }
  // 视图k-v搜索触发
  handleKeyValueSearch(v: ISearchItem[]) {
    const { panels, hasGroup, overview_panels } = this.sceneData;
    // 不同的场景类型，获取的panels不一样
    const currentPanels = this.localSceneType === 'overview' ? overview_panels : panels;
    const list = [];
    const mergeSearch = v.reduce((pre, cur) => {
      const item = pre[cur.id];
      if (!item) {
        // eslint-disable-next-line no-param-reassign
        pre[cur.id] = deepClone(cur);
      } else {
        item.values = [...item.values, ...cur.values.filter(set => !item.values.some(child => child.id === set.id))];
      }
      return pre;
    }, {});
    const searchList: ISearchItem[] = Object.values(mergeSearch);
    currentPanels.forEach(panel => {
      const listPanel = list.find(item => item.id === panel.id);
      searchList.some(item => {
        if (!item.values?.length) {
          if (panel.id.toString()?.includes?.(item.id) || panel.title.includes(item.id)) {
            !listPanel && list.push({ ...panel });
            return true;
          }
          if (panel.panels?.length) {
            const panels = panel.panels.filter(
              set =>
                set.title?.includes?.(item.id) ||
                set.subTitle?.includes(item.id) ||
                set.id.toString()?.includes(item.id)
            );
            const listPanels = listPanel?.panels || [];
            panels.length &&
              list.push({
                ...panel,
                panels: [...listPanels, ...panels.filter(item => !listPanels.some(set => set.id === item.id))]
              });
          }
          return false;
        }
        if (!hasGroup) {
          if (item.values.some(v => panel.id.toString().includes(v.id) || panel.title.toString().includes(v.name))) {
            list.push({ ...panel });
            return true;
          }
          return false;
        }
        if (panel.id === item.id) {
          list.push({
            ...panel,
            panels: panel.panels?.filter(set =>
              item.values.some(
                val =>
                  set.title?.includes?.(val.id) ||
                  set.subTitle?.includes?.(val.id) ||
                  set.id.toString().includes(val.id)
              )
            )
          });
          return true;
        }
        return false;
      });
    });
    const rowPanel: IPanelModel = list.find(item => item.type === 'row');
    if (rowPanel) rowPanel.collapsed = true;
    this.localPanels = list;
  }
  // 左侧选择栏显示或隐藏触发
  handleSelectPanelActive(v: boolean) {
    this.isSelectPanelActive = v;
  }
  // info栏acitve change
  handleInfoActive(v: boolean) {
    this.infoActive = this.isSplitPanel ? false : v;
  }
  // 立刻刷新
  handleImmediateReflesh() {
    this.refleshImmediate = random(10);
  }
  // 图表布局方式变更
  handleChartChange(layoutId: number) {
    localStorage.setItem(DASHBOARD_PANEL_COLUMN_KEY, layoutId.toString());
    this.columns = layoutId;
  }

  /**
   * @description: 选中host tree的节点
   * @param {ICurNode} node 节点数据
   */
  async handleCheckedNode() {
    this.compares = { targets: [] };
    if (this.compareType === 'target') {
      this.compareType = 'none';
    }
    if (this.sceneData.variables?.length) {
      this.filtersReady = !this.sceneData.hasRequiredVariable;
      this.refleshVariablesKey = random(10);
    }
  }
  // route navbar title change
  // @Emit('titleChange')
  headerTitleChange(v: string, data?: TreeNodeItem) {
    this.currentTitle = v;
    this.$emit('titleChange', v, data);
  }
  /** 主机列表 */
  compareHostchange(list) {
    this.compareHostList = list;
  }

  /** 时间对比值变更 */
  handleCompareTimeChange(timeList: string[]) {
    this.timeOffset = timeList;
    this.handleUpdateViewOptions();
  }
  /** 对比类型变更 */
  handleCompareTypeChange(type: PanelToolsType.CompareId) {
    this.compareType = type;
    this.timeOffset = type === 'time' ? ['1d'] : [];
    this.handleCompareTargetChange();
  }
  /** 目标对比值更新 */
  handleCompareTargetChange(viewOptions?: IViewOptions) {
    this.compares = viewOptions?.compares || { targets: [] };
    this.handleUpdateViewOptions();
  }
  // 汇聚方法改变时触发
  handleMethodChange(v: string) {
    this.method = v;
    this.handleUpdateViewOptions();
  }
  // 刷新间隔设置
  handleIntervalChange(v: string) {
    this.interval = v;
    this.handleUpdateViewOptions();
  }
  // 获取变量
  handleGetVariables(list: FilterDictType): Record<string, any> {
    return list.reduce((pre, cur) => {
      const temp = Object.entries(cur).reduce((total, curItem) => {
        const value = curItem[1];
        // eslint-disable-next-line max-len
        return {
          ...total,
          [curItem[0]]: (Array.isArray(value) ? !!value.length : !!String(value)) ? curItem[1] : undefined
        };
      }, {});
      return { ...pre, ...temp };
    }, {});
  }
  /** 变量值更新 */
  handleFilterVarChange(list: FilterDictType[]) {
    this.handleFilterVarDataReady(list);
    this.handleResizeCollapse();
  }

  /** 变量数据请求完毕 */
  handleFilterVarDataReady(list: FilterDictType[]) {
    /** 统计filter参与过滤的数量 */
    this.filterCount = list.reduce((len, cur) => {
      // eslint-disable-next-line no-param-reassign
      Object.entries(cur).every(item => (Array.isArray(item[1]) ? !!item[1].length : item[1] !== '')) && (len += 1);
      return len;
    }, 0);
    this.variables = this.handleGetVariables(list);
    this.handleUpdateViewOptions();
    this.filtersReady = true;
  }
  /** 更新viewOptions */
  async handleUpdateViewOptions() {
    await this.$nextTick();
    /** 是否存在目标对比 */
    const hasTarget = this.localViewOptions.compares?.targets?.length;
    /** 开启了groups筛选 | 含有目标对比 需要groug_by参数  目标对比时候 需要将group_by进行合集去重操作 */
    if (this.sceneData?.enableGroup || hasTarget) {
      // eslint-disable-next-line max-len
      const targetGroupBy = hasTarget
        ? Object.keys(this.localViewOptions.compares?.targets?.[0] || {}).map(key => key)
        : [];
      const groupsGroupBy = this.sceneData?.enableGroup ? this.groups : [];
      const newGroupBy = [...targetGroupBy, ...groupsGroupBy];
      this.group_by = [...new Set(newGroupBy)];
    } else {
      this.group_by = undefined;
    }
    const targets = deepClone(this.compares?.targets);
    /** 处理存在compare_fields时候的目标数据*/
    let currentTarget = { ...this.filters, ...this.variables };
    let compareTargets = this.compareType === 'target' ? targets : [];
    const selectortTarget = this.sceneData?.selectorPanel?.targets?.[0];
    if (!!selectortTarget?.compareFieldsSort?.length) {
      // eslint-disable-next-line max-len
      currentTarget = selectortTarget?.handleCreateFilterDictValue(
        this.filters,
        true,
        selectortTarget.compareFieldsSort
      );
      // eslint-disable-next-line max-len
      compareTargets = targets?.map(item =>
        selectortTarget?.handleCreateFilterDictValue(item, true, selectortTarget.compareFieldsSort)
      );
    }
    const variables: Record<string, any> = {
      ...this.filters,
      ...this.variables,
      compare_targets: compareTargets?.map(item => this.resetHostFields(item)),
      current_target: this.resetHostFields(currentTarget)
    };
    this.viewOptions = {
      // filter_dict: filterDict,
      ...variables,
      method: this.isEnableMethodSelect ? this.method : 'AVG',
      // eslint-disable-next-line no-nested-ternary
      interval: this.interval || 'auto',
      group_by: this.group_by ? [...this.group_by] : [],
      filters: this.filters
    };
    this.handleResetRouteQuery();
  }
  resetHostFields(target: Record<string, any>) {
    if (!target || !window.host_data_fields?.length) return target;
    return window.host_data_fields.reduce((pre, cur) => ({ ...pre, [cur]: target[cur] }), {});
  }
  handleResetRouteQuery() {
    const filters = {};
    Object.keys(this.variables).forEach(key => {
      filters[`var-${key}`] = this.variables[key];
    });
    Object.keys(this.filters).forEach(key => {
      const value = this.filters[key];
      filters[`filter-${key}`] = typeof value === 'object' ? JSON.stringify(value) : value;
    });

    /** queryData无变更的字段则不同步到路由参数 */
    const queryData = {};
    Object.keys(this.queryData).forEach(key => {
      const isArrayVal = Array.isArray(this.queryData[key]);
      const targetVal = this.queryData[key];
      if (isArrayVal && targetVal.length) {
        queryData[key] = targetVal;
      } else if (!isArrayVal && targetVal !== DEFAULT_QUERY_DATA[key]) {
        queryData[key] = targetVal;
      }
    });
    const queryDataStr = Object.keys(queryData).length ? encodeURIComponent(JSON.stringify(queryData)) : undefined;

    this.$router.replace({
      name: this.$route.name,
      query: {
        ...filters,
        method: this.method,
        interval: this.interval.toString(),
        groups: this.groups,
        dashboardId: this.dashboardId,
        // timeRange: this.timeRange as string,
        from: this.timeRange[0],
        to: this.timeRange[1],
        timezone: this.timezone,
        refleshInterval: this.refleshInterval.toString(),
        // selectorSearchCondition: encodeURIComponent(JSON.stringify(this.selectorSearchCondition)),
        queryData: queryDataStr,
        key: random(10),
        // 详情名称，用于面包屑
        name: this.$route.query?.name,
        sceneId: this.sceneId,
        sceneType: this.localSceneType,
        queryString: this.queryString,
        preciseFilter: String(this.isPreciseFilter) /** 是否开启精准过滤 */,
        compares:
          this.compareType === 'target' && !!this.compares.targets?.length
            ? encodeURIComponent(JSON.stringify(this.compares))
            : undefined /** 目标对比 */,
        timeOffset:
          this.compareType === 'time' && !!this.timeOffset.length
            ? encodeURIComponent(JSON.stringify(this.timeOffset))
            : undefined /** 时间对比 */
      }
    });
  }
  /** 更新viewOptions的值 */
  async handleViewOptionsChange(viewOptions: IViewOptions) {
    this.filtersReady = !this.sceneData.hasRequiredVariable;
    this.compares = viewOptions.compares;
    this.filters = viewOptions.filters;
    this.groups = viewOptions.groups;
    if (this.sceneData.fetchPanel) {
      this.loading = true;
      this.selectorReady = false;
      const panels = await getPanelData(this.sceneData.fetchPanel, viewOptions);
      this.sceneData.updatePanels(panels);
      this.localPanels = this.handleGetLocalPanels(panels);
      this.loading = false;
    }
    this.selectorReady = true;
    this.handleUpdateViewOptions();
    if (this.showMode === 'list') {
      this.showMode = 'default';
    }
  }
  handleDashboardModeChange(v: boolean) {
    this.dashbordMode = v ? 'list' : 'chart';
  }

  handleOverviewChange() {
    this.compareType = 'none';
    this.compares = { targets: [] };
  }

  /** 切换集群的overview模式 */
  async handleClusterOverviewChange(val: boolean) {
    this.localSceneType = val ? 'overview' : 'detail';
    await this.handleTabChange(this.dashboardId);
    if (this.localSceneType === 'overview') {
      this.headerTitleChange(this.$tc('概览'));
    }
  }

  /** groups值变更 */
  handleGroupsChange(groups: string[]) {
    this.groups = groups;
    this.handleUpdateViewOptions();
    this.handleResizeCollapse();
  }

  /** 更新变量区域高度 */
  handleResizeCollapse() {
    this.$nextTick(() => this.collapseRef?.handleContentResize());
  }
  handleRefleshChange(v: number) {
    this.refleshInterval = v;
    this.handleResetRouteQuery();
  }
  handleTimeRangeChange(v: TimeRangeType) {
    this.timeRange = v;
    this.handleResetRouteQuery();
    this.$emit('timeRangeChange', v);
  }
  /** 时区变更 */
  handleTimezoneChange(timezone: string) {
    this.timezone = timezone;
    this.handleResetRouteQuery();
    this.$emit('timezoneChange', timezone);
  }
  handleSelectorPanelChange(viewOptions: IViewOptions) {
    this.selectorReady = true;
    this.handleViewOptionsChange(viewOptions);
  }

  /** 切换集群详情 */
  async handleToClusterDetail(viewOptions: IViewOptions) {
    await this.$nextTick();
    if (this.localSceneType === 'detail') {
      this.handleSelectorPanelChange(viewOptions);
    } else {
      this.handleSelectorPanelChange(viewOptions);
      this.handleTabChange(this.dashboardId);
    }
  }

  /** 宽窄表切换概览/详情 */
  async handleSelectorTableOverviewChange(val: boolean) {
    this.localSceneType = val ? 'overview' : 'detail';
    this.localPanels = [];
    await this.$nextTick();
    const { panels, overview_panels: overviewPanels } = this.sceneData;
    this.localPanels = val ? overviewPanels : panels;
    this.emitLocalSceneTypeChange();
    this.handleUpdateViewOptions();
    if (this.showMode === 'list') {
      this.showMode = 'default';
    }
  }

  handleSelectorPanelSearch(condition) {
    this.selectorSearchCondition = condition;
    this.handleResetRouteQuery();
  }

  /** 处理跳转视图详情 */
  handleLinkToDetail(data: ITableItem<'link'>) {
    this.$router.replace({
      path: `${window.__BK_WEWEB_DATA__?.baseroute || ''}${data.url}`.replace(/\/\//g, '/')
    });
    this.handleSetDefaultParams();
    this.handleTabChange(this.dashboardId);
  }

  /**
   * 集群切换概览视图
   */
  handleBackToOverview() {
    this.dashbordMode = 'chart';
    this.headerTitleChange(this.$tc('概览'));
  }

  /**
   * 1、处理切换tab时候是否需要保留置顶的搜索条件
   * 2、以及k8s选择了集群会在切换时候保留到表格的搜素条件中去
   * 3、未传入toggleTabSearchFilterKeys则切换清空tab
   * @param searchList 搜索条件
   * @returns
   */
  handleTableSearchConditon(searchList: IQueryDataSearch) {
    if (!this.handleKeyValueSearch.length) return [];
    const searchValue = Object.entries(this.filters).reduce((total, item) => {
      const [key, value] = item;
      if (this.toggleTabSearchFilterKeys.includes(key)) {
        total.push({
          [key]: value
        });
      }
      return total;
    }, []);
    const localSearchList = searchList.length ? searchList : searchValue;
    return localSearchList.filter(item => {
      const includeKeys = this.toggleTabSearchFilterKeys;
      const keys = Object.keys(item);
      return includeKeys.includes(keys[0]);
    });
  }

  /**
   * 切换tab操作
   * @param item tab数据项
   */
  async handleMenuTabChange(item: ITabItem) {
    this.queryString = '';
    this.currentTitle = '';
    this.localSceneType = item.type as SceneType;
    if (this.tab2SceneType && item.type === 'detail') {
      this.localSceneType = 'overview';
    }
    this.queryData = {
      ...this.queryData,
      search: this.handleTableSearchConditon(this.queryData.search),
      selectorSearch: [], // tab切换清空侧栏搜索框
      page: 1,
      keyword: '', // 清空搜索输入框
      filter: '', // 清空状态过滤
      sort: '', // 清空置顶排序
      filterDict: {} // 清空表格表头过滤
    };
    if (this.localSceneType === 'overview') {
      if (item.id === 'cluster') {
        this.filters = {};
        this.queryData.search = [];
      }
    }
    this.dashboardId = item.id as string;
    this.handleTabChange(item.id as any);
    if (item.show_panel_count) {
      const data = await getSceneViewList({
        scene_id: this.sceneId,
        type: this.localSceneType
      }).catch(() => []);
      this.tabList.forEach(tab => {
        if (!!tab.panel_count) {
          const count = data.find(d => d.id === tab.id)?.panel_count || 0;
          // eslint-disable-next-line no-param-reassign
          tab.panel_count = count;
        }
      });
    }
  }

  /** 切换精准过滤状态 更新url参数 */
  handlePreciseFilteringChange() {
    this.handleResetRouteQuery();
  }
  // 左侧panel拖拽宽度变化时触发
  handleLeftPanelWidthChange(mode: ShowModeType) {
    const hasChange = this.showMode !== mode;
    if (hasChange) {
      this.showMode = mode;
      this.collapseInfo = true;
    }
    if (mode === 'default') {
      const dashboardPanelEl = this.$el.querySelector('.dashboard-panel-wrap');
      if (!dashboardPanelEl) return;
      const rect = dashboardPanelEl.getBoundingClientRect();
      if (rect.width > 1 && rect.width <= 720) {
        this.collapseInfo = true;
        if (rect.width <= 640) {
          this.showMode = 'list';
        }
      }
    }
  }
  handleDetailShowChange(show: boolean) {
    this.collapseInfo = !show;
  }
  /** 渲染左侧操作栏 contentHeight:左侧栏的内容区域高度 width: 容器的宽度*/
  handleGetSelectPanel(contentHeight: number, width: number) {
    if (!this.sceneData.showSelectPanel) return undefined;
    switch (this.sceneData.selectorPanel.type) {
      case 'topo_tree': // topo类型展示
        return (
          <HostTree
            viewOptions={this.localViewOptions}
            panel={this.sceneData.selectorPanel}
            checkedNode={this.localViewOptions.filters}
            isTargetCompare={this.compareType === 'target'}
            height={contentHeight}
            width={width}
            tabActive={this.sceneData.id}
            statusMapping={this.sceneData.statusMapping}
            onCheckedChange={this.handleCheckedNode}
            onListChange={this.compareHostchange}
            onTitleChange={this.headerTitleChange}
            onChange={this.handleViewOptionsChange}
            onOverviewChange={this.handleOverviewChange}
          />
        );
      case 'apm_topo': // 接口
      case 'apm_exception_topo': // 接口
        return (
          <ApmApiPanel
            height={contentHeight}
            viewOptions={this.localViewOptions}
            panel={this.sceneData.selectorPanel}
            onListChange={this.compareHostchange}
            onTitleChange={this.headerTitleChange}
            onChange={this.handleSelectorPanelChange}
          />
        );
      case 'apm_service_topo': // 接口
        return (
          <CommonTree
            viewOptions={this.localViewOptions}
            panel={this.sceneData.selectorPanel}
            height={contentHeight}
            checkedNode={this.localViewOptions.filters}
            condition={this.selectorSearchCondition}
            onListChange={this.compareHostchange}
            onTitleChange={this.headerTitleChange}
            onChange={this.handleSelectorPanelChange}
            onSearchChange={this.handleSelectorPanelSearch}
          />
        );
      case 'list-cluster': // list类型展示 k8s集群侧栏
        return (
          <CommonListK8s
            viewOptions={this.localViewOptions}
            height={contentHeight}
            panel={this.sceneData.selectorPanel}
            isTargetCompare={this.compareType === 'target'}
            isOverview={this.localSceneType === 'overview'}
            onListChange={this.compareHostchange}
            onTitleChange={this.headerTitleChange}
            onChange={this.handleToClusterDetail}
            onOverviewChange={this.handleClusterOverviewChange}
          />
        );
      case 'list': // list类型展示
        return (
          <CommonList
            ref='commonListRef'
            sceneId={this.sceneId}
            height={contentHeight}
            viewOptions={this.localViewOptions}
            panel={this.sceneData.selectorPanel}
            onCheckedChange={this.handleCheckedNode}
            isTargetCompare={this.compareType === 'target'}
            onListChange={this.compareHostchange}
            onTitleChange={this.headerTitleChange}
            onChange={this.handleSelectorPanelChange}
          />
        );
      case 'target_list': // 含有对比功能的列表 如主机列表
        return (
          <HostList
            panel={this.sceneData.selectorPanel}
            viewOptions={this.localViewOptions}
            height={contentHeight}
            width={width}
            onCheckedChange={this.handleCheckedNode}
            onTitleChange={this.headerTitleChange}
            isTargetCompare={this.compareType === 'target'}
            onListChange={this.compareHostchange}
            onOverviewChange={this.handleOverviewChange}
            onChange={this.handleViewOptionsChange}
          ></HostList>
        );
      case 'table': // 宽窄表
        // case 'apm_topo': // 测试 TODO
        return (
          <CommonSelectTable
            panel={this.sceneData.selectorPanel}
            showMode={this.showMode}
            width={width}
            viewOptions={this.localViewOptions}
            hasOverviewPanels={this.hasOverviewPanels}
            isOverview={this.localSceneType === 'overview'}
            onTitleChange={this.headerTitleChange}
            onChange={this.handleViewOptionsChange}
            onOverviewChange={this.handleSelectorTableOverviewChange}
          />
        );
      default:
        return undefined;
    }
  }
  render() {
    return (
      <div
        class='common-page'
        v-monitor-loading={{ isLoading: this.loading }}
      >
        {this.showK8sGuidePage && (
          <GuidePage
            guideData={introduce.data.k8s.introduce}
            guideId={'k8s'}
          />
        )}
        {this.sceneData && [
          <PageTitle
            class='common-page-title'
            activeTab={this.dashboardId}
            needAddViewBtn={this.sceneData.viewEditable}
            tabList={this.tabList}
            searchData={this.sceneData.searchData}
            searchValue={this.searchValue}
            showSearch={this.sceneData.panelCount > 1 && this.sceneData.searchData.length > 0}
            bookMarkMode={this.sceneData.mode}
            showFilter={!!this.sceneData.variables.length || this.sceneData.enableGroup}
            showSelectPanel={false}
            filterActive={this.filterActive}
            showInfo={false}
            selectPanelActive={this.isSelectPanelActive}
            filterCount={this.filterCount}
            onFilterChange={val => (this.filterActive = val)}
            onSelectPanelChange={this.handleSelectPanelActive}
            onSearchChange={this.handleSearchChange}
            onTabChange={this.handleMenuTabChange}
            onListPanelChange={this.handleDashboardModeChange}
            onAddTab={() => this.handleAddTab('edit-tab')}
          >
            <div
              class='title-content'
              slot='title'
            >
              {this.$slots.nav}
            </div>
            <div slot='tabSetting'>{this.$slots.tabSetting}</div>
            {!this.readonly && !!this.sceneData.alarmPanel && (
              <AlarmTools
                key={this.alarmToolsKey}
                filters={this.filters}
                variables={this.variables}
                panel={this.sceneData.alarmPanel}
                slot='tools'
                style={{ marginRight: '4px' }}
              />
            )}
            <div
              slot='tools'
              class='tools-wrap'
            >
              <DashboardTools
                isSplitPanel={this.isSplitPanel}
                refleshInterval={this.refleshInterval}
                timeRange={this.timeRange}
                timezone={this.timezone}
                showSplitPanel={this.isShowSplitPanel}
                showListMenu={!this.readonly && this.localSceneType !== 'overview'}
                menuList={this.sceneData.dasbordToolMenuList}
                downSampleRange={this.downSampleRange}
                showDownSampleRange={false}
                onImmediateReflesh={this.handleImmediateReflesh}
                onRefleshChange={this.handleRefleshChange}
                onTimeRangeChange={this.handleTimeRangeChange}
                onFullscreenChange={this.handleFullscreen}
                onSplitPanelChange={this.handleSplitPanel}
                onSelectedMenu={this.handleShowSettingModel}
                onDownSampleRangeChange={this.handleDownSampleRangeChange}
                onTimezoneChange={this.handleTimezoneChange}
              >
                {this.$slots.dashboardTools}
              </DashboardTools>
              {!!this.$slots.buttonGroups && <span class='tools-button-groups'>{this.$slots.buttonGroups}</span>}
            </div>
          </PageTitle>,
          <div
            class='common-page-container'
            key={this.selectorPanelKey}
          >
            <keep-alive>
              {this.sceneData.showSelectPanel && this.showSelectPanel && (
                <CommonDetail
                  style={{ display: this.readonly ? 'none' : 'block' }}
                  lineText={''}
                  title={this.$t('列表').toString()}
                  enableResizeListener={true}
                  onShrink={() => (this.isSelectPanelActive = !this.isSelectPanelActive)}
                  onShowChange={show => !show && (this.isSelectPanelActive = false)}
                  toggleSet={this.toggleSet}
                  resetDragPosKey={this.resetDragPosKey}
                  indexList={this.indexList}
                  needOverflow={false}
                  onWidthChange={this.handleLeftPanelWidthChange}
                  showMode={this.showMode}
                  specialDrag={true}
                  scencId={this.sceneId}
                  defaultWidth={this.sceneData.defaultSelectorPanelWidth}
                  scopedSlots={{
                    default: ({ contentHeight, width }) => (
                      <div class={['host-tree-container', 'no-padding']}>
                        {/* 主机树形组件 */}
                        {this.handleGetSelectPanel(contentHeight, width)}
                      </div>
                    )
                  }}
                ></CommonDetail>
              )}
            </keep-alive>
            {this.showMode !== 'list' &&
              this.selectorReady && [
                <div
                  class='dashboard-panel-wrap'
                  ref='dashboardPanelWrap'
                >
                  <div class='dashboard-panel-tools'>
                    {
                      // 变量筛选
                      (!!this.sceneData.variables.length || this.sceneData.enableGroup) && (
                        <div class='dashboard-panel-filter-wrap'>
                          <Collapse
                            ref='collapseRef'
                            expand={this.filterActive}
                            renderAnimation={false}
                            onExpandChange={val => (this.filterActive = val)}
                          >
                            <div class='dashboard-panel-filter-content'>
                              {!!this.sceneData.variables.length && (
                                <FilterVarSelectGroup
                                  ref='filterVarSelectGroupRef'
                                  key={this.sceneData.id + this.refleshVariablesKey}
                                  scencId={this.sceneId}
                                  sceneType={this.localSceneType}
                                  pageId={this.dashboardId}
                                  panelList={this.sceneData.variables}
                                  variables={this.variables}
                                  needAddBtn={this.sceneData.variableEditable}
                                  onChange={this.handleFilterVarChange}
                                  onDataReady={this.handleFilterVarDataReady}
                                  onAddFilter={() => this.handleAddTab('edit-variate')}
                                />
                              )}
                              {this.sceneData.enableGroup ? (
                                <GroupSelect
                                  class='k8s-group-select'
                                  value={Array.isArray(this.groups) ? this.groups : [this.groups]}
                                  scencId={this.sceneId}
                                  pageId={this.dashboardId}
                                  sceneType={this.localSceneType}
                                  panel={this.sceneData.groupPanel}
                                  onChange={this.handleGroupsChange}
                                />
                              ) : undefined}
                            </div>
                          </Collapse>
                        </div>
                      )
                    }
                    {/* 对比、布局、合并视图工具栏 */}
                    {this.isEnablePanelTool && (
                      <PanelTools
                        layoutActive={this.columns}
                        needLayout={this.isEnableColumnsSelect && !this.isSingleChart}
                        needSplit={this.needSplitSwitch}
                        onLayoutChange={this.handleChartChange}
                      >
                        <span
                          slot='prepend'
                          class='panel-tools-prepend'
                        >
                          {this.isEnableIntervalSelect && (
                            <FilterVarSelectSimple
                              value={this.interval}
                              options={PANEL_INTERVAL_LIST}
                              field={'interval'}
                              label={this.$t('汇聚周期')}
                              onChange={this.handleIntervalChange}
                            />
                          )}
                          {this.isEnableMethodSelect && (
                            <FilterVarSelectSimple
                              value={this.method}
                              options={METHOD_LIST.concat(...CP_METHOD_LIST)}
                              field={'method'}
                              label={this.$t('汇聚方法')}
                              onChange={this.handleMethodChange}
                            />
                          )}
                          {this.isShowCompareTool && (
                            <CompareSelect
                              needTargetSelect
                              targetOptions={this.compareHostList}
                              type={this.compareType}
                              compareListEnable={this.compareTypeMap}
                              panel={this.sceneData.selectorPanel}
                              curTarget={this.currentTitle}
                              timeValue={this.compareType === 'time' ? (this.timeOffset as string[]) : undefined}
                              targetValue={this.compareType === 'target' ? this.localViewOptions : undefined}
                              onTimeChange={this.handleCompareTimeChange}
                              onTypeChange={this.handleCompareTypeChange}
                              onTargetChange={this.handleCompareTargetChange}
                            />
                          )}
                          {this.sceneData.isShowPreciseFilter && (
                            <bk-checkbox
                              v-model={this.isPreciseFilter}
                              class='precise-filtering'
                              onChange={this.handlePreciseFilteringChange}
                            >
                              {this.$t('精准过滤')}
                            </bk-checkbox>
                          )}
                        </span>
                      </PanelTools>
                    )}
                  </div>
                  {/* 所有视图无数据提示 如apm视图无数据指引 */}
                  {!!this.$slots.noData && <div class='view-has-no-data-main'>{this.$slots.noData}</div>}
                  {this.filtersReady ? (
                    <DashboardPanel
                      isSingleChart={this.isSingleChart}
                      needOverviewBtn={!!this.sceneData?.list?.length}
                      key={this.sceneData.id}
                      id={this.dashboardPanelId}
                      dashboardId={this.dashboardId}
                      column={this.sceneData.mode === 'custom' ? 'custom' : this.columns + 1}
                      panels={this.dashbordMode === 'chart' ? this.preciseFilteringPanels : this.sceneData.list}
                      // onLinkTo={this.handleUpdateCurrentData}
                      onBackToOverview={this.handleBackToOverview}
                      onLintToDetail={this.handleLinkToDetail}
                    />
                  ) : (
                    <div class='empty-wrapper'>{this.$t('加载中...')}</div>
                  )}
                </div>,
                <div
                  class='split-panel-wrapper'
                  style={{
                    width: `${this.splitPanelWidth}px`,
                    display: this.splitPanelWidth > SPLIT_MIN_WIDTH && this.isSplitPanel ? 'flex' : 'none'
                  }}
                >
                  {this.isSplitPanel ? (
                    <SplitPanel
                      columns={this.columns}
                      dashboardId={this.dashboardPanelId}
                      splitMaxWidth={Math.max(this.splitPanelWidth + 300, SPLIT_MAX_WIDTH)}
                      splitWidth={this.splitPanelWidth}
                      toggleSet={this.toggleSet}
                      defaultViewOptions={this.viewOptions}
                      onDragMove={this.handleDragMove}
                    />
                  ) : undefined}
                </div>
              ]}
            <keep-alive>
              {this.enableDetail && (
                <CommonDetail
                  panel={this.isOverview ? this.sceneData.overviewDetailPanel : this.sceneData.detailPanel}
                  title={this.$tc('详情')}
                  toggleSet={this.toggleSet}
                  startPlacement={'left'}
                  needShrinkBtn={false}
                  placement={'right'}
                  maxWidth={500}
                  collapse={this.collapseInfo}
                  selectorPanelType={this.sceneData?.selectorPanel?.type || ''}
                  onTitleChange={this.headerTitleChange}
                  onLinkToDetail={this.handleLinkToDetail}
                  onShowChange={this.handleDetailShowChange}
                />
              )}
            </keep-alive>
          </div>,
          !this.readonly ? (
            <SettingModal
              show={this.showSetting}
              menuList={this.sceneData.settingMenuList as any}
              activeMenu={this.activeSettingId as string}
              beforeClose={this.handleBeforeCloseSettings}
              onChange={this.toggleSettingModel}
              onMenuChange={this.handleMenuChange}
              zIndex={1999}
            >
              {this.showSetting && (
                <settings-wrapper
                  ref='settingsWrapRef'
                  initAddSetting={this.initAddSetting}
                  active={this.activeSettingId}
                  activeTab={this.dashboardId}
                  viewType={this.localSceneType}
                  sceneId={this.sceneId}
                  bookMarkData={this.tabList}
                  title={this.title}
                  onActiveChange={val => (this.activeSettingId = val)}
                  onPanelChange={val => (this.isPanelChange = val)}
                />
              )}
            </SettingModal>
          ) : undefined
        ]}
      </div>
    );
  }
}
