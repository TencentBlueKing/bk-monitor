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
import { type PropType, computed, defineComponent, nextTick, onMounted, onScopeDispose, shallowRef, watch } from 'vue';

import { Button, Message } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { resolveExportScale } from '../../utils/export-image';
import {
  type FlameFrame,
  findFrame,
  formatProfileValue,
  formatProportion,
  frameColor,
  layoutFlame,
} from '../../utils/flame-layout';
import ProfileDetails from './profile-details';
import ProfilePopup from './profile-popup';

import type { FlameNode } from '../../types';

const ROW_HEIGHT = 20;

export default defineComponent({
  name: 'ProfileFlameCanvas',
  props: {
    data: { type: Object as PropType<FlameNode>, default: undefined },
    focusPath: { type: Array as PropType<string[]>, default: () => [] },
    keyword: { type: String, default: '' },
    highlight: { type: String, default: '' },
    direction: { type: String, default: 'ltr' },
    unit: { type: String, default: '' },
    dataType: { type: String, default: '' },
  },
  emits: { focusChange: (_path: string[]) => true, select: (_name: string) => true, search: (_name: string) => true },
  setup(props, { emit, expose }) {
    const { t } = useI18n();
    const viewport = shallowRef<HTMLElement>();
    const canvas = shallowRef<HTMLCanvasElement>();
    const tooltip = shallowRef<null | { frame: FlameFrame; x: number; y: number }>(null);
    const menu = shallowRef<null | { frame: FlameFrame; x: number; y: number }>(null);
    const layout = computed(() => layoutFlame(props.data));
    // 以调用路径恢复焦点，避免后端重复 id 或布局索引变化定位到另一个函数。
    const focusKey = computed(() => {
      let node = props.data;
      for (const name of props.focusPath) {
        node = node?.children?.find(child => child.name === name);
        if (!node) return 0;
      }
      return layout.value.frames.find(frame => frame.node === node)?.key || 0;
    });
    const focus = computed(() => layout.value.frames[focusKey.value] || layout.value.frames[0]);
    const contentHeight = computed(() => layout.value.rows.length * ROW_HEIGHT);
    let observer: ResizeObserver;
    let raf = 0;

    // 按 CSS 像素坐标绘制火焰图内容，倍率由调用方通过 scale 设定。
    function paint(context: CanvasRenderingContext2D, width: number, height: number, scrollTop: number) {
      context.fillStyle = '#f5f6f9';
      context.fillRect(0, 0, width, height);
      if (!focus.value?.width) return;
      const selected = focus.value;
      const startRow = Math.floor(scrollTop / ROW_HEIGHT);
      const endRow = Math.min(layout.value.rows.length, startRow + Math.ceil(height / ROW_HEIGHT) + 1);
      const keyword = props.keyword.trim().toLowerCase();
      context.font = '12px Arial, sans-serif';
      context.textBaseline = 'middle';
      for (let depth = startRow; depth < endRow; depth++) {
        const row = layout.value.rows[depth];
        // 行按 x 排序；只绘制焦点子树与视口覆盖的节点。
        for (const frame of row) {
          if (frame.x + frame.width <= selected.x) continue;
          if (frame.x >= selected.x + selected.width) break;
          const x = Math.max(0, ((frame.x - selected.x) / selected.width) * width);
          const w = Math.min(width - x, (frame.width / selected.width) * width);
          if (w < 0.5) continue;
          const y = depth * ROW_HEIGHT - scrollTop;
          const match = keyword && frame.node.name.toLowerCase().includes(keyword);
          const highlighted = props.highlight === frame.node.name;
          context.fillStyle =
            (keyword && !match) || depth < selected.depth ? '#aaa' : frameColor(frame.node.name, frame.node.diff_info);
          context.fillRect(x, y, Math.max(0.5, w - 1), ROW_HEIGHT - 1);
          if (highlighted) {
            context.strokeStyle = '#3a84ff';
            context.lineWidth = 2;
            context.strokeRect(x + 1, y + 1, Math.max(0, w - 3), ROW_HEIGHT - 3);
          }
          if (w > 14) {
            context.save();
            context.beginPath();
            context.rect(x + 3, y, w - 6, ROW_HEIGHT);
            context.clip();
            context.fillStyle = '#313238';
            context.globalAlpha = 1;
            const text = `${frame.node.name} (${formatProportion(frame.node.value, props.data?.value)}, ${formatProfileValue(frame.node.value, props.unit)})`;
            const textWidth = context.measureText(text).width;
            context.fillText(
              text,
              props.direction === 'rtl' && textWidth > w - 6 ? x + w - textWidth - 3 : x + 3,
              y + ROW_HEIGHT / 2
            );
            context.restore();
          }
        }
      }
      context.globalAlpha = 1;
    }

    function renderCanvas() {
      const element = viewport.value;
      const target = canvas.value;
      if (!element || !target) return;
      const width = element.clientWidth;
      const height = element.clientHeight;
      const ratio = window.devicePixelRatio || 1;
      // 画布仅覆盖可见区域，完整深度由占位内容提供滚动高度，避免深堆栈生成超大位图。
      target.width = Math.round(width * ratio);
      target.height = Math.round(height * ratio);
      target.style.width = `${width}px`;
      target.style.height = `${height}px`;
      target.style.transform = `translateY(${element.scrollTop}px)`;
      const ctx = target.getContext('2d');
      ctx.scale(ratio, ratio);
      paint(ctx, width, height, element.scrollTop);
    }

    function scheduleRender() {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(renderCanvas);
    }

    function hitTest(event: MouseEvent) {
      // 将视口像素还原为布局坐标；横向需考虑当前放大的子树，纵向需补上滚动偏移。
      if (!focus.value || !viewport.value) return;
      const bounds = viewport.value.getBoundingClientRect();
      const x = event.clientX - bounds.left;
      const y = event.clientY - bounds.top;
      const depth = Math.floor((y + viewport.value.scrollTop) / ROW_HEIGHT);
      return {
        frame: findFrame(
          layout.value.rows[depth] || [],
          focus.value.x + (x / viewport.value.clientWidth) * focus.value.width
        ),
        x,
        y,
      };
    }

    function handleMove(event: MouseEvent) {
      if (menu.value) return;
      const hit = hitTest(event);
      tooltip.value = hit?.frame ? { frame: hit.frame, x: event.clientX, y: event.clientY } : null;
    }

    function handleClick(event: MouseEvent) {
      const hit = hitTest(event);
      if (!hit?.frame || hit.frame.width <= 0) return;
      const path: string[] = [];
      let frame = hit.frame;
      while (frame.parent >= 0) {
        path.push(frame.node.name);
        frame = layout.value.frames[frame.parent];
      }
      emit('focusChange', path.reverse());
      emit('select', hit.frame.node.name);
      viewport.value.scrollTop = 0;
      tooltip.value = null;
      scheduleRender();
    }

    function handleContextMenu(event: MouseEvent) {
      event.preventDefault();
      const hit = hitTest(event);
      menu.value = hit?.frame ? { frame: hit.frame, x: event.clientX, y: event.clientY } : null;
      tooltip.value = null;
    }

    function menuAction(action: 'copy' | 'highlight' | 'reset') {
      const name = menu.value?.frame.node.name;
      menu.value = null;
      if (action === 'copy' && name) {
        let failed = false;
        try {
          copyText(name, () => {
            failed = true;
          });
        } catch {
          failed = true;
        }
        Message({ theme: failed ? 'error' : 'success', message: t(failed ? '复制失败，请手动复制' : '复制成功') });
      }
      if (action === 'highlight' && name) emit('search', name);
      if (action === 'reset') reset();
    }

    function reset() {
      menu.value = null;
      emit('focusChange', []);
      tooltip.value = null;
      if (viewport.value) viewport.value.scrollTop = 0;
      emit('select', '');
      scheduleRender();
    }

    function exportPng() {
      const element = viewport.value;
      if (!element) return;
      const width = element.clientWidth;
      const height = element.clientHeight;
      if (!width || !height) return;
      const scale = resolveExportScale(width, height);
      // 离屏按导出倍率重绘可见区域，导出结果不受屏幕像素比影响。
      const target = document.createElement('canvas');
      target.width = Math.round(width * scale);
      target.height = Math.round(height * scale);
      const ctx = target.getContext('2d');
      ctx.scale(scale, scale);
      paint(ctx, width, height, element.scrollTop);
      target.toBlob(blob => {
        if (!blob) return;
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.download = 'profiling-flame.png';
        link.href = url;
        link.click();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
      });
    }
    expose({ exportPng });
    watch(
      () => props.data,
      () => {
        tooltip.value = null;
        menu.value = null;
        nextTick(scheduleRender);
      }
    );
    watch(() => [props.keyword, props.highlight, props.direction, props.focusPath], scheduleRender);
    onMounted(() => {
      observer = new ResizeObserver(scheduleRender);
      observer.observe(viewport.value);
      scheduleRender();
    });
    onScopeDispose(() => {
      observer?.disconnect();
      cancelAnimationFrame(raf);
    });
    return {
      t,
      viewport,
      canvas,
      menu,
      menuAction,
      handleContextMenu,
      focusKey,
      focus,
      tooltip,
      contentHeight,
      handleMove,
      handleClick,
      reset,
      scheduleRender,
    };
  },
  render() {
    const tip = this.tooltip;
    return (
      <div class='profile-flame'>
        {!!this.focusKey && (
          <div class='flame-focus'>
            <Button
              v-tippy={this.t('恢复完整火焰图')}
              theme='primary'
              text
              onClick={this.reset}
            >
              {this.t('重置')}
            </Button>
            <span title={this.focus?.node.name}>{this.focus?.node.name}</span>
          </div>
        )}
        <div
          ref='viewport'
          class='flame-viewport'
          onScroll={() => {
            this.tooltip = null;
            this.scheduleRender();
          }}
        >
          <div
            style={{ height: `${this.contentHeight}px` }}
            class='flame-scroll-content'
          >
            <canvas
              ref='canvas'
              aria-label={this.t('火焰图')}
              role='img'
              onClick={this.handleClick}
              onContextmenu={this.handleContextMenu}
              onDblclick={this.reset}
              onMouseleave={() => {
                this.tooltip = null;
              }}
              onMousemove={this.handleMove}
            />
          </div>
        </div>
        <ProfilePopup point={tip}>
          {tip && (
            <ProfileDetails
              dataType={this.dataType}
              diff={tip.frame.node.diff_info}
              name={tip.frame.node.name}
              rootTotal={this.data?.value}
              self={tip.frame.node.self || 0}
              total={tip.frame.node.value}
              unit={this.unit}
            />
          )}
        </ProfilePopup>
        <ProfilePopup
          point={this.menu}
          interactive
          onClose={() => {
            this.menu = null;
          }}
        >
          <Button
            v-tippy={this.t('复制当前函数的完整名称')}
            onClick={() => this.menuAction('copy')}
          >
            <i class='icon-monitor icon-mc-copy' />
            {this.t('复制函数名')}
          </Button>
          <Button
            v-tippy={this.t('搜索并高亮相同名称的函数')}
            onClick={() => this.menuAction('highlight')}
          >
            <i class='icon-monitor icon-mc-search' />
            {this.t('高亮相似堆栈')}
          </Button>
          <Button
            v-tippy={this.t('清除高亮并恢复完整火焰图')}
            onClick={() => this.menuAction('reset')}
          >
            <i class='icon-monitor icon-shuaxin' />
            {this.t('重置视图')}
          </Button>
        </ProfilePopup>
      </div>
    );
  },
});
