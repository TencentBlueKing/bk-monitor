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
import { Component, Emit, Inject, InjectReactive, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc, modifiers } from 'vue-tsx-support';

import { Debounce, deepClone } from '../../../../../monitor-common/utils/utils';
import StatusTab from '../../../../../monitor-ui/chart-plugins/plugins/table-chart/status-tab';
import { IViewOptions, PanelModel } from '../../../../../monitor-ui/chart-plugins/typings';
import { VariablesService } from '../../../../../monitor-ui/chart-plugins/utils/variable';
import EmptyStatus from '../../../../components/empty-status/empty-status';
import { EmptyStatusOperationType, EmptyStatusType } from '../../../../components/empty-status/types';
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

import './common-list.scss';

interface ICommonListProps {
  // 场景id
  sceneId: string;
  // panel实例
  panel: PanelModel;
  // 视图数据参数配置
  viewOptions: IViewOptions;
  // 是否为目标对比
  isTargetCompare: boolean;
  height?: number;
  isCustomGePanelData?: boolean;
}

interface ICommonListEvent {
  // 选中列表行数据触发
  onChange: IViewOptions;
  // 标题修改触发
  onTitleChange: string;
  // get list
  onListChange: Record<string, any>[];
  // 选中一个item
  onCheckedChange: void;
}

@Component
export default class CommonList extends tsc<ICommonListProps, ICommonListEvent> {
  /** 当前输入的viewOptions数据 */
  @Prop({ type: Object }) viewOptions: IViewOptions;
  /** 接口数据 */
  @Prop({ type: Object }) panel: PanelModel;
  /** 是否为目标对比 */
  @Prop({ default: false, type: Boolean }) isTargetCompare: boolean;
  @Prop({ type: Number }) height: number;
  /** 外部自定义请求数据 */
  @Prop({ type: Boolean, default: false }) isCustomGePanelData: boolean;
  @Prop({ type: String, default: '' }) sceneId: string;
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
  emptyType: EmptyStatusType = 'empty';

  /** 状态可选项 */
  statusList = [];

  /** 搜索条件可选项 */
  conditionList = [];
  /** 搜索条件 - 后端搜索 */
  searchCondition = [];

