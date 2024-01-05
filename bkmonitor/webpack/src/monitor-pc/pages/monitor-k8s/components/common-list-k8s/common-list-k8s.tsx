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
import { IQueryData, IQueryDataSearch, ITableFilterItem } from '../../typings';
import {
  filterSelectorPanelSearchList,
  transformConditionValueParams,
  transformQueryDataSearch,
  updateBkSearchSelectName
} from '../../utils';
import CommonStatus from '../common-status/common-status';

import './common-list-k8s.scss';

interface ICommonListProps {
  // panel实例
  panel: PanelModel;
  // 视图数据参数配置
  viewOptions: IViewOptions;
  // 是否为目标对比
  isTargetCompare: boolean;
  isOverview: boolean;
  height?: number;
}

interface ICommonListEvent {
  // 选中列表行数据触发
  onChange: IViewOptions;
  // 标题修改触发
  onTitleChange: string;
  // get list
  onListChange: Record<string, any>[];
  onOverviewChange: boolean;
}

@Component
export default class CommonListK8s extends tsc<ICommonListProps, ICommonListEvent> {
  /** 当前输入的viewOptions数据 */
  @Prop({ type: Object }) viewOptions: IViewOptions;
  /** 接口数据 */
  @Prop({ type: Object }) panel: PanelModel;
  /** 是否为目标对比 */
  @Prop({ default: false, type: Boolean }) isTargetCompare: boolean;
  /** 是否为数据总览模式 */
  @Prop({ type: Boolean, default: true }) isOverview: boolean;
  // 高度
  @Prop({ type: Number }) height: number;
  @InjectReactive('width') readonly width!: number;
  /** 搜索条件 */
  @InjectReactive('queryData') readonly queryData!: IQueryData;
  /** 侧栏搜索条件更新url方法 */
  @Inject('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;
  keyword = '';
  loading = false;
  list: Record<string, any>[] = [];

  currentStatus: ITableFilterItem['id'] = 'all';
  statusList: ITableFilterItem[] = [
    {
      id: 'success',
      status: 'success',
      name: 0,
      tips: window.i18n.tc('健康状态良好')
    },
    {
      id: 'failed',
      status: 'failed',
      name: 0,
      tips: window.i18n.tc('异常')
    },
    {
      id: 'disabled',
      status: 'disabled',
      name: 0,
      tips: window.i18n.tc('全部无数据')
    }
  ];

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
    return this.isOverview ? '' : this.panel.targets?.[0]?.handleCreateItemId?.(this.scopedVars, true) || '';
  }

  get localList() {
    if (this.conditionList.length) return this.list;
    if (!this.list?.length) return [];
    // if (!this.keyword.length) return this.list;
    return this.list.filter(
      item =>
        (item.name.includes(this.keyword) || item.id.toString().includes(this.keyword)) &&
        (this.currentStatus === 'all' ? true : item.status.type === this.currentStatus)
    );
  }

  /** 目标对比选中的主机id */
  get compareTargets() {
    // eslint-disable-next-line max-len
    return (
      this.viewOptions?.compares?.targets?.map(item => this.panel.targets?.[0]?.handleCreateItemId(item, true)) || []
    );
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

  mounted() {
    this.getPanelData();
  }
  activated() {
    this.getCheckedItemName();
  }
  getCheckedItemName() {
    if (this.isOverview) {
      this.handleTitleChange('概览');
    } else {
      const checkedItem = this.list.find(item => item.id === this.activeId);
      const title = checkedItem ? checkedItem.name : this.list[0]?.name || '';
      !!title && this.handleTitleChange(title);
    }
  }
  // 获取列表数据
  async getPanelData() {
    this.loading = true;
    const variablesService = new VariablesService(this.scopedVars);
    const promiseList = this.panel.targets.map(item =>
      (this as any).$api[item.apiModule]
        [item.apiFunc]({
          ...variablesService.transformVariables(item.data),
          condition_list: transformConditionValueParams(this.searchCondition)
        })
        .then(data => {
          const list = Array.isArray(data) ? data : data.data;
          this.conditionList = data.condition_list || [];
          this.searchCondition = updateBkSearchSelectName(this.conditionList, this.searchCondition);
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
    const [data] = await Promise.all(promiseList).catch(() => [[]]);
    this.list = data;
    // if (this.activeId === '' && this.list[0]) {
    //   this.handleSelect(this.list[0]);
    // }
    this.handleStatusCount();
    this.$emit('listChange', this.list.slice());
    this.getCheckedItemName();
    setTimeout(() => {
      (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
    }, 20);
    this.loading = false;
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
    (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
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
    if (this.isOverview) this.handleSelectOverview(false);
  }
  @Emit('titleChange')
  handleTitleChange(title: string) {
    return title;
  }

  /**
   * 统计集群状态数量
   */
  handleStatusCount() {
    this.list.forEach(item => {
      if (item.status.type === 'success') (this.statusList[0].name as number) += 1;
      if (item.status.type === 'failed') (this.statusList[1].name as number) += 1;
      if (item.status.type === 'disabled') (this.statusList[2].name as number) += 1;
    });
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
  /** 切换overview模式 */
  @Emit('overviewChange')
  handleSelectOverview(val: boolean) {
    return val;
  }

  /** 状态修改 */
  handleStatusChange() {
    this.$nextTick(() => {
      (this.$refs.virtualInstance as any)?.setListData?.(this.localList);
    });
  }
  render() {
    return (
      <div
        class='common-panel-list-k8s'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='list-k8s-container'>
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
          <StatusTab
            v-model={this.currentStatus}
            disabledClickZero
            class='status-tab'
            statusList={this.statusList}
            onChange={this.handleStatusChange}
          ></StatusTab>
          <div
            class={['overview-btn-wrap', { active: this.isOverview }]}
            onClick={() => this.handleSelectOverview(true)}
          >
            <i class='icon-monitor icon-mc-overview'></i>
            <span class='overview-text'>{this.$t('概览')}</span>
          </div>
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
                        onClick={() => this.handleSelect(data)}
                        class={[
                          `list-wrapper-item ${data.id === this.activeId ? 'item-active' : ''}`,
                          {
                            'checked-target': this.isTargetCompare && this.compareTargets.includes(itemId)
                          }
                        ]}
                      >
                        <span class='status-tag-wrap'>
                          <CommonStatus type={data.status.type}></CommonStatus>
                        </span>
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
                        <span>{data.name || '--'}</span>
                      </div>
                    );
                  }
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
      </div>
    );
  }
}
