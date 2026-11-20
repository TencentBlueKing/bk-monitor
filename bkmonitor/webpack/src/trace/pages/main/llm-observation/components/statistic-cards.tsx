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
import { type CSSProperties, type ObjectDirective, type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Exception } from 'bkui-vue';
import tippy, { type Instance } from 'tippy.js';
import { useI18n } from 'vue-i18n';

import { formatTokenCount } from '../utils/helpers';
import {
  type LlmMatrixViewNode,
  decodeToolNameFromId,
  flexWeight,
  formatMatrixPercent,
  isToolLeafId,
  splitTokenMatrixPanes,
  toMatrixViewNode,
} from '../utils/token-matrix';

import type { LlmTokenMatrixNode } from '../utils/token-matrix';

import './statistic-cards.scss';

const CHART_HEIGHT = 334;
/** 比例极小的 >0 块仍保留的最小宽度，保证可见并显示省略号 */
const MIN_BLOCK_WIDTH = 32;

/** 顶部概览统计项，value / unit 已格式化 */
export type LlmStatisticCard = {
  key: string;
  label: string;
  theme?: 'success';
  unit?: string;
  value: string;
};

function rowStyle(node: LlmMatrixViewNode): CSSProperties {
  // 同行内各块（含 tools / container）均按自身 token 值占比分配宽度
  return {
    flex: `${flexWeight(node)} 1 0`,
    // 比例极小的 >0 块仍保留最小宽度，超出部分由省略号承接
    minWidth: MIN_BLOCK_WIDTH,
  };
}

function fillStyle(): CSSProperties {
  return {
    flex: '1 1 0',
    minHeight: 0,
    // 父元素（容器 / tools）默认也至少保留 32px，过窄时内部子元素由 overflow 裁切不展示
    minWidth: MIN_BLOCK_WIDTH,
  };
}

/** 块宽度接近最小宽度时视为过窄，折叠为省略号 */
const COLLAPSED_WIDTH = MIN_BLOCK_WIDTH + 2;

const BLOCK_SELECTOR = [
  '.llm-token-matrix-block',
  '.llm-token-matrix-tools',
  '.llm-token-matrix-container',
  '.llm-token-matrix-tool',
  '.llm-token-matrix-title',
].join(',');

/** 可能出现省略号的文本节点：各块名称、标题的名称 / 数值 / 百分比 */
const ELLIPSIS_TARGET_SELECTOR = [
  '.llm-token-matrix-block-name',
  '.llm-token-matrix-title-name',
  '.llm-token-matrix-title-value',
  '.llm-token-matrix-title-pct',
  '.llm-token-matrix-tool-name',
].join(',');

/** 仅当块自身（不含嵌套子块）的文本被省略号截断时才需要面板 */
function hasOwnEllipsis(el: HTMLElement): boolean {
  return Array.from(el.querySelectorAll<HTMLElement>(ELLIPSIS_TARGET_SELECTOR)).some(
    item => item.closest(BLOCK_SELECTOR) === el && item.scrollWidth > item.clientWidth
  );
}

/** 可承载子块的块级元素，用于定位容器 / tools 的直接子块 */
const NESTED_BLOCK_SELECTOR = [
  '.llm-token-matrix-block',
  '.llm-token-matrix-tools',
  '.llm-token-matrix-container',
  '.llm-token-matrix-tool',
].join(',');

/** 向上寻找最近的块级祖先（不含自身） */
function closestBlockAncestor(el: HTMLElement): HTMLElement | null {
  let parent = el.parentElement;
  while (parent) {
    if (parent.matches(NESTED_BLOCK_SELECTOR)) return parent;
    parent = parent.parentElement;
  }
  return null;
}

/** 直接子块：容器内为模型 / 用户消息等一行子块，tools 内为工具项 */
function directChildBlocks(el: HTMLElement): HTMLElement[] {
  return Array.from(el.querySelectorAll<HTMLElement>(NESTED_BLOCK_SELECTOR)).filter(
    item => closestBlockAncestor(item) === el
  );
}

/**
 * 块是否已折叠为省略号：
 * - 自身被压到最小宽度附近；
 * - 或容器内直接子块（模型 / 用户消息等）全部已折叠，此时整体折叠，不再并排展示多个残块。
 */
function isBlockCollapsed(el: HTMLElement): boolean {
  const width = el.getBoundingClientRect().width;
  // 尚未参与布局（宽度为 0）时不做判定，避免初始挂载误折叠
  if (!width) return false;
  if (width <= COLLAPSED_WIDTH) return true;
  if (!el.classList.contains('llm-token-matrix-container')) return false;
  const children = directChildBlocks(el);
  if (!children.length) return false;
  return children.every(isBlockCollapsed);
}

