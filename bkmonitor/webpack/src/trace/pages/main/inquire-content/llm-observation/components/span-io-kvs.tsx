/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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

import { type PropType, computed, defineComponent, nextTick, shallowRef, watch } from 'vue';

import { useResizeObserver } from '@vueuse/core';

import type { LlmKvPair } from '../../../llm-observation/utils/typings';

import './span-io-kvs.scss';

/** overflow-tips 内容过长时截断，避免 Popover 撑满视口 */
export const sliceTooltipContent = (content: string): string =>
  content.length > 200 ? `${content.substring(0, 200)}...` : content;

/** 多 KV 时 value 共享 max-width 的下限：再小就改走裁剪 / 隐藏 */
const MIN_VALUE_MAX_WIDTH = 120;

type KvClipPart = '' | 'key' | 'value';

interface KvLayout {
  clipIndex: number;
  clipPart: KvClipPart;
  clipWidth: number;
  hiddenFrom: number;
}

const isFullLayout = (layout: KvLayout) => layout.clipIndex === -1 && layout.hiddenFrom === Number.POSITIVE_INFINITY;

/** 按内容宽度铺 KV；valueCap 用于多 KV 时先压 value，再决定裁剪 / 隐藏 */
const layoutKvs = (
  available: number,
  gap: number,
  keys: number[],
  values: number[],
  valueCap = Number.POSITIVE_INFINITY
): KvLayout => {
  let used = 0;
  let clipIndex = -1;
  let clipPart: KvClipPart = '';
  let clipWidth = 0;
  let hiddenFrom = Number.POSITIVE_INFINITY;
  for (let i = 0; i < keys.length; i++) {
    const extra = i === 0 ? 0 : gap;
    const keyWidth = keys[i];
    const valueWidth = Math.min(values[i], valueCap);
    if (used + extra + keyWidth + valueWidth <= available + 0.5) {
      used += extra + keyWidth + valueWidth;
      continue;
    }
    const remain = Math.max(0, available - used - extra);
    if (remain >= keyWidth + 1) {
      clipIndex = i;
      clipPart = 'value';
      clipWidth = remain;
      hiddenFrom = i + 1;
    } else if (remain >= 1) {
      clipIndex = i;
      clipPart = 'key';
      clipWidth = remain;
      hiddenFrom = i + 1;
    } else {
      hiddenFrom = i;
    }
    break;
  }
  return { clipIndex, clipPart, clipWidth, hiddenFrom };
};

/** 多个 KV 才压 value：尽量抬高共享 max-width，最低 120；压到 120 仍放不下则交给原裁剪逻辑 */
const resolveValueMaxWidth = (available: number, gap: number, keys: number[], values: number[]): number => {
  if (keys.length <= 1) return Number.POSITIVE_INFINITY;
  const longest = values.reduce((max, width) => Math.max(max, width), 0);
  if (longest <= MIN_VALUE_MAX_WIDTH) return Number.POSITIVE_INFINITY;
  if (isFullLayout(layoutKvs(available, gap, keys, values))) return Number.POSITIVE_INFINITY;
  if (!isFullLayout(layoutKvs(available, gap, keys, values, MIN_VALUE_MAX_WIDTH))) return MIN_VALUE_MAX_WIDTH;

  let low = MIN_VALUE_MAX_WIDTH;
  let high = longest;
  while (high - low > 0.5) {
    const mid = (low + high) / 2;
    if (isFullLayout(layoutKvs(available, gap, keys, values, mid))) low = mid;
    else high = mid;
  }
  return low;
};

