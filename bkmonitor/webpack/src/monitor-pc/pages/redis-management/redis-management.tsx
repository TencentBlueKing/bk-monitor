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
import { Component, Vue } from 'vue-property-decorator';

import { getRedisManagementOverview } from 'monitor-api/modules/redis-management';

import {
  type IBoundaryDraft,
  type ICostPrefix,
  type IRouteSegment,
  buildBoundaryDraft,
  buildSparklineSegments,
  calculateMarkerHeight,
  calculateMemoryScale,
  canEditBoundary,
} from './route-model';

import './redis-management.scss';

interface IApiMemory {
  capacity_bytes: null | number;
  current_bytes: null | number;
  current_usage_ratio: null | number;
  max_3h_bytes: null | number;
  max_3h_usage_ratio: null | number;
  missing_points: number;
  observed_at: null | number;
  trend: Array<[null | number, number]>;
}

interface IApiNode {
  cache_type: string;
  id: number;
  is_default: boolean;
  is_enable: boolean;
  memory: IApiMemory;
  node_alias: string;
  snapshot: null | {
    coverage: null | Record<string, number>;
    routing_matches_current: boolean | null;
    snapshot_time: null | string;
  };
}

interface IHotStrategy {
  bk_biz_id: null | number;
  estimated_peak_members: number;
  lower_bytes: number;
  series_upper_bound: null | number;
  snapshot_node_id: number;
  snapshot_time: null | string;
  strategy_id: number;
  upper_bytes: number;
}

interface IOverview {
  generated_at: number;
  nodes: IApiNode[];
  cost_evidence: {
    cost_prefix: Array<{
      lower_bytes: number;
      measured_count: number;
      peak_members: number;
      strategy_id: number;
      unmeasured_count: number;
      upper_bytes: number;
    }>;
    hot_strategies: IHotStrategy[];
    missing_snapshot_count: number;
    nodes: Array<{
      node_id: number;
      routing_matches_current: boolean | null;
      snapshot_time: null | string;
    }>;
    stale_strategy_count: number;
    status: 'complete' | 'partial' | 'unavailable';
    unmeasured_strategy_count: number;
    valid_strategy_count: number;
  };
  routing: {
    max_strategy_id: number;
    routers: Array<{
      node: null | { id: number };
      score_range: { ceil: number; floor: number };
      strategy_score: number;
    }>;
    snapshot_id: string;
    terminal_score: null | number;
    topology_validation: { errors: string[]; valid: boolean };
  };
}

const COLORS = ['#3a84ff', '#8b75e8', '#2dcbba', '#ff9c01', '#699df4', '#ea6b66'];
const TOPOLOGY_ERROR_LABELS: Record<string, string> = {
  duplicate_positive_route_boundary: '存在重复路由边界',
  missing_positive_route: '缺少有效路由',
  route_references_disabled_node: '路由引用了停用节点',
  route_references_unknown_node: '路由引用了不存在的节点',
  terminal_route_does_not_cover_current_strategies: '当前策略范围未被完整覆盖',
};

const formatBytes = (value: null | number) => {
  if (value === null || !Number.isFinite(value)) return '--';
  const units = ['B', 'KiB', 'MiB', 'GiB', 'TiB'];
  let current = value;
  let index = 0;
  while (current >= 1024 && index < units.length - 1) {
    current /= 1024;
    index += 1;
  }
  return `${current >= 100 || index === 0 ? current.toFixed(0) : current.toFixed(1)} ${units[index]}`;
};

const formatPercent = (value: null | number) => (value === null ? '--' : `${(value * 100).toFixed(1)}%`);
const formatInteger = (value: number) => Math.round(value).toLocaleString('zh-CN');

@Component
export default class RedisManagement extends Vue {
  data: IOverview | null = null;
  draft: IBoundaryDraft | null = null;
  loading = false;
  draggingBoundary: null | number = null;

  created() {
    this.loadOverview();
  }

  get nodes() {
    return this.data?.nodes ?? [];
  }

  get maxStrategyId() {
    return Math.max(this.data?.routing.max_strategy_id ?? 1, 1);
  }

  get committedRoutes(): IRouteSegment[] {
    return (this.data?.routing.routers ?? [])
      .filter(item => item.node && item.score_range.floor <= this.maxStrategyId)
      .map(item => ({
        from: item.score_range.floor,
        to: Math.min(item.score_range.ceil, this.maxStrategyId),
        nodeId: item.node.id,
      }));
  }

  get displayRoutes() {
    return this.draft?.routes ?? this.committedRoutes;
  }

