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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';

import './collapse-tags.scss';

type CollapseTagsProps = {
  /** 需要渲染的tag数组 */
  data: string[] | unknown[];
  /** 标签溢出时溢出标签hover显示的提示内容 */
  ellipsisTip?: (ellipsisList: string[] | unknown[]) => Element;
  /** 是否启用标签溢出时省略显示 */
  enableEllipsis?: boolean;
  /** tag 之间的水平间距（默认为 4px），不建议另外css单独设置，计算tag宽度溢出时需要使用该值进行计算 */
  tagColGap?: number;
};

@Component
export default class CollapseTags extends tsc<CollapseTagsProps> {
  /** 根元素实例 */
  @Ref('tagContainerRef') tagContainerRef: Record<string, any>;
  /** 标签容器实例 */
  @Ref('sectionRef') sectionRef: Record<string, any>;
  /** 最大折叠数字渲染元素实例 */
  @Ref('maxCountCollectTagRef') maxCountCollectTagRef: Record<string, any>;
  /** 后置插槽容器实例 */
  @Ref('afterSlotContainerRef') afterSlotContainerRef: Record<string, any>;

  /** 需要渲染的tag数组 */
  @Prop({ type: Array, default: () => [] }) data!: string[] | unknown[];
  /** tag 之间的水平间距（默认为 4px），不建议另外css单独设置，计算tag宽度溢出时需要使用该值进行计算 */
  @Prop({ type: Number, default: 4 }) tagColGap: number;
  /** 是否启用标签溢出时省略显示 */
  @Prop({ type: Boolean, default: true }) enableEllipsis: boolean;
  /** 标签溢出时溢出标签hover显示的提示内容 */
  @Prop({ type: Function }) ellipsisTip: (ellipsisList: string[] | unknown[]) => Element;
  /** 占位符 */
  @Prop({ type: String, default: '--' }) placeholder: string;

  /** 尺寸监听器实例 */
  resizeObserverInstance = null;
  /** 视口监听器实例 */
  intersectionObserverInstance = null;
  /** 标签容器最后一次宽度缓存 */
  lastTagContainerWidth = 0;

  /** 显示最大数量折叠标签实例（主要用于计算不用于展示） */
  calculateTagCount = this.data?.length || 0;
  /** 容器宽度是否发生了改变 */
  hasResize = true;
  /** 标签容器是否在可视区域 */
  isInViewport = false;

  get cssVars() {
    return {
      '--tag-col-gap': `${this.tagColGap}px`,
    };
  }

  @Watch('data')
  dataChange() {
    this.calculateOverflow();
  }
  @Watch('enableEllipsis')
  enableEllipsisChange() {
    this.calculateOverflow();
  }

  @Watch('tagContainerRef')
  tagContainerChange(nVal) {
    if (!nVal) {
      return;
    }
    this.cleanupObserver();
    this.$nextTick(this.setupObserver);
  }
  mounted() {
    this.$nextTick(this.setupObserver);
  }

  beforeDestroy() {
    this.cleanupObserver();
  }

  /**
   * @description 核心计算逻辑（带防抖）
   **/
  @Debounce(200)
  calculateOverflow() {
    if (!this.isInViewport || !this.hasResize) return;
    this.calculateTagCount = this?.data?.length || 0;
    if (!this.enableEllipsis) {
      return;
    }
    requestAnimationFrame(() => {
      const tagsList = this.sectionRef?.children || [];
      // 缓存当前帧中tag元素的宽高信息对象，避免频繁调用getBoundingClientRect影响性能
      const tagElBoundingClientRectMap = new WeakMap();
      // 获取后置插槽宽度(包括渲染后置插槽元素时多出的间隔宽度)
      const afterSlotContainerWidth = (this.$scopedSlots as any)?.after
        ? this.afterSlotContainerRef?.getBoundingClientRect?.()?.width + this.tagColGap
        : 0;
      // 获取容器宽度
      const containerWidth = this.sectionRef?.parentNode?.getBoundingClientRect?.().width - afterSlotContainerWidth;
      let totalWidth = 0;
      let visibleCount = 0;

      // 第一轮：计算在不显示折叠标签时能容纳的标签数量
      for (let i = 0; i < tagsList.length; i++) {
        const elRect = tagsList[i]?.getBoundingClientRect?.();
        tagElBoundingClientRectMap.set(tagsList[i], elRect);
        const tagWidth = elRect?.width;
        const newWidth = totalWidth + tagWidth + (i > 0 ? this.tagColGap : 0);
        if (newWidth < containerWidth) {
          totalWidth = newWidth;
          visibleCount = i + 1;
        } else {
          break;
        }
      }

      // 如果所有标签都能显示，则不需要折叠
      if (visibleCount === tagsList.length) {
        this.calculateTagCount = visibleCount;
        return;
      }

      // 如果执行到这里了，那么说明 折叠标签元素 肯定是需要显示的，所以 totalWidth 需要加上 折叠标签的宽度以及间隔宽度
      const collectTagWidth = this.maxCountCollectTagRef?.getBoundingClientRect?.().width || 0;
      totalWidth = totalWidth + collectTagWidth + this.tagColGap;
      if (totalWidth < containerWidth) {
        this.calculateTagCount = visibleCount;
        return;
      }

      // 第二轮：走到这里则说明剩余的空间不足以显示折叠标签，所以需要逐个递减至可以容纳折叠标签
      while (visibleCount > 0) {
        visibleCount--;
        const elRect =
          tagElBoundingClientRectMap.get(tagsList[visibleCount]) || tagsList[visibleCount]?.getBoundingClientRect?.();
        const tagWidth = elRect?.width;
        totalWidth = totalWidth - tagWidth - this.tagColGap;
        if (totalWidth < containerWidth) break;
      }
      this.calculateTagCount = Math.max(visibleCount, 0); // 确保visibleCount不为负数
    });
  }

