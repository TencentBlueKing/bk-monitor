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

import { Debounce } from 'monitor-common/utils/utils';

import { resize } from '../../../../components/ip-selector/common/observer-directive';
import { DASHBOARD_PANEL_COLUMN_KEY } from '../../typings';
import { type PanelToolsType, COMPARE_LIST, PANEL_LAYOUT_LIST } from '../../typings/panel-tools';

import './panel-tools.scss';

/**
 * dashboard-panel 的工具栏-包含功有对比方式（不对比 | 时间对比 | 目标对比 | 指标对比）、图表布局、合并视图等功能
 */
@Component({
  directives: {
    resize,
  },
})
export default class PanelsTools extends tsc<PanelToolsType.IProps, PanelToolsType.IEvents> {
  /** 图表布局方式 0: 一栏 1: 二栏 2: 三栏 */
  @Prop({ default: 0, type: Number }) layoutActive: number;
  /** 合并视图状态 !split */
  @Prop({ default: true, type: Boolean }) split: boolean;
  /** 是否需要合并视图 */
  @Prop({ default: false, type: Boolean }) needSplit: boolean;
  /** 是否需要图表分栏布局按钮 */
  @Prop({ default: true, type: Boolean }) needLayout: boolean;
  /** 是否禁用图表分栏布局按钮 */
  @Prop({ default: false, type: Boolean }) disabledLayout: boolean;

  /** 所有的对比方式 */
  compareList: PanelToolsType.ICompareListItem[] = COMPARE_LIST;

  /** 图表布局图表 */
  panelLayoutList = PANEL_LAYOUT_LIST;

  /** 是否展示布局描述 */
  showLayoutName = false;

  /** 当前布局方式 */
  get currentLayout() {
    return this.panelLayoutList[this.layoutActive];
  }
  /**
   * @description: 切换视图布局
   */
  @Emit('layoutChange')
  handleChangeLayout(id: number) {
    (this.$refs?.layoutDropdown as any)?.hide();
    localStorage.setItem(DASHBOARD_PANEL_COLUMN_KEY, (id - 1).toString());
    return id - 1;
  }

  /**
   * @description: 合并视图状态变更
   * @param {boolean} value
   * @return {boolean}
   */
  @Emit('splitChange')
  handleSplitChange(value: boolean) {
    return !value;
  }

  /**
   * @description: 对比数据变更
   * @param {PanelToolsType.Compare} data
   * @return {PanelToolsType.Compare}
   */
  @Emit('compareChange')
  handleCompareChnage(data: PanelToolsType.Compare) {
    return data;
  }

  @Debounce(300)
  handleResize(el: HTMLElement) {
    const react = el.getBoundingClientRect();
    this.showLayoutName = react.width > 600;
  }

  render() {
    return (
      <div
        class='panels-tools-wrap'
        v-resize={this.handleResize}
      >
        <span class='panels-tools-left'>{this.$slots.prepend}</span>
        {/* <span class="panels-tools-center" /> */}
        <span class='panels-tools-right'>
          {this.needLayout && (
            <bk-dropdown-menu
              ref='layoutDropdown'
              style='height: inhiert'
              class='right-item'
              disabled={this.disabledLayout}
            >
              <span
                class='panels-tools-layout right-item'
                slot='dropdown-trigger'
                v-en-style='width: 120px'
              >
                <i
                  class='icon-monitor icon-mc-two-column'
                  v-bk-tooltips={{
                    content: this.currentLayout.name,
                    delay: 200,
                    disabled: !!this.showLayoutName,
                    appendTo: 'parent',
                    allowHTML: false,
                  }}
                />
                {this.showLayoutName ? <span class='layout-name'>{this.currentLayout.name}</span> : undefined}
              </span>
              <ul
                class='layout-list'
                slot='dropdown-content'
              >
                {this.panelLayoutList.map(item => (
                  <li
                    key={item.id}
                    class={`layout-list-item ${item.id === this.layoutActive + 1 ? 'item-active' : ''}`}
                    onClick={() => this.handleChangeLayout(item.id)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            </bk-dropdown-menu>
          )}
          {this.needSplit ? (
            <span class='panels-tools-split right-item'>
              <span class='panels-tools-split-label'>{this.$t('合并视图')}</span>
              {/* 是否分割视图 true 分割 false 合并视图 */}
              <bk-switcher
                size='small'
                theme='primary'
                value={!this.split}
                onChange={this.handleSplitChange}
              />
            </span>
          ) : undefined}
          {!!this.$slots.append && <span class='panels-tools-append'>{this.$slots.append}</span>}
        </span>
      </div>
    );
  }
}
