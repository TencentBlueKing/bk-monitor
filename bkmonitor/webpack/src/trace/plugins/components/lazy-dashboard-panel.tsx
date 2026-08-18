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
  computed,
  defineComponent,
  nextTick,
  onBeforeUnmount,
  onMounted,
  provide,
  ref,
  shallowRef,
  toRef,
  watch,
} from 'vue';

import { random } from 'monitor-common/utils/utils';
import { type DashboardColumnType, type IPanelModel, PanelModel } from 'monitor-ui/chart-plugins/typings';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { useI18n } from 'vue-i18n';

import ChartWrapper from './chart-wrapper';

import type { DateValue } from '@blueking/date-picker';
import type { SceneType } from 'monitor-pc/pages/monitor-k8s/typings';

import './dashboard-panel.scss';
/** 接收图表当前页面跳转事件 */
export const UPDATE_SCENES_TAB_DATA = 'UPDATE_SCENES_TAB_DATA';

export default defineComponent({
  name: 'LazyDashboardPanel',
  props: {
    // 视图集合：后端返回的原始 Panel 列表，可包含 row 类型（分组）和普通图表。
    panels: { required: false, type: Array as PropType<IPanelModel[]> },
    // dashboard 唯一标识，用于 echarts groupId / 面板联动。
    id: { required: true, type: String },
    // 自动展示初始化列数
    column: { default: 'custom', type: [String, Number] as PropType<DashboardColumnType> },
    // 是否为拆分面板，供后代组件通过 provide 获取展示差异。
    isSplitPanel: { default: false, type: Boolean },
    // 单图模式开关：只展示一张图，其他逻辑直接跳过。
    isSingleChart: { default: false, type: Boolean },
    // 单图模式下是否显示"返回概览"按钮。
    needOverviewBtn: { type: Boolean, default: false },
    // 返回概览 或者 详情页面
    backToType: { default: () => '', type: String as PropType<SceneType> },
    // 下钻时需要的 dashboardId（如接口联动）。
    dashboardId: { type: String, default: '' },
    // 渲染命中逻辑：matchDisplay 判断是否需要展示某个 panel。
    matchFields: { default: () => {}, type: Object },
  },
  emits: ['linkTo', 'lintToDetail', 'backToOverview', 'successLoad'],
  setup(props, { emit }) {
    const { t } = useI18n();
    // 当前面板是否拆分给子组件，避免多层级 props 传递。
    provide('isSplitPanel', toRef(props, 'isSplitPanel'));

    /**
     * 作用域级别的 dataZoom 事件广播。
     * 每个 LazyDashboardPanel 实例拥有独立的 ref，保证同 Collapse 组内图表联动、
     * 跨 Collapse 组互不影响。
     *
     * 使用 { range, sourceId } 结构：
     * - range: 框选后的时间范围
     * - sourceId: 发起框选的图表实例 ID，用于避免自身重复处理
     *
     * FailureAlarmChart 通过 inject 获取，
     * watch({ immediate: false }) 确保后续懒加载的图表不会收到历史 zoom 事件。
     */
    const panelZoomRange = shallowRef<{ range: DateValue; sourceId: string } | null>(null);
    provide('lazyPanelZoomRange', panelZoomRange);

    // 视图实例集合
    const localPanels = ref<PanelModel[]>([]);
    // 规范化列数：非法值降级为 1
    const normalizedColumn = computed(() => {
      const numericColumn = typeof props.column === 'number' ? props.column : Number(props.column);
      return Number.isFinite(numericColumn) && numericColumn > 0 ? numericColumn : 1;
    });

    // 单图模式下的唯一 Panel
    const singleChartPanel = computed(() => {
      const panels = props.panels.filter(item => (item.type === 'row' ? !!item.panels?.length : true));
      return new PanelModel(panels[0]?.type === 'row' ? panels[0]?.panels?.[0] : panels[0]);
    });

    // ========= IntersectionObserver 懒加载 & tooltip 边界控制 =========

    /** 曾进入过视口的 panel id 集合（只增不减，用于控制是否渲染 ChartWrapper） */
    const renderedPanelIds = ref<Set<string>>(new Set());

    /** 当前在视口范围内的 panel id 集合（随滚动增减），用于 dataZoom 联动范围判定 */
    const viewportPanelIds = ref<Set<string>>(new Set());
    provide('viewportPanelIds', viewportPanelIds);
    let observer: IntersectionObserver | null = null;
    /** panel id → DOM 元素映射，用于 observe / unobserve */
    const itemRefs = new Map<string, HTMLElement>();

    const setItemRef = (panelId: string, el: HTMLElement | null) => {
      if (el) {
        itemRefs.set(panelId, el);
        // 如果 observer 已初始化，立刻 observe
        if (observer) {
          observer.observe(el);
        }
      } else {
        const existing = itemRefs.get(panelId);
        if (existing && observer) {
          observer.unobserve(existing);
        }
        itemRefs.delete(panelId);
      }
    };

    /** 获取指定 panel DOM 内所有 echarts 实例 */
    const getEchartsInstances = (panelEl: HTMLElement) => {
      const canvasDoms = panelEl.querySelectorAll<HTMLElement>('.chart-base, .echart-instance, [_echarts_instance_]');
      const targets = canvasDoms.length ? Array.from(canvasDoms) : [panelEl];
      const instances: echarts.ECharts[] = [];
      for (const dom of targets) {
        const inst = echarts.getInstanceByDom(dom);
        if (inst) instances.push(inst);
      }
      return instances;
    };

    /** 被移出联动组的 echarts 实例缓存，用于重新进入视口时恢复 */
    const disconnectedMap = new Map<string, echarts.ECharts[]>();

    /**
     * 图表滚出视口时：隐藏 tooltip 并将实例从联动组中移除，
     * 阻止视口外图表因联动而显示 tooltip。
     */
    const disconnectPanelFromGroup = (panelId: string, panelEl: HTMLElement) => {
      const instances = getEchartsInstances(panelEl);
      if (!instances.length) return;
      for (const inst of instances) {
        // 先隐藏当前 tooltip
        inst.dispatchAction({ type: 'hideTip' });
        inst.dispatchAction({ type: 'updateAxisPointer', currTrigger: 'leave' });
        // 将实例从联动组中移除
        inst.group = '';
      }
      disconnectedMap.set(panelId, instances);
    };

    /** 图表重新进入视口时：恢复实例的 group，重新加入联动组 */
    const reconnectPanelToGroup = (panelId: string) => {
      const instances = disconnectedMap.get(panelId);
      if (!instances) return;
      for (const inst of instances) {
        if (inst.isDisposed?.()) continue;
        inst.group = props.id.toString();
      }
      disconnectedMap.delete(panelId);
      echarts.connect(props.id.toString());
    };

    /** 获取滚动容器 .failure-view，作为 IntersectionObserver 的 root 和 tooltip 边界参照 */
    const getScrollRoot = (): Element | null => {
      return document.querySelector('.failure-view') || null;
    };

    /**
     * 通过 monkey-patch echarts.setOption，拦截 tooltip.position 回调并包装 .failure-view 边界检查。
     * 不直接设置 tooltip.show = false，因为 base-echart.tsx 的 initPropsWatcher 会在 options
     * 变化时重新调用 setOption 覆盖配置；而 patch setOption 本身可以持续生效。
     */
    const patchedInstances = new WeakSet<echarts.ECharts>();

    /** 包装 tooltip.position，当 tooltip 超出 .failure-view 可视区域时隐藏 */
    const wrapPositionFn = (originalPosition: (...args: any[]) => any, inst: echarts.ECharts) => {
      const wrapped = (pos: any, params: any, dom: any, rect: any, size: any) => {
        const result = originalPosition(pos, params, dom, rect, size);
        if (!result) return result;

        const viewRoot = getScrollRoot();
        if (!viewRoot) return result;
        const viewRect = viewRoot.getBoundingClientRect();

        const chartDom = inst.getDom?.();
        if (!chartDom) return result;
        const chartRect = chartDom.getBoundingClientRect();

        const tooltipLeft = chartRect.left + (result.left ?? 0);
        const tooltipTop = chartRect.top + (result.top ?? 0);
        const tooltipRight = tooltipLeft + (size.contentSize?.[0] ?? 0);
        const tooltipBottom = tooltipTop + (size.contentSize?.[1] ?? 0);

        const isOutside =
          tooltipBottom < viewRect.top ||
          tooltipTop > viewRect.bottom ||
          tooltipRight < viewRect.left ||
          tooltipLeft > viewRect.right;

        return isOutside ? { left: -9999, top: -9999 } : result;
      };
      (wrapped as any).__isWrapped = true;
      return wrapped;
    };

    /** 对单个 echarts 实例进行 setOption patch，拦截 tooltip.position */
    const patchInstance = (inst: echarts.ECharts) => {
      if (patchedInstances.has(inst)) return;
      patchedInstances.add(inst);

      const originalSetOption = inst.setOption.bind(inst);
      (inst as any).setOption = (option: any, ...rest: any[]) => {
        if (option?.tooltip) {
          const tooltipCfg = option.tooltip;
          if (typeof tooltipCfg.position === 'function' && !(tooltipCfg.position as any).__isWrapped) {
            tooltipCfg.position = wrapPositionFn(tooltipCfg.position, inst);
          }
        }
        return originalSetOption(option, ...rest);
      };

      // 对已有的 tooltip.position 也进行包装
      const currentOption = inst.getOption?.() as any;
      if (currentOption?.tooltip) {
        const tooltipCfg = Array.isArray(currentOption.tooltip) ? currentOption.tooltip[0] : currentOption.tooltip;
        if (typeof tooltipCfg?.position === 'function' && !(tooltipCfg.position as any).__isWrapped) {
          originalSetOption({ tooltip: { position: wrapPositionFn(tooltipCfg.position, inst) } } as any, {
            notMerge: false,
            lazyUpdate: false,
            silent: true,
          });
        }
      }
    };

    /** 扫描 panel DOM 内的 echarts 实例并 patch，返回成功 patch 的数量 */
    const patchPanelInstances = (panelEl: HTMLElement) => {
      const instances = getEchartsInstances(panelEl);
      for (const inst of instances) {
        patchInstance(inst);
      }
      return instances.length;
    };

    /**
     * 持久化 MutationObserver：监听 panel DOM 内 echarts 实例的创建 / 重建。
     *
     * 背景：MonitorCharts 在数据重新加载时会 loading=true → VueEcharts 卸载 → loading=false → VueEcharts 重新挂载，
     * 新 echarts 实例通过 vue-echarts 的 watchEffect 自动携带 group = dashboardId。
     * 如果此时面板不在视口内，新实例不会被 disconnectPanelFromGroup 断开（因为 IntersectionObserver
     * 的 isIntersecting=false 事件已经在 VueEcharts 卸载前触发过了），导致 tooltip 联动到视口外。
     *
     * 修复：observer 保持活跃（仅监听 _echarts_instance_ 属性变化，开销极小），
     * 每次检测到新实例时，既 patch tooltip 位置裁剪，又检查视口状态 —— 不在视口内则立即断开 group。
     */
    const panelMutationObservers = new Map<string, MutationObserver>();

    const startPanelPatchObserver = (panelId: string, panelEl: HTMLElement) => {
      if (panelMutationObservers.has(panelId)) return;
      // 先尝试直接 patch 已有实例（不 return，后续仍启动 observer 以检测重建）
      patchPanelInstances(panelEl);

      const mo = new MutationObserver(() => {
        const count = patchPanelInstances(panelEl);
        if (count > 0 && !viewportPanelIds.value.has(panelId)) {
          // 新实例产生但面板不在视口 → 立即断开 group，防止 tooltip 联动到视口外
          disconnectPanelFromGroup(panelId, panelEl);
        }
      });

      // 仅监听 _echarts_instance_ 属性变化（echarts.init 设置），开销极低
      mo.observe(panelEl, {
        subtree: true,
        attributes: true,
        attributeFilter: ['_echarts_instance_'],
      });
      panelMutationObservers.set(panelId, mo);
    };

    /** 停止所有 panel 的 MutationObserver */
    const stopAllPatchObservers = () => {
      for (const [, mo] of panelMutationObservers) {
        mo.disconnect();
      }
      panelMutationObservers.clear();
    };

    const initObserver = () => {
      const root = getScrollRoot();
      observer = new IntersectionObserver(
        entries => {
          let renderedChanged = false;
          let viewportChanged = false;
          const nextRendered = new Set(renderedPanelIds.value);
          const nextViewport = new Set(viewportPanelIds.value);
          for (const entry of entries) {
            const panelId = (entry.target as HTMLElement).dataset.panelId;
            if (!panelId) continue;
            if (entry.isIntersecting) {
              reconnectPanelToGroup(panelId);
              if (!nextViewport.has(panelId)) {
                nextViewport.add(panelId);
                viewportChanged = true;
              }
              if (!nextRendered.has(panelId)) {
                nextRendered.add(panelId);
                renderedChanged = true;
                const el = itemRefs.get(panelId);
                if (el) startPanelPatchObserver(panelId, el);
              }
            } else {
              if (nextRendered.has(panelId)) {
                nextTick(() => disconnectPanelFromGroup(panelId, entry.target as HTMLElement));
              }
              if (nextViewport.has(panelId)) {
                nextViewport.delete(panelId);
                viewportChanged = true;
              }
            }
          }
          if (renderedChanged) {
            renderedPanelIds.value = nextRendered;
          }
          if (viewportChanged) {
            viewportPanelIds.value = nextViewport;
          }
        },
        {
          root,
          rootMargin: '200px 0px', // 提前 200px 预加载
        }
      );
      // observe 已经存在的元素
      for (const el of itemRefs.values()) {
        observer.observe(el);
      }
    };

    const destroyObserver = () => {
      if (observer) {
        observer.disconnect();
        observer = null;
      }
    };

    /** 曾进入过视口即视为可见，保持渲染状态 */
    const isPanelVisible = (panelId: string) => renderedPanelIds.value.has(panelId);

    // ========= End 懒加载 & tooltip 边界控制 =========

    watch(
      () => props.panels,
      () => {
        if (!props.panels) return;
        // panels 刷新后 DOM 会重建：必须卸掉旧 MutationObserver / 视口与 disconnect 缓存，
        // 否则同 panelId 会因 has(panelId) 短路导致新 DOM 挂不上 patch，并造成泄漏。
        stopAllPatchObservers();
        disconnectedMap.clear();
        viewportPanelIds.value = new Set();
        handleInitPanelsGridPosition(props.panels);
        localPanels.value = handleInitLocalPanels(props.panels);
        renderedPanelIds.value = new Set();
      },
      { immediate: true }
    );

    watch(normalizedColumn, () => {
      echarts.disconnect(props.id.toString());
      handleInitPanelsGridPosition(localPanels.value);
      handleConnectEcharts();
    });

    // 将扁平面板根据列数分组成行
    const panelRows = computed(() => {
      const panels = localPanels.value;
      if (!panels.length) return [];
      const column = normalizedColumn.value;
      if (column <= 1) {
        return panels.map(panel => ({
          key: `${panel.id}`,
          panels: [panel],
        }));
      }
      const rows: { key: string; panels: PanelModel[] }[] = [];
      let currentRow: PanelModel[] = [];
      const pushRow = (rowPanels: PanelModel[]) => {
        const key = rowPanels.map(item => item.id).join('-') || random(6);
        rows.push({ key, panels: rowPanels });
      };
      const flushCurrentRow = () => {
        if (currentRow.length) {
          pushRow(currentRow);
          currentRow = [];
        }
      };
      panels.forEach(panel => {
        const occupyFullRow = panel.type === 'row';
        if (occupyFullRow) {
          flushCurrentRow();
          pushRow([panel]);
          return;
        }
        currentRow.push(panel);
        if (currentRow.length >= column) {
          flushCurrentRow();
        }
      });
      flushCurrentRow();
      return rows;
    });

    onMounted(() => {
      // 初始化 observer
      initObserver();
      // 等待所有子视图实例创建完进行视图实例的关联
      handleConnectEcharts();
    });

    onBeforeUnmount(() => {
      destroyObserver();
      stopAllPatchObservers();
      disconnectedMap.clear();
      echarts.disconnect(props.id.toString());
    });

    /** 将所有 echarts 实例连接到同一 group 实现联动（>=300 个图表时跳过以防性能问题） */
    function handleConnectEcharts() {
      setTimeout(() => {
        if (localPanels.value?.length < 300) {
          echarts.connect(props.id.toString());
        }
      }, 1500);
    }

    /** 根据列数设置各图表的 legend 布局 */
    function handleInitPanelsGridPosition(panels: IPanelModel[]) {
      if (!panels) return;
      const updatePanelsGridPosition = (list: IPanelModel[]) => {
        for (const item of list) {
          if (item.type === 'row') {
            if (item.panels?.length) {
              updatePanelsGridPosition(item.panels);
            }
          } else {
            const displayMode = props.column === 1 ? item.options?.legend?.displayMode || 'table' : 'list';
            const placement = props.column === 1 ? item.options?.legend?.placement || 'right' : 'bottom';
            item.options = {
              ...item.options,
              legend: {
                displayMode,
                placement,
              },
            } as any;
          }
        }
      };
      updatePanelsGridPosition(panels);
    }

    /** 构造"未分组"行 Panel，将散列面板包裹在 row panel 下保持 UI 一致 */
    function getUnGroupPanel(y: number): IPanelModel {
      return {
        gridPos: {
          x: 0,
          y,
          w: 24,
          h: 1,
        },
        id: random(10),
        options: {},
        panels: [],
        targets: [],
        title: '',
        type: 'row',
        collapsed: true,
        subTitle: '',
      };
    }

    /** 将 Panel 数据转换为 PanelModel，注入 dashboardId 等上下文 */
    function getTransformPanel(panel: IPanelModel) {
      const item = new PanelModel({
        ...panel,
        dashboardId: props.id,
        panelIds: panel?.panels?.map(item => item.id) || [],
      });
      return item;
    }

    /** 初始化 dashboard：将原始 panels 转换为 PanelModel 列表并处理分组关系 */
    function handleInitLocalPanels(panels: IPanelModel[]) {
      const list: PanelModel[] = [];
      let unGroupList: PanelModel[] = [];
      let i = 0;
      const len = panels.length;
      let isInUnGroup = false;
      let hasRowGroup = false;
      while (i < len) {
        const panel = panels[i];
        const isRowPanel = panel.type === 'row';
        if (isRowPanel) {
          if (isInUnGroup && unGroupList.length) {
            unGroupList.forEach(item => {
              item.updateShow(true);
              item.groupId = list[list.length - 1].id;
            });
          }
          list.push(...unGroupList);
          isInUnGroup = false;
          unGroupList = [];
          const rowPanel = getTransformPanel(panel);
          list.push(rowPanel);
          if (panel?.panels?.length) {
            const childList = panel.panels.map(item =>
              getTransformPanel({
                ...item,
                show: !!panel.collapsed,
                groupId: rowPanel.id,
              })
            );
            list.push(...childList);
          }
          hasRowGroup = true;
        } else {
          if (hasRowGroup && !isInUnGroup) {
            const rowPanel = getUnGroupPanel(list[list.length - 1].gridPos.y + 1);
            list.push(new PanelModel({ ...rowPanel }));
            isInUnGroup = true;
          }
          unGroupList.push(getTransformPanel(panel));
        }
        i += 1;
      }
      if (unGroupList.length) {
        if (list[list.length - 1]?.type === 'row') {
          unGroupList.forEach(item => {
            item.updateShow(true);
            item.groupId = list[list.length - 1].id;
          });
        }
        list.push(...unGroupList);
      }
      return list;
    }

    /** 选中图表触发事件 */
    function handleChartCheck(check: boolean, panel: PanelModel) {
      panel.updateChecked(check);
    }

    /** 根据 matchDisplay 过滤字段控制 panel 是否展示 */
    function getPanelDisplay(panel: PanelModel) {
      if (!panel.show) return 'none';
      if (panel.matchDisplay && props.matchFields) {
        return Object.keys(panel.matchDisplay).every(key => props.matchFields[key] === panel.matchDisplay[key])
          ? 'flex'
          : 'none';
      }
      return 'flex';
    }

    /** 分组折叠/展开 */
    function handleCollapse(collapse: boolean, panel: PanelModel) {
      panel.updateCollapsed(collapse);
      panel.panels?.forEach(item => {
        const panel = localPanels.value.find(set => set.id === item.id);
        panel?.updateShow(collapse);
      });
    }
    const handleSuccessLoad = () => emit('successLoad');

    function renderFn() {
      if (!props.panels?.length) return <div class='dashboard-panel empty-data'>{t('查无数据')}</div>;
      const columnPercent = (1 / normalizedColumn.value) * 100;
      return (
        <div
          id='dashboard-panel'
          class='dashboard-panel'
        >
          {props.isSingleChart ? (
            <div class='single-chart-content'>
              <div class={['single-chart-main', { 'has-btn': !!props.backToType }]}>
                <div class='single-chart-wrap'>
                  <ChartWrapper
                    groupId={props.id}
                    isNewAlarmView={true}
                    panel={singleChartPanel.value}
                  />
                </div>
              </div>
            </div>
          ) : (
            <div
              key='flex-dashboard'
              class='flex-dashboard'
            >
              {panelRows.value.map(row => (
                <div
                  key={row.key}
                  class='flex-dashboard-row'
                >
                  {row.panels.map(panel => {
                    const panelIdStr = `${panel.id}`;
                    const isVisible = isPanelVisible(panelIdStr);
                    return (
                      <div
                        id={`${panel.id}__key__`}
                        key={`${panel.id}__key__`}
                        ref={el => setItemRef(panelIdStr, el as HTMLElement)}
                        style={{
                          width: `calc(${columnPercent}% - 16px)`,
                          maxWidth: `calc(${columnPercent}% - 16px)`,
                          flex: `${columnPercent}%`,
                          display: getPanelDisplay(panel),
                          height: ['related-log-chart', 'exception-guide'].includes(panel.type)
                            ? 'calc(100vh - 240px)'
                            : undefined,
                        }}
                        class={{
                          'flex-dashboard-item': true,
                          'row-panel': panel.type === 'row',
                          'exception-panel': panel.type === 'exception-guide',
                        }}
                        data-panel-id={panelIdStr}
                      >
                        {isVisible ? (
                          <ChartWrapper
                            key={`${panel.id}__key__`}
                            groupId={props.id}
                            isNewAlarmView={true}
                            panel={panel}
                            onChartCheck={v => handleChartCheck(v, panel)}
                            onCollapse={v => panel.type === 'row' && handleCollapse(v, panel)}
                            onSuccessLoad={handleSuccessLoad}
                          />
                        ) : (
                          <div class='lazy-chart-placeholder'>
                            <div class='lazy-chart-loading'>
                              <div class='dot-loading'>
                                <span />
                                <span />
                                <span />
                              </div>
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              ))}
            </div>
          )}
        </div>
      );
    }

    return {
      renderFn,
      localPanels,
    };
  },
  render() {
    return this.renderFn();
  },
});