/** hover 放大面板：克隆块的真实 DOM（含内部子元素）并解除折叠 / 裁切，完整展示 */
function panelContent(el: HTMLElement): HTMLElement {
  const panel = document.createElement('div');
  panel.className = 'llm-token-matrix-panel';
  const background = el.style.background;
  const clone = el.cloneNode(true) as HTMLElement;
  clone.removeAttribute('style');
  clone.classList.remove('is-collapsed');
  // 子元素可能也处于折叠态，一并解除，保证面板内父子元素完整展示
  clone.querySelectorAll('.is-collapsed').forEach(item => item.classList.remove('is-collapsed'));
  if (background) clone.style.background = background;
  panel.appendChild(clone);
  return panel;
}

/** 全局共享同一个面板：同一时间最多只展示一个 */
type TipsState = {
  instance: Instance | null;
  destroy: () => void;
};
const tipsStates = new WeakMap<HTMLElement, TipsState>();
let activeState: TipsState | null = null;

function closeActivePanel() {
  if (!activeState) return;
  const state = activeState;
  const instance = state.instance;
  activeState = null;
  state.instance = null;
  instance?.destroy();
}

/**
 * 块级 hover 面板：
 * 1. 块被压到最小宽度附近时折叠为省略号（...），内部子元素不展示；
 *    容器（会话内容块）在模型 / 用户消息等直接子块全部折叠时整体折叠为省略号；
 * 2. 仅块自身文本确实省略时才 hover 弹出；
 * 3. 全局单例面板，hover 新块时先关闭旧面板，避免同时出现多个。
 */
const blockTips: ObjectDirective<HTMLElement> = {
  mounted(el) {
    const state: TipsState = { instance: null, destroy: () => undefined };
    tipsStates.set(el, state);
    const isCollapsed = () => isBlockCollapsed(el);
    const shouldShow = () => isCollapsed() || hasOwnEllipsis(el);

    // 子块变窄时父容器自身宽度不变，无法触发其 ResizeObserver；
    // 因此由发生变化的块向上回溯，逐层刷新祖先容器的折叠态。
    const syncCollapsed = () => {
      let node: HTMLElement | null = el;
      while (node) {
        node.classList.toggle('is-collapsed', isBlockCollapsed(node));
        node = closestBlockAncestor(node);
      }
    };
    syncCollapsed();

    const observer = new ResizeObserver(() => {
      syncCollapsed();
      if (state.instance && !shouldShow()) state.instance.hide();
    });
    observer.observe(el);

    const onEnter = (event: MouseEvent) => {
      event.stopPropagation();
      if (!shouldShow()) return;
      // 弹出当前块前先关闭其它块的面板，保证同一时间只有一个
      if (activeState !== state) closeActivePanel();
      if (state.instance) return;

      state.instance = tippy(el, {
        allowHTML: true,
        content: () => panelContent(el),
        delay: [300, 0],
        maxWidth: 'none',
        onMount: instance => {
          instance.popper.classList.add('llm-token-matrix-tippy');
          // 原生箭头由 popper 精确对准触发块，以其为真值把面板中心对齐到箭头，
          // 再用负 margin 抵消箭头随面板的位移，保证三者中心一致
          const box = instance.popper.querySelector<HTMLElement>('.tippy-box');
          const arrow = instance.popper.querySelector<HTMLElement>('.tippy-arrow');
          if (!box || !arrow) return;
          const alignPanelToArrow = () => {
            if (!box.isConnected) return;
            const boxRect = box.getBoundingClientRect();
            const arrowRect = arrow.getBoundingClientRect();
            const delta = arrowRect.left + arrowRect.width / 2 - (boxRect.left + boxRect.width / 2);
            // 已对齐（δ≈0）时无需重复，保证可重复调用
            if (Math.abs(delta) < 0.5) return;
            box.style.transform = `translateX(${delta}px)`;
            arrow.style.marginLeft = `${-delta}px`;
          };
          // 内容由克隆 DOM 注入，待布局稳定后再测量；两帧后校一次，内容尺寸变化时再补一次
          requestAnimationFrame(() => requestAnimationFrame(alignPanelToArrow));
          setTimeout(alignPanelToArrow, 120);
        },
        onHidden: () => {
          if (activeState === state) activeState = null;
          const instance = state.instance;
          state.instance = null;
          instance?.destroy();
        },
        onShow: () => {
          if (!shouldShow()) return false;
        },
        placement: 'top',
        theme: 'light',
        trigger: 'mouseenter',
      });
      activeState = state;
      setTimeout(() => {
        if (state.instance && shouldShow() && !state.instance.state.isShown) {
          state.instance.clearDelayTimeouts();
          state.instance.show();
        }
      }, 300);
    };
    el.addEventListener('mouseenter', onEnter);

    state.destroy = () => {
      observer.disconnect();
      el.removeEventListener('mouseenter', onEnter);
      if (activeState === state) activeState = null;
      const instance = state.instance;
      state.instance = null;
      instance?.destroy();
    };
  },
  beforeUnmount(el) {
    tipsStates.get(el)?.destroy();
    tipsStates.delete(el);
  },
};

