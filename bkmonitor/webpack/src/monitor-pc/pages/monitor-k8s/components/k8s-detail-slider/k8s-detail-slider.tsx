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

import type { K8sTableFilterByEvent, K8sTableColumnResourceKey } from '../k8s-table-new/k8s-table-new';
import type { IViewOptions } from 'monitor-ui/chart-plugins/typings';

import './k8s-detail-slider.scss';

export interface K8sDetailSliderActiveTitle {
  tag: K8sTableColumnResourceKey | string;
  field: string;
}

interface K8sDetailSliderProps {
  /** 抽屉页是否显示 */
  isShow?: boolean;
  resourceDetail?: Partial<Record<K8sTableColumnKeysEnum, string>>;
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

  @Prop({
    type: Object,
    default: () => ({
      pod: 'bk-consul-1',
    }),
  })
  resourceDetail: Partial<Record<K8sTableColumnKeysEnum, string>>;
  @ProvideReactive() viewOptions: IViewOptions = {
    filters: {},
    variables: {},
  };

  panel: PanelModel = null;
  loading = false;
  popoverInstance = null;

  get groupByField() {
    if (this.resourceDetail.container) return K8sTableColumnKeysEnum.CONTAINER;
    if (this.resourceDetail.pod) return K8sTableColumnKeysEnum.POD;
    if (this.resourceDetail.workload) return K8sTableColumnKeysEnum.WORKLOAD;
    return K8sTableColumnKeysEnum.NAMESPACE;
  }

  get showOperate() {
    return this.isShow && this.groupByField !== K8sTableColumnKeysEnum.CONTAINER;
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

  @Emit('groupChange')
  groupChange(groupId: K8sTableColumnResourceKey) {
    return groupId;
  }

  @Emit('filterChange')
  filterChange() {
    // return {
    //   groupId: this.activeTitle.tag,
    //   ids: this.filterParams.ids,
    // };
  }

  /** 更新 详情接口 配置 */
  updateDetailPanel() {
    const [workload_type, workload_name] = this.resourceDetail.workload?.split(':') || [];
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
              workload_type: workload_type,
              pod_name: this.resourceDetail?.pod,
              container_name: this.resourceDetail?.container,
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