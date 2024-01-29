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
import { Component as tsc, modifiers } from 'vue-tsx-support';

import { fetchItemStatus } from '../../../../monitor-api/modules/strategies';
import {
  ChartTitleMenuType,
  CurrentTargetType,
  IExtendMetricData,
  IMenuChildItem,
  IMenuItem,
  ITitleAlarm,
  IViewOptions
} from '../../typings';
import { createMetricTitleTooltips } from '../../utils';
import { VariablesService } from '../../utils/variable';

import ChartMenu, { IChartTitleMenuEvents } from './chart-title-menu';

import './chart-title.scss';

export interface IChartTitleProps {
  // 主标题
  title: string;
  // 副标题
  subtitle?: string;
  // 带icon说明
  descrition?: string;
  // 告警信息
  alarm?: ITitleAlarm;
  // 采集周期
  collectInterval?: string;
  // 是否显示更多图标
  showMore?: boolean;
  // 可设置图标的功能的id列表
  menuList?: ChartTitleMenuType[];
  draging?: boolean;
  // 指标数据
  metrics?: IExtendMetricData[];
  // 是否显示添加指标到策略选项
  showAddMetric?: boolean;
  /** 是否展示title的各个icon */
  showTitleIcon?: boolean;
  // 下拉中是否显示添加指标到策略选项
  showMenuAddMetric?: boolean;
  // 是否实时
  isInstant?: boolean;
  /** 下钻类型 */
  drillDownOption?: IMenuChildItem[];
  inited?: boolean;
  /** 修改掉菜单的点击区域, 为true时 菜单区域仅为icon区域 */
  customArea?: boolean;
}

interface IChartTitleEvent {
  onMenuClick: IMenuItem;
  onSelectChild: IChartTitleMenuEvents['onSelectChild'];
  onAlarmClick: ITitleAlarm;
  onUpdateDragging: boolean;
  onMetricClick: IExtendMetricData;
  onAllMetricClick: () => void;
}

enum AlarmStatus {
  /** 没有配置策略 */
  not_confit_strategy = 0,
  /** 已经配置策略 */
  already_config_strategy = 1,
  /** 告警中 */
  on_warning = 2
}

