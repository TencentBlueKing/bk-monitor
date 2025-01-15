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

import { defineComponent, onMounted, reactive, ref, watch } from 'vue';

import './resize-container.scss';

export default defineComponent({
  props: {
    width: { default: null, type: Number },
    maxWidth: { default: null, type: Number },
    minWidth: { default: null, type: Number },
    height: { default: null, type: Number },
    maxHeight: { default: null, type: Number },
    minHeight: { default: null, type: Number },
    placeholder: { default: '', type: String },
  },
  setup(props) {
    const el = ref<HTMLDivElement>(null);
    const resize = reactive({
      startClientX: 0,
      startClientY: 0,
      width: null,
      height: null,
    });

    watch(
      () => props.width,
      w => (resize.width = w),
      { immediate: true }
    );
    watch(
      () => props.height,
      h => (resize.height = h),
      { immediate: true }
    );

    // 限制宽度
    const widthRange = (width: number): number => {
      const min = props.minWidth;
      const max = props.maxWidth;
      width = min && width <= min ? min : width;
      width = max && width >= max ? max : width;
      return width;
    };

    // 限制高度
    const heightRange = (height: number): number => {
      const min = props.minHeight;
      const max = props.maxHeight;
      height = min && height <= min ? min : height;
      height = max && height >= max ? max : height;
      return height;
    };

    const handleMouseDown = (e: MouseEvent) => {
      resize.startClientX = e.clientX;
      resize.startClientY = e.clientY;
      document.addEventListener('mousemove', handleMousemove, false);
      document.addEventListener('mouseup', handleMouseup, false);
    };
    const handleMousemove = (e: MouseEvent) => {
      if (resize.startClientX === 0) return;
      if (resize.width === null) {
        const wrapEl = el.value;
        resize.width = wrapEl.clientWidth;
        resize.height = wrapEl.clientHeight;
      }
      const offsetX = e.clientX - resize.startClientX;
      const offsetY = e.clientY - resize.startClientY;
      resize.startClientX = e.clientX;
      resize.startClientY = e.clientY;
      resize.width = widthRange(resize.width + offsetX);
      resize.height = heightRange(resize.height + offsetY);
    };
    const handleMouseup = () => {
      resize.startClientX = 0;
      resize.startClientY = 0;
      document.removeEventListener('mousemove', handleMousemove, false);
      document.removeEventListener('mouseup', handleMousemove, false);
    };

    onMounted(() => {
      props.minHeight && !props.height && (resize.height = props.minHeight);
      props.maxWidth && !props.width && (resize.width = props.maxWidth);
    });
    return {
      el,
      resize,
      handleMouseDown,
      handleMousemove,
      handleMouseup,
    };
  },
  render() {
    return (
      <div
        ref='el'
        style={{
          width: `${this.resize.width}px`,
          height: `${this.resize.height}px`,
        }}
        class='resize-container-wrap'
      >
        <div class='resize-container-content'>{this.$slots.default()}</div>
        <div
          class='resize-wrap'
          onMousedown={this.handleMouseDown}
          onMousemove={this.handleMousemove}
          onMouseup={this.handleMouseup}
        >
          <i class='resize-icon-inner' />
          <i class='resize-icon-wrap' />
        </div>
      </div>
    );
  },
});