  /** 目标对比选中的目标数据 */
  localCompareTargets = [];

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
    return this.panel.targets?.[0]?.handleCreateItemId?.(this.scopedVars, true) || '';
  }

  get localList() {
    if (this.conditionList.length) {
      return this.list.filter(item => (this.currentStatus === 'all' ? true : item.status?.type === this.currentStatus));
    }
    if (!this.list?.length) return [];
    // if (!this.keyword.length) return this.list;
    return this.list.filter(item =>
      (item.name.includes(this.keyword) || item.id.toString().includes(this.keyword)) && this.currentStatus === 'all'
        ? true
        : item.status?.type === this.currentStatus
    );
  }

  /** 目标对比选中的主机id */
  get compareTargets() {
    // eslint-disable-next-line max-len
    return (
      this.viewOptions?.compares?.targets?.map(item => this.panel.targets?.[0]?.handleCreateItemId(item, true)) || []
    );
  }

  /** 是否启用状态筛选组件 */
  get isEnableStatusFilter() {
    return this.panel.options?.selector_list?.status_filter ?? false;
  }

  @Watch('compareTargets')
  compareTargetsChange() {
    this.localCompareTargets = deepClone(this.viewOptions?.compares?.targets || []);
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

  mounted() {
    !this.isCustomGePanelData && this.getPanelData();
  }

  /** 自定义发起请求的方法请求 */
  customGetPanelData(needLoading = false): Promise<any> {
    return this.getPanelData(needLoading);
  }

  // 获取列表数据
  async getPanelData(needLoading = true) {
    needLoading && (this.loading = true);
    const [startTime, endTime] = handleTransformToTimestamp(this.timeRange);
    const variablesService = new VariablesService(this.scopedVars);
    this.emptyType = this.keyword ? 'search-empty' : 'empty';
    const promiseList = this.panel.targets.map(item =>
      (this as any).$api[item.apiModule]
        [item.apiFunc]({
          ...variablesService.transformVariables(item.data),
          start_time: startTime,
          end_time: endTime,
          condition_list: transformConditionValueParams(this.searchCondition),
          filter: this.filter === 'all' ? '' : this.filter,
          keyword: this.keyword
        })
        .then(data => {
          const list = Array.isArray(data) ? data : data.data;
          this.conditionList = data.condition_list || [];
          this.searchCondition = updateBkSearchSelectName(this.conditionList, this.searchCondition);
          this.statusList = data.filter || [];
          return list?.map?.(set => {
            const id = item.handleCreateItemId(set) || set.id;
            return {
              ...set,
              id,
              name: set.name || id
            };
          });
        })
    );
    const [data] = await Promise.all(promiseList).catch(() => {
      this.emptyType = '500';
      return [[]];
    });
    this.list = data;
    if (this.activeId === '' && this.list[0]) {
      this.handleSelect(this.list[0]);
    }
    this.$emit('listChange', this.list.slice());
    const checkedItem = this.list.find(item => item.id === this.activeId);
    this.handleTitleChange(checkedItem ? checkedItem.name : this.list[0]?.name || '');
    setTimeout(() => {
      (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
    }, 20);
    needLoading && (this.loading = false);
  }

  handleSearch() {
    this.getPanelData();
    const selectorSearch = transformConditionValueParams(this.searchCondition);
    this.handleUpdateQueryData({
      ...this.queryData,
      selectorSearch
    });
  }
  @Debounce(300)
  handleLocalSearch(v: string) {
    this.keyword = v;
    this.emptyType = v ? 'search-empty' : 'empty';
    // 部分场景已支持接口搜索关键字过滤 其余保留前端搜索
    if (this.sceneId === 'apm_service') {
      this.getPanelData();
    } else {
      (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
    }
    this.handleUpdateQueryData({
      ...this.queryData,
      keyword: v
    });
  }
  handleRefresh() {
    this.getPanelData();
  }
  handleSelect(data: Record<string, any>) {
    if (this.activeId === data?.id) return;
    const viewOptions = deepClone(this.viewOptions) as IViewOptions;
    const value = this.panel.targets[0].handleCreateCompares(data);
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

  /** 点击列表进行目标对比 */
  handleAddCompare(item) {
    const value = this.panel.targets?.[0]?.handleCreateCompares(item);
    this.localCompareTargets.push(value);
    const viewOptions: IViewOptions = {
      ...this.viewOptions,
      compares: {
        targets: this.localCompareTargets
      }
    };
    this.$emit('change', viewOptions);
  }

  /** 筛选组件 */
  handleStatusFilter() {
    this.$nextTick(() => {
      (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
    });
  }

  @Emit('checkedChange')
  handleSelectedItem(data: Record<string, any>) {
    this.handleSelect(data);
  }

  handleOperation(type: EmptyStatusOperationType) {
    if (type === 'refresh') {
      this.getPanelData();
      return;
    }

    if (type === 'clear-filter') {
      this.keyword = '';
      this.getPanelData();
      return;
    }
  }
  render() {
    return (
      <div
        class='common-panel-list'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='list-header'>
          {this.conditionList.length ? (
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
        {this.isEnableStatusFilter && (
          <StatusTab
            class='status-tab'
            v-model={this.currentStatus}
            statusList={this.statusList}
            onChange={this.handleStatusFilter}
          ></StatusTab>
        )}
        <div class='list-wrapper'>
          {this.localList?.length ? (
            <bk-virtual-scroll
              ref='virtualInstance'
              item-height={32}
              scopedSlots={{
                default: ({ data }) => {
                  const itemId = this.panel.targets[0]?.handleCreateItemId(data);
                  return (
                    <div
                      onClick={() => this.handleSelectedItem(data)}
                      class={[
                        `list-wrapper-item ${data.id === this.activeId ? 'item-active' : ''}`,
                        {
                          'checked-target': this.isTargetCompare && this.compareTargets.includes(itemId)
                        }
                      ]}
                    >
                      {!!data.status?.type && (
                        <CommonStatus
                          class='status-icon'
                          type={data.status.type}
                        ></CommonStatus>
                      )}
                      {this.isTargetCompare ? (
                        <span class='compare-btn-wrap'>
                          {this.compareTargets.includes(itemId) ? (
                            <i class='icon-monitor icon-mc-check-small'></i>
                          ) : (
                            <span
                              class='compare-btn-text'
                              onClick={modifiers.stop(() => this.handleAddCompare(data))}
                            >
                              {this.$t('对比')}
                            </span>
                          )}
                        </span>
                      ) : undefined}
                      <span
                        class='item-name'
                        v-bk-overflow-tips
                      >
                        {data.name || '--'}
                      </span>
                    </div>
                  );
                }
              }}
            ></bk-virtual-scroll>
          ) : (
            <EmptyStatus
              type={this.emptyType}
              onOperation={this.handleOperation}
            />
          )}
        </div>
      </div>
    );
  }
}
