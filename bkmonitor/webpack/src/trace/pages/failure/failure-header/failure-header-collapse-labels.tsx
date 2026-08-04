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
import { type PropType, computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue';

import { Tag } from 'bkui-vue';

import './failure-header-collapse-labels.scss';

/** 标签之间的水平间距，需与样式 column-gap 保持一致 */
const TAG_GAP = 4;

/**
 * 故障详情 Header 专用的单行标签折叠组件。
 * 标签过多时不换行，超出部分收成 +N；hover +N 时 tooltip 逐行展示被折叠项。
 */
export default defineComponent({
  name: 'FailureHeaderCollapseLabels',
  props: {
    /** 故障标签原始列表，展示前会去掉 `/` */
    labels: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
  },
  setup(props) {
    /** 根容器，用于读取可用宽度 */
    const containerRef = ref<HTMLElement | null>(null);
    /** 测量层：始终渲染全部标签，不影响可见布局 */
    const measureLabelsRef = ref<HTMLElement | null>(null);
    /** 测量用的 +N 节点，宽度按「+全部数量」预留，避免位数变化导致换行 */
    const measurePlusRef = ref<HTMLElement | null>(null);
    /** 当前可见标签数量，初始按全量展示，挂载后再按宽度折叠 */
    const visibleCount = ref((props.labels || []).length);
    /** 祖先节点尺寸监听，需在卸载时断开 */
    let resizeObserver: null | ResizeObserver = null;

    /** 清洗后的展示文案（去掉 `/`，与历史 Header Tag 规则一致） */
    const displayLabels = computed(() => (props.labels || []).map(item => String(item ?? '').replace(/\//g, '')));

    /**
     * 可用宽度取父级 `.info-name-extra` 扣除「编辑」后的剩余空间。
     * 不能用自身 clientWidth：折叠后自身会缩成内容宽，窗口变大时无法再展开。
     */
    const getAvailableWidth = () => {
      const el = containerRef.value;
      const extra = el?.parentElement;
      if (!extra) return el?.clientWidth || 0;
      const editEl = extra.querySelector('.info-edit') as HTMLElement | null;
      const editWidth = editEl?.offsetWidth || 0;
      const marginRight = el ? Number.parseFloat(getComputedStyle(el).marginRight) || 0 : 0;
      return Math.max(extra.clientWidth - editWidth - marginRight, 0);
    };

    /**
     * 按可用宽度计算单行可展示的标签数量。
     * 全部能放下则不折叠；否则从末尾递减，给 +N 留出位置。
     */
    const calculateVisibleCount = () => {
      const labels = displayLabels.value;
      if (!labels.length) {
        visibleCount.value = 0;
        return;
      }

      const containerWidth = getAvailableWidth();
      const measureWrap = measureLabelsRef.value;
      // 容器尚未撑开时不计算，避免把 visibleCount 误判为 0
      if (!containerWidth || !measureWrap) return;

      const tagEls = measureWrap.querySelectorAll<HTMLElement>('.header-collapse-label-item');
      const widths: number[] = [];
      tagEls.forEach(el => widths.push(el.offsetWidth));
      if (!widths.length) return;

      /** 用「+全部数量」预估 +N 宽度，避免 +9 变成 +10 时把编辑挤下去 */
      const plusWidth = measurePlusRef.value?.offsetWidth || 0;

      /**
       * 计算前 n 个标签占用的总宽度。
       * @param count 计入的标签个数
       * @param withPlus 是否额外加上 +N 及其间距
       */
      const calcWidth = (count: number, withPlus: boolean) => {
        let width = 0;
        for (let i = 0; i < count; i++) {
          width += (i > 0 ? TAG_GAP : 0) + (widths[i] || 0);
        }
        if (withPlus) {
          width += (count > 0 ? TAG_GAP : 0) + plusWidth;
        }
        return width;
      };

      // 全部能放下则不折叠
      if (calcWidth(widths.length, false) <= containerWidth) {
        visibleCount.value = widths.length;
        return;
      }

      // 从全量往回减，直到「可见标签 + +N」能放进当前宽度
      let count = widths.length;
      while (count > 0 && calcWidth(count, true) > containerWidth) {
        count--;
      }
      visibleCount.value = count;
    };

    /**
     * 观察 `.header-info`：它是 header 里的弹性区域，窗口缩放时宽度会变。
     */
    const setupObserver = () => {
      const el = containerRef.value;
      if (!el) return;
      cleanupObserver();
      const headerInfo = el.closest('.header-info');
      if (!headerInfo) return;
      resizeObserver = new ResizeObserver(() => {
        calculateVisibleCount();
      });
      resizeObserver.observe(headerInfo);
    };

    const cleanupObserver = () => {
      resizeObserver?.disconnect();
      resizeObserver = null;
    };

    // ref 挂上后再绑定观察器，避免节点未就绪时漏绑
    watch(
      () => containerRef.value,
      el => {
        if (!el) {
          cleanupObserver();
          return;
        }
        nextTick(() => {
          calculateVisibleCount();
          setupObserver();
        });
      }
    );

    // 标签数据变化时先按全量渲染，再在下一帧按实际宽度折叠，减少闪烁
    watch(
      () => displayLabels.value,
      list => {
        visibleCount.value = list.length;
        nextTick(calculateVisibleCount);
      }
    );

    onMounted(() => {
      window.addEventListener('resize', calculateVisibleCount);
      nextTick(() => {
        calculateVisibleCount();
        setupObserver();
      });
    });

    onBeforeUnmount(() => {
      window.removeEventListener('resize', calculateVisibleCount);
      cleanupObserver();
    });

    return {
      containerRef,
      measureLabelsRef,
      measurePlusRef,
      visibleCount,
      displayLabels,
      /** hover +N 时逐行展示被折叠的标签，与 TagDisplay 一样走 v-bk-tooltips 的 VNode content */
      renderCollapsedTip: () => {
        const collapsedLabels = displayLabels.value.slice(visibleCount.value);
        return (
          <div class='failure-header-collapse-labels-tip'>
            {collapsedLabels.map((item, index) => (
              <div key={`${item}-${index}`}>{item}</div>
            ))}
          </div>
        );
      },
    };
  },
  render() {
    const labels = this.displayLabels;
    if (!labels.length) return null;

    const collapseCount = labels.length - this.visibleCount;
    const showPlus = collapseCount > 0;
    const visibleLabels = labels.slice(0, this.visibleCount);

    return (
      <span
        ref='containerRef'
        class='failure-header-collapse-labels'
      >
        {/* 可见层：只渲染当前能放下的标签 */}
        <span class='visible-labels'>
          {visibleLabels.map((item, index) => (
            <Tag
              key={`${item}-${index}`}
              class='header-collapse-label-item'
            >
              {item}
            </Tag>
          ))}
        </span>
        {showPlus && (
          <span
            key={`plus-${this.visibleCount}`}
            class='header-collapse-plus'
            v-bk-tooltips={{
              content: this.renderCollapsedTip(),
            }}
          >
            +{collapseCount}
          </span>
        )}
        {/* 测量层：始终渲染全部标签，供宽度计算使用 */}
        <span
          ref='measureLabelsRef'
          class='measure-labels'
        >
          {labels.map((item, index) => (
            <Tag
              key={`measure-${item}-${index}`}
              class='header-collapse-label-item'
            >
              {item}
            </Tag>
          ))}
        </span>
        {/* 隐藏的 +N，用于预留折叠标记宽度 */}
        <span
          ref='measurePlusRef'
          class='header-collapse-plus measure-plus'
        >
          +{labels.length}
        </span>
      </span>
    );
  },
});
