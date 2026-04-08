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
import { type PropType, computed, defineComponent, onBeforeUnmount, onMounted, provide, ref, toRef, watch } from 'vue';

import { VirtualRender } from 'bkui-vue';
import { random } from 'monitor-common/utils/utils';
import { type DashboardColumnType, type IPanelModel, PanelModel } from 'monitor-ui/chart-plugins/typings';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { useI18n } from 'vue-i18n';

import ChartWrapper from './chart-wrapper';

import type { SceneType } from 'monitor-pc/pages/monitor-k8s/typings';

import './dashboard-panel.scss';
/** 接收图表当前页面跳转事件 */
export const UPDATE_SCENES_TAB_DATA = 'UPDATE_SCENES_TAB_DATA';

type PanelRow = {
  key: string;
  // 当前行所包含的 Panel 列表，长度 <= props.column
  panels: PanelModel[];
};

export default defineComponent({
  name: 'FlexDashboardPanelMigrated',
  props: {
    // 视图集合：后端返回的原始 Panel 列表，可包含 row 类型（分组）和普通图表。
    panels: { required: false, type: Array as PropType<IPanelModel[]> },
    // dashboard 唯一标识，用于 echarts groupId / 面板联动。
    id: { required: true, type: String },
    // 自动展示初始化列数
    column: { default: 'custom', type: [String, Number] as PropType<DashboardColumnType> },
    // 是否为拆分面板，供后代组件通过 provide 获取展示差异。
    isSplitPanel: { default: false, type: Boolean },
    // 单图模式开关：只展示一张图，其他逻辑直接跳过虚拟列表。
    isSingleChart: { default: false, type: Boolean },
    // 单图模式下是否显示“返回概览”按钮。
    needOverviewBtn: { type: Boolean, default: false },
    // 返回概览 或者 详情页面
    backToType: { default: () => '', type: String as PropType<SceneType> },
    // 下钻时需要的 dashboardId（如接口联动）。
    dashboardId: { type: String, default: '' },
    // 渲染命中逻辑：matchDisplay 判断是否需要展示某个 panel。
    matchFields: { default: () => {}, type: Object },
    // 自定义高度
    customHeightFn: { type: [Function, null], default: null },
    // 是否显示告警视图图表
    isAlarmView: { type: Boolean, default: false },
  },
  emits: ['linkTo', 'lintToDetail', 'backToOverview', 'successLoad'],
  setup(props, { emit }) {
    const { t } = useI18n();
    // 当前面板是否拆分给子组件，避免多层级 props 传递。
    provide('isSplitPanel', toRef(props, 'isSplitPanel'));
    // 视图实例集合
    const localPanels = ref<PanelModel[]>([]);
    // 规范化列数
    const normalizedColumn = computed(() => {
      const numericColumn = typeof props.column === 'number' ? props.column : Number(props.column);
      return Number.isFinite(numericColumn) && numericColumn > 0 ? numericColumn : 1;
    });

    // 单图模式下的唯一 Panel
    const singleChartPanel = computed(() => {
      const panels = props.panels.filter(item => (item.type === 'row' ? !!item.panels?.length : true));
      return new PanelModel(panels[0]?.type === 'row' ? panels[0]?.panels?.[0] : panels[0]);
    });

    watch(
      () => props.panels,
      () => {
        if (!props.panels) return;
        // 根据列数动态调整 legend 布局。
        handleInitPanelsGridPosition(props.panels);
        // 将原始结构转换为虚拟列表可直接使用的 PanelModel 列表。
        localPanels.value = handleInitLocalPanels(props.panels);
      },
      {
        immediate: true,
      }
    );

    // 列数改变时需要重置 echarts 联动 + 布局
    watch(normalizedColumn, () => {
      echarts.disconnect(props.id.toString());
      handleInitPanelsGridPosition(localPanels.value);
      handleConnectEcharts();
    });

    // 将扁平面板重新根据列数分组成 VirtualRender 行
    const virtualRows = computed<PanelRow[]>(() => {
      const panels = localPanels.value;
      if (!panels.length) return [];
      const column = normalizedColumn.value;
      // 单列或无有效列数时，直接将每个 panel 视为一行，避免不必要的拆分。
      if (column <= 1) {
        return panels.map(panel => ({
          key: `${panel.id}`,
          panels: [panel],
        }));
      }
      const rows: PanelRow[] = [];
      let currentRow: PanelModel[] = [];
      const pushRow = (rowPanels: PanelModel[]) => {
        const key = rowPanels.map(item => item.id).join('-') || random(6);
        rows.push({ key, panels: rowPanels });
      };
      /** flushCurrentRow：在以下两种场景触发：
       * 1. 遇到 row panel，需要先结束残余行。
       * 2. 当前行已填满 column 个面板。
       */
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
      // 收尾：补上最后一行。
      flushCurrentRow();
      return rows;
    });

    // 按虚拟行数量自动切换高度，从而让视图高度与数据体量匹配，避免渲染多余留白或滚动不足。
    const virtualHeight = computed(() => {
      const rowCount = virtualRows.value.length;
      if (rowCount <= 1) return '284px';
      if (rowCount === 2) return '568px';
      return '646px';
    });

    onMounted(() => {
      // 等待所以子视图实例创建完进行视图示例的关联 暂定5000ms 后期进行精细化配置
      handleConnectEcharts();
    });

    onBeforeUnmount(() => {
      echarts.disconnect(props.id.toString());
    });

    /**
     * 将当前 dashboard 下的所有 echarts 实例连接到同一个 group，确保联动功能生效。
     * 注意：过多图表（>=300）时不触发，以防性能问题。
     */
    function handleConnectEcharts() {
      setTimeout(() => {
        if (localPanels.value?.length < 300) {
          echarts.connect(props.id.toString());
        }
      }, 1500);
    }

    /**
     * @description: 设置各个图表的位置大小信息
     * @param {*}
     * @return {*}
     */
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

    /**
     * 构造一个“未分组”的行 Panel，用于将散列面板包裹在 row panel 下，保持 UI 一致。
     */
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

    /**
     * 包装 Panel 数据为 PanelModel，注入 dashboardId / groupId 等上下文信息。
     */
    function getTransformPanel(panel: IPanelModel) {
      const item = new PanelModel({
        ...panel,
        dashboardId: props.id,
        panelIds: panel?.panels?.map(item => item.id) || [],
      });
      return item;
    }

    /**
     * @description:初始化 dashboard 转换为 panelModel 并重新计算各个视图位置大小
     * @param {IPanelModel} panels
     * @return {*}
     */
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
          // 是否组
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

    /**
     * @description: 选中图表触发事件
     * @param {boolean} check 是否选中
     * @param {PanelModel} panel 图表panel model
     * @return {*}
     */
    function handleChartCheck(check: boolean, panel: PanelModel) {
      panel.updateChecked(check);
    }

    /** matchDisplay（过滤字段）控制每个 panel 是否展示。 */
    function getPanelDisplay(panel: PanelModel) {
      if (!panel.show) return 'none';
      if (panel.matchDisplay && props.matchFields) {
        return Object.keys(panel.matchDisplay).every(key => props.matchFields[key] === panel.matchDisplay[key])
          ? 'flex'
          : 'none';
      }
      return 'flex';
    }

    /**
     * 分组时开闭设置
     */
    function handleCollapse(collapse: boolean, panel: PanelModel) {
      panel.updateCollapsed(collapse);
      panel.panels?.forEach(item => {
        const panel = localPanels.value.find(set => set.id === item.id);
        panel?.updateShow(collapse);
      });
    }
    // 子图加载成功时，向父组件抛出事件，用于刷新/打点。
    const handleSuccessLoad = () => {
      emit('successLoad');
    };

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
                    isAlarmView={props.isAlarmView}
                    panel={singleChartPanel.value}
                  />
                </div>
              </div>
            </div>
          ) : (
            [
              // 按行分片渲染
              <VirtualRender
                height={virtualHeight.value}
                auto-reset={true}
                group-count={6}
                lineHeight={284}
                list={virtualRows.value}
              >
                {{
                  default: ({ data }: { data: PanelRow[] }) => (
                    <div
                      key='flex-dashboard'
                      style={{ height: virtualHeight.value }}
                      class='flex-dashboard'
                    >
                      {data.map(row => (
                        <div
                          key={row.key}
                          class='flex-dashboard-row'
                        >
                          {row.panels.map(panel => (
                            <div
                              id={`${panel.id}__key__`}
                              key={`${panel.id}__key__`}
                              style={{
                                // 按列数平均分配宽度，并留出列间距 16px。
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
                            >
                              <ChartWrapper
                                key={`${panel.id}__key__`}
                                groupId={props.id}
                                isAlarmView={props.isAlarmView}
                                panel={panel}
                                onChartCheck={v => handleChartCheck(v, panel)}
                                onCollapse={v => panel.type === 'row' && handleCollapse(v, panel)}
                                onSuccessLoad={handleSuccessLoad}
                              />
                            </div>
                          ))}
                        </div>
                      ))}
                    </div>
                  ),
                }}
              </VirtualRender>,
            ]
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