/** 模型 Span 顶部概览：收起条展示统计，展开后按输入 / 输出层级画矩形树 */
export default defineComponent({
  name: 'LlmStatisticCards',
  directives: { blockTips },
  props: {
    /** 已格式化的统计项，顺序由调用方给定 */
    cards: {
      type: Array as PropType<LlmStatisticCard[]>,
      default: () => [],
    },
    matrixLoading: {
      type: Boolean,
      default: false,
    },
    /** llm_detail.token_matrix.nodes，输入 / 输出两棵树 */
    nodes: {
      type: Array as PropType<LlmTokenMatrixNode[]>,
      default: () => [],
    },
  },
  emits: {
    'locate-tool': (_toolName: string) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();
    const expanded = shallowRef(false);

    const panes = computed(() => splitTokenMatrixPanes(props.nodes));
    const inputNode = computed(() => {
      const { input, total } = panes.value;
      return input ? toMatrixViewNode(input, total || undefined) : null;
    });
    const outputNode = computed(() => {
      const { output, total } = panes.value;
      return output ? toMatrixViewNode(output, total || undefined) : null;
    });
    const hasMatrix = computed(() => Boolean(inputNode.value || outputNode.value));

    const handleToggle = () => {
      expanded.value = !expanded.value;
    };

    const handleToolClick = (node: LlmMatrixViewNode) => {
      if (!isToolLeafId(node.id)) return;
      const toolName = decodeToolNameFromId(node.id) || node.name || '';
      if (toolName) emit('locate-tool', toolName);
    };

    const renderTitle = (node: LlmMatrixViewNode) => (
      <div
        v-block-tips
        class='llm-token-matrix-title'
      >
        <span class='llm-token-matrix-title-name'>{node.name}</span>
        <span class='llm-token-matrix-title-value'>{formatTokenCount(node.value)}</span>
        <span class='llm-token-matrix-title-pct'>{formatMatrixPercent(node.percent)}</span>
      </div>
    );

    const renderBlockHead = (node: LlmMatrixViewNode) => (
      <div class='llm-token-matrix-block-head'>
        <div class='llm-token-matrix-block-name'>{node.name}</div>
        <div class='llm-token-matrix-block-meta'>
          <span class='llm-token-matrix-block-value'>{formatTokenCount(node.value)}</span>
          <span class='llm-token-matrix-block-pct'>{formatMatrixPercent(node.percent)}</span>
        </div>
      </div>
    );

    const renderLeaf = (node: LlmMatrixViewNode, style: CSSProperties) => (
      <div
        key={node.id}
        v-block-tips
        class='llm-token-matrix-block'
        style={{ ...style, background: node.color }}
      >
        {renderBlockHead(node)}
      </div>
    );

    const renderTool = (node: LlmMatrixViewNode) => {
      const clickable = isToolLeafId(node.id);
      const title = node.call_count != null ? `${node.name} ×${node.call_count}` : node.name;
      return (
        <div
          key={node.id}
          v-block-tips
          class={['llm-token-matrix-tool', { 'is-clickable': clickable }]}
          onClick={() => handleToolClick(node)}
        >
          <span class='llm-token-matrix-tool-name'>{title}</span>
          <span class='llm-token-matrix-tool-meta'>
            {formatTokenCount(node.value)} · {formatMatrixPercent(node.percent)}
          </span>
        </div>
      );
    };

    const renderTools = (node: LlmMatrixViewNode, style: CSSProperties) => (
      <div
        key={node.id}
        v-block-tips
        class='llm-token-matrix-tools'
        style={{ ...style, background: node.color }}
      >
        {renderBlockHead(node)}
        <div class='llm-token-matrix-tool-list'>{node.children.map(renderTool)}</div>
      </div>
    );

    function renderChild(node: LlmMatrixViewNode, inRow = true) {
      const style = inRow ? rowStyle(node) : fillStyle();
      if (node.kind === 'tools') return renderTools(node, style);
      if (node.kind === 'container') return renderContainer(node, style);
      return renderLeaf(node, style);
    }

    function renderRow(nodes: LlmMatrixViewNode[], fill = false) {
      return (
        <div class={['llm-token-matrix-row', { 'is-fill': fill, 'is-top': !fill }]}>
          {nodes.map(child => renderChild(child, true))}
        </div>
      );
    }

    function renderContainer(node: LlmMatrixViewNode, style: CSSProperties) {
      return (
        <div
          key={node.id}
          v-block-tips
          class='llm-token-matrix-container'
          style={style}
        >
          {renderTitle(node)}
          {node.children.length ? renderRow(node.children, true) : null}
        </div>
      );
    }

    const renderPaneBody = (node: LlmMatrixViewNode) => {
      const leaves = node.children.filter(child => child.kind === 'leaf');
      const rest = node.children.filter(child => child.kind !== 'leaf');
      if (!rest.length) return leaves.length ? renderRow(leaves, true) : null;
      return (
        <>
          {leaves.length ? renderRow(leaves, false) : null}
          <div class='llm-token-matrix-pane-rest'>{rest.map(child => renderChild(child, false))}</div>
        </>
      );
    };

    const renderPane = (node: LlmMatrixViewNode | null) => {
      if (!node) {
        return (
          <Exception
            class='llm-statistic-cards-empty'
            scene='part'
            title={t('暂无数据')}
            type='empty'
          />
        );
      }
      return (
        <div class='llm-token-matrix-pane'>
          {renderTitle(node)}
          <div class='llm-token-matrix-pane-body'>{renderPaneBody(node)}</div>
        </div>
      );
    };

    /** 加载态骨架块：结构与真实块一致，仅以占位条替代名称 / 数值 */
    const renderBlockSkeleton = (key: string, style: CSSProperties) => (
      <div
        key={key}
        class='llm-token-matrix-block is-skeleton'
        style={style}
      >
        <div class='llm-token-matrix-block-head'>
          <div class='skeleton-element llm-token-matrix-block-skeleton is-name' />
          <div class='skeleton-element llm-token-matrix-block-skeleton is-meta' />
        </div>
      </div>
    );

    /** 加载态骨架面板：对齐真实输入 / 输出面板的标题与块布局 */
    const renderPaneSkeleton = () => (
      <div class='llm-token-matrix-pane'>
        <div class='llm-token-matrix-title'>
          <div class='skeleton-element llm-token-matrix-title-skeleton is-name' />
          <div class='skeleton-element llm-token-matrix-title-skeleton is-value' />
          <div class='skeleton-element llm-token-matrix-title-skeleton is-pct' />
        </div>
        <div class='llm-token-matrix-pane-body'>
          <div class='llm-token-matrix-row is-top'>
            {[
              { id: 'top-0', weight: 3 },
              { id: 'top-1', weight: 2 },
            ].map(item =>
              renderBlockSkeleton(item.id, {
                flex: `${item.weight} 1 0`,
                minWidth: MIN_BLOCK_WIDTH,
              })
            )}
          </div>
          <div class='llm-token-matrix-pane-rest'>{renderBlockSkeleton('rest-0', fillStyle())}</div>
        </div>
      </div>
    );

    return {
      t,
      expanded,
      hasMatrix,
      inputNode,
      outputNode,
      handleToggle,
      renderPane,
      renderPaneSkeleton,
    };
  },
  render() {
    return (
      <div class={['llm-statistic-cards', { 'is-expanded': this.expanded }]}>
        <div
          class='llm-statistic-cards-header'
          onClick={this.handleToggle}
        >
          <i class={['icon-monitor icon-mc-arrow-right llm-statistic-cards-arrow', { 'is-expanded': this.expanded }]} />
          <span class='llm-statistic-cards-divider is-lead' />
          <div class='llm-statistic-cards-metrics'>
            {this.cards.map((item, index) => (
              <div
                key={item.key}
                class='llm-statistic-cards-metric-wrap'
              >
                {index ? <span class='llm-statistic-cards-divider' /> : null}
                <div class='llm-statistic-cards-metric'>
                  <span class='llm-statistic-cards-metric-label'>{item.label}</span>
                  <span
                    class='llm-statistic-cards-metric-value'
                    v-overflow-tips
                  >
                    {item.value}
                    {item.unit ? ` ${item.unit}` : ''}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
        {this.expanded ? (
          <div
            class='llm-statistic-cards-body'
            style={{ height: `${CHART_HEIGHT}px` }}
          >
            {this.hasMatrix ? (
              <div class='llm-token-matrix'>
                <div class='llm-token-matrix-side'>{this.renderPane(this.inputNode)}</div>
                <div class='llm-token-matrix-side'>{this.renderPane(this.outputNode)}</div>
              </div>
            ) : this.matrixLoading ? (
              <div class='llm-token-matrix'>
                <div class='llm-token-matrix-side'>{this.renderPaneSkeleton()}</div>
                <div class='llm-token-matrix-side'>{this.renderPaneSkeleton()}</div>
              </div>
            ) : (
              <Exception
                class='llm-statistic-cards-empty'
                scene='part'
                title={this.t('暂无数据')}
                type='empty'
              />
            )}
          </div>
        ) : null}
      </div>
    );
  },
});
