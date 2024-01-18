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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from '../../../../../monitor-common/utils/utils';
import { resize } from '../../../../../monitor-pc/components/ip-selector/common/observer-directive';

import { IInfo } from './types';

import './metrics-collapse.scss';

const DASHBOARD_PANEL_COLUMN_KEY = '__aiops_metrics_chart_view_type__';

interface IProps {
  layoutActive?: Number;
  needLayout?: boolean;
  showCollapse?: boolean;
  title: string;
  info: IInfo;
}

@Component({
  directives: {
    resize
  }
})
export default class AiopsMetricsCollapse extends tsc<IProps> {
  @Prop({ type: Object, default: () => {} }) info: IInfo;
  @Prop({ type: String, default: '' }) title: string;
  /** 图表布局方式 0: 一栏 1: 二栏 2: 三栏 */
  @Prop({ default: 0, type: Number }) layoutActive: number;
  /** 是否需要图表分栏布局按钮 */
  @Prop({ default: true, type: Boolean }) needLayout: boolean;

  /** 是否展示头部展开收起 */
  @Prop({ default: true, type: Boolean }) showCollapse: boolean;

  /** 展开收起 */
  isCollapse = false;

  /** 是否展示修改布局icon */
  showLayoutPopover = false;

  /** 图表布局图表 */
  panelLayoutList = [
    {
      id: 1,
      name: this.$t('一列')
    },
    {
      id: 3,
      name: this.$t('三列')
    }
  ];

  /** 是否展示布局描述 */
  showLayoutName = false;

  /** 当前布局方式 */
  get currentLayout() {
    return this.panelLayoutList[this.layoutActive > 0 ? 1 : 0];
  }
  /** 当前指标数据量 */
  get recommendedMetricCount() {
    return this.info?.recommended_metric_count;
  }
  /**
   * @description: 切换视图布局
   */
  @Emit('layoutChange')
  handleChangeLayout(id: number) {
    (this.$refs?.popover as any)?.hideHandler();
    localStorage.setItem(DASHBOARD_PANEL_COLUMN_KEY, (id - 1).toString());
    return id - 1;
  }

  @Debounce(300)
  handleResize(el: HTMLElement) {
    const react = el.getBoundingClientRect();
    this.showLayoutName = react.width > 600;
  }
  handleStop(e) {
    this.$refs.popover?.showHandler?.();
    e.stopPropagation();
    e.preventDefault();
    return false;
  }
  /** 切换展开收起 */
  handleToggleCollapse(activeAuto = false) {
    if (activeAuto && !this.isCollapse) {
      return;
    }
    this.isCollapse = !this.isCollapse;
  }
  render() {
    return (
      <div
        class='aiops-correlation-metrics'
        v-resize={this.handleResize}
      >
        <div class='correlation-metrics-collapse'>
          <div
            class={[
              'correlation-metrics-collapse-head',
              `correlation-metrics-collapse-head-${!this.showCollapse ? 'hide' : 'show'}`
            ]}
          >
            <i
              onClick={this.handleToggleCollapse.bind(this, false)}
              class={[
                'bk-icon bk-card-head-icon collapse-icon',
                this.isCollapse ? 'icon-right-shape' : 'icon-down-shape'
              ]}
            ></i>
            <span
              class='correlation-metrics-title'
              onClick={this.handleToggleCollapse.bind(this, false)}
            >
              {this.title}
            </span>
            <div class={['correlation-metrics-right', this.showLayoutPopover && 'correlation-metrics-right-show']}>
              {this.needLayout && (
                <bk-popover
                  ref='popover'
                  placement='bottom'
                  {...{
                    props: {
                      extCls: 'correlation-metrics-layout-popover',
                      arrow: false,
                      delay: 0,
                      theme: 'light',
                      onShow: () => (this.showLayoutPopover = true),
                      onHide: () => (this.showLayoutPopover = false)
                    }
                  }}
                >
                  <span
                    class='panels-tools-layout right-item'
                    onClick={this.handleStop}
                  >
                    <i
                      class='icon-monitor icon-mc-two-column'
                      v-bk-tooltips={{
                        content: this.currentLayout.name,
                        delay: 200,
                        disabled: !!this.showLayoutName,
                        appendTo: 'parent',
                        allowHTML: false
                      }}
                    ></i>
                    {this.showLayoutName ? <span class='layout-name'>{this.currentLayout.name}</span> : undefined}
                  </span>
                  <ul
                    slot='content'
                    class='layout-list'
                  >
                    {this.panelLayoutList.map(item => (
                      <li
                        class={`layout-list-item ${item.id === this.layoutActive + 1 ? 'item-active' : ''}`}
                        onClick={() => this.handleChangeLayout(item.id)}
                        key={item.id}
                      >
                        {item.name}
                      </li>
                    ))}
                  </ul>
                </bk-popover>
              )}
            </div>
          </div>
          <bk-transition name='collapse'>
            <div
              v-show={!(this.isCollapse && this.showCollapse)}
              class={['correlation-metrics-collapse-content']}
            >
              {(this.$scopedSlots as any)?.default?.({ column: this.layoutActive + 1 })}
            </div>
          </bk-transition>
        </div>
      </div>
    );
  }
}
