/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community Edition):
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
import { computed, ComputedRef, defineComponent, PropType, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { Popover } from 'bkui-vue';
import { fetchItemStatus } from 'monitor-api/modules/strategies';

import { createMetricTitleTooltips } from '../../utils';
import {
  ChartTitleMenuType,
  IChartTitleMenuEvents,
  IExtendMetricData,
  IMenuChildItem,
  IMenuItem,
  ITitleAlarm
} from '../typings';

import TitleMenu from './title-menu';

import './chart-title.scss';

export default defineComponent({
  name: 'ChartTitle',
  props: {
    title: String,
    subtitle: String,
    metrics: {
      type: Array as PropType<IExtendMetricData[]>,
      default: () => []
    },
    collectInterval: {
      type: String,
      default: '0'
    },
    showMore: Boolean,
    draging: Boolean,
    isInstant: Boolean,
    showAddMetric: {
      type: Boolean,
      default: true
    },
    menuList: {
      type: Array as PropType<ChartTitleMenuType[]>,
      default: () => []
    },
    drillDownOption: {
      type: Array as PropType<IMenuChildItem[]>,
      default: () => []
    }
  },
  emits: ['updateDragging', 'menuClick', 'selectChild', 'metricClick', 'allMetricClick', 'alarmClick'],
  setup(props, { emit }) {
    const chartTitleRef = ref<HTMLDivElement>();
    const showMenu = ref(false);
    const menuLeft = ref(0);
    const popoverInstance = ref(null);
    const alarmStatus = ref<ITitleAlarm>({ status: 0, alert_number: 0, strategy_number: 0 });
    const isShowChildren = ref(false);
    const { t } = useI18n();
    const alarmTips = computed(() => {
      const { status, alert_number, strategy_number } = alarmStatus.value;
      let content = '';
      switch (status) {
        case 1:
          content = t('已设置 {0} 个策略', [strategy_number]).toString();
          break;
        case 2:
          content = t('告警中，告警数量：{0}', [alert_number]).toString();
          break;
        default:
        case 0:
          content = t('未配置策略').toString();
          break;
      }
      return {
        content,
        showOnInit: false,
        trigger: 'mouseenter',
        placements: ['top']
      };
    });
    const showMetricAlarm = computed(() => props.metrics?.length === 1);
    const metricTitleData: ComputedRef<IExtendMetricData> = computed<IExtendMetricData>(() => props.metrics[0]);
    watch(
      () => props.metrics,
      async (v, o) => {
        if (props.metrics?.length !== 1) return;
        const id = props.metrics[0].metric_id || `${props.metrics[0].result_table_id}.${props.metrics[0].metric_field}`;
        const oldId = o?.length ? o[0].metric_id || `${o[0].result_table_id}.${o[0].metric_field}` : '';
        if (id === oldId) return;
        const data = await fetchItemStatus({ metric_ids: [id] }).catch(() => ({ [id]: 0 }));
        alarmStatus.value = data?.[id];
      },
      { immediate: true }
    );
    function handleShowMenu(e: any) {
      if (!props.draging) {
        if (!props.showMore) return;
        showMenu.value = !showMenu.value;
        const rect = chartTitleRef.value?.getBoundingClientRect();
        if (typeof rect !== 'undefined') {
          menuLeft.value = rect.width - 185 < e.layerX ? rect.width - 185 : e.layerX;
        }
      }
      emit('updateDragging', false);
    }
    function handleMenuClick(item: IMenuItem) {
      item.checked = !item.checked;
      emit('menuClick', item);
      isShowChildren.value = false;
      showMenu.value = false;
    }
    function handleMenuChildClick(data: IChartTitleMenuEvents['onSelectChild']) {
      emit('selectChild', data);
    }
    function handleMetricSelect(metric: IExtendMetricData) {
      emit('metricClick', metric);
    }
    function handleAllMetricSelect(e: Event) {
      e.stopPropagation();
      emit('allMetricClick');
    }

    function handleAlarmClick(e: MouseEvent) {
      e.stopPropagation();
      emit('alarmClick', alarmStatus.value);
    }
    function handleShowTips(e: MouseEvent) {
      if (metricTitleData.value) {
        e.stopPropagation();
        if (e.target !== e.currentTarget) return;
        // this.popoverInstance = this.$bkPopover(e.target, {
        //   content: createMetricTitleTooltips(this.metricTitleData),
        //   trigger: 'manual',
        //   theme: 'tippy-metric',
        //   arrow: true,
        //   placement: 'auto',
        //   boundary: 'window'
        // });
        // this.popoverInstance?.show(100);
      }
    }
    function handleHideTips(e: MouseEvent) {
      e.stopPropagation();
      if (e.target !== e.currentTarget) return;
      // this.popoverInstance?.hide(0);
      // this.popoverInstance?.destroy();
      // this.popoverInstance = null;
    }
    function handleTitleBlur() {
      setTimeout(() => {
        if (!isShowChildren.value) {
          showMenu.value = false;
          isShowChildren.value = false;
        }
      }, 200);
    }
    function handleShowChildren() {
      isShowChildren.value = true;
    }
    function handleChildMenuToggle(val: boolean) {
      if (!val) {
        showMenu.value = false;
        isShowChildren.value = false;
      }
    }
    return {
      chartTitleRef,
      showMenu,
      menuLeft,
      popoverInstance,
      alarmStatus,
      isShowChildren,
      alarmTips,
      showMetricAlarm,
      metricTitleData,
      handleShowMenu,
      handleMenuClick,
      handleMenuChildClick,
      handleMetricSelect,
      handleAllMetricSelect,
      handleAlarmClick,
      handleShowTips,
      handleHideTips,
      handleTitleBlur,
      handleShowChildren,
      handleChildMenuToggle
    };
  },
  render() {
    return (
      <div class='title-wrapper'>
        <div
          ref='chartTitleRef'
          class='chart-title'
          tabindex={-1}
          onBlur={this.handleTitleBlur}
          onClick={this.handleShowMenu}
        >
          <div class='main-title'>
            {this.showMetricAlarm ? (
              <Popover
                key={this.alarmTips.content}
                content={this.alarmTips.content}
              >
                <i
                  class={`icon-monitor icon-mc-chart-alert alarm-icon icon-btn status-${this.alarmStatus.status + 1}`}
                  onClick={this.handleAlarmClick}
                />
              </Popover>
            ) : undefined}
            <div class={['title-name', { 'has-more': this.showMore }]}>{this.title}</div>
            {this.showMetricAlarm && this.metricTitleData?.collect_interval ? (
              <Popover content={this.$t('数据步长')}>
                <span class='title-interval'>{this.metricTitleData.collect_interval}m</span>
              </Popover>
            ) : undefined}
            {this.showMetricAlarm && this.metricTitleData ? (
              <Popover
                v-slots={{
                  default: () => (
                    <i
                      class='icon-monitor icon-hint tips-icon'
                      style={{ display: this.showMore ? 'flex' : 'none' }}
                    />
                  ),
                  content: () => (
                    <div
                      class='common-chart-tooltips-wrap'
                      v-html={createMetricTitleTooltips(this.metricTitleData)}
                    ></div>
                  )
                }}
              ></Popover>
            ) : undefined}
            <span class='title-center'></span>
            {this.showMetricAlarm && this.metricTitleData ? (
              <Popover content={this.$t('添加策略')}>
                <i
                  class='icon-monitor icon-mc-add-strategy strategy-icon icon-btn'
                  style={{
                    display: this.showMore && this.showAddMetric ? 'flex' : 'none'
                  }}
                  onClick={this.handleAllMetricSelect}
                ></i>
              </Popover>
            ) : undefined}
            {
              <Popover content={this.$t('更多')}>
                <span
                  style={{
                    marginLeft: this.metricTitleData && this.showAddMetric ? '0' : 'auto',
                    display: this.showMore ? 'flex' : 'none'
                  }}
                  tabindex='undefined'
                  class='icon-monitor icon-mc-more more-icon icon-btn'
                />
              </Popover>
            }
          </div>
          {this.subtitle && <div class='sub-title'>{this.subtitle}</div>}
        </div>
        <TitleMenu
          list={this.menuList}
          drillDownOption={this.drillDownOption}
          onSelect={this.handleMenuClick}
          onMetricSelect={this.handleMetricSelect}
          onChildMenuToggle={this.handleChildMenuToggle}
          metrics={this.metrics}
          showAddMetric={this.showAddMetric}
          style={{
            left: `${this.menuLeft}px`,
            top: '36px',
            display: this.showMenu ? 'flex' : 'none'
          }}
          onSelectChild={this.handleMenuChildClick}
        ></TitleMenu>
      </div>
    );
  }
});