  get costPrefix(): ICostPrefix[] {
    return (this.data?.cost_evidence.cost_prefix ?? []).map(item => ({
      strategyId: item.strategy_id,
      lowerBytes: item.lower_bytes,
      measuredCount: item.measured_count,
      upperBytes: item.upper_bytes,
      peakMembers: item.peak_members,
      unmeasuredCount: item.unmeasured_count,
    }));
  }

  get enabledNodeIds() {
    return this.nodes.filter(node => node.is_enable).map(node => node.id);
  }

  get hotStrategies() {
    return this.data?.cost_evidence.hot_strategies ?? [];
  }

  get memoryScale() {
    return calculateMemoryScale(this.hotStrategies.map(strategy => strategy.upper_bytes));
  }

  get draftEvidenceComplete() {
    if (!this.draft) return false;
    const sourceEvidence = this.data?.cost_evidence.nodes.find(item => item.node_id === this.draft.sourceNodeId);
    return sourceEvidence?.routing_matches_current === true && this.draft.unmeasuredCount === 0;
  }

  get draftHasKnownCost() {
    return !!this.draft && (this.draftEvidenceComplete || this.draft.measuredCount > 0);
  }

  get evidenceLabel() {
    if (this.data?.cost_evidence.status === 'complete') return '成本证据完整';
    if (this.data?.cost_evidence.status === 'partial') return '成本证据部分可用';
    return '暂无有效成本证据';
  }

  get costSnapshotTimeLabel() {
    const evidenceNodes = this.data?.cost_evidence.nodes ?? [];
    if (!evidenceNodes.length) return '暂无';
    return evidenceNodes
      .map(item => {
        const snapshotTime = item.snapshot_time ? new Date(item.snapshot_time).toLocaleString() : '暂无';
        return `${this.nodeName(item.node_id)} ${snapshotTime}`;
      })
      .join(' · ');
  }

  get futureRoute() {
    const futureId = this.maxStrategyId + 1;
    return (this.data?.routing.routers ?? []).find(
      item => item.score_range.floor <= futureId && item.score_range.ceil >= futureId
    );
  }

  nodeById(nodeId: number) {
    return this.nodes.find(node => node.id === nodeId);
  }

  nodeName(nodeId: number) {
    return this.nodeById(nodeId)?.node_alias || `#${nodeId}`;
  }

  nodeColor(nodeId: number) {
    const index = Math.max(
      0,
      this.nodes.findIndex(node => node.id === nodeId)
    );
    return COLORS[index % COLORS.length];
  }

  formatNodeMemory(value: null | number, nodeId: number) {
    const capacity = this.nodeById(nodeId)?.memory.capacity_bytes;
    const ratio = value !== null && capacity && capacity > 0 ? value / capacity : null;
    return `${formatBytes(value)} (${formatPercent(ratio)})`;
  }

  formatTopologyErrors(errors: string[]) {
    return errors.map(error => TOPOLOGY_ERROR_LABELS[error] ?? '路由拓扑异常').join('、');
  }

  async loadOverview() {
    this.loading = true;
    try {
      this.data = await getRedisManagementOverview({}, { needBiz: false });
      this.draft = null;
    } finally {
      this.loading = false;
    }
  }

  beginBoundaryDrag(event: PointerEvent, boundaryIndex: number) {
    if (
      !canEditBoundary(
        this.committedRoutes,
        boundaryIndex,
        this.enabledNodeIds,
        this.data?.routing.topology_validation.valid === true
      )
    )
      return;
    if (this.draft && this.draft.boundaryIndex !== boundaryIndex) return;
    const track = this.$refs.routeTrack as HTMLElement;
    if (!track) return;
    event.preventDefault();
    this.draggingBoundary = boundaryIndex;

    const move = (pointerEvent: PointerEvent) => {
      const rect = track.getBoundingClientRect();
      const ratio = Math.max(0, Math.min(1, (pointerEvent.clientX - rect.left) / rect.width));
      const boundary = Math.round(ratio * this.maxStrategyId);
      const original = this.committedRoutes[boundaryIndex]?.to;
      if (original === undefined || boundary === original) {
        this.draft = null;
        return;
      }
      this.draft = buildBoundaryDraft(this.committedRoutes, boundaryIndex, boundary, this.costPrefix);
    };
    const finish = () => {
      this.draggingBoundary = null;
      document.removeEventListener('pointermove', move);
      document.removeEventListener('pointerup', finish);
      document.removeEventListener('pointercancel', finish);
    };
    document.addEventListener('pointermove', move);
    document.addEventListener('pointerup', finish);
    document.addEventListener('pointercancel', finish);
  }

