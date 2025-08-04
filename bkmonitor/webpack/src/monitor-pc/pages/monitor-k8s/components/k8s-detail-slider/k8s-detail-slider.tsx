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
import { Component, Emit, Inject, InjectReactive, Prop, ProvideReactive, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import K8sDimensionDrillDown from 'monitor-ui/chart-plugins/plugins/k8s-custom-graph/k8s-dimension-drilldown';
import { PanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import { type IK8SMetricItem, K8sTableColumnKeysEnum } from '../../typings/k8s-new';
import CommonDetail from '../common-detail';
import K8SCharts from '../k8s-charts/k8s-charts';

import type { DrillDownEvent, K8sTableColumnResourceKey, K8sTableGroupByEvent } from '../k8s-table-new/k8s-table-new';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './k8s-detail-slider.scss';

export interface K8sDetailSliderActiveTitle {
  field: string;
  tag: K8sTableColumnResourceKey | string;
}

interface K8sDetailSliderEvent {
  onShowChange?: boolean;
}
interface K8sDetailSliderProps {
  hideMetrics: string[];
  /** 抽屉页是否显示 */
  isShow?: boolean;
  metricList: IK8SMetricItem[];
  resourceDetail?: Partial<Record<K8sTableColumnKeysEnum, string>>;
}

@Component
export default class K8sDetailSlider extends tsc<K8sDetailSliderProps, K8sDetailSliderEvent> {
  @InjectReactive('commonParams') commonParams: Record<string, any>;
  @Prop({ type: Array, default: () => [] }) metricList: IK8SMetricItem[];
  @Prop({ type: Array, default: () => [] }) hideMetrics: string[];
  /** 抽屉页是否显示 */
  @Prop({ type: Boolean, default: false }) isShow: boolean;

  // 其中 externalParam 属性接口请求传参时忽略属性，组件个性化逻辑传参处理
  @Prop({
    type: Object,
    required: true,
  })
  resourceDetail: Partial<Record<K8sTableColumnKeysEnum, string> & { externalParam: { isCluster: boolean } }>;
  @ProvideReactive() viewOptions: IViewOptions = {
    filters: {},
    variables: {},
  };
  @Inject({ from: 'onFilterChange', default: () => null }) readonly onFilterChange: (
    id: string,
    groupId: K8sTableColumnResourceKey,
    isSelect: boolean
  ) => void;
  @Inject({ from: 'onGroupChange', default: () => null }) readonly onDrillDown: (
    item: K8sTableGroupByEvent,
    showCancelDrill?: boolean
  ) => void;

  panel: PanelModel = null;
  loading = false;
  popoverInstance = null;

  get groupByField() {
    if (this.resourceDetail.container) return K8sTableColumnKeysEnum.CONTAINER;
    if (this.resourceDetail.pod) return K8sTableColumnKeysEnum.POD;
    if (this.resourceDetail.ingress) return K8sTableColumnKeysEnum.INGRESS;
    if (this.resourceDetail.service) return K8sTableColumnKeysEnum.SERVICE;
    if (this.resourceDetail.workload) return K8sTableColumnKeysEnum.WORKLOAD;
    if (this.resourceDetail.node) return K8sTableColumnKeysEnum.NODE;
    if (this.resourceDetail?.externalParam?.isCluster) {
      return K8sTableColumnKeysEnum.CLUSTER;
    }
    return K8sTableColumnKeysEnum.NAMESPACE;
  }

  get showOperate() {
    return (
      this.isShow && ![K8sTableColumnKeysEnum.CONTAINER, K8sTableColumnKeysEnum.CLUSTER].includes(this.groupByField)
    );
  }
  get filterCommonParams() {
    return {
      ...this.commonParams,
      resource_type: this.groupByField,
      filter_dict: Object.fromEntries(
        Object.entries(this.resourceDetail)
          .filter(([k, v]) => k !== 'externalParam' && v?.length && k !== K8sTableColumnKeysEnum.CLUSTER)
          .map(([k, v]) => [k, [v]])
      ),
      with_history: true,
    };
  }

  get chartResourceList() {
    const obj = {};
    for (const key in this.resourceDetail) {
      if (key !== 'externalParam' && key !== K8sTableColumnKeysEnum.CLUSTER && this.resourceDetail[key]?.length) {
        obj[key] = this.resourceDetail[key];
      }
    }
    return [obj] as Record<K8sTableColumnKeysEnum, string>[];
  }

  @Watch('isShow')
  handleResourceChange(v: boolean) {
    if (!v) return;
    this.updateDetailPanel();
  }

  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  groupChange(drillDown: DrillDownEvent) {
    this.onDrillDown({ ...drillDown, filterById: this.resourceDetail[this.groupByField] }, true);
    this.emitIsShow(false);
  }

  /**
   * @description 添加筛选/移除筛选 按钮点击回调
   * @param id 数据Id
   * @param groupId 维度Id
   * @param isSelect 是否选中
   */
  filterChange() {
    this.onFilterChange(this.resourceDetail[this.groupByField], this.groupByField, true);
    this.emitIsShow(false);
  }

  /** 更新 详情接口 配置 */
  updateDetailPanel() {
    const [workload_kind, workload_name] = this.resourceDetail.workload?.split(':') || [];
    this.panel = new PanelModel({
      targets: [
        {
          datasource: 'info',
          dataType: 'info',
          api: 'k8s.getResourceDetail',
          data: Object.fromEntries(
            Object.entries({
              bcs_cluster_id: this.resourceDetail?.cluster,
              namespace: this.resourceDetail?.namespace,
              resource_type: this.groupByField,
              workload_name: workload_name,
              workload_type: workload_kind,
              pod_name: this.resourceDetail?.pod,
              container_name: this.resourceDetail?.container,
              service_name: this.resourceDetail?.service,
              ingress_name: this.resourceDetail?.ingress,
              node_name: this.resourceDetail?.node,
            }).filter(([, v]) => !!v)
          ),
        },
      ],
    });
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
          <span class='title-tag'>{this.groupByField}</span>
          <span class='title-value'> {this.resourceDetail[this.groupByField]}</span>
        </div>
        {this.showOperate ? (
          <div class='title-right'>
            <bk-button
              class={['title-btn is-default']}
              theme={'default'}
              onClick={this.filterChange}
            >
              <span class={['icon-monitor icon-a-sousuo']} />
              <span class='title-btn-label'>{this.$t('添加为筛选项')}</span>
            </bk-button>
            <K8sDimensionDrillDown
              dimension={this.groupByField}
              enableTip={false}
              value={this.groupByField}
              onHandleDrillDown={v => this.groupChange(v as DrillDownEvent)}
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
          <K8SCharts
            filterCommonParams={this.filterCommonParams}
            groupBy={[this.groupByField]}
            hideMetrics={this.hideMetrics}
            isDetailMode={true}
            metricList={this.metricList}
            resourceListData={this.chartResourceList}
          />
        </div>
        {this.groupByField !== K8sTableColumnKeysEnum.NAMESPACE ? (
          <div class='detail-content-right'>
            <CommonDetail
              collapse={false}
              defaultWidth={400}
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
        ) : undefined}
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
