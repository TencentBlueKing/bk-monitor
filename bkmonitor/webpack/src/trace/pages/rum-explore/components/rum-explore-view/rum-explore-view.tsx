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
import { defineComponent, useTemplateRef, watch } from 'vue';

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
  },
  setup(props) {
    const backTopRef = useTemplateRef<InstanceType<typeof BackTop>>('backTopRef');

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

    return {};
  },
  render() {
    return (
      <div class={RUM_EXPLORE_VIEW_CLASS}>
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