  routeStyle(route: IRouteSegment) {
    return {
      left: `${((route.from - 1) / this.maxStrategyId) * 100}%`,
      width: `${((route.to - route.from + 1) / this.maxStrategyId) * 100}%`,
      background: this.nodeColor(route.nodeId),
    };
  }

  renderNodeCard(node: IApiNode) {
    const evidenceTime = node.snapshot?.snapshot_time
      ? new Date(node.snapshot.snapshot_time).toLocaleString()
      : '暂无成本证据';
    const routeMatched = node.snapshot?.routing_matches_current;
    const measured = node.snapshot?.coverage?.measured;
    const routeTotal = node.snapshot?.coverage?.route_matched;
    return (
      <div class='redis-node-card'>
        <div class='redis-node-card__header'>
          <span
            style={{ background: this.nodeColor(node.id) }}
            class='redis-node-dot'
          />
          <strong>{node.node_alias}</strong>
          {node.is_default && <span class='redis-node-tag'>默认</span>}
          <span class={['redis-node-state', { disabled: !node.is_enable }]}>
            {node.is_enable ? '已启用' : '已停用'}
          </span>
        </div>
        <div class='redis-node-card__metrics'>
          <div>
            <span>当前内存</span>
            <strong>{formatBytes(node.memory.current_bytes)}</strong>
            <em>{formatPercent(node.memory.current_usage_ratio)}</em>
          </div>
          <div>
            <span>3 小时最大内存</span>
            <strong>{formatBytes(node.memory.max_3h_bytes)}</strong>
            <em>{formatPercent(node.memory.max_3h_usage_ratio)}</em>
          </div>
        </div>
        <svg
          class='redis-node-card__trend'
          preserveAspectRatio='none'
          viewBox='0 0 180 42'
        >
          {buildSparklineSegments(node.memory.trend).map((points, index) => (
            <polyline
              key={index}
              points={points}
              stroke={this.nodeColor(node.id)}
            />
          ))}
        </svg>
        <div class='redis-node-card__foot'>
          <span>
            指标时间 {node.memory.observed_at ? new Date(node.memory.observed_at * 1000).toLocaleString() : '--'}
          </span>
          <span>成本快照 {evidenceTime}</span>
          {typeof measured === 'number' && typeof routeTotal === 'number' && (
            <span>
              成本覆盖 {formatInteger(measured)}/{formatInteger(routeTotal)}
            </span>
          )}
          {routeMatched === false && <span class='is-warning'>快照路由已变化</span>}
          {node.memory.missing_points > 0 && <span>{node.memory.missing_points} 个趋势缺口</span>}
        </div>
      </div>
    );
  }

  renderHotStrategy(strategy: IHotStrategy) {
    const exceeded = strategy.upper_bytes > this.memoryScale;
    const left = ((strategy.strategy_id - 1) / this.maxStrategyId) * 100;
    const title = [
      `策略 ${strategy.strategy_id}`,
      strategy.bk_biz_id === null ? '' : `业务 ${strategy.bk_biz_id}`,
      `series ${formatInteger(strategy.series_upper_bound ?? 0)}`,
      `预估内存峰值 ${formatBytes(strategy.lower_bytes)}–${formatBytes(strategy.upper_bytes)}`,
      `节点 ${this.nodeName(strategy.snapshot_node_id)}`,
      strategy.snapshot_time ? `证据时间 ${new Date(strategy.snapshot_time).toLocaleString()}` : '',
    ]
      .filter(Boolean)
      .join('\n');
    return (
      <a
        key={strategy.strategy_id}
        style={{ left: `${left}%`, height: `${calculateMarkerHeight(strategy.upper_bytes, this.memoryScale)}px` }}
        class={['redis-hot-marker', { exceeded }]}
        href={`?bizId=${strategy.bk_biz_id ?? window.cc_biz_id}#/strategy-config/detail/${strategy.strategy_id}`}
        rel='noopener'
        target='_blank'
        title={title}
      >
        {exceeded && <span class='redis-hot-marker__arrow'>↑</span>}
        <span class='redis-hot-marker__point' />
      </a>
    );
  }

