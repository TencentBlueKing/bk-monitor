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
import { Component, Emit, Inject, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc, modifiers } from 'vue-tsx-support';
import { Debounce, deepClone, typeTools } from 'monitor-common/utils/utils';
import StatusTab from 'monitor-ui/chart-plugins/plugins/table-chart/status-tab';
import { IViewOptions, PanelModel } from 'monitor-ui/chart-plugins/typings';
import { VariablesService } from 'monitor-ui/chart-plugins/utils/variable';

import { IStatusData } from '../../../collector-config/collector-view-detail/status-tab-list';
import { IQueryData, IQueryDataSearch } from '../../../monitor-k8s/typings';
import {
  filterSelectorPanelSearchList,
  transformConditionValueParams,
  transformQueryDataSearch,
  updateBkSearchSelectName
} from '../../../monitor-k8s/utils';
import { StatusClassNameType } from '../host-tree/host-tree';

import './host-list.scss';

export const DEFAULT_TAB_LIST = [
  {
    name: window.i18n.tc('全部'),
    type: 'all'
  },
  {
    type: 'success',
    status: 'success',
    tips: `${window.i18n.t('正常')}  (${window.i18n.t('近3个周期数据')})`,
    color: 'success'
  },
  {
    type: 'failed',
    status: 'failed',
    tips: `${window.i18n.t('异常')}  (${window.i18n.t('下发采集失败')})`,
    color: 'failed'
  },
  {
    type: 'nodata',
    status: 'disabled',
    tips: `${window.i18n.t('无数据')}  (${window.i18n.t('近3个周期数据')})`,
    color: 'nodata'
  }
];
export interface IProps {
  panel: PanelModel;
  onChange: IViewOptions;
  height: number;
  width: number;
  viewOptions: IViewOptions;
  isTargetCompare?: boolean;
}
export interface IEvents {
  onChange: IViewOptions;
  onListChange: {
    id: string;
    name: string;
  };
  onCompareChange: string[];
  onTitleChange: any;
  onOverviewChange: void;
  onCheckedChange: (a: boolean) => void;
  onSearchChange: any[];
}

@Component
export default class HostList extends tsc<IProps, IEvents> {
  @Prop({ type: Object }) panel: PanelModel;
  @Prop({ type: Object }) viewOptions: IViewOptions;
  @Prop({ default: 500, type: Number }) height: number;
  @Prop({ default: 200, type: Number }) width: number;
  /** 是否存在目标对比 */
  @Prop({ default: false, type: Boolean }) isTargetCompare: boolean;

  @Ref() hostListRef: any;

  @InjectReactive('queryData') readonly queryData!: IQueryData;
  /** 侧栏搜索条件更新url方法 */
  @Inject('handleUpdateQueryData') handleUpdateQueryData: (queryData: IQueryData) => void;

  /** 数据加载状态 */
  loading = false;

  /** 主机状态数据 */
  hostStatusData: IStatusData = {};
  /** 主机的状态筛选 */
  currentStatus = 'all';

  /** 搜索关键字 */
  searchKeyword = '';

  /** 主机列表 */
  hostListData = [];
  /** 缓存全部数据 */
  hoastListDataCache = [];

  /** 目标对比选中的数据 */
  localCompareTargets: Array<Record<string, any>> = [];

  /** 主机状态status字段映射 */
  hostStatusMap = {
    SUCCESS: 'success',
    FAILED: 'failed',
    NODATA: 'nodata'
  };

  /** 选中值 默认数据总览*/
  selectId: 'overview' | string = 'overview';

  conditionList = [];
  searchCondition = [];

  /** 过滤已选得搜索条件 */
  get currentConditionList() {
    return filterSelectorPanelSearchList(this.conditionList, this.searchCondition);
  }

  get statusMapping() {
    const defaultStatus = [
      {
        id: 'SUCCESS',
        name: '正常',
        color: 'success'
      },
      {
        id: 'FAILED',
        name: '失败',
        color: 'warning'
      },
      {
        id: 'NODATA',
        name: '无数据',
        color: 'nodata'
      }
    ];
    return this.panel.options?.[this.panel?.type]?.status_mapping || defaultStatus;
  }
  /** 状态筛选数据 */
  get statusList() {
    return DEFAULT_TAB_LIST.map(item => ({
      id: item.type,
      name: item.name || (this.hostStatusData[item.type]?.count ?? 0),
      tips: item.tips,
      status: item.status
    }));
  }

  /** 接口数据 */
  get targets() {
    return this.panel.targets;
  }

  /** 用于前端目标对比时拼接id */
  get fieldsSort() {
    return this.targets[0].fieldsSort;
  }

  /** 是否开启了主机状态栏 */
  get enableStatusFilter() {
    return !!this.panel.options?.target_list?.show_status_bar;
  }
  /** 是否开启数据总览 */
  get enableOverview() {
    return !!this.panel.options?.target_list?.show_overview;
  }

  /** 搜索框占位提示 */
  get placeholder() {
    return this.panel.options?.target_list?.placeholder || this.$t('搜索IP / 主机名');
  }

