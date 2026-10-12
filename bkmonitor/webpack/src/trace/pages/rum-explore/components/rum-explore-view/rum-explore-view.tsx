/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { defineComponent, onBeforeUnmount, onMounted, useTemplateRef, watch } from 'vue';

import BackTop from '../../../../components/back-top/back-top';
import { RUM_EXPLORE_VIEW_CLASS } from '../../constants';

import './rum-explore-view.scss';

export default defineComponent({
  name: 'RumExploreView',
  props: {
    /**
     * 回到顶部信号。
     * 当该值发生变化时，视图容器会自动滚动到顶部（无动画）。
     * 由数据层（useRumTableData）在查询/排序/时间范围/刷新变化时重新生成。
     */
    backTopSignal: {
      type: String,
      default: '',
    },
    /**
     * 容器高度变化时是否同步插槽内吸顶元素的定位。
     * 仅当插槽内容带吸顶表头（表格 headerAffixedTop）时才需要开启，默认关闭。
     */
    syncAffixOnResize: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const backTopRef = useTemplateRef<InstanceType<typeof BackTop>>('backTopRef');
    /** 根节点：表格的滚动容器，也是插槽内吸顶表头（tdesign Affix）锚定的容器 */
    const viewRef = useTemplateRef<HTMLElement>('viewRef');
    /** 容器尺寸观察器，仅在 syncAffixOnResize 开启时创建 */
    let viewResizeObserver: ResizeObserver = null;
    /** 上一次观测到的容器高度，用于过滤纯宽度变化 */
    let viewHeight = 0;
    /** 待执行的吸顶重算帧 id，用于合并同一帧内的多次尺寸变化 */
    let affixSyncRafId = 0;

    /**
     * @description 容器高度变化时同步插槽内吸顶元素的定位
     * 插槽内表格的吸顶表头是 position: fixed（tdesign Affix），top 由本容器 rect 推导，
     * 却只在「容器 scroll / window resize」时重算，常驻筛选收起等纵向重排没有这两个事件，
     * 表头会停在旧位置遮挡表格，因此在容器高度变化后补一次重算。
     * 只在 window 上派发 resize：在容器上派发 scroll 会被触底加载逻辑当成真实滚动而多请求一页数据；
     * 纯宽度变化不派发，吸顶错位只由纵向重排引起。
     * @param {ResizeObserverEntry[]} entries 尺寸变化条目，取第一条的 contentRect 高度做比对
     * @returns {void}
     */
    const syncAffixPosition = (entries: ResizeObserverEntry[]) => {
      const height = entries[0]?.contentRect?.height ?? 0;
      if (height === viewHeight) return;
      viewHeight = height;
      if (affixSyncRafId) return;
      affixSyncRafId = window.requestAnimationFrame(() => {
        affixSyncRafId = 0;
        window.dispatchEvent(new Event('resize'));
      });
    };

    /**
     * @description 回到顶部
     * @param {boolean} enableAnimate 是否启用动画
     */
    const handleBackTop = (enableAnimate = true) => {
      backTopRef.value?.handleBackTop?.(enableAnimate);
    };

    // 监听数据层信号，查询/排序/时间范围/刷新变化时无动画回到顶部
    watch(
      () => props.backTopSignal,
      () => {
        if (props.backTopSignal) {
          handleBackTop(false);
        }
      }
    );

    onMounted(() => {
      if (!props.syncAffixOnResize || !viewRef.value) return;
      viewResizeObserver = new ResizeObserver(syncAffixPosition);
      viewResizeObserver.observe(viewRef.value);
    });
    onBeforeUnmount(() => {
      viewResizeObserver?.disconnect();
      if (affixSyncRafId) {
        window.cancelAnimationFrame(affixSyncRafId);
      }
    });

    return {};
  },
  render() {
    return (
      <div
        ref='viewRef'
        class={RUM_EXPLORE_VIEW_CLASS}
      >
        {this.$slots.affixedTop ? <div class='rum-explore-view-affixed-top'>{this.$slots.affixedTop?.()}</div> : null}
        <div class='rum-explore-view-table'>{this.$slots.default?.()}</div>
        <BackTop
          ref='backTopRef'
          class='back-to-top'
          scrollTop={100}
        >
          <i class='icon-monitor icon-BackToTop' />
        </BackTop>
      </div>
    );
  },
});
