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
import { Component, Emit, InjectReactive, Prop, Ref, Watch } from 'vue-property-decorator';
import { modifiers, Component as tsc } from 'vue-tsx-support';

import { fetchItemStatus } from 'monitor-api/modules/strategies';

import { createMetricTitleTooltips, deduplicateByField, fitPosition } from '../../utils';
import { VariablesService } from '../../utils/variable';
import ChartMenu, { type IChartTitleMenuEvents } from './chart-title-menu';

import type {
  ChartTitleMenuType,
  CurrentTargetType,
  IExtendMetricData,
  IMenuChildItem,
  IMenuItem,
  ITitleAlarm,
  IViewOptions,
} from '../../typings';

import './chart-title.scss';

enum AlarmStatus {
  /** 已经配置策略 */
  already_config_strategy = 1,
  /** 没有配置策略 */
  not_confit_strategy = 0,
  /** 告警中 */
  on_warning = 2,
}

export interface IChartTitleProps {
  // 告警信息
  alarm?: ITitleAlarm;
  // 采集周期
  collectInterval?: string;
  // 数据步长（步长过大情况时需要）
  collectIntervalDisplay?: string;
  /** 修改掉菜单的点击区域, 为true时 菜单区域仅为icon区域 */
  customArea?: boolean;
  // 带icon说明
  description?: string;
  dragging?: boolean;
  /** 下钻类型 */
  drillDownOption?: IMenuChildItem[];
  initialized?: boolean;
  /** title的内容是否需要hover才展示 */
  isHoverShow?: boolean;
  // 是否实时
  isInstant?: boolean;
  // 可设置图标的功能的id列表
  menuList?: ChartTitleMenuType[];
  // 指标数据
  metrics?: IExtendMetricData[];
  // 是否展示更多菜单
  needMoreMenu?: boolean;
  rawInterval?: string;
  // 是否显示添加指标到策略选项
  showAddMetric?: boolean;
  // 下拉中是否显示添加指标到策略选项
  showMenuAddMetric?: boolean;
  // 是否显示更多图标
  showMore?: boolean;
  /** 是否展示title的各个icon */
  showTitleIcon?: boolean;
  // 副标题
  subtitle?: string;
  // 主标题
  title: string;
}

interface IChartTitleEvent {
  onAlarmClick: ITitleAlarm;
  onMenuClick: IMenuItem;
  onMetricClick: IExtendMetricData;
  onSelectChild: IChartTitleMenuEvents['onSelectChild'];
  onUpdateDragging: boolean;
  onAllMetricClick: () => void;
}

@Component
export default class ChartTitle extends tsc<
  IChartTitleProps,
  IChartTitleEvent,
  {
    customSlot: string;
    iconList: string;
    subTitle: string;
    title: string;
  }
