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
import {
  type PropType,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onUpdated,
  shallowRef,
  useTemplateRef,
  watch,
} from 'vue';

import { RumEllipsisModeEnum } from '../../constants';

import type { RumEllipsisModeType } from '../../constants';

import './ellipsis-text.scss';

/** 中间省略插入的省略号，不参与字符截断计算 */
const ELLIPSIS_DOT = '...';
/** 中间省略时尾部保留的字符占比 */
const TAIL_RATIO = 1 / 3;
/** 判断能否放下时的容差，抵消 clientWidth 取整与文本宽度亚像素的差异 */
const WIDTH_TOLERANCE = 0.5;
/** canvas 粗测可能略小于真实布局宽度，DOM 精测回退次数上限 */
const DOM_RETRY_LIMIT = 3;

/** 所有实例共享的隐藏测量节点与 canvas，避免每个单元格都往 body 挂节点 */
let measureElement: HTMLElement = null;
let measureFontKey = '';
let measureContext: CanvasRenderingContext2D = null;

const getMeasureElement = () => {
  if (!measureElement) {
    measureElement = document.createElement('span');
    measureElement.style.cssText =
      'position: absolute; top: 0; left: -9999px; visibility: hidden; white-space: pre; pointer-events: none;';
    document.body.appendChild(measureElement);
  }
  return measureElement;
};

/**
 * 每次截断只取一次计算样式，之后 canvas 粗测与 DOM 精测复用同一套字体。
 * canvas 只用来快速二分，最终结果再用真实布局校验。
 */
