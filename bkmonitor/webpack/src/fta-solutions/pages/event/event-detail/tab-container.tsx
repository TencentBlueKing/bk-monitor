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
import { Component, Prop, ProvideReactive, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { DEFAULT_TIME_RANGE } from 'monitor-pc/components/time-range/utils';
import { MetricType } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';

import CirculationRecord from './circulation-record';
import HandleExperiences from './handle-experiences';
import LogInfo from './log-info';
import PerformanceView from './performance-view';
import RelatedEvents from './related-events';
import SceneView from './scene-view';
import TraceInfo from './trace-info';
import ViewInfo from './view-info';

import type { IDetail } from './type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './tab-container.scss';

enum EPanelsNames {
  circulationRecord = 'circulationRecord',
  handleExperience = 'handleExperience',
  hostProcess = 'hostProcess',
  logInfo = 'logInfo',
  performance = 'performance',
  relatedEvents = 'relatedEvents',
  sceneView = 'sceneView',
  traceInfo = 'traceInfo',
  viewInfo = 'viewInfo',
}

const { i18n } = window;

interface ITabContainerProps {
  isScrollEnd?: boolean;
  alertId?: number | string;
  show?: boolean;
  detail?: IDetail;
  activeTab?: string;
  actions?: any[];
  traceIds?: string[];
  sceneId?: string;
  sceneName?: string;
}

interface IDataZoomTimeRange {
  timeRange: [] | TimeRangeType;
}

@Component({
  name: 'TabContainer',
})
export default class TabContainer extends tsc<ITabContainerProps> {
  /** 时间范围 */
  @ProvideReactive('timeRange') timeRange: TimeRangeType = DEFAULT_TIME_RANGE;
  /** aiops联动抛出的缩放时间范围 */
  @ProvideReactive('dataZoomTimeRange') dataZoomTimeRange: IDataZoomTimeRange = {
    timeRange: [],
  };
  @Prop({ type: Boolean, default: false }) isScrollEnd: boolean;
  @Prop({ type: [Number, String], default: 0 }) alertId: number | string;
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: String, default: '' }) activeTab: string;
  @Prop({ type: Object, default: () => ({}) }) detail: IDetail;
  @Prop({ type: Array, default: () => [] }) actions: any[];
  /* trace ID 集合 用于trace标签页页展示 */
  @Prop({ type: Array, default: () => [] }) traceIds: string[];
  /* sceneId 用于场景视图tab展示 */
  @Prop({ type: String, default: '' }) sceneId: string;
  /* 用于场景视图tab跳转到场景详情页 */
  @Prop({ type: String, default: '' }) sceneName: string;
  @Ref('setPopover') setPopoverRef: any;

  public panels = [
    { name: EPanelsNames.viewInfo, label: i18n.t('视图信息') },
    { name: EPanelsNames.logInfo, label: i18n.t('日志') },
    { name: EPanelsNames.performance, label: i18n.t('主机') },
    { name: EPanelsNames.hostProcess, label: i18n.t('进程') },
    { name: EPanelsNames.sceneView, label: i18n.t('场景视图') },
    { name: EPanelsNames.traceInfo, label: 'Trace' },
    { name: EPanelsNames.handleExperience, label: i18n.t('处理经验') },
    { name: EPanelsNames.circulationRecord, label: i18n.t('流转记录') },
    { name: EPanelsNames.relatedEvents, label: i18n.t('关联事件') },
  ];
  public active = '';

  public circulationFilter = [
    {
      id: 'CREATE',
      name: i18n.t('告警产生'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'CONVERGE',
      name: i18n.t('告警收敛'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'RECOVER',
      name: i18n.t('告警恢复'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'RECOVERING',
      name: i18n.t('告警恢复中'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'CLOSE',
      name: i18n.t('告警关闭'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'DELAY_RECOVER',
      name: i18n.t('延迟恢复'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'ABORT_RECOVER',
      name: i18n.t('中断恢复'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'SYSTEM_RECOVER',
      name: i18n.t('系统恢复'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'SYSTEM_CLOSE',
      name: i18n.t('系统关闭'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'ACK',
      name: i18n.t('告警确认'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'SEVERITY_UP',
      name: i18n.t('告警级别调整'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'ACTION',
      name: i18n.t('处理动作'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'ALERT_QOS',
      name: i18n.t('告警流控'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
    {
      id: 'EVENT_DROP',
      name: i18n.t('事件忽略'),
      checked: true,
      mockChecked: true,
      disabled: false,
    },
  ];

  public relatedEventsParams = {
    start_time: 0,
    end_time: 0,
  };

  get getConditions(): string[] {
    const condition = [];
    this.circulationFilter.forEach(item => {
      if (item.mockChecked) {
        condition.push(item.id);
      }
    });
    return condition;
  }
  // 判断当前panel是否是Promql类型的 是则不展示aiops指标推荐等功能
  get checkPromqlPanel() {
    const { promql, data_source_label } = this.detail?.extra_info?.strategy?.items?.[0]?.query_configs?.[0] ?? {};
    return promql && data_source_label === 'prometheus';
  }
  get panelsFilter() {
    /* 是否显示主机tab */
    const hasPerformance = this.detail?.dimensions?.some(item => ['bk_target_ip', 'ip'].includes(item.key));
    const hasHostProcess =
      this.detail?.category === 'host_process' &&
      this.detail?.dimensions?.some(item => item.key === 'tags.display_name');
    return this.panels.filter(item => {
      if (item.name === EPanelsNames.performance) {
        return hasPerformance;
      }
      if (item.name === EPanelsNames.hostProcess) {
        return hasHostProcess;
      }
      if (item.name === EPanelsNames.logInfo) {
        return hasPerformance;
      }
      /* tracetab */
      if (item.name === EPanelsNames.traceInfo) {
        return !!this.traceIds.length;
      }
      /* 场景视图 */
      if (item.name === EPanelsNames.sceneView) {
        return !!this.sceneId;
      }
      return true;
    });
  }

  /**
   * @description 是否为主机智能异常检测
   */
  get isHostAnomalyDetection() {
    return this.detail?.extra_info?.strategy?.items?.[0]?.algorithms?.[0]?.type === MetricType.HostAnomalyDetection;
  }

  @Watch('show')
  handleShow(v) {
    if (v) {
      this.active = this.activeTab ? this.activeTab : 'viewInfo';
    }
  }

  tabChange(v) {
    if (!this.show) {
      return false;
    }
    this.relatedEventsParams = {
      start_time: 0,
      end_time: 0,
    };
    this.active = v;
  }

  handleCheckColChange(item) {
    const filter = this.circulationFilter.find(f => f.id === item.id);
    filter.checked = !item.checked;
    // const result = Object.keys(this.circulationFilter).map(key => (
    //   { id: key, checked: this.circulationFilter[key].checked }
    // ))
  }

  handleConfirmPopover() {
    this.circulationFilter.forEach(item => {
      item.mockChecked = item.checked;
    });
    this.setPopoverRef.instance.hide(0);
  }

  handleHideFilterPopover() {
    this.circulationFilter.forEach(item => {
      item.checked = item.mockChecked;
    });
  }

  handleRelatedEvents(v) {
    this.relatedEventsParams.end_time = v.end_time;
    this.relatedEventsParams.start_time = v.start_time;
    this.active = EPanelsNames.relatedEvents;
  }

  getCirculationFilterComponent() {
    return (
      <div class='circulation-filter-btn'>
        <bk-popover
          ref='setPopover'
          width='515'
          placement='bottom-end'
          theme='light strategy-setting'
          trigger='click'
          on-hide={this.handleHideFilterPopover}
        >
          <div class='filter-btn'>
            <span class='icon-monitor icon-menu-setting' />
          </div>
          <div
            class='circulation-tool-popover'
            slot='content'
          >
            <div class='tool-popover-title'>{this.$t('字段显示设置')}</div>
            <ul class='tool-popover-content'>
              {this.circulationFilter.map(item => (
                <li
                  key={item.id}
                  class='tool-popover-content-item'
                >
                  <bk-checkbox
                    disabled={item.disabled}
                    value={item.checked}
                    on-change={() => this.handleCheckColChange(item)}
                  >
                    {item.name}
                  </bk-checkbox>
                </li>
              ))}
            </ul>
            <div class='tool-popover-footer'>
              <bk-button
                class='footer-btn'
                theme='primary'
                on-click={this.handleConfirmPopover}
              >
                {this.$t('确定')}
              </bk-button>
              <bk-button
                on-click={() => {
                  this.setPopoverRef.instance.hide(0);
                }}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          </div>
        </bk-popover>
      </div>
    );
  }

  render() {
    return (
      <div class='event-detail-tab'>
        <bk-tab
          key={`tab-key-${this.panelsFilter.length}`}
          active={this.active}
          type={'unborder-card'}
          on-tab-change={this.tabChange}
        >
          {this.panelsFilter.map(item => (
            <bk-tab-panel
              {...{ props: item }}
              key={item.name}
            />
          ))}
        </bk-tab>
        {this.active === EPanelsNames.circulationRecord ? this.getCirculationFilterComponent() : undefined}
        <div class='tab-panel-main'>
          <ViewInfo
            alertId={this.alertId}
            detail={this.detail}
            isScrollEnd={this.isScrollEnd}
            show={this.active === EPanelsNames.viewInfo}
          />
          {/* {!!window.enable_aiops && !this.isHostAnomalyDetection && !this.checkPromqlPanel && (
            <AiopsContainer
              detail={this.detail}
              show={this.active === EPanelsNames.viewInfo}
            />
          )} */}
          <HandleExperiences
            detail={this.detail}
            show={this.active === EPanelsNames.handleExperience}
          />
          <CirculationRecord
            actions={this.actions}
            conditions={this.getConditions}
            detail={this.detail}
            isScrollEnd={this.isScrollEnd}
            show={this.active === EPanelsNames.circulationRecord}
            on-related-events={this.handleRelatedEvents}
          />
          <RelatedEvents
            alertId={this.alertId}
            detail={this.detail}
            params={this.relatedEventsParams}
            show={this.active === EPanelsNames.relatedEvents}
          />
          <PerformanceView
            detail={this.detail}
            show={this.active === EPanelsNames.performance}
          />
          <PerformanceView
            detail={this.detail}
            isProcess={true}
            show={this.active === EPanelsNames.hostProcess}
          />
          {/* 日志 tab */}
          <LogInfo
            detail={this.detail}
            show={this.active === EPanelsNames.logInfo}
          />
          {/* trace tab */}
          <TraceInfo
            detail={this.detail}
            show={this.active === EPanelsNames.traceInfo}
            traceIds={this.traceIds}
          />
          <SceneView
            detail={this.detail}
            sceneId={this.sceneId}
            sceneName={this.sceneName}
            show={this.active === EPanelsNames.sceneView}
          />
        </div>
      </div>
    );
  }
}
