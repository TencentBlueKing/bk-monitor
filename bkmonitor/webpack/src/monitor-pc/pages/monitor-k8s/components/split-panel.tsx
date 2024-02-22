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
import { Component, Emit, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorDrag from '../../../../fta-solutions/pages/event/monitor-drag';
import { queryCustomEventGroup } from '../../../../monitor-api/modules/custom_report';
import { getSceneView, getSceneViewList } from '../../../../monitor-api/modules/scene_view';
import { LANGUAGE_COOKIE_KEY } from '../../../../monitor-common/utils';
import bus from '../../../../monitor-common/utils/event-bus';
import { docCookies, random } from '../../../../monitor-common/utils/utils';
import { DEFAULT_METHOD } from '../../../../monitor-ui/chart-plugins/constants';
import { BookMarkModel, IPanelModel, IViewOptions } from '../../../../monitor-ui/chart-plugins/typings';
import { IntervalType } from '../../../components/cycle-input/typings';
import FilterVarSelectGroup from '../../monitor-k8s/components/filter-var-select/filter-var-select-group';
import GroupSelect from '../../monitor-k8s/components/group-select/group-select';
import { FilterDictType } from '../../performance/performance-detail/host-tree/host-tree';
import { SceneType, SPLIT_MAX_WIDTH, SPLIT_MIN_WIDTH, SPLIT_PANEL_LIST, SplitPanelModel } from '../typings';

import './split-panel.scss';

interface ISplitPanelProps {
  // 分屏最大宽度
  splitMaxWidth?: number;
  // 分屏最小宽度
  splitMinWidth?: number;
  // 主框架上的menu是否缩进
  toggleSet?: boolean;
  // 是否需要拖拽
  needDrag?: boolean;
  // 默认分屏关联页面
  defaultRelated?: string;
  // 默认分屏dashboard ID
  dashboardId?: string;
  // 默认viewOptions
  defaultViewOptions?: IViewOptions;
  // 初始分屏宽度
  splitWidth?: number;
  // 图表布局
  columns?: number;
}
interface ISplitPanelEvent {
  // 拖拽时触发事件
  onDragMove: number;
}

type IDashbordMode = 'list' | 'chart';
@Component({
  components: {
    Event: () => import('../../../../fta-solutions/pages/event/event'),
    DashboardPanel: () => import('../../../../monitor-ui/chart-plugins/components/dashboard-panel')
  }
})
export default class SplitPanel extends tsc<ISplitPanelProps, ISplitPanelEvent> {
  // 分屏最大宽度
  @Prop({ default: SPLIT_MAX_WIDTH, type: Number }) readonly splitMaxWidth: number;
  // 分屏最小宽度
  @Prop({ default: SPLIT_MIN_WIDTH, type: Number }) readonly splitMinWidth: number;
  // 主框架上的menu是否缩进
  @Prop({ default: false, type: Boolean }) readonly toggleSet: boolean;
  // 是否需要拖拽
  @Prop({ default: true, type: Boolean }) readonly needDrag: boolean;
  // 默认分屏关联页面
  @Prop({ default: '', type: String }) readonly defaultRelated: string;
  // 默认分屏dashboard ID
  @Prop({ default: random(10), type: String }) readonly dashboardId: string;
  // 默认viewOptions
  @Prop({ default: () => ({}), type: Object }) readonly defaultViewOptions?: IViewOptions;
  // 初始分屏宽度
  @Prop({ default: SPLIT_MIN_WIDTH, type: Number }) readonly splitWidth: number;
  // 图表布局
  @Prop({ default: 0, type: Number }) readonly columns: number;

  // 关联页面 scene_id
  relatePage = 'host';
  // 特殊中间层关联列表  如 自定义事件列表 采集列表 自定义指标列表 等
  relateMiddlewareList = [];
  relateMiddlewareId = '';
  // 关联tab选项
  relateTab = '';
  // 关联页面tab列表
  relateTabList = [];
  // panels
  localPanels: IPanelModel[] = [];
  // sceneType
  sceneType: SceneType = 'detail';
  // 是否刷新变量
  refleshVariablesKey: string = random(10);
  sceneData: BookMarkModel = null;
  loading = false;
  // 图表特殊配置项
  variables: Record<string, any> = {};
  group_by: string[] = [];
  method = '';
  interval: IntervalType = 'auto';
  // 变量是否已经获取完毕
  filtersReady = false;
  /** groups筛选的维度值 */
  groupsGroupBy: string[] = [];
  // 判断新开页按钮的样式为简易/完整
  isSimple = false;

  dashbordMode: IDashbordMode = 'chart';

  // 分屏内独立的viewotions
  @ProvideReactive('viewOptions') viewOptions: IViewOptions = {};

  // 分屏页面列表 拍平处理
  get flatPageList(): SplitPanelModel[] {
    return SPLIT_PANEL_LIST.reduce((pre, cur) => (pre.push(...cur.children), pre), []);
  }
  // 选中的分屏页面
  get activePage(): SplitPanelModel {
    return this.flatPageList.find(item => item.id === this.relatePage);
  }
  // 场景id
  get sceneId() {
    if (['custom_event'].includes(this.relatePage)) {
      return `${this.relatePage}_${this.relateMiddlewareId}`;
    }
    return this.relatePage;
  }
  @Watch('defaultViewOptions.interval')
  onIntervalChange() {
    if (this.defaultViewOptions.interval) {
      this.interval = this.defaultViewOptions.interval as IntervalType;
      this.handleUpdateViewOptions();
    }
  }
  created() {
    this.variables = { ...this.defaultViewOptions.variables, ...this.defaultViewOptions.filters };
    this.group_by = [...this.defaultViewOptions.group_by];
    this.interval = this.defaultViewOptions.interval as IntervalType;
    this.method = this.defaultViewOptions.method;

    // 默认支持打开关联查看的页面 default host
    this.relatePage = this.defaultRelated || 'host';
    this.handleRelatePageChange(this.relatePage);
    this.handleUpdateViewOptions();
    bus.$on('dashboardModeChangeInSplitPanel', this.handleDashboardModeChange);
  }
  beforeDestroy() {
    bus.$off('dashboardModeChangeInSplitPanel', this.handleDashboardModeChange);
  }
  @Watch('splitWidth', { immediate: true })
  handleSplitWidth(v: number) {
    this.isSimple = v < 800;
  }

  @Emit('dragMove')
  handleDragMove(v: number) {
    return v;
  }
  handleDashboardModeChange(type: IDashbordMode) {
    this.dashbordMode = type;
  }
  /** 关联页面变更 */
  async handleRelatePageChange(pageId: string) {
    this.loading = true;
    this.sceneData = null;
    this.relatePage = pageId;
    this.relateTabList = [];
    this.relateTab = '';
    this.relateMiddlewareList = [];
    this.relateMiddlewareId = '';
    this.localPanels = [];
    this.filtersReady = false;
    this.dashbordMode = 'chart';
    await this.$nextTick();
    if (this.activePage.contentType === 'dashboard') {
      if (this.activePage.id === 'custom_event') {
        // 获取自定义事件列表
        const { list = [] } = await queryCustomEventGroup({
          page: 1,
          page_size: 1000
        }).catch(() => ({ total: 0, list: [] }));
        this.relateMiddlewareList = list.map(item => ({ id: item.bk_event_group_id, name: item.name }));
        this.relateMiddlewareId = this.relateMiddlewareList[0]?.id;
      }
      await this.handleMiddlewareChange(this.relateMiddlewareId);
    } else {
      this.filtersReady = true;
    }
    this.loading = false;
  }
  // 分屏中间页面层级变化时触发
  async handleMiddlewareChange(middlewareId: string) {
    this.loading = true;
    this.relateTabList = [];
    this.relateTab = '';
    this.relateMiddlewareId = middlewareId;
    this.localPanels = [];
    this.filtersReady = false;
    this.sceneData = null;
    this.dashbordMode = 'chart';
    const data = await getSceneViewList({ scene_id: this.sceneId, type: 'detail' }).catch(() => []);
    this.relateTabList = (data || []).map(item => ({
      ...item,
      name:
        docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en'
          ? item.id
          : item.name + (item.type === 'overview' ? this.$t('概览') : this.$t('详情'))
    }));
    if (data.length) {
      const [{ id, type }] = this.relateTabList;
      await this.handleRelateTabChange(`${id}_${type}`);
    }
    this.loading = false;
  }
  /** 关联页面tab变更 */
  async handleRelateTabChange(relateTabId: string) {
    if (!relateTabId) return;
    this.dashbordMode = 'chart';
    this.relateTab = relateTabId;
    const [, sceneType] = relateTabId.split('_');
    this.sceneType = sceneType as SceneType;
    await this.handleGetSceneView();
  }
  /**
   * @description: 获取分屏视图
   * @param {string} id 视图id
   * @param {string} type
   */
  async handleGetSceneView() {
    this.loading = true;
    const [id, type] = this.relateTab.split('_');
    const data = await getSceneView({
      scene_id: this.sceneId,
      type,
      id,
      is_split: true
    }).catch(() => ({ id: '', panels: [], name: '' }));
    this.sceneData = new BookMarkModel(data || { id: '', panels: [], name: '' });
    this.localPanels = this.handleGetLocalPanels(this.sceneData.panels);
    this.filtersReady = !this.sceneData.hasRequiredVariable;
    this.loading = false;
  }

  /** 变量值更新 */
  handleFilterVarChange(list: FilterDictType[]) {
    this.handleFilterVarDataReady(list);
  }

  /** 变量数据请求完毕 */
  handleFilterVarDataReady(list: FilterDictType[]) {
    this.variables = {
      /** 过滤空字符串、空数组的变量值 */
      ...list.reduce((pre, cur) => ({ ...pre, ...cur }), {})
    };
    this.handleUpdateViewOptions();
    this.filtersReady = true;
  }

  /** 更新viewOptions */
  handleUpdateViewOptions() {
    /** 开启了groups筛选 | 含有目标对比 需要groug_by参数  目标对比时候 需要将group_by进行合集去重操作 */
    if (this.sceneData?.enableGroup) {
      const groupsGroupBy = this.sceneData?.enableGroup ? this.groupsGroupBy : [];
      const newGroupBy = [...groupsGroupBy];
      this.group_by = [...new Set(newGroupBy)];
    } else {
      this.group_by = undefined;
    }
    this.viewOptions = {
      variables: {
        ...this.viewOptions.filters,
        ...this.variables
      },
      interval: this.interval,
      method: this.method || DEFAULT_METHOD,
      group_by: this.group_by ? [...this.group_by] : []
    };
  }
  handleGetLocalPanels(panels: IPanelModel[]) {
    /** 处理只有未分组数据时候的panels */
    if (panels.length === 1 && panels[0].id === '__UNGROUP__') {
      return panels[0].panels;
    }
    return panels;
  }

  // 跳转到新页
  handleNewPage() {
    const url = `${location.origin}${location.pathname}${location.search}`;
    const { current_target } = this.variables;
    const urlMap = {
      host: `${url}#/performance/detail/${current_target?.bk_target_ip || 0}-${
        current_target?.bk_target_cloud_id || 0
      }`,
      kubernetes: `${url}#/k8s?dashboardId=${this.relateTab.replace(`_${this.sceneType}`, '')}`,
      alert_event: `${url}#/event-center`,
      action_event: `${url}#/event-center?searchType=action&activeFilterId=action`,
      custom_event: `${url}#/custom-escalation-event-view/${this.relateMiddlewareId}`
    };
    window.open(urlMap[this.relatePage]);
  }

  // 作为新页面打开
  newPageBtn() {
    return (
      <span class='new-page-btn'>
        {<span class='btn-text'>{this.$t('新开页')}</span>}
        {/* <span class="icon-monitor icon-fenxiang"></span> */}
      </span>
    );
  }

  filterComponent() {
    return (
      <div class='filter-content'>
        {this.activePage.hasFilter && this.sceneData && (
          <div class='filter-row'>
            {!!this.sceneData.variables?.length && (
              <FilterVarSelectGroup
                key={this.sceneData.id + this.refleshVariablesKey}
                scencId={this.relatePage}
                sceneType={this.sceneType}
                pageId={this.relateTab.replace(/_(detail|overview)$/gim, '')}
                variables={this.variables}
                panelList={this.sceneData.variables}
                onChange={this.handleFilterVarChange}
                onDataReady={this.handleFilterVarDataReady}
              />
            )}
            {this.sceneData.enableGroup && (
              <div class='group-column'>
                <div class='split-line'></div>
                <GroupSelect
                  class='k8s-group-select'
                  value={this.groupsGroupBy}
                  scencId={this.relatePage}
                  pageId={this.relateTab.replace(/_(detail|overview)$/gim, '')}
                  sceneType={this.sceneType}
                />
              </div>
            )}
          </div>
        )}
        {this.activePage.hasSearchInput && (
          <bk-input
            placeholder={this.$t('搜索并筛选')}
            class='filter-content-input'
            right-icon={'bk-icon icon-search'}
          />
        )}
      </div>
    );
  }
  // 内容区显示判断
  contentComponent() {
    if (!this.filtersReady) return <div class='monitor-loading-wrap'>{this.$t('加载中...')}</div>;
    switch (this.activePage.contentType) {
      case 'dashboard': // 视图类型
        return (
          this.sceneData && (
            <DashboardPanel
              isSplitPanel={true}
              key={this.sceneData.id}
              id={this.dashboardId}
              column={this.sceneData.mode === 'custom' ? 'custom' : this.columns + 1}
              panels={this.dashbordMode === 'chart' ? this.localPanels : this.sceneData.list}
            />
          )
        );
      case 'event': // 事件类型 即事件的分屏页面
        return (
          <Event
            isSplitEventPanel={true}
            defaultParams={this.activePage.defaultParams}
          />
        );
      default:
        return;
    }
  }

  render() {
    return (
      <div
        class='split-panel'
        v-monitor-loading={{ isLoading: this.loading }}
      >
        <div class='split-panel-tools'>
          <div class='associate-query'>
            <span class='query-label mr10'>{this.$t('关联查看')}</span>
            <bk-select
              class='bk-select-simplicity query-select'
              ext-popover-cls='associate-view-popover'
              clearable={false}
              behavior='simplicity'
              v-model={this.relatePage}
              onChange={this.handleRelatePageChange}
            >
              {SPLIT_PANEL_LIST.map((group, index) => (
                <bk-option-group
                  name={group.name}
                  key={index}
                  show-count={false}
                >
                  {group.children.map(option => (
                    <bk-option
                      key={option.id}
                      id={option.id}
                      name={option.name}
                    ></bk-option>
                  ))}
                </bk-option-group>
              ))}
            </bk-select>
            {!!this.relateMiddlewareList?.length && (
              <bk-select
                class='bk-select-simplicity query-select'
                v-model={this.relateMiddlewareId}
                clearable={false}
                behavior='simplicity'
                onChange={this.handleMiddlewareChange}
              >
                {this.relateMiddlewareList.map(option => (
                  <bk-option
                    key={option.id}
                    id={option.id}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-select>
            )}
            {this.relateTabList?.length > 0 && (
              <bk-select
                class='bk-select-simplicity query-select'
                v-model={this.relateTab}
                clearable={false}
                behavior='simplicity'
                onChange={this.handleRelateTabChange}
              >
                {this.relateTabList.map(option => (
                  <bk-option
                    key={`${option.id}_${option.type}`}
                    id={`${option.id}_${option.type}`}
                    name={option.name}
                  ></bk-option>
                ))}
              </bk-select>
            )}
            <span
              class='view-detail-link mr10'
              onClick={this.handleNewPage}
            >
              {this.newPageBtn()}
            </span>
          </div>
          {this.filterComponent()}
        </div>
        <div class='split-panel-content'>{this.contentComponent()}</div>
        <MonitorDrag
          startPlacement='left'
          minWidth={this.splitMinWidth}
          maxWidth={this.splitMaxWidth}
          toggleSet={this.toggleSet}
          on-move={this.handleDragMove}
        />
      </div>
    );
  }
}
