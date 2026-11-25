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
import { type CSSProperties, type PropType, computed, defineComponent, shallowRef } from 'vue';

import { Exception } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { formatCompactToken } from '../utils/helpers';
import { LLM_SEARCH_SECTION } from '../utils/search';
import {
  type LlmMatrixViewNode,
  decodeToolNameFromId,
  flexWeight,
  formatMatrixPercent,
  isToolLeafId,
  splitTokenMatrixPanes,
  toMatrixViewNode,
} from '../utils/token-matrix';

import type { LlmSearchSectionId } from '../utils/search';
import type { LlmTokenMatrixNode } from '../utils/token-matrix';

import './statistic-cards.scss';

const CHART_HEIGHT = 334;
/** 展开区域相对设计高度的缩放比：整体高度收敛为原高度的 2/3 */
const EXPANDED_SCALE = 2 / 3;
const EXPANDED_HEIGHT = CHART_HEIGHT * EXPANDED_SCALE;

/** 顶部概览统计项，value / unit 已格式化 */
export type LlmStatisticCard = {
  key: string;
  label: string;
  theme?: 'success';
  unit?: string;
  value: string;
};

/** 色块所属分栏：输入 / 输出，用于就近归位到时间流分区 */
type MatrixPane = 'input' | 'output';

function rowStyle(node: LlmMatrixViewNode): CSSProperties {
  // 同行内各块（含 tools / container）均按自身 token 值占比分配宽度
  return {
    flex: `${flexWeight(node)} 1 0`,
  };
}

function fillStyle(): CSSProperties {
  return {
    flex: '1 1 0',
    minHeight: 0,
  };
}