  renderRouteAxis() {
    return (
      <section class='redis-routing-panel'>
        <div class='redis-section-head'>
          <div>
            <h3>策略路由</h3>
            <p>热策略高度表示预估内存峰值；拖动一个节点边界可实时查看容量草稿。</p>
          </div>
          <div class='redis-route-scale'>内存刻度 0–{formatBytes(this.memoryScale)}</div>
        </div>
        <div class='redis-route-context'>
          <span>当前策略范围 1–{formatInteger(this.maxStrategyId)}</span>
          <span>
            {this.evidenceLabel} · 已识别 {this.data?.cost_evidence.valid_strategy_count ?? 0} 条
            {(this.data?.cost_evidence.unmeasured_strategy_count ?? 0) > 0 &&
              ` · ${this.data.cost_evidence.unmeasured_strategy_count} 条未计入估算`}
            {(this.data?.cost_evidence.stale_strategy_count ?? 0) > 0 &&
              ` · ${this.data.cost_evidence.stale_strategy_count} 条路由已变化`}
            {(this.data?.cost_evidence.missing_snapshot_count ?? 0) > 0 &&
              ` · ${this.data.cost_evidence.missing_snapshot_count} 个节点缺少成本证据`}
          </span>
        </div>
        <div class='redis-route-snapshot'>成本快照时间：{this.costSnapshotTimeLabel}</div>
        {this.data?.routing.topology_validation.valid === false && (
          <p class='redis-route-warning'>
            当前路由拓扑存在异常，仅支持查看，暂不能调整边界：
            {this.formatTopologyErrors(this.data.routing.topology_validation.errors)}
          </p>
        )}
        <div class='redis-route-layout'>
          <div class='redis-route-main'>
            <div class='redis-route-visual'>
              <div class='redis-memory-line redis-memory-line--top' />
              <div class='redis-memory-line redis-memory-line--middle' />
              <div class='redis-hot-layer'>{this.hotStrategies.map(item => this.renderHotStrategy(item))}</div>
              <div
                ref='routeTrack'
                class='redis-route-track'
              >
                {this.displayRoutes.map(route => (
                  <div
                    key={`${route.from}-${route.nodeId}`}
                    style={this.routeStyle(route)}
                    class='redis-route-segment'
                  >
                    <strong>{this.nodeName(route.nodeId)}</strong>
                    <span>
                      {formatInteger(route.from)}–{formatInteger(route.to)}
                    </span>
                  </div>
                ))}
                {this.committedRoutes.slice(0, -1).map((route, index) => {
                  const selected = this.draft?.boundaryIndex === index;
                  const boundary = selected ? this.draft.boundary : route.to;
                  const editable = canEditBoundary(
                    this.committedRoutes,
                    index,
                    this.enabledNodeIds,
                    this.data?.routing.topology_validation.valid === true
                  );
                  return (
                    <button
                      key={`boundary-${index}`}
                      style={{ left: `${(boundary / this.maxStrategyId) * 100}%` }}
                      class={[
                        'redis-route-boundary',
                        {
                          selected,
                          dragging: this.draggingBoundary === index,
                          locked: !editable || (this.draft && !selected),
                        },
                      ]}
                      on={{ pointerdown: (event: PointerEvent) => this.beginBoundaryDrag(event, index) }}
                      title={editable ? '拖动边界生成容量草稿' : '当前边界不可调整'}
                      type='button'
                    >
                      <span class='redis-route-boundary-label'>strategy_id {formatInteger(boundary)}</span>
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
          <div class='redis-future-route'>
            <strong>未来策略</strong>
            <span>
              {formatInteger(this.maxStrategyId + 1)}–
              {formatInteger(Math.max((this.data?.routing.terminal_score ?? 1) - 1, this.maxStrategyId))}
            </span>
            <em>新增策略 → {this.futureRoute?.node ? this.nodeName(this.futureRoute.node.id) : '未覆盖'}</em>
          </div>
        </div>
        <div class='redis-route-legend'>
          {this.nodes.map(node => (
            <span key={node.id}>
              <i style={{ background: this.nodeColor(node.id) }} />
              {node.node_alias}
            </span>
          ))}
          <span class='hot'>● 已知热策略</span>
        </div>
      </section>
    );
  }

  formatNodeMemoryRange(lower: null | number, upper: null | number, nodeId: number) {
    if (lower === null || upper === null) return '--';
    if (lower === upper) return this.formatNodeMemory(lower, nodeId);
    return `${this.formatNodeMemory(lower, nodeId)}–${this.formatNodeMemory(upper, nodeId)}`;
  }

  renderMemoryChange() {
    const costLabel = this.draftHasKnownCost
      ? `${formatBytes(this.draft.lowerBytes)}–${formatBytes(this.draft.upperBytes)}`
      : '--';
    return (
      <div class='redis-draft-state'>
        <h4>调整后内存预估</h4>
        {[this.draft.sourceNodeId, this.draft.targetNodeId].map(nodeId => {
          const node = this.nodeById(nodeId);
          const isSource = nodeId === this.draft.sourceNodeId;
          const currentLower =
            !isSource && this.draftHasKnownCost && node?.memory.current_bytes != null
              ? node.memory.current_bytes + this.draft.lowerBytes
              : null;
          const currentUpper =
            !isSource && this.draftHasKnownCost && node?.memory.current_bytes != null
              ? node.memory.current_bytes + this.draft.upperBytes
              : null;
          const maxLower =
            !isSource && this.draftHasKnownCost && node?.memory.max_3h_bytes != null
              ? node.memory.max_3h_bytes + this.draft.lowerBytes
              : null;
          const maxUpper =
            !isSource && this.draftHasKnownCost && node?.memory.max_3h_bytes != null
              ? node.memory.max_3h_bytes + this.draft.upperBytes
              : null;
          return (
            <div
              key={nodeId}
              class='redis-draft-node'
            >
              <strong>
                {this.nodeName(nodeId)}
                <em>
                  {isSource ? '预计迁出' : '预计迁入'} {costLabel}
                </em>
              </strong>
              <span>
                当前 {this.formatNodeMemory(node?.memory.current_bytes ?? null, nodeId)} →{' '}
                {isSource ? '调整后观测' : this.formatNodeMemoryRange(currentLower, currentUpper, nodeId)}
              </span>
              <span>
                3 小时最大 {this.formatNodeMemory(node?.memory.max_3h_bytes ?? null, nodeId)} →{' '}
                {isSource ? '调整后观测' : this.formatNodeMemoryRange(maxLower, maxUpper, nodeId)}
              </span>
            </div>
          );
        })}
      </div>
    );
  }

  renderDraft() {
    if (!this.draft) return null;
    const impacted = this.hotStrategies.filter(
      strategy => strategy.strategy_id >= this.draft.range.from && strategy.strategy_id <= this.draft.range.to
    );
    const costSummary = this.draftEvidenceComplete
      ? `预估迁移内存 ${formatBytes(this.draft.lowerBytes)}–${formatBytes(this.draft.upperBytes)}`
      : this.draft.measuredCount > 0
        ? `当前证据覆盖的迁移内存 ${formatBytes(this.draft.lowerBytes)}–${formatBytes(this.draft.upperBytes)}`
        : '迁移内存证据不足';
    return (
      <section class='redis-draft-panel'>
        <div class='redis-section-head'>
          <div>
            <h3>路由调整草稿</h3>
            <p>草稿不会修改当前路由；同一时间只能调整这一根边界。</p>
          </div>
          <button
            class='bk-button bk-default'
            type='button'
            onClick={() => (this.draft = null)}
          >
            取消调整
          </button>
        </div>
        <div class='redis-draft-summary'>
          <strong>边界 strategy_id {formatInteger(this.draft.boundary)}</strong>
          <span>
            {this.nodeName(this.draft.sourceNodeId)} → {this.nodeName(this.draft.targetNodeId)}
          </span>
          <span>
            策略范围 {formatInteger(this.draft.range.from)}–{formatInteger(this.draft.range.to)}
          </span>
          <span>{costSummary}</span>
        </div>
        <div class='redis-draft-grid'>{this.renderMemoryChange()}</div>
        <div class='redis-draft-impact'>
          <span title='迁移范围内策略的 Redis 检测结果在清理周期内可能同时存在的成员数量。它不是策略数、series 数或告警数。'>
            {this.draftEvidenceComplete ? '估算峰值成员' : '当前证据覆盖的峰值成员'}{' '}
            <strong>{this.draftHasKnownCost ? formatInteger(this.draft.peakMembers) : '--'}</strong>
          </span>
          <span>
            范围内已知热策略 <strong>{impacted.length}</strong>
          </span>
          <div>
            {impacted.map(strategy => (
              <a
                key={strategy.strategy_id}
                href={`?bizId=${strategy.bk_biz_id ?? window.cc_biz_id}#/strategy-config/detail/${strategy.strategy_id}`}
                rel='noopener'
                target='_blank'
              >
                #{strategy.strategy_id} ↗
              </a>
            ))}
          </div>
        </div>
      </section>
    );
  }

  render() {
    return (
      <div
        class='redis-management'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='redis-management__toolbar'>
          <div>
            <h2>Redis 节点管理</h2>
            <p>查看节点容量、策略路由与已知热策略，并生成单次边界调整的容量草稿。</p>
          </div>
          <button
            class='bk-button bk-default'
            type='button'
            onClick={this.loadOverview}
          >
            刷新
          </button>
        </div>
        {this.data && (
          <div>
            <div class='redis-node-grid'>{this.nodes.map(node => this.renderNodeCard(node))}</div>
            {this.renderRouteAxis()}
            {this.renderDraft()}
          </div>
        )}
      </div>
    );
  }
}