@Component
export default class ChartTitle extends tsc<IChartTitleProps, IChartTitleEvent> {
  @Prop({ default: '' }) title: string;
  @Prop({ default: '' }) subtitle: string;
  @Prop({ default: '' }) descrition: string;
  @Prop({ default: () => [] }) metrics: IExtendMetricData[];
  @Prop({ default: '0' }) collectInterval: string;
  @Prop({ default: false }) showMore: boolean;
  @Prop({ default: false }) customArea: boolean;
  @Prop() menuList: ChartTitleMenuType[];
  @Prop({ default: () => [] }) drillDownOption: IMenuChildItem[];
  @Prop() draging: boolean;
  @Prop({ type: Boolean, default: true }) showMenuAddMetric: boolean;
  @Prop({ type: Boolean, default: true }) showAddMetric: boolean;
  @Prop({ type: Boolean, default: true }) showTitleIcon: boolean;
  @Prop({ type: Boolean, default: false }) isInstant: boolean;
  @Prop({ type: Boolean, default: true }) inited: boolean;

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
      case AlarmStatus.not_confit_strategy:
        content = window.i18n.t('未配置策略').toString();
        break;
    }
    return {
      content,
      showOnInit: false,
      trigger: 'mouseenter',
      placements: ['top'],
      allowHTML: false
    };
  }
  /** aiops title高度不一致，需要特殊向上偏移 */
  get menuPosition() {
    return !this.showTitleIcon ? { top: '32px' } : {};
  }
  get showMetricAlarm() {
    return !this.readonly && this.metrics?.length === 1;
  }
  get metricTitleData() {
    return this.metrics[0];
  }

  get currentMetricsIds() {
    return this.metrics[0].metric_id || `${this.metrics[0].result_table_id}.${this.metrics[0].metric_field}`;
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
    !this.readonly && this.inited && this.allowUpdateStatus && this.alertFilterable && this.handleFetchItemStatus();
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
      bk_biz_id: this.viewOptions.filters?.bk_biz_id || this.$store.getters.bizId
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

    if (!this.draging) {
      if (!this.showMore) return;
      this.showMenu = !this.showMenu;
      const rect = this.chartTitleRef.getBoundingClientRect();
      this.menuLeft = rect.width - 185 < e.layerX ? rect.width - 185 : e.layerX;
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
      targetStr: this.eventSearchStr
    };
  }
  handleShowTips(e: MouseEvent) {
    if (this.metricTitleData) {
      e.stopPropagation();
      if (e.target !== e.currentTarget) return;
      this.popoverInstance = this.$bkPopover(e.target, {
        content: createMetricTitleTooltips(this.metricTitleData),
        trigger: 'manual',
        theme: 'tippy-metric',
        arrow: true,
        placement: 'auto',
        boundary: 'window'
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
                v-bk-tooltips={this.alarmTips}
                class={[
                  'icon-monitor',
                  'alarm-icon',
                  'icon-btn',
                  this.alarmStatus.status === AlarmStatus.already_config_strategy && 'icon-mc-strategy status-strategy',
                  this.alarmStatus.status === AlarmStatus.not_confit_strategy &&
                    'icon-mc-strategy status-strategy-not-config',
                  this.alarmStatus.status === AlarmStatus.on_warning && 'icon-mc-chart-alert status-3'
                ]}
                onClick={modifiers.stop(this.handleAlarmClick)}
              />
            ) : undefined}
            <div
              class={['title-name', { 'has-more': this.showMore }]}
              v-bk-overflow-tips={{
                interactive: this.showTitleIcon
              }}
            >
              {this.title}
            </div>
            {this.inited && [
              this.showTitleIcon && this.showMetricAlarm && this.metricTitleData?.collect_interval ? (
                <span
                  class='title-interval'
                  v-bk-tooltips={{
                    content: this.$t('数据步长'),
                    delay: 200,
                    appendTo: 'parent'
                  }}
                >
                  {this.metricTitleData.collect_interval}
                  {this.metricTitleData.collect_interval < 10 ? 'm' : 's'}
                </span>
              ) : undefined,
              (this.$scopedSlots as any)?.customSlot?.(),
              this.showTitleIcon && this.showMetricAlarm && this.metricTitleData ? (
                <i
                  class='bk-icon icon-info-circle tips-icon'
                  style={{ display: this.showMore ? 'flex' : 'none' }}
                  onMouseenter={this.handleShowTips}
                  onMouseleave={this.handleHideTips}
                />
              ) : undefined,
              this.descrition && (
                <i
                  class='bk-icon icon-info-circle tips-icon'
                  v-bk-tooltips={{
                    content: this.descrition,
                    allowHTML: true,
                    boundary: 'window',
                    distance: 0,
                    placements: ['top']
                  }}
                />
              ),
              <span class='title-center'></span>,
              this.showTitleIcon && this.showMetricAlarm && this.metricTitleData ? (
                <i
                  class='icon-monitor icon-mc-add-strategy strategy-icon icon-btn'
                  style={{
                    display: this.showMore && this.showAddMetric ? 'flex' : 'none'
                  }}
                  v-bk-tooltips={{
                    content: this.$t('添加策略'),
                    delay: 200
                  }}
                  onClick={this.handleAllMetricSelect}
                ></i>
              ) : undefined,
              <span
                onClick={this.customArea ? this.handleShowMenu.bind(this, 'customArea') : () => {}}
                style={{
                  marginLeft: this.metricTitleData && this.showAddMetric ? '0' : 'auto',
                  display: this.showMore ? 'flex' : 'none'
                }}
                v-bk-tooltips={{
                  content: this.$t('更多'),
                  delay: 200
                }}
                tabindex='undefined'
                class='icon-monitor icon-mc-more more-icon icon-btn'
              />
            ]}
          </div>
          {this.subtitle && <div class='sub-title'>{(this.$scopedSlots as any)?.subTitle?.() || this.subtitle}</div>}
        </div>
        <ChartMenu
          list={this.menuList}
          drillDownOption={this.drillDownOption}
          onShowChildren={this.handleShowChildren}
          onSelect={this.handleMenuClick}
          onMetricSelect={this.handleMetricSelect}
          onChildMenuToggle={this.handleChildMenuToggle}
          metrics={this.metrics}
          showAddMetric={this.showAddMetric && this.showMenuAddMetric}
          style={{
            left: `${this.menuLeft}px`,
            display: this.showMenu ? 'flex' : 'none',
            ...this.menuPosition
          }}
          onSelectChild={this.handleMenuChildClick}
        ></ChartMenu>
      </div>
    );
  }
}