/** 模型 Span 顶部概览：收起条展示统计，展开后按输入 / 输出层级画矩形树 */
export default defineComponent({
  name: 'LlmStatisticCards',
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
    /** 开启色块 hover / 点击交互：点击后就近定位到时间流对应折叠分区 */
    interactive: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    'locate-section': (_sectionId: LlmSearchSectionId) => true,
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

    /** 输入 / 输出分栏宽度：按两侧 token 占比分配，缺失数据的一侧回退为 1 */
    const sideStyle = (node: LlmMatrixViewNode | null): CSSProperties => ({
      flex: `${node ? flexWeight(node) : 1} 1 0`,
    });

    const handleToggle = () => {
      expanded.value = !expanded.value;
    };

    const handleToolClick = (node: LlmMatrixViewNode) => {
      if (!isToolLeafId(node.id)) return;
      const toolName = decodeToolNameFromId(node.id) || node.name || '';
      if (toolName) emit('locate-tool', toolName);
    };

    /** 色块归属的时间流折叠分区：output 整棵子树归输出；input 侧 system / definitions 单独归位，其余归输入 */
    const resolveSectionId = (pane: MatrixPane, node: LlmMatrixViewNode): LlmSearchSectionId => {
      if (pane === 'output') return LLM_SEARCH_SECTION.timelineOutput;
      if (node.id === 'system') return LLM_SEARCH_SECTION.inputSystem;
      if (node.id === 'definitions') return LLM_SEARCH_SECTION.inputTools;
      return LLM_SEARCH_SECTION.timelineInput;
    };

    const handleBlockClick = (pane: MatrixPane, node: LlmMatrixViewNode) => {
      if (!props.interactive) return;
      emit('locate-section', resolveSectionId(pane, node));
    };

    const renderTitle = (node: LlmMatrixViewNode) => (
      <div class='llm-token-matrix-title'>
        <span class='llm-token-matrix-title-name'>{node.name}</span>
        <span class='llm-token-matrix-title-value'>{formatCompactToken(node.value)}</span>
        <span class='llm-token-matrix-title-pct'>{formatMatrixPercent(node.percent)}</span>
      </div>
    );

    const renderBlockHead = (node: LlmMatrixViewNode) => (
      <div class='llm-token-matrix-block-head'>
        <div class='llm-token-matrix-block-name'>{node.name}</div>
        <div class='llm-token-matrix-block-meta'>
          <span class='llm-token-matrix-block-value'>{formatCompactToken(node.value)}</span>
          <span class='llm-token-matrix-block-pct'>{formatMatrixPercent(node.percent)}</span>
        </div>
      </div>
    );

    const renderLeaf = (node: LlmMatrixViewNode, style: CSSProperties, pane: MatrixPane) => (
      <div
        key={node.id}
        class='llm-token-matrix-block'
        style={{ ...style, background: node.color }}
        onClick={() => handleBlockClick(pane, node)}
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
          class={['llm-token-matrix-tool', { 'is-clickable': clickable }]}
          onClick={(event: Event) => {
            // 工具叶子优先定位同名工具调用行，避免冒泡到工具块再次定位分区
            if (!clickable) return;
            event.stopPropagation();
            handleToolClick(node);
          }}
        >
          <span class='llm-token-matrix-tool-name'>{title}</span>
          <span class='llm-token-matrix-tool-meta'>
            {formatCompactToken(node.value)}
            {' · '}
            <span class='llm-token-matrix-tool-pct'>{formatMatrixPercent(node.percent)}</span>
          </span>
        </div>
      );
    };

    const renderTools = (node: LlmMatrixViewNode, style: CSSProperties, pane: MatrixPane) => (
      <div
        key={node.id}
        class='llm-token-matrix-tools'
        style={{ ...style, background: node.color }}
        onClick={() => handleBlockClick(pane, node)}
      >
        {renderBlockHead(node)}
        <div class='llm-token-matrix-tool-list'>{node.children.map(renderTool)}</div>
      </div>
    );

    function renderChild(node: LlmMatrixViewNode, pane: MatrixPane, inRow = true) {
      const style = inRow ? rowStyle(node) : fillStyle();
      if (node.kind === 'tools') return renderTools(node, style, pane);
      if (node.kind === 'container') return renderContainer(node, style, pane);
      return renderLeaf(node, style, pane);
    }

    function renderRow(nodes: LlmMatrixViewNode[], pane: MatrixPane, fill = false) {
      return (
        <div class={['llm-token-matrix-row', { 'is-fill': fill, 'is-top': !fill }]}>
          {nodes.map(child => renderChild(child, pane, true))}
        </div>
      );
    }

    function renderContainer(node: LlmMatrixViewNode, style: CSSProperties, pane: MatrixPane) {
      return (
        <div
          key={node.id}
          class='llm-token-matrix-container'
          style={style}
        >
          {renderTitle(node)}
          {node.children.length ? renderRow(node.children, pane, true) : null}
        </div>
      );
    }

    const renderPaneBody = (node: LlmMatrixViewNode, pane: MatrixPane) => {
      const leaves = node.children.filter(child => child.kind === 'leaf');
      const rest = node.children.filter(child => child.kind !== 'leaf');
      if (!rest.length) return leaves.length ? renderRow(leaves, pane, true) : null;
      return (
        <>
          {leaves.length ? renderRow(leaves, pane, false) : null}
          <div class='llm-token-matrix-pane-rest'>{rest.map(child => renderChild(child, pane, false))}</div>
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
      const pane: MatrixPane = node.id === 'output' ? 'output' : 'input';
      return (
        <div class='llm-token-matrix-pane'>
          {renderTitle(node)}
          <div class='llm-token-matrix-pane-body'>{renderPaneBody(node, pane)}</div>
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
      sideStyle,
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
            style={
              {
                height: `${EXPANDED_HEIGHT}px`,
                '--llm-matrix-scale': EXPANDED_SCALE,
              } as CSSProperties
            }
          >
            {this.hasMatrix ? (
              <div class={['llm-token-matrix', { 'is-interactive': this.interactive }]}>
                <div
                  class='llm-token-matrix-side'
                  style={this.sideStyle(this.inputNode)}
                >
                  {this.renderPane(this.inputNode)}
                </div>
                <div
                  class='llm-token-matrix-side'
                  style={this.sideStyle(this.outputNode)}
                >
                  {this.renderPane(this.outputNode)}
                </div>
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