  /** 列表高度 */
  get listHeight() {
    let { height } = this;
    const MARGIN_BOTTOM = 8;
    /** 搜索框高度 */
    height = height - 32 - MARGIN_BOTTOM;
    if (this.enableStatusFilter) height -= 32 + MARGIN_BOTTOM;
    if (this.isTargetCompare) height -= 34 + MARGIN_BOTTOM;
    if (this.enableOverview) height -= 32 + MARGIN_BOTTOM;
    return height;
  }

  /** 目标对比选中的主机id */
  get compareTargets() {
    // eslint-disable-next-line max-len
    return (
      this.viewOptions?.compares?.targets?.map(item => this.panel.targets?.[0]?.handleCreateItemId(item, true)) || []
    );
  }

  async created() {
    await this.handleGetDataList();
    this.initDisplayBack();
  }

  @Watch('queryData.selectorSearch', { immediate: true })
  conditionChange(search: IQueryDataSearch) {
    this.searchCondition = updateBkSearchSelectName(this.conditionList, transformQueryDataSearch(search || []));
  }

  @Watch('width')
  @Debounce(300)
  widthChange() {
    this.hostListRef?.resize();
  }

  @Watch('compareTargets', { immediate: true })
  compareTargetsChange() {
    this.localCompareTargets = deepClone(this.viewOptions?.compares?.targets || []);
  }

  /** 处理选中回显 */
  initDisplayBack() {
    this.selectId = this.panel.targets?.[0]?.handleCreateItemId?.(this.viewOptions.filters, true) || 'overview';
    const item = this.hostListData.find(item => this.panel.targets?.[0]?.handleCreateItemId?.(item) === this.selectId);
    this.$emit('titleChange', !!item ? item.name : this.$tc('概览'));
  }

  /** 请求接口 */
  async handleGetDataList() {
    const variablesService = new VariablesService(this.viewOptions);
    const promiseList = this.targets.map(item =>
      this.$api[item.apiModule]
        [item.apiFunc]({
          ...variablesService.transformVariables(item.data),
          condition_list: transformConditionValueParams(this.searchCondition)
        })
        .then(data => {
          const list = typeTools.isObject(data) ? data.data : data;
          this.conditionList = data.condition_list || [];
          this.searchCondition = updateBkSearchSelectName(this.conditionList, this.searchCondition);
          return list;
        })
        .catch(err => {
          console.error(err);
          return [];
        })
    );
    this.loading = true;
    const res = await Promise.all(promiseList).catch(err => {
      console.error(err);
      return [];
    });
    this.loading = false;
    this.hostListData = res.reduce((total, cur) => total.concat(cur), []);
    this.handleListChange(this.hostListData);
    this.hoastListDataCache = deepClone(this.hostListData);
    this.updataHostStatus();
    this.updateHostList();
  }
  /** 更新主机状态数据 */
  updataHostStatus() {
    if (this.enableStatusFilter) {
      this.hostStatusData = this.hostListData.reduce((total, cur) => {
        const key = this.hostStatusMap[cur.status];
        const value = total[key];
        if (!value) {
          total[key] = {
            count: 1
          };
        } else {
          value.count += 1;
        }
        return total;
      }, {});
    }
  }
  /** 更新主机列表的数据 */
  updateHostList() {
    this.$nextTick(() => {
      this.hostListRef?.setListData(this.hostListData);
    });
  }
  /** 生成唯一的id */
  getItemId(item: Object) {
    const itemIds = [];
    this.fieldsSort.forEach(set => {
      const [key] = set;
      itemIds.push(item[key]);
    });
    return itemIds.join('-');
  }

  /** 获取输出外部的filterDict数据 */
  getFilterDictData(item?) {
    return this.fieldsSort.reduce((total, cur) => {
      const [valueKey, key] = cur;
      total[key] = this.selectId === 'overview' ? undefined : item[valueKey];
      return total;
    }, {});
  }

  /** 点击选中 */
  handleClickItem(id, item) {
    this.selectId = id;
    this.localCompareTargets = [];
    const filters = this.getFilterDictData(item);
    this.$emit('titleChange', id === 'overview' ? this.$tc('概览') : item?.name, item);
    const viewOptions: IViewOptions = {
      ...this.viewOptions,
      filters,
      compares: {
        targets: []
      }
    };
    this.$emit('checkedChange');
    return this.handleViewOptionsChange(viewOptions);
  }

  @Emit('change')
  handleViewOptionsChange(viewOptions: IViewOptions): IViewOptions {
    return viewOptions;
  }

  @Emit('overviewChange')
  handleClickOverview() {
    this.handleClickItem('overview', {});
  }

  /** 选择主机状态 */
  handleStatusFilter(status: string) {
    this.currentStatus = status;
    this.handleFilterHostList();
  }

