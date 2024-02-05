/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { Component, Emit, Inject, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce, deepClone } from '../../../../../monitor-common/utils/utils';
import StatusTab from '../../../../../monitor-ui/chart-plugins/plugins/table-chart/status-tab';
import { IViewOptions, PanelModel } from '../../../../../monitor-ui/chart-plugins/typings';
import { VariablesService } from '../../../../../monitor-ui/chart-plugins/utils/variable';
import type { TimeRangeType } from '../../../../components/time-range/time-range';
import { handleTransformToTimestamp } from '../../../../components/time-range/utils';
import { IQueryData, IQueryDataSearch } from '../../typings';
import {
  filterSelectorPanelSearchList,
  transformConditionValueParams,
  transformQueryDataSearch,
  updateBkSearchSelectName
} from '../../utils';
import CommonStatus from '../common-status/common-status';

import './apm-api-panel.scss';

interface ICommonListProps {
  // panel实例
  panel: PanelModel;
  // 视图数据参数配置
  viewOptions: IViewOptions;
  height?: number;
}

interface ICommonListEvent {
  // 选中列表行数据触发
  onChange: IViewOptions;
  // 标题修改触发
  onTitleChange: string;
  // get list
  onListChange: Record<string, any>[];
}
export interface ITabItem {
  name: string;
  id: string;
  tips: string;
  status: string;
}
@Component
export default class ApmTopo extends tsc<ICommonListProps, ICommonListEvent> {
  /** 当前输入的viewOptions数据 */
  @Prop({ type: Object }) viewOptions: IViewOptions;
  /** 接口数据 */
  @Prop({ type: Object }) panel: PanelModel;
  @Prop({ type: Number }) height: number;
  @InjectReactive('timeRange') readonly timeRange!: TimeRangeType;
  @InjectReactive('width') readonly width!: number;
  /** 侧栏搜索条件 */
  @InjectReactive('queryData') readonly queryData!: IQueryData;
  /** 侧栏搜索条件更新url方法 */
  @Inject('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;
  /** 状态筛选 */
  currentStatus = 'all';
  keyword = '';
  /** 列表带过来的filter过滤 */
  filter = '';
  loading = false;
  list: Record<string, any>[] = [];

  /** checkbox filter */
  checkboxDict: string[] = [];

  /** 状态可选项 */
  statusList = [];

  /** 搜索条件可选项 */
  conditionList = [];
  /** 搜索条件 - 后端搜索 */
  searchCondition = [];

  // 选项卡列表
  tabList: ITabItem[] = [];
  // 选中的选项卡
  activeTab = '';
  /** 过滤已选得搜索条件 */
  get currentConditionList() {
    return filterSelectorPanelSearchList(this.conditionList, this.searchCondition);
  }
  // scoped 变量
  get scopedVars() {
    return {
      ...(this.viewOptions || {}),
      ...(this.viewOptions?.filters || {}),
      ...(this.viewOptions?.current_target || [])
    };
  }
  // active id
  get activeId() {
    return this.panel.targets?.[0]?.handleCreateItemId?.(this.scopedVars, true, undefined, '|') || '';
  }

  get localList() {
    if (this.conditionList.length) {
      return this.list.filter(item => (this.currentStatus === 'all' ? true : item.status?.type === this.currentStatus));
    }
    if (!this.list?.length) return [];
    const localList = this.list.filter(item =>
      (item.name.includes(this.keyword) || item.id.toString().includes(this.keyword)) && this.currentStatus === 'all'
        ? true
        : item.status?.type === this.currentStatus
    );
    if (localList.some(item => item.metric?.[this.activeTab]?.percent)) {
      return localList.sort(
        (a, b) =>
          +b.metric[this.activeTab].percent.replace('%', '') - +a.metric[this.activeTab].percent.replace('%', '')
      );
    }
    return localList;
  }

  /** 是否需要更新表格搜索条件到url */
  get needQueryUpdateUrl() {
    return this.panel.options?.selector_list?.query_update_url || false;
  }

  @Watch('timeRange')
  // 数据时间间隔
  handleTimeRangeChange() {
    this.getPanelData();
  }

  @Watch('width')
  handleWidthChange() {
    (this.$refs.virtualInstance as any)?.resize();
  }
  @Watch('height')
  handleHeightChange() {
    (this.$refs.virtualInstance as any)?.resize();
  }
  @Watch('queryData.selectorSearch', { immediate: true })
  conditionChange(search: IQueryDataSearch) {
    this.searchCondition = updateBkSearchSelectName(this.conditionList, transformQueryDataSearch(search || []));
  }
  @Watch('queryData.keyword', { immediate: true })
  keywordChange(val: string) {
    this.keyword = val || '';
  }
  @Watch('queryData.filter', { immediate: true })
  filterChange(val: string) {
    this.filter = val || '';
  }
  @Watch('queryData.checkboxs', { immediate: true })
  checkboxChange(val: string[]) {
    this.checkboxDict = val;
  }
  @Watch('localList')
  handleLocalListChange() {
    this.handleSetList();
  }
  mounted() {
    this.getPanelData();
  }

  // 获取列表数据
  async getPanelData() {
    this.loading = true;
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService(this.scopedVars);
    const checkFilters =
      this.checkboxDict?.reduce((pre, cur) => {
        // eslint-disable-next-line no-param-reassign
        pre[cur] = true;
        return pre;
      }, {}) || undefined;
    const promiseList = this.panel.targets.map(item =>
      (this as any).$api[item.apiModule]
        [item.apiFunc]({
          ...variablesService.transformVariables(item.data),
          condition_list: transformConditionValueParams(this.searchCondition),
          filter: this.filter === 'all' ? '' : this.filter,
          keyword: this.keyword,
          start_time: startTime,
          end_time: endTime,
          ...checkFilters
        })
        .then(data => {
          const list = Array.isArray(data) ? data : data.data;
          this.conditionList = data.condition_list || [];
          this.searchCondition = updateBkSearchSelectName(this.conditionList, this.searchCondition);
          this.statusList = data.filter || [];
          this.tabList = data.sort || [];
          if (!this.activeTab && data.sort?.length) {
            this.activeTab = data.sort[0].id || '';
          }
          return list?.map?.(set => {
            const id = item.handleCreateItemId(set, false, undefined, '|') || set.id;
            return {
              ...set,
              id,
              name: set.name || id
            };
          });
        })
    );
    const [data] = await Promise.all(promiseList).catch(() => [[]]);
    this.list = data;
    if (this.activeId === '' && this.list[0]) {
      this.handleSelect(this.list[0]);
    }
    this.$emit('listChange', this.list.slice());
    const checkedItem = this.list.find(item => item.id === this.activeId);
    this.handleTitleChange(checkedItem ? checkedItem.name : this.list[0]?.name || '');
    this.handleSetList();
    this.loading = false;
  }
  handleSetList() {
    setTimeout(() => {
      (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
    }, 20);
  }
  handleSearch() {
    this.getPanelData();
    const selectorSearch = transformConditionValueParams(this.searchCondition);
    if (this.needQueryUpdateUrl) {
      this.handleUpdateQueryData({
        ...this.queryData,
        selectorSearch
      });
    }
  }
  @Debounce(300)
  handleLocalSearch(v: string) {
    this.keyword = v;
    this.getPanelData();
    if (this.needQueryUpdateUrl) {
      this.handleUpdateQueryData({
        ...this.queryData,
        keyword: v
      });
    }
  }
  handleRefresh() {
    this.getPanelData();
  }
  handleSelect(data: Record<string, any>) {
    if (this.activeId === data?.id) return;
    const viewOptions = deepClone(this.viewOptions) as IViewOptions;
    const value = this.panel.targets[0].handleCreateFilterDictValue(data);
    viewOptions.filters = { ...(value || {}) };
    viewOptions.compares = {
      targets: []
    };
    this.handleTitleChange(data.name);
    this.$emit('change', viewOptions);
  }
  @Emit('titleChange')
  handleTitleChange(title: string) {
    return title;
  }

  /** 获取数量值 */
  formaterCount(data) {
    const isValid = val => !!val || val === 0;
    if (isValid(data.metric?.[this.activeTab]?.value)) {
      return data.metric?.[this.activeTab]?.value;
    }
    if (isValid(data.count)) {
      return data.count;
    }
    return '';
  }

  /** 筛选组件 */
  handleStatusFilter() {
    this.$nextTick(() => {
      (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
    });
  }
  handleTabChange(name: string) {
    this.activeTab = name;
  }
  render() {
    return (
      <div
        class='apm-api-panel'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='list-header'>
          {!!this.conditionList.length ? (
            <bk-search-select
              placeholder={this.$t('搜索')}
              vModel={this.searchCondition}
              show-condition={false}
              data={this.currentConditionList}
              show-popover-tag-change={false}
              onChange={this.handleSearch}
            />
          ) : (
            <bk-input
              v-model={this.keyword}
              right-icon='bk-icon icon-search'
              placeholder={this.$t('搜索')}
              onInput={this.handleLocalSearch}
            ></bk-input>
          )}
          <bk-button
            class='reflesh-btn'
            onClick={this.handleRefresh}
          >
            <i class='icon-monitor icon-shuaxin'></i>
          </bk-button>
        </div>
        {!!this.statusList.length && (
          <StatusTab
            class='status-tab'
            v-model={this.currentStatus}
            statusList={this.statusList}
            onChange={this.handleStatusFilter}
          ></StatusTab>
        )}
        {!!this.tabList.length && (
          <bk-tab
            class='list-tab'
            type='unborder-card'
            labelHeight={42}
            on-tab-change={this.handleTabChange}
            active={this.activeTab}
          >
            {this.tabList.map(tab => (
              <bk-tab-panel
                name={tab.id}
                key={tab.id}
                label={tab.name}
              ></bk-tab-panel>
            ))}
          </bk-tab>
        )}
        <div class='list-wrapper'>
          {this.localList?.length ? (
            <bk-virtual-scroll
              ref='virtualInstance'
              item-height={36}
              scopedSlots={{
                default: ({ data }) => (
                  <div
                    onClick={() => this.handleSelect(data)}
                    style={{ '--percent': data.metric?.[this.activeTab]?.percent || data.percent || '0%' }}
                    class={[`list-wrapper-item ${data.id === this.activeId ? 'item-active' : ''}`]}
                  >
                    {!!data.status?.type && (
                      <CommonStatus
                        class='status-icon'
                        type={data.status.type}
                      ></CommonStatus>
                    )}
                    <span class='item-name'>{data.name || '--'}</span>
                    <span class='item-count'>{this.formaterCount(data)}</span>
                  </div>
                )
              }}
            ></bk-virtual-scroll>
          ) : (
            <bk-exception
              class='exception-part'
              type='search-empty'
              scene='part'
            />
          )}
        </div>
      </div>
    );
  }
}
