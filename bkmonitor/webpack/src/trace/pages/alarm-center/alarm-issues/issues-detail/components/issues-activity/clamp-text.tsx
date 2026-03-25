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
import { type PropType, defineComponent, nextTick, onMounted, shallowRef, watch } from 'vue';

import './clamp-text.scss';

export default defineComponent({
  name: 'ClampText',
  props: {
    /** 文本内容 */
    content: {
      type: null as unknown as PropType<null | string>,
      default: null,
    },
    /** 最大行数 */
    maxLines: {
      type: Number,
      default: 3,
    },
  },
  emits: {
    expand: (_content: string) => true,
  },
  setup(props, { emit }) {
    const textRef = shallowRef<HTMLSpanElement>();
    const isClamped = shallowRef(false);

    /**
     * 检测文本是否超出最大行数
     */
    const checkOverflow = () => {
      nextTick(() => {
        if (!textRef.value) {
          isClamped.value = false;
          return;
        }
        const lineHeight = Number.parseInt(getComputedStyle(textRef.value).lineHeight, 10) || 20;
        const maxHeight = lineHeight * props.maxLines;
        isClamped.value = textRef.value.offsetHeight > maxHeight;
      });
    };

    onMounted(() => {
      checkOverflow();
    });

    watch(
      () => props.content,
      () => {
        checkOverflow();
      }
    );

    const handleExpand = () => {
      if (props.content) {
        emit('expand', props.content);
      }
    };

    return {
      textRef,
      isClamped,
      handleExpand,
    };
  },
  render() {
    const { content, isClamped, handleExpand } = this;

    return (
      <span class='clamp-text-wrapper'>
        <span
          ref='textRef'
          class={['clamp-text-content', { 'is-clamped': isClamped }]}
        >
          {content}
        </span>
        <i
          class='icon-monitor icon-xiangqing1 clamp-text-icon'
          onClick={handleExpand}
        />
      </span>
    );
  },
});