  /** 控制列表item的显隐 */
  isShowItem(item) {
    const status = this.hostStatusMap[item.status || ''];
    let matchStatus = true;
    let matchName = true;
    if (status) {
      matchStatus = this.currentStatus === 'all' ? true : this.currentStatus === status;
    }
    if (this.searchKeyword) {
      const matchNameTarget = [item.name, item.bk_host_name];
      matchName = matchNameTarget.some(item => `${item}`.indexOf(this.searchKeyword) > -1);
    }
    return matchStatus && matchName;
  }

  handleSearch() {
    this.handleGetDataList();
    const selectorSearch = transformConditionValueParams(this.searchCondition);
    this.handleUpdateQueryData({
      ...this.queryData,
      selectorSearch
    });
  }

  @Debounce(300)
  handleLocalSearch(val) {
    this.searchKeyword = val;
    this.handleFilterHostList();
  }

  /** 过滤数据操作 */
  handleFilterHostList() {
    this.hostListData = this.hoastListDataCache.filter(item => this.isShowItem(item));
    this.updateHostList();
  }

  @Emit('listChange')
  handleListChange(list) {
    return list.map(item => ({
      ...item,
      id: this.panel.targets[0].handleCreateItemId(item)
    }));
  }

  /** 对比操作 */
  handleAddCompare(item) {
    const value = this.panel.targets?.[0]?.handleCreateCompares(item);
    this.localCompareTargets.push(value);
    const viewOptions: IViewOptions = {
      ...this.viewOptions,
      compares: {
        targets: this.localCompareTargets
      }
    };
    this.handleViewOptionsChange(viewOptions);
  }

  /** 生成主机主机的状态类名 */
  getItemStatusClassName(status: string | number): StatusClassNameType {
    const target = this.statusMapping.find(item => item.id === status);
    return (target.color as StatusClassNameType) || 'none';
  }

  render() {
    const scopedSlots = {
      default: data => {
        const item = data.data;
        const itemId = this.getItemId(item);
        return (
          <div
            v-bk-overflow-tips={{ content: item.ip || item.name }}
            class={[
              'host-item-wrap',
              {
                active: itemId === this.selectId,
                'checked-target': this.isTargetCompare && this.compareTargets.includes(itemId)
              }
            ]}
            onClick={() => this.handleClickItem(itemId, item)}
          >
            {!!this.hostStatusMap[item.status] ? (
              <span
                class={[
                  'host-status',
                  this.hostStatusMap[item.status],
                  `status-${this.getItemStatusClassName(item.status)}`
                ]}
              ></span>
            ) : undefined}
            <span class={['host-item-ip']}>{item.ip || item.name}</span>
            {!!item.bk_host_name ? <span class='host-item-host-name'>({item.bk_host_name})</span> : undefined}
            {this.isTargetCompare ? (
              <span class='compare-btn-wrap'>
                {this.compareTargets.includes(itemId) ? (
                  <i class='icon-monitor icon-mc-check-small'></i>
                ) : (
                  <span
                    class='compare-btn-text'
                    onClick={modifiers.stop(() => this.handleAddCompare(item))}
                  >
                    {this.$t('对比')}
                  </span>
                )}
              </span>
            ) : undefined}
          </div>
        );
      }
    };
    return (
      <div
        class='host-list-wrap'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='host-list-main'>
          <div class='host-list-tool'>
            {this.conditionList.length ? (
              <bk-search-select
                placeholder={this.$t('搜索')}
                vModel={this.searchCondition}
                show-condition={false}
                show-popover-tag-change={false}
                data={this.currentConditionList}
                onChange={this.handleSearch}
              />
            ) : (
              <bk-input
                class='host-search'
                value={this.searchKeyword}
                right-icon='bk-icon icon-search'
                placeholder={this.placeholder}
                onInput={this.handleLocalSearch}
              ></bk-input>
            )}
            {this.enableStatusFilter && (
              <StatusTab
                needAll={false}
                disabledClickZero
                v-model={this.currentStatus}
                statusList={this.statusList}
                onChange={this.handleStatusFilter}
              ></StatusTab>
            )}
            {this.enableOverview && (
              <div
                class={['overview-btn', { active: this.selectId === 'overview' }]}
                onClick={this.handleClickOverview}
              >
                <i class='icon-monitor icon-mc-overview'></i>
                {this.$t('概览')}
              </div>
            )}
            {this.isTargetCompare ? (
              <bk-alert
                class='target-compare-tips'
                type='info'
                title={this.$t('选择目标进行对比')}
              ></bk-alert>
            ) : undefined}
          </div>

          {this.hostListData.length ? (
            [
              // this.enableOverview
              //   ? <div
              //     class={['overview-btn', { active: this.selectId === 'overview' }]}
              //     onClick={this.handleClickOverview}>
              //     <i class="icon-monitor icon-mc-overview"></i>
              //     {this.$t('概览')}</div>
              //   : undefined,
              this.hostListData.length ? (
                <bk-virtual-scroll
                  style={{ height: `${this.listHeight}px` }}
                  ref='hostListRef'
                  item-height={32}
                  scopedSlots={scopedSlots}
                />
              ) : undefined
            ]
          ) : (
            <bk-exception
              type='empty'
              scene='part'
            />
          )}
        </div>
      </div>
    );
  }
}