> {
  @Prop({ default: '' }) title: string;
  @Prop({ default: '' }) subtitle: string;
  @Prop({ default: '' }) description: string;
  @Prop({ default: () => [] }) metrics: IExtendMetricData[];
  @Prop({ default: '0' }) collectInterval: string;
  @Prop({ default: false }) showMore: boolean;
  @Prop({ default: true }) needMoreMenu: boolean;
  @Prop({ default: false }) customArea: boolean;
  @Prop() menuList: ChartTitleMenuType[];
  @Prop({ default: () => [] }) drillDownOption: IMenuChildItem[];
  @Prop() dragging: boolean;
  @Prop({ type: Boolean, default: true }) showMenuAddMetric: boolean;
  @Prop({ type: Boolean, default: true }) showAddMetric: boolean;
  @Prop({ type: Boolean, default: true }) showTitleIcon: boolean;
  @Prop({ type: Boolean, default: false }) isInstant: boolean;
  @Prop({ type: Boolean, default: true }) initialized: boolean;
  @Prop({ type: String, default: '' }) collectIntervalDisplay: string;
  /** title的内容是否需要hover才展示 */
  @Prop({ type: Boolean, default: false }) isHoverShow: boolean;

  @Ref('chartTitle') chartTitleRef: HTMLDivElement;
  // 是否只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  // 图表特殊参数
  @InjectReactive('viewOptions') readonly viewOptions!: IViewOptions;
  // 图表的告警状态接口是否需要加入$current_target作为请求参数
  @InjectReactive('alertFilterable') readonly alertFilterable!: boolean;

  private showMenu = false;
  private menuLeft = 0;
  private popoverInstance = null;
  private alarmStatus: ITitleAlarm = { status: 0, alert_number: 0, strategy_number: 0 };
  private isShowChildren = false;
  private allowUpdateStatus = false;
  private eventSearchStr = '';
  get alarmTips() {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { status, alert_number, strategy_number } = this.alarmStatus;
    let content = '';
    switch (status) {
      case AlarmStatus.already_config_strategy:
        content = window.i18n.t('已设置 {0} 个策略', [strategy_number]).toString();
        break;
      case AlarmStatus.on_warning:
        content = window.i18n.t('告警中，告警数量：{0}', [alert_number]).toString();
        break;
      default:
        content = window.i18n.t('未配置策略').toString();
        break;
    }
    return {
      content,
      showOnInit: false,
      trigger: 'mouseenter',
      placements: ['top'],
      allowHTML: false,
    };
  }
  /** aiops title高度不一致，需要特殊向上偏移 */
  get menuPosition() {
    return !this.showTitleIcon ? { top: '32px' } : {};
  }
  get showMetricAlarm() {
    const metrics = new Set(this.metrics?.map(item => item.metric_id) || []);
    return !this.readonly && Array.from(metrics).length === 1;
  }
  get metricTitleData() {
    return this.metrics[0];
  }

  get metricTitleTooltips() {
    return this.showMetricAlarm
      ? createMetricTitleTooltips(this.metricTitleData)
      : deduplicateByField(this.metrics, 'metric_id')
          .map(metric => createMetricTitleTooltips(metric))
          .join('<hr class="custom-hr" />');
  }

  get currentMetricsIds() {
    return this.metrics[0].metric_id || `${this.metrics[0].result_table_id}.${this.metrics[0].metric_field}`;
  }
  get showAddStrategy() {
    return !this.$route.name.includes('strategy');
  }
  get isMac() {
    return /Macintosh|Mac/.test(navigator.userAgent);
  }
  @Watch('metrics', { immediate: true })
  async handleMetricChange(v, o) {
    if (this.metrics?.length !== 1) return;
    const oldId = o?.length ? o[0].metric_id || `${o[0].result_table_id}.${o[0].metric_field}` : '';
    if (this.currentMetricsIds === oldId) return;
    !this.readonly && this.handleFetchItemStatus();
    this.allowUpdateStatus = true;
  }

  @Watch('viewOptions.current_target', { deep: true })
  currentTargetChange() {
    !this.readonly &&
      this.initialized &&
      this.allowUpdateStatus &&
      this.alertFilterable &&
      this.handleFetchItemStatus();
  }

  /**
   * 获取告警数据
   * @param ids 指标ids
   */
  async handleFetchItemStatus(ids: string = this.currentMetricsIds) {
    /** 需要额外参数的情况 */
    let otherParams: Record<string, any> = {};
    this.eventSearchStr = '';
    if (this.alertFilterable) {
      const variablesService = new VariablesService(this.viewOptions);
      otherParams = variablesService.transformVariables({ target: '$current_target' }) || {};
      this.eventSearchStr = this.handleEventSearchString(otherParams.target as CurrentTargetType);
    }
    const params = {
      metric_ids: [ids],
      ...otherParams,
      bk_biz_id: this.viewOptions?.filters?.bk_biz_id || this.$store.getters.bizId,
    };
    const data = await fetchItemStatus(params).catch(() => ({ [ids]: 0 }));
    this.alarmStatus = data?.[ids];
  }

  /**
   * 处理跳转事件中心的精确目标的搜索条件
   * @param target
   * @returns
   */
  handleEventSearchString(target: CurrentTargetType): string {
    let str = '';
    if (target?.bk_inst_id) {
      str = `bk_service_instance_id : ${target.bk_inst_id}`;
    } else if (target?.bk_target_ip) {
      str = `ip: ${target.bk_target_ip} AND bk_cloud_id : ${target.bk_target_cloud_id}`;
    }
    return str;
  }

  handleShowMenu(area: string, e: any) {
    // /** 如果自定义区域在菜单时需要阻止冒泡 */
    if (area !== 'all') {
      e.stopPropagation();
      e.preventDefault();
    }
    if ((this.customArea && area === 'all') || (!this.customArea && area !== 'all')) {
      this.showMenu = false;
      return;
    }

    if (!this.dragging) {
      if (!this.showMore) return;
      this.showMenu = !this.showMenu;
      const rect = this.chartTitleRef.getBoundingClientRect();
      const { innerWidth } = window;
      // 自身宽度 + 距离右侧浏览器窗口宽度（innerWidth - rect.right）
      const rightWidth = 180 + innerWidth - rect.right;
      const position = fitPosition(
        {
          left: e.x,
          top: e.y,
        },
        rightWidth
      );
      this.menuLeft = position.left - rect.x;
    }
    this.$emit('updateDragging', false);
  }
  handleMenuClick(item: IMenuItem) {
    item.checked = !item.checked;
    this.$emit('menuClick', item);
    this.isShowChildren = false;
    this.showMenu = false;
    // this.handleTitleBlur();
  }
  /**
   * 点击下来菜单的子选项
   */
  @Emit('selectChild')
  handleMenuChildClick(data: IChartTitleMenuEvents['onSelectChild']) {
    this.showMenu = false;
    return data;
  }
  handleMetricSelect(metric: IExtendMetricData) {
    this.$emit('metricClick', metric);
  }
  handleAllMetricSelect(e: Event) {
    e.stopPropagation();
    this.$emit('allMetricClick');
  }
  @Emit('alarmClick')
  handleAlarmClick() {
    return {
      ...this.alarmStatus,
      targetStr: this.eventSearchStr,
    };
  }
  handleShowTips(e: MouseEvent) {
    if (this.metricTitleData) {
      e.stopPropagation();
      if (e.target !== e.currentTarget) return;
      this.popoverInstance = this.$bkPopover(e.target, {
        content: this.metricTitleTooltips,
        trigger: 'manual',
        theme: 'tippy-metric',
        arrow: true,
        placement: 'auto',
        boundary: 'window',
      });
      this.popoverInstance?.show(100);
    }
  }
  handleHideTips(e: MouseEvent) {
    e.stopPropagation();
    if (e.target !== e.currentTarget) return;
    this.popoverInstance?.hide(0);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
  }
  handleTitleBlur() {
    setTimeout(() => {
      if (!this.isShowChildren) {
        this.showMenu = false;
        this.isShowChildren = false;
      }
    }, 200);
  }
  handleShowChildren() {
    this.isShowChildren = true;
  }

  handleChildMenuToggle(val: boolean) {
    if (!val) {
      this.showMenu = false;
      this.isShowChildren = false;
    }
  }

  render() {
    return (
      <div class='title-wrapper'>
        <div
          ref='chartTitle'
          class='chart-title'
          tabindex={-1}
          onBlur={this.handleTitleBlur}
          onClick={this.handleShowMenu.bind(this, 'all')}
        >
          <div class='main-title'>
            {this.showMetricAlarm && this.showTitleIcon ? (
              <i
                class={[
                  'icon-monitor',
                  'alarm-icon',
                  'icon-btn',
                  this.alarmStatus.status === AlarmStatus.already_config_strategy && 'icon-mc-strategy status-strategy',
                  this.alarmStatus.status === AlarmStatus.not_confit_strategy &&
                    'icon-mc-strategy status-strategy-not-config',
                  this.alarmStatus.status === AlarmStatus.on_warning && 'icon-mc-chart-alert status-3',
                ]}
                v-bk-tooltips={this.alarmTips}
                onClick={modifiers.stop(this.handleAlarmClick)}
              />
            ) : undefined}
            <div
              style={{ fontWeight: this.isMac ? 500 : 600 }}
              class={['title-name', { 'has-more': this.showMore }]}
              v-bk-overflow-tips={{
                interactive: this.showTitleIcon,
                onShow: () => {
                  return !this.$scopedSlots?.title;
                },
              }}
            >
              {this.$scopedSlots?.title ? this.$scopedSlots?.title?.('') : this.title}
            </div>
            {this.initialized && [
              (this.showTitleIcon && this.showMetricAlarm && this.metricTitleData?.collect_interval) ||
              this.collectIntervalDisplay ? (
                <span
                  key='title-interval'
                  class='title-interval'
                  v-bk-tooltips={{
                    content: this.$t('数据步长'),
                    delay: 200,
                    appendTo: () => document.body,
                  }}
                >
                  {this.collectIntervalDisplay
                    ? this.collectIntervalDisplay
                    : `${this.metricTitleData.collect_interval}${this.metricTitleData.collect_interval < 10 ? 'm' : 's'}`}
                </span>
              ) : undefined,
              this.$scopedSlots?.customSlot?.(''),
              this.showTitleIcon && this.metrics.length ? (
                <i
                  key={'custom-icon'}
                  style={{ display: this.showMore ? 'flex' : 'none' }}
                  class='bk-icon icon-info-circle tips-icon'
                  onMouseenter={this.handleShowTips}
                  onMouseleave={this.handleHideTips}
                />
              ) : undefined,
              this.description && (
                <i
                  class='bk-icon icon-info-circle tips-icon'
                  v-bk-tooltips={{
                    content: this.description,
                    allowHTML: true,
                    boundary: 'window',
                    distance: 0,
                    placements: ['top'],
                  }}
                />
              ),
              <span
                key={'title-center'}
                class={['title-center', { 'hover-show': this.isHoverShow }]}
              >
                {this.initialized && this.$slots?.default}
              </span>,
              <span
                key={'title-icon-list'}
                class='title-icon-list'
              >
                {this.$scopedSlots.iconList?.('')}
              </span>,
              this.showAddStrategy && this.showTitleIcon && this.showMetricAlarm && this.metricTitleData ? (
                <i
                  key={'添加策略'}
                  style={{
                    display: this.showMore && this.showAddMetric ? 'flex' : 'none',
                  }}
                  class={[
                    'icon-monitor icon-mc-add-strategy strategy-icon icon-btn',
                    // { 'hover-show': this.isHoverShow },
                  ]}
                  v-bk-tooltips={{
                    content: this.$t('添加策略'),
                    delay: 200,
                  }}
                  onClick={this.handleAllMetricSelect}
                />
              ) : undefined,
              <span
                key={'更多'}
                style={{
                  marginLeft: this.isHoverShow ? 0 : this.metricTitleData && this.showAddMetric ? '0' : 'auto',
                  display: this.showMore && this.needMoreMenu ? 'flex' : 'none',
                }}
                class='icon-monitor icon-mc-more more-icon icon-btn'
                v-bk-tooltips={{
                  content: this.$t('更多'),
                  interactive: false,
                }}
                tabindex='0'
                onClick={this.customArea ? this.handleShowMenu.bind(this, 'customArea') : () => {}}
              />,
            ]}
          </div>
          {this.subtitle && <div class='sub-title'>{this.$scopedSlots?.subTitle?.('') || this.subtitle}</div>}
        </div>
        <ChartMenu
          style={{
            left: `${this.menuLeft}px`,
            display: this.needMoreMenu && this.showMenu ? 'flex' : 'none',
            ...this.menuPosition,
          }}
          drillDownOption={this.drillDownOption}
          list={this.menuList}
          metrics={this.metrics}
          showAddMetric={this.showAddMetric && this.showMenuAddMetric}
          showMenu={this.showMenu}
          onChildMenuToggle={this.handleChildMenuToggle}
          onMetricSelect={this.handleMetricSelect}
          onSelect={this.handleMenuClick}
          onSelectChild={this.handleMenuChildClick}
          onShowChildren={this.handleShowChildren}
        />
      </div>
    );
  }
}
