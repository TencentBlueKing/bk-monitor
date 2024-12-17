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

import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';
import { PanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import { K8sTableColumnKeysEnum } from '../../typings/k8s-new';
import CommonDetail from '../common-detail';
// import K8SCharts from '../k8s-charts/k8s-charts';
import K8sTableNew from '../k8s-table-new/k8s-table-new';

import type { K8sGroupDimension } from '../../k8s-dimension';
import type { IFilterByItem } from '../filter-by-condition/utils';
import type { K8sTableFilterByEvent, K8sTableColumnResourceKey, K8sTableRow } from '../k8s-table-new/k8s-table-new';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './k8s-detail-slider.scss';

export interface K8sDetailSliderActiveTitle {
  tag: K8sTableColumnResourceKey | string;
  field: string;
}

interface K8sDetailSliderProps {
  /** 抽屉页是否显示 */
  isShow?: boolean;
  /** table表格数据 */
  tableData: K8sTableRow[];
  /** GroupBy 选择器选中数据类实例 */
  groupInstance: K8sGroupDimension;
  /** 筛选 Filter By 过滤项 */
  filterBy: IFilterByItem[];
  /** 当前选中tabel数据项索引 */
  activeRowIndex: number;
  /** 当前数据项标题 */
  activeTitle: K8sDetailSliderActiveTitle;
  /** 集群Id */
  clusterId: string;
}
interface K8sDetailSliderEvent {
  onShowChange?: boolean;
  onGroupChange: (groupId: K8sTableColumnResourceKey) => void;
  onFilterChange: (item: K8sTableFilterByEvent) => void;
}

@Component
export default class K8sDetailSlider extends tsc<K8sDetailSliderProps, K8sDetailSliderEvent> {
  /** 抽屉页是否显示 */
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  /** table表格数据 */
  @Prop({ type: Array, default: () => [] }) tableData: K8sTableRow[];
  /** GroupBy 选择器选中数据类实例 */
  @Prop({ type: Object }) groupInstance: K8sGroupDimension;
  /** 筛选 Filter By 过滤项 */
  @Prop({ type: Array, default: () => [] }) filterBy: IFilterByItem[];
  /** 当前选中tabel数据项索引 */
  @Prop({ type: Number }) activeRowIndex: number;
  /** 当前数据项标题 */
  @Prop({ type: Object }) activeTitle: K8sDetailSliderActiveTitle;
  /** 集群 */
  @Prop({ type: String }) clusterId: string;

  @ProvideReactive() viewOptions: IViewOptions = {
    filters: {},
    variables: {},
  };

  panel: PanelModel = null;
  loading = false;
  popoverInstance = null;

  get filterParams() {
    const field = this.activeTitle.field;
    const groupItem = this.filterBy?.find?.(v => v.key === this.activeTitle.tag);
    const filterIds = (groupItem?.value?.length && groupItem?.value.filter(v => v !== field)) || [];
    const hasFilter = groupItem?.value?.length && filterIds?.length !== groupItem?.value?.length;
    const param = hasFilter
      ? {
          icon: 'icon-sousuo-',
          ids: filterIds,
          btnText: '移除该筛选项',
          btnTheme: 'primary',
          textColorClass: '',
        }
      : {
          icon: 'icon-a-sousuo',
          ids: [...filterIds, field],
          btnText: '添加为筛选项',
          btnTheme: 'default',
          textColorClass: 'is-default',
        };
    return {
      hasFilter,
      ...param,
    };
  }

  get showOperate() {
    const { tag } = this.activeTitle;
    const dimensions = this.groupInstance.dimensionsMap[tag];
    return this.isShow && dimensions?.length;
  }

  @Watch('isShow')
  handleResourceChange(v) {
    if (!v) return;
    this.modifyApiOptions();
  }

  @Watch('activeTitle.tag')
  handleActiveTitleTagChange(v) {
    if (!v) return;
    // @ts-ignore
    this.viewOptions.resource_type = v;
  }

  @Watch('clusterId', { immediate: true })
  handleClusterIdChange(v) {
    if (!v) return;
    // @ts-ignore
    this.viewOptions[K8sTableColumnKeysEnum.CLUSTER] = v;
  }

  @Watch('activeRowIndex')
  handleActiveRowIndexChange(v) {
    if (v === -1) return;
    const rowData = this.tableData[v];
    const { tag } = this.activeTitle;
    const viewOptions = {
      ...this.viewOptions,
      ...rowData,
      filters: {},
      variables: {},
    };
    if (tag === K8sTableColumnKeysEnum.WORKLOAD) {
      // @ts-ignore
      viewOptions.workload_name = K8sTableNew.getWorkloadValue(tag, 0)(rowData);
      viewOptions.workload_type = K8sTableNew.getWorkloadValue(tag, 1)(rowData);
    }

    this.viewOptions = viewOptions;
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  @Emit('groupChange')
  groupChange(groupId: K8sTableColumnResourceKey) {
    return groupId;
  }

  @Emit('filterChange')
  filterChange() {
    return {
      groupId: this.activeTitle.tag,
      ids: this.filterParams.ids,
    };
  }

  /** 获取默认的详情接口配置 */
  getDefaultApiOptions() {
    return {
      targets: [
        {
          datasource: 'info',
          dataType: 'info',
          api: 'k8s.getResourceDetail',
          data: {
            bcs_cluster_id: `$${K8sTableColumnKeysEnum.CLUSTER}`,
            namespace: `$${K8sTableColumnKeysEnum.NAMESPACE}`,
            resource_type: '$resource_type',
          },
        },
      ],
    };
  }

  /** 定义请求详情接口时所需要传的参数 */
  defineApiDynamicParams() {
    switch (this.activeTitle.tag) {
      case K8sTableColumnKeysEnum.WORKLOAD:
        return {
          workload_name: '$workload_name',
          workload_type: '$workload_type',
        };
      case K8sTableColumnKeysEnum.POD:
        return {
          pod_name: `$${K8sTableColumnKeysEnum.POD}`,
        };
      case K8sTableColumnKeysEnum.CONTAINER:
        return {
          pod_name: `$${K8sTableColumnKeysEnum.POD}`,
          container_name: `$${K8sTableColumnKeysEnum.CONTAINER}`,
        };
      default:
        return {};
    }
  }

  /** 更新 详情接口 配置 */
  modifyApiOptions() {
    const apiOptions = this.getDefaultApiOptions();
    const dynamicParam = this.defineApiDynamicParams();
    apiOptions.targets[0].data = {
      ...apiOptions.targets[0].data,
      ...dynamicParam,
    };
    this.panel = new PanelModel(apiOptions);
  }

  /** 隐藏详情 */
  handleHiddenSlider() {
    this.emitIsShow(false);
  }

  /** 抽屉页标题渲染 */
  tplTitle() {
    return (
      <div class='title-wrap'>
        <div class='title-left'>
          <span class='title-tag'>{this.activeTitle.tag}</span>
          <span class='title-value'> {this.activeTitle.field}</span>
          <span
            class='icon-monitor icon-copy-link title-icon'
            v-bk-tooltips={{ content: '复制链接', placement: 'right' }}
          />
        </div>
        {this.showOperate ? (
          <div class='title-right'>
            <bk-button
              class={['title-btn', this.filterParams.textColorClass]}
              theme={this.filterParams.btnTheme}
              onClick={this.filterChange}
            >
              <span class={['icon-monitor', this.filterParams.icon]} />
              <span class='title-btn-label'>{this.$t(this.filterParams.btnText)}</span>
            </bk-button>
            <K8sDimensionDrillDown
              dimension={this.activeTitle.tag}
              enableTip={false}
              value={this.activeTitle.tag}
              onHandleDrillDown={v => this.groupChange(v.dimension as K8sTableColumnResourceKey)}
            >
              <bk-button
                class='title-btn is-default'
                slot='trigger'
              >
                <span class='icon-monitor icon-xiazuan' />
                <span class='title-btn-label'>{this.$t('下钻')}</span>
              </bk-button>
            </K8sDimensionDrillDown>
          </div>
        ) : null}
      </div>
    );
  }

  /** 抽屉页右侧详情渲染 */
  tplContent() {
    return (
      <div class='k8s-detail-content'>
        <div class='detail-content-left'>
          {/* <K8SCharts
            filterCommonParams={this.filterCommonParams}
            groupBy={this.groupInstance.groupFilters}
            hideMetrics={this.hideMetrics}
            metricList={this.metricList}
          /> */}
        </div>
        <div class='detail-content-right'>
          <CommonDetail
            collapse={false}
            maxWidth={500}
            needShrinkBtn={false}
            panel={this.panel}
            placement={'right'}
            selectorPanelType={''}
            startPlacement={'left'}
            title={this.$tc('详情')}
            toggleSet={true}
            onLinkToDetail={() => {}}
            onShowChange={() => {}}
            onTitleChange={() => {}}
          />
        </div>
      </div>
    );
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='k8s-detail-slider'
        isShow={this.isShow}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        width={'80vw'}
        quick-close={true}
        onHidden={this.handleHiddenSlider}
      >
        <div
          class='slider-title'
          slot='header'
        >
          {this.tplTitle()}
        </div>
        <div
          slot='content'
          v-bkloading={{ isLoading: this.loading }}
        >
          {this.tplContent()}
        </div>
      </bk-sideslider>
    );
  }
}
