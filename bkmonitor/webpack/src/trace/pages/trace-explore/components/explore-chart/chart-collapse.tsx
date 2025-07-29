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

import { computed, defineComponent, onMounted, shallowRef } from 'vue';

import { get, set } from '@vueuse/core';

import MonitorCrossDrag from '../../../../components/monitor-cross-drag/monitor-cross-drag';

import './chart-collapse.scss';

export default defineComponent({
  name: 'ChartCollapse',
  props: {
    /** header 区域标题 */
    title: {
      type: String,
    },
    /** header 区域描述 */
    description: {
      type: String,
    },
    /** 默认高度（初始化时 container 区域的高度） */
    defaultHeight: {
      type: Number,
      default: 166,
    },
    /** 初始化时折叠面板默认是否展开状态 */
    defaultIsExpand: {
      type: Boolean,
      default: true,
    },
    /** 是否需要 resize 功能 */
    hasResize: {
      type: Boolean,
      default: true,
    },
    /** 折叠收起时需要展示内容的高度 */
    collapseShowHeight: {
      type: Number,
      default: 36,
    },
  },
  setup(props, { slots }) {
    /** 折叠面板，是否展开图表 */
    const isExpand = shallowRef(true);
    /** 显示内容区域高度 -- 主要用于配合 resize 操作时使用 */
    const containerHeight = shallowRef(0);

    const scopedSlotsParam = computed(() => ({
      isExpand: isExpand.value,
    }));

    /** 将chart容器高度转换成 css height 属性 */
    const chartContainerHeightForStyle = computed(() =>
      containerHeight.value ? `${containerHeight.value}px` : 'auto'
    );
    /** css 变量 */
    const cssVars = computed(() => ({
      // 容器头部高度（也是折叠状态下需要显示的高度）
      '--header-height': `${props.collapseShowHeight}px`,
      // 容器头部区域垂直内边距
      '--header-intersect-padding': '0px',
      // 容器整体高度
      '--container-height': chartContainerHeightForStyle.value,
      // 容器切换折叠状态时动画持续时长
      '--expand-animation-duration': '0.6s',
    }));

    onMounted(() => {
      initConfig();
    });

    /**
     * @description 初始化配置
     */
    function initConfig() {
      if (!containerHeight.value) {
        set(containerHeight, props.defaultHeight);
      }
      set(isExpand, props.defaultIsExpand);
    }

    /**
     * @description 拖拽 resize 操作后回调
     * @param {number} height  拖拽操作后的新高度
     * */
    function handleCrossResize(height: number) {
      set(containerHeight, height);
    }

    /**
     * @description: 展开/收起 折叠面板
     */
    function handleExpandChange() {
      set(isExpand, !get(isExpand));
    }

    /**
     * @description 默认 header 中 触发展开收起trigger 区域渲染
     */
    function defaultHeaderCustomRender() {
      return <div class='default-header-custom' />;
    }

    /**
     * @description header 中能够触发展开收起事件的 trigger 区域默认元素渲染函数
     */
    function defaultHeaderTriggerRender() {
      return (
        <div class='header-trigger-default'>
          <i class='icon-monitor icon-mc-triangle-down chart-icon' />
          <span class='chart-trigger-title'>{props.title}</span>
          <span class='chart-trigger-description'>
            {(slots as any)?.triggerDescription?.(scopedSlotsParam.value) || props.description}
          </span>
        </div>
      );
    }

    return {
      cssVars,
      isExpand,
      scopedSlotsParam,
      handleCrossResize,
      handleExpandChange,
      defaultHeaderCustomRender,
      defaultHeaderTriggerRender,
    };
  },

  render() {
    return (
      <div
        style={this.cssVars}
        class={`chart-collapse-wrapper ${this.isExpand ? 'is-expand' : ''}`}
      >
        <div class='chart-collapse-wrapper-collapse'>
          <div class='chart-collapse-wrapper-container'>
            <div class='chart-collapse-header'>
              <div
                class='chart-collapse-header-trigger'
                onClick={this.handleExpandChange}
              >
                {(this.$slots as any)?.headerTrigger?.(this.scopedSlotsParam) || this.defaultHeaderTriggerRender()}
              </div>
              <div class='chart-collapse-header-custom'>
                {(this.$slots as any)?.headerCustom?.(this.scopedSlotsParam) || this.defaultHeaderCustomRender()}
              </div>
            </div>
            <div class='chart-collapse-content'>{this.$slots?.default?.(this.scopedSlotsParam) || ''}</div>
            {this.hasResize && <MonitorCrossDrag onMove={this.handleCrossResize} />}
          </div>
        </div>
      </div>
    );
  },
});
