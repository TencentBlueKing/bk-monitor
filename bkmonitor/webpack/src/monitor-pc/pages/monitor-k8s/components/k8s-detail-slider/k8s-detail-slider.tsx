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
import { Component, Emit, Prop, ProvideReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { PanelModel } from 'monitor-ui/chart-plugins/typings/dashboard-panel';

import CommonDetail from '../common-detail';
import K8sDimensionDrillDown from '../k8s-left-panel/k8s-dimension-drilldown';
import { sliderMockData } from '../k8s-table-new/utils';

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
  @ProvideReactive() viewOptions: IViewOptions = {
    filters: {},
    variables: {
      ...sliderMockData,
    },
  };

  // TODO 测试数据
  panel = new PanelModel({
    targets: [
      {
        datasource: 'info',
        dataType: 'info',
        api: 'scene_view.getKubernetesPod',
        data: {
          bcs_cluster_id: '$bcs_cluster_id',
          namespace: '$namespace',
          pod_name: '$pod_name',
        },
      },
    ],
  });
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
      ids: param.ids,
      icon: param.icon,
      btnText: param.btnText,
      btnTheme: param.btnTheme,
      textColorClass: param.textColorClass,
    };
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

  // 隐藏详情
  handleHiddenSlider() {
    this.emitIsShow(false);
  }

  // 标题
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
      </div>
    );
  }

  // 内容
  tplContent() {
    return (
      <div class='k8s-detail-content'>
        <div class='detail-content-left'>left</div>
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
