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
import { type PropType, computed, defineComponent, onBeforeUnmount, onMounted, provide, ref, toRef, watch } from 'vue';

import { random } from 'monitor-common/utils/utils';
import { type DashboardColumnType, type IPanelModel, PanelModel } from 'monitor-ui/chart-plugins/typings';
import { echarts } from 'monitor-ui/monitor-echarts/types/monitor-echarts';
import { useI18n } from 'vue-i18n';

import ChartWrapper from './chart-wrapper';

import type { SceneType } from 'monitor-pc/pages/monitor-k8s/typings';

import './dashboard-panel.scss';
/** 接收图表当前页面跳转事件 */
export const UPDATE_SCENES_TAB_DATA = 'UPDATE_SCENES_TAB_DATA';

export default defineComponent({
  name: 'FlexDashboardPanelMigrated',
  props: {
    // 视图集合
    panels: { required: false, type: Array as PropType<IPanelModel[]> },
    // dashboard id
    id: { required: true, type: String },
    // 自动展示初始化列数
    column: { default: 'custom', type: [String, Number] as PropType<DashboardColumnType> },
    // 注意：这里还需要提供 provide 。
    isSplitPanel: { default: false, type: Boolean },
    // 是否为单图模式
    isSingleChart: { default: false, type: Boolean },
    // 是否需要返回概览按钮 isSingleChart: true生效
    needOverviewBtn: { type: Boolean, default: false },
    // 返回概览 或者 详情页面
    backToType: { default: () => '', type: String as PropType<SceneType> },
    dashboardId: { type: String, default: '' },
    matchFields: { default: () => {}, type: Object },
    /** 自定义高度 */
    customHeightFn: { type: [Function, null], default: null },
    /** 是否显示告警视图图表 */
    isAlarmView: { type: Boolean, default: false },
  },
  emits: ['linkTo', 'lintToDetail', 'backToOverview', 'successLoad'],
  setup(props, { emit }) {
    const { t } = useI18n();
    provide('isSplitPanel', toRef(props, 'isSplitPanel'));
    // 视图实例集合
    const localPanels = ref<PanelModel[]>([]);

    const singleChartPanel = computed(() => {
      const panels = props.panels.filter(item => (item.type === 'row' ? !!item.panels?.length : true));
      return new PanelModel(panels[0]?.type === 'row' ? panels[0]?.panels?.[0] : panels[0]);
    });

    watch(
      () => props.panels,
      () => {
        if (!props.panels) return;
        handleInitPanelsGridPosition(props.panels);
        localPanels.value = handleInitLocalPanels(props.panels);
      },
      {
        immediate: true,
      }
    );

    watch(
      () => props.column,
      () => {
        echarts.disconnect(props.id.toString());
        handleInitPanelsGridPosition(localPanels.value);
        handleConnectEcharts();
      }
    );

    onMounted(() => {
      // 等待所以子视图实例创建完进行视图示例的关联 暂定5000ms 后期进行精细化配置
      handleConnectEcharts();
    });

    onBeforeUnmount(() => {
      echarts.disconnect(props.id.toString());
    });

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
     * @description: 分组时开闭设置
     * @param {boolean} collapse
     * @param {PanelModel} panel
     * @return {*}
     */
    function handleCollapse(collapse: boolean, panel: PanelModel) {
      panel.updateCollapsed(collapse);
      panel.panels?.forEach(item => {
        const panel = localPanels.value.find(set => set.id === item.id);
        panel?.updateShow(collapse);
      });
    }
    const handleSuccessLoad = () => {
      emit('successLoad');
    };

    function renderFn() {
      if (!props.panels?.length) return <div class='dashboard-panel empty-data'>{t('查无数据')}</div>;
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
              <div
                key='flex-dashboard'
                class='flex-dashboard'
              >
                {localPanels.value.map(panel => (
                  <div
                    id={`${panel.id}__key__`}
                    key={`${panel.id}__key__`}
                    style={{
                      width: `calc(${(1 / +props.column) * 100}% - 16px)`,
                      maxWidth: `calc(${(1 / +props.column) * 100}% - 16px)`,
                      flex: `${(1 / +props.column) * 100}%`,
                      display: getPanelDisplay(panel),
                      height: ['related-log-chart', 'exception-guide'].includes(panel.type) && 'calc(100vh - 240px)',
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
              </div>,
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
