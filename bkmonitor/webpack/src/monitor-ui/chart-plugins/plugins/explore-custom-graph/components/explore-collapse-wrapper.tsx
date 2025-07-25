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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import MonitorCrossDrag from '../../../components/monitor-cross-drag/monitor-cross-drag';

import './explore-collapse-wrapper.scss';

interface ExploreCollapseWrapperProps {
  collapseShowHeight?: number;
  defaultHeight?: number;
  defaultIsExpand?: number;
  description?: string;
  hasResize?: boolean;
  title?: string;
}

@Component
export default class ExploreCollapseWrapper extends tsc<ExploreCollapseWrapperProps> {
  /** header 区域标题 */
  @Prop({ type: String }) title: string;
  /** header 区域描述 */
  @Prop({ type: String }) description: string;
  /** 默认高度（初始化时 container 区域的高度） */
  @Prop({ type: Number, default: 166 }) defaultHeight: number;
  /** 初始化时折叠面板默认是否展开状态 */
  @Prop({ type: Boolean, default: true }) defaultIsExpand: boolean;
  /** 是否需要 resize 功能 */
  @Prop({ type: Boolean, default: true }) hasResize: boolean;
  /** 折叠收起时需要展示内容的高度 */
  @Prop({ type: Number, default: 36 }) collapseShowHeight: number;

  /** 显示内容区域高度 -- 主要用于配合 resize 操作时使用 */
  containerHeight = 0;
  /** 折叠面板，是否展开图表 */
  isExpand = true;

  /** 将容器高度转换成 css height 属性 */
  get containerHeightForStyle() {
    return this.containerHeight ? `${this.containerHeight}px` : 'auto';
  }

  /** css 变量 */
  get cssVars() {
    return {
      // 容器头部高度（也是折叠状态下需要显示的高度）
      '--header-height': `${this.collapseShowHeight}px`,
      // 容器头部区域垂直内边距
      '--header-intersect-padding': '7px',
      // 容器整体高度
      '--container-height': this.containerHeightForStyle,
    };
  }

  /** scopedSlots 参数 */
  get scopedSlotsParam() {
    return {
      isExpand: this.isExpand,
    };
  }

  mounted() {
    this.initConfig();
  }

  /**
   * @description 初始化配置
   */
  initConfig() {
    if (!this.containerHeight) {
      this.containerHeight = this.defaultHeight;
    }
    this.isExpand = this.defaultIsExpand;
  }

  /**
   * @description 拖拽 resize 操作后回调
   * @param {number} height  拖拽操作后的新高度
   * */
  handleCrossResize(height: number) {
    this.containerHeight = height;
  }

  /**
   * @description: 展开/收起 折叠面板
   */
  handleExpandChange() {
    this.isExpand = !this.isExpand;
  }

  /**
   * @description 默认 header 中 触发展开收起trigger 区域渲染
   */
  defaultHeaderCustomRender() {
    return <div class='default-header-custom' />;
  }

  /**
   * @description header 中能够触发展开收起事件的 trigger 区域默认元素渲染函数
   */
  defaultHeaderTriggerRender() {
    return (
      <div class='header-trigger-default'>
        <i class='icon-monitor icon-mc-triangle-down chart-icon' />
        <span class='chart-trigger-title'>{this.title}</span>
        <span class='chart-trigger-description'>
          {(this.$scopedSlots as any)?.triggerDescription?.(this.scopedSlotsParam) || this.description}
        </span>
      </div>
    );
  }

  render() {
    return (
      <div
        style={this.cssVars}
        class={`explore-collapse-wrapper ${this.isExpand ? 'is-expand' : ''}`}
      >
        <div class='explore-collapse-wrapper-collapse'>
          <div class='explore-collapse-wrapper-container'>
            <div class='explore-collapse-header'>
              <div
                class='explore-collapse-header-trigger'
                onClick={this.handleExpandChange}
              >
                {(this.$scopedSlots as any)?.headerTrigger?.(this.scopedSlotsParam) ||
                  this.defaultHeaderTriggerRender()}
              </div>
              <div class='explore-collapse-header-custom'>
                {(this.$scopedSlots as any)?.headerCustom?.(this.scopedSlotsParam) || this.defaultHeaderCustomRender()}
              </div>
            </div>
            <div class='explore-collapse-content'>{this.$slots?.default || ''}</div>
            {this.hasResize && <MonitorCrossDrag onMove={this.handleCrossResize} />}
          </div>
        </div>
      </div>
    );
  }
}