  /**
   * @description 设置观察器
   **/
  setupObserver() {
    this.setupResizeObserver();
    this.setupIntersectionObserver();
  }

  /**
   * @description 设置resize观察器(目前场景只需要监听水平方向)
   */
  setupResizeObserver() {
    if (!this.resizeObserverInstance) {
      this.resizeObserverInstance = new ResizeObserver(entries => {
        for (const entry of entries) {
          const currentWidth = entry.contentRect.width;
          if (currentWidth === this.lastTagContainerWidth) {
            return;
          }
          this.lastTagContainerWidth = currentWidth;
          this.hasResize = true;
          this.calculateOverflow();
        }
      });
      if (this.tagContainerRef) this.resizeObserverInstance.observe(this.tagContainerRef);
    }
  }

  /**
   * @description 设置IntersectionObserver观察器
   */
  setupIntersectionObserver() {
    if (!this.intersectionObserverInstance) {
      this.intersectionObserverInstance = new IntersectionObserver(entries => {
        for (const entry of entries) {
          this.isInViewport = entry.isIntersecting;
          this.calculateOverflow();
        }
      });
      if (this.tagContainerRef) this.intersectionObserverInstance.observe(this.tagContainerRef);
    }
  }

  /**
   * @description 清理观察器
   */
  cleanupObserver() {
    if (this.resizeObserverInstance) {
      this.resizeObserverInstance.disconnect();
      this.resizeObserverInstance = null;
    }
    if (this.intersectionObserverInstance) {
      this.intersectionObserverInstance.disconnect();
      this.intersectionObserverInstance = null;
    }
  }

  render() {
    /** 数据总长度 */
    const dataLen = (this.data || []).length;
    if (dataLen === 0) {
      return (
        <div class='bk-common-v2-tag-empty-placeholder'>
          {(this.$scopedSlots as any)?.placeholder?.() || this.placeholder}
          {(this.$scopedSlots as any)?.after ? (
            <span
              ref='afterSlotContainerRef'
              class='after-slot-container'
            >
              {(this.$scopedSlots as any)?.after([], [])}
            </span>
          ) : null}
        </div>
      );
    }
    /** 折叠个数 */
    const collapseCount = dataLen - this.calculateTagCount;
    /** 是否展示折叠标签 */
    const canShowCollapseTag = collapseCount > 0;
    /** 需要渲染的数据数组 */
    const showList = (this.data || []).slice(0, this.calculateTagCount);
    /** 折叠的数据数组 */
    const ellipsisList = (this.data || []).slice(this.calculateTagCount);
    return (
      <span
        ref='tagContainerRef'
        style={this.cssVars}
        class='bk-common-v2-tag-show'
      >
        <span
          ref='sectionRef'
          class='item-tags'
        >
          {showList.map((tag, index) => {
            return (this.$scopedSlots as any)?.customTag?.(tag, index) || <bk-tag key={index}>{tag}</bk-tag>;
          })}
        </span>
        {canShowCollapseTag && (
          <span
            class='collapse-tag'
            v-bk-tooltips={{
              content: this.ellipsisTip ? this.ellipsisTip(ellipsisList) : ellipsisList.join(', '),
              theme: 'dark text-wrap max-width-50vw',
              delay: 300,
            }}
          >
            +{collapseCount}
          </span>
        )}
        {(this.$scopedSlots as any)?.after ? (
          <span
            ref='afterSlotContainerRef'
            class='after-slot-container'
          >
            {(this.$scopedSlots as any)?.after(this.data, ellipsisList)}
          </span>
        ) : null}
        <span
          ref='maxCountCollectTagRef'
          class='collapse-tag collapse-tag-fill'
        >
          +{dataLen}
        </span>
      </span>
    );
  }
}
