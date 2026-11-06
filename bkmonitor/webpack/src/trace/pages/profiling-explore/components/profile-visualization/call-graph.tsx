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
import { type PropType, defineComponent, onScopeDispose, shallowRef, watch } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { ProfileViewState } from '../../types';

export default defineComponent({
  name: 'ProfileCallGraph',
  props: {
    svg: { type: String, required: true },
    view: { type: Object as PropType<ProfileViewState['callGraph']>, default: () => ({ scale: 1, x: 0, y: 0 }) },
  },
  emits: { viewChange: (_view: ProfileViewState['callGraph']) => true },
  setup(props, { emit }) {
    const { t } = useI18n();
    const url = shallowRef('');
    const scale = shallowRef(1);
    const offset = shallowRef({ x: 0, y: 0 });
    const persistView = () => emit('viewChange', { scale: scale.value, ...offset.value });
    watch(
      () => props.view,
      value => {
        scale.value = value.scale;
        offset.value = { x: value.x, y: value.y };
      },
      { immediate: true }
    );
    let drag: null | { startX: number; startY: number; x: number; y: number } = null;
    const reset = () => {
      scale.value = 1;
      offset.value = { x: 0, y: 0 };
      persistView();
    };
    watch(
      () => props.svg,
      value => {
        if (url.value) URL.revokeObjectURL(url.value);
        // SVG 作为图片载入，不把接口内容注入 DOM。
        url.value = value ? URL.createObjectURL(new Blob([value], { type: 'image/svg+xml' })) : '';
      },
      { immediate: true }
    );
    onScopeDispose(() => {
      if (url.value) URL.revokeObjectURL(url.value);
    });
    return {
      t,
      url,
      scale,
      offset,
      reset,
      zoom: (factor: number) => {
        scale.value = Math.min(8, Math.max(0.2, scale.value * factor));
        persistView();
      },
      pointerDown: (event: PointerEvent) => {
        if (event.button !== 0) return;
        (event.currentTarget as HTMLElement).setPointerCapture(event.pointerId);
        drag = { x: event.clientX, y: event.clientY, startX: offset.value.x, startY: offset.value.y };
      },
      pointerMove: (event: PointerEvent) => {
        if (drag) offset.value = { x: drag.startX + event.clientX - drag.x, y: drag.startY + event.clientY - drag.y };
      },
      pointerUp: () => {
        // 拖动结束才同步快照，避免每个 pointermove 都触发路由写入。
        if (drag) persistView();
        drag = null;
      },
    };
  },
  render() {
    return (
      <div class='profile-callgraph'>
        <div class='callgraph-controls'>
          <Button
            aria-label={this.t('缩小')}
            size='small'
            onClick={() => this.zoom(0.8)}
          >
            −
          </Button>
          <Button
            size='small'
            onClick={this.reset}
          >
            {this.t('重置')}
          </Button>
          <Button
            aria-label={this.t('放大')}
            size='small'
            onClick={() => this.zoom(1.25)}
          >
            +
          </Button>
        </div>
        <div
          class='callgraph-viewport'
          onPointercancel={this.pointerUp}
          onPointerdown={this.pointerDown}
          onPointermove={this.pointerMove}
          onPointerup={this.pointerUp}
          onWheel={event => {
            event.preventDefault();
            this.zoom(event.deltaY > 0 ? 0.9 : 1.1);
          }}
        >
          <img
            style={{ transform: `translate(${this.offset.x}px, ${this.offset.y}px) scale(${this.scale})` }}
            alt={this.t('功能调用图')}
            draggable={false}
            src={this.url}
          />
        </div>
      </div>
    );
  },
});