/** 按内容宽度铺 KV：多 KV 时先动态压 value，再只给最后放不下的一项定宽打省略号 */
export default defineComponent({
  name: 'LlmSpanIoKvs',
  props: {
    pairs: {
      type: Array as PropType<LlmKvPair[]>,
      required: true,
    },
  },
  setup(props) {
    const rootRef = shallowRef<HTMLElement>();
    const clipIndex = shallowRef(-1);
    const clipPart = shallowRef<KvClipPart>('');
    const clipWidth = shallowRef(0);
    const hiddenFrom = shallowRef(Number.POSITIVE_INFINITY);
    const valueMaxWidth = shallowRef(Number.POSITIVE_INFINITY);
    const keyWidths = shallowRef<number[]>([]);
    const valueWidths = shallowRef<number[]>([]);

    const pairsSignature = computed(() => props.pairs.map(pair => `${pair.key}\0${pair.value}`).join('\0'));

    const readPieceWidth = (el: Element | null, fallback: number) => {
      if (!(el instanceof HTMLElement)) return fallback;
      return el.getBoundingClientRect().width || fallback;
    };

    /** value 可能已被 max-width 截断，用 scrollWidth 拿回自然宽度 */
    const readValueNaturalWidth = (el: Element | null, fallback: number) => {
      if (!(el instanceof HTMLElement)) return fallback;
      return Math.max(el.scrollWidth, el.getBoundingClientRect().width) || fallback;
    };

    const measure = () => {
      const root = rootRef.value;
      if (!root) return;
      const items = Array.from(root.children) as HTMLElement[];
      if (!items.length) {
        clipIndex.value = -1;
        clipPart.value = '';
        clipWidth.value = 0;
        hiddenFrom.value = Number.POSITIVE_INFINITY;
        valueMaxWidth.value = Number.POSITIVE_INFINITY;
        return;
      }

      const available = root.clientWidth;
      const gap = Number.parseFloat(getComputedStyle(root).columnGap || getComputedStyle(root).gap) || 0;
      const canReadAll = hiddenFrom.value === Number.POSITIVE_INFINITY;
      const nextKeys =
        canReadAll || keyWidths.value.length !== items.length
          ? items.map((el, index) => {
              if (!canReadAll && index >= hiddenFrom.value) return keyWidths.value[index] ?? 0;
              const keyEl = el.querySelector('.llm-span-io-kv-key');
              if (index === clipIndex.value && clipPart.value === 'key') {
                return Math.max(keyEl instanceof HTMLElement ? keyEl.scrollWidth : 0, keyWidths.value[index] ?? 0);
              }
              return readPieceWidth(keyEl, keyWidths.value[index] ?? 0);
            })
          : keyWidths.value;
      const nextValues =
        canReadAll || valueWidths.value.length !== items.length
          ? items.map((el, index) => {
              if (!canReadAll && index >= hiddenFrom.value) return valueWidths.value[index] ?? 0;
              const valueEl = el.querySelector('.llm-span-io-kv-value');
              if (index === clipIndex.value && clipPart.value === 'key') {
                return valueWidths.value[index] ?? 0;
              }
              return Math.max(readValueNaturalWidth(valueEl, 0), valueWidths.value[index] ?? 0);
            })
          : valueWidths.value;
      keyWidths.value = nextKeys;
      valueWidths.value = nextValues;

      const nextValueMaxWidth = resolveValueMaxWidth(available, gap, nextKeys, nextValues);
      const nextLayout = layoutKvs(available, gap, nextKeys, nextValues, nextValueMaxWidth);
      const sameValueMaxWidth =
        nextValueMaxWidth === valueMaxWidth.value || Math.abs(nextValueMaxWidth - valueMaxWidth.value) < 0.5;
      if (
        nextLayout.clipIndex === clipIndex.value &&
        nextLayout.clipPart === clipPart.value &&
        nextLayout.hiddenFrom === hiddenFrom.value &&
        Math.abs(nextLayout.clipWidth - clipWidth.value) < 0.5 &&
        sameValueMaxWidth
      ) {
        return;
      }
      clipIndex.value = nextLayout.clipIndex;
      clipPart.value = nextLayout.clipPart;
      clipWidth.value = nextLayout.clipWidth;
      hiddenFrom.value = nextLayout.hiddenFrom;
      valueMaxWidth.value = nextValueMaxWidth;
    };

    useResizeObserver(rootRef, measure);
    watch(pairsSignature, () => {
      clipIndex.value = -1;
      clipPart.value = '';
      clipWidth.value = 0;
      hiddenFrom.value = Number.POSITIVE_INFINITY;
      valueMaxWidth.value = Number.POSITIVE_INFINITY;
      keyWidths.value = [];
      valueWidths.value = [];
      nextTick(measure);
    });

    return () => (
      <div
        ref={rootRef}
        class='llm-span-io-kvs'
      >
        {props.pairs.map((item, index) => {
          const hidden = index >= hiddenFrom.value;
          const isClipValue = index === clipIndex.value && clipPart.value === 'value';
          const isClipKey = index === clipIndex.value && clipPart.value === 'key';
          const valueStyle = Number.isFinite(valueMaxWidth.value)
            ? { maxWidth: `${valueMaxWidth.value}px` }
            : undefined;
          return (
            <span
              key={`${item.key}-${index}`}
              style={
                isClipValue || isClipKey
                  ? { width: `${clipWidth.value}px`, maxWidth: `${clipWidth.value}px` }
                  : undefined
              }
              class={[
                'llm-span-io-kv',
                { 'is-hidden': hidden, 'is-clip-value': isClipValue, 'is-clip-key': isClipKey },
              ]}
            >
              <span
                class='llm-span-io-kv-key'
                v-overflow-tips={{ content: sliceTooltipContent(item.key), placement: 'top' }}
              >
                {item.key}
              </span>
              <span
                style={valueStyle}
                class='llm-span-io-kv-value'
                v-overflow-tips={{ content: sliceTooltipContent(item.value), placement: 'top' }}
              >
                :{item.value}
              </span>
            </span>
          );
        })}
      </div>
    );
  },
});