const createMeasurer = (source: HTMLElement) => {
  const style = window.getComputedStyle(source);
  const node = getMeasureElement();
  const fontKey = `${style.fontWeight}|${style.fontSize}|${style.fontFamily}|${style.letterSpacing}`;
  if (fontKey !== measureFontKey) {
    measureFontKey = fontKey;
    node.style.fontFamily = style.fontFamily;
    node.style.fontSize = style.fontSize;
    node.style.fontWeight = style.fontWeight;
    node.style.letterSpacing = style.letterSpacing;
  }
  if (!measureContext) measureContext = document.createElement('canvas').getContext('2d');
  measureContext.font = `${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
  (measureContext as CanvasRenderingContext2D & { letterSpacing: string }).letterSpacing =
    style.letterSpacing === 'normal' ? '0px' : style.letterSpacing;
  return {
    byCanvas: (value: string) => measureContext.measureText(value).width,
    byDom: (value: string) => {
      node.textContent = value;
      return node.getBoundingClientRect().width;
    },
  };
};

/** 共享 ResizeObserver：所有单元格共用一个观察器，按元素分发回调 */
const resizeCallbacks = new WeakMap<Element, Set<(width: number) => void>>();
let sharedResizeObserver: ResizeObserver = null;

const observeResize = (element: Element, callback: (width: number) => void) => {
  if (!sharedResizeObserver) {
    sharedResizeObserver = new ResizeObserver(entries => {
      entries.forEach(entry => {
        resizeCallbacks.get(entry.target)?.forEach(handler => {
          handler(entry.contentRect.width);
        });
      });
    });
  }
  let callbacks = resizeCallbacks.get(element);
  if (!callbacks) {
    callbacks = new Set();
    resizeCallbacks.set(element, callbacks);
    sharedResizeObserver.observe(element);
  }
  callbacks.add(callback);
};

/** 复合单元格一个 td 内有多段省略文本，只移除实例自己的回调，其余实例仍在观察时保持订阅 */
const unobserveResize = (element: Element, callback: (width: number) => void) => {
  const callbacks = resizeCallbacks.get(element);
  if (!callbacks) return;
  callbacks.delete(callback);
  if (callbacks.size > 0) return;
  resizeCallbacks.delete(element);
  sharedResizeObserver?.unobserve(element);
};

/**
 * 单元格文本省略展示，根节点就是文本容器，调用方的 class 与事件通过 attrs 透传。
 * end / start 只改 CSS，DOM 保留完整文本；middle 用二分截断生成 head...tail，并通过 data-full-text 把完整文本交给悬浮提示。
 * 根节点的 data-ellipsis-text 与 data-full-text 是省略状态的对外契约，dom-helper 据此判断是否已省略。
 */
export default defineComponent({
  name: 'RumEllipsisText',
  inheritAttrs: false,
  props: {
    /** 完整文本 */
    text: {
      type: String,
      default: '',
    },
    /** 省略方式，默认与控件默认值一致：开头省略 */
    mode: {
      type: String as PropType<RumEllipsisModeType>,
      default: RumEllipsisModeEnum.START,
    },
  },
  setup(props) {
    const rootRef = useTemplateRef<HTMLElement>('rootRef');
    /** 中间省略时实际展示的文本，end / start 直接用完整文本 */
    const displayText = shallowRef(props.text);
    /** 是否被中间省略截断：截断后不再溢出，需要额外标记给悬浮提示 */
    const isTruncated = shallowRef(false);
    /** 观察的列单元格与上次宽度，宽度没变就不重算 */
    let observedElement: Element = null;
    let observedWidth = 0;

    /**
     * 渲染后校验真实溢出：flex 布局会随内容收缩，测量时算出的可用宽度可能偏大，
     * 截断文本仍溢出就会再叠出 CSS 省略号，这里按实际宽度再截一次。
     */
    const verifyTruncation = (text: string, round: number) => {
      if (round >= DOM_RETRY_LIMIT) return;
      nextTick(() => {
        const element = rootRef.value;
        if (!element || props.mode !== RumEllipsisModeEnum.MIDDLE) return;
        // scrollWidth 会向上取整，1px 内视为不溢出
        if (element.scrollWidth - element.clientWidth <= 1.5) return;
        truncateMiddle(element, text, element.clientWidth, round + 1);
      });
    };

    /** 按真实可用宽度二分截断；根元素宽度只有在完整文本状态下才等于布局给出的可用宽度 */
    const truncateMiddle = (element: HTMLElement, text: string, width: number, round = 0) => {
      if (!width) {
        displayText.value = text;
        isTruncated.value = false;
        return;
      }
      const measurer = createMeasurer(element);
      if (measurer.byDom(text) <= width + WIDTH_TOLERANCE) {
        displayText.value = text;
        isTruncated.value = false;
        verifyTruncation(text, round);
        return;
      }
      // 按码点切分，避免把 emoji 等代理对截断成乱码
      const chars = Array.from(text);
      const tailLength = Math.max(1, Math.floor(chars.length * TAIL_RATIO));
      const tail = chars.slice(-tailLength).join('');
      const limit = Math.max(width - WIDTH_TOLERANCE, 0);
      const buildText = (headLength: number) => `${chars.slice(0, headLength).join('')}${ELLIPSIS_DOT}${tail}`;
      let low = 0;
      let high = chars.length - tailLength;
      while (low < high) {
        const middle = Math.ceil((low + high) / 2);
        if (measurer.byCanvas(buildText(middle)) <= limit) low = middle;
        else high = middle - 1;
      }
      // canvas 宽度与真实布局有偏差时，用共享节点精测并回退
      let head = low;
      let retry = 0;
      while (head > 0 && retry < DOM_RETRY_LIMIT && measurer.byDom(buildText(head)) > limit) {
        head -= 1;
        retry += 1;
      }
      displayText.value = buildText(head);
      isTruncated.value = true;
      verifyTruncation(text, round);
    };

    const updateMiddleText = () => {
      const element = rootRef.value;
      const text = props.text ?? '';
      if (!element || props.mode !== RumEllipsisModeEnum.MIDDLE || !text) {
        displayText.value = text;
        isTruncated.value = false;
        return;
      }
      // 已截断时先恢复完整文本，等布局按全文算完再取可用宽度
      if (displayText.value !== text) {
        displayText.value = text;
        nextTick(() => {
          const current = rootRef.value;
          if (current && props.mode === RumEllipsisModeEnum.MIDDLE) {
            truncateMiddle(current, props.text ?? '', current.clientWidth);
          }
        });
        return;
      }
      truncateMiddle(element, text, element.clientWidth);
    };

    /** 宽度变化回调：只有宽度真的变了才重算，避免高度等变化引起无效重排 */
    const handleResize = (width: number) => {
      if (props.mode !== RumEllipsisModeEnum.MIDDLE || Math.abs(width - observedWidth) < 1) return;
      observedWidth = width;
      updateMiddleText();
    };

    /** 只有中间省略需要观察宽度；观察单元格而不是根元素，根元素会随截断收缩导致循环 */
    const syncResizeObserver = () => {
      const element = rootRef.value;
      if (props.mode !== RumEllipsisModeEnum.MIDDLE || !element) {
        if (observedElement) unobserveResize(observedElement, handleResize);
        observedElement = null;
        observedWidth = 0;
        return;
      }
      const target = element.closest('td') ?? element.parentElement ?? element;
      if (target === observedElement) return;
      if (observedElement) unobserveResize(observedElement, handleResize);
      observedElement = target;
      // 置 0 让首次回调通过过滤，列重建后也能重新计算一次
      observedWidth = 0;
      observeResize(target, handleResize);
    };

    const refresh = () => {
      updateMiddleText();
      syncResizeObserver();
    };

    watch(
      () => [props.text, props.mode],
      () => {
        nextTick(refresh);
      },
      { immediate: true }
    );
    /** 列宽拖拽可能重建单元格，组件复用时观察目标会失效，这里按需重新绑定 */
    onUpdated(() => {
      syncResizeObserver();
    });
    onBeforeUnmount(() => {
      if (observedElement) unobserveResize(observedElement, handleResize);
      observedElement = null;
    });

    return { rootRef, displayText, isTruncated };
  },
  render() {
    return (
      <span
        ref='rootRef'
        {...this.$attrs}
        class={['rum-ellipsis-text', `is-${this.mode}`, this.$attrs.class]}
        data-ellipsis-text={this.mode}
        data-full-text={this.isTruncated ? this.text : undefined}
      >
        {this.mode === RumEllipsisModeEnum.MIDDLE ? this.displayText : <bdi dir='ltr'>{this.text}</bdi>}
      </span>
    );
  },
});
