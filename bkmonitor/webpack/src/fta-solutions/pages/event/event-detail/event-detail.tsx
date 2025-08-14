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
import { Component, Emit, Mixins, Prop, ProvideReactive } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { alertDetail, listAlertFeedback, searchAction } from 'monitor-api/modules/alert';
import { listIndexByHost } from 'monitor-api/modules/alert_events';
import { graphTraceQuery } from 'monitor-api/modules/grafana';
import { checkAllowedByActionIds } from 'monitor-api/modules/iam';
import { getPluginInfoByResultTable } from 'monitor-api/modules/scene_view';
import { random } from 'monitor-common/utils/utils';
import { destroyTimezone, getDefaultTimezone } from 'monitor-pc/i18n/dayjs';
import * as eventAuth from 'monitor-pc/pages/event-center/authority-map';
import LogRetrievalDialog from 'monitor-pc/pages/event-center/event-center-detail/log-retrieval-dialog/log-retrieval-dialog';
import { MetricType } from 'monitor-pc/pages/strategy-config/strategy-config-set-new/typings';
import authorityStore from 'monitor-pc/store/modules/authority';
import authorityMixinCreate from 'monitor-ui/mixins/authorityMixin';
import { throttle } from 'throttle-debounce';

import { createAutoTimeRange } from './aiops-chart';
import AiopsContainer from './aiops/aiops-container-new';
import AlarmConfirm from './alarm-confirm';
import AlarmDispatch from './alarm-dispatch';
import BasicInfo from './basic-info';
import EventDetailHead from './event-detail-head';
import Feedback from './feedback';
import HandleStatusDialog from './handle-status-dialog';
import ManualDebugStatus from './manual-debug-status';
import ManualProcess from './manual-process';
import QuickShield from './quick-shield';
import TabContainer from './tab-container';

import type { IDetail } from './type';
import type { TimeRangeType } from 'monitor-pc/components/time-range/time-range';

import './event-detail.scss';

const authMap = ['manage_rule_v2', 'manage_event_v2', 'manage_downtime_v2'];
interface IDataZoomTimeRange {
  timeRange: [] | TimeRangeType;
}
Component.registerHooks(['beforeRouteLeave']);
@Component({
  name: 'EventDetail',
})
export default class EventDetail extends Mixins(authorityMixinCreate(eventAuth)) {
  @Prop({ default: '', type: [String, Number] }) id: string;
  @Prop({ default: '', type: String }) activeTab: string;
  @Prop({ type: Number, default: +window.bk_biz_id }) bizId: number;
  /** 是否需要展示顶部菜单栏 */
  @Prop({ type: Boolean, default: true }) isShowHead: boolean;
  // bizId
  @ProvideReactive('bkBizId') bkBizId = null;
  // 时区
  @ProvideReactive('timezone') timezone: string = window.timezone || getDefaultTimezone();
  /** aiops联动抛出的缩放时间范围 */
  @ProvideReactive('dataZoomTimeRange') dataZoomTimeRange: IDataZoomTimeRange = {
    timeRange: [],
  };

  // public id = 0
  basicInfo: IDetail = {
    id: '', // 告警id
    bk_biz_id: 0, // 业务id
    alert_name: '', // 告警名称
    first_anomaly_time: 0, // 首次异常事件
    begin_time: 0, // 事件产生事件
    create_time: 0, // 告警产生时间
    is_ack: false, // 是否确认
    is_shielded: false, // 是否屏蔽
    is_handled: false, // 是否已处理
    dimension: [], // 维度信息
    severity: 0, // 严重程度
    status: '',
    description: '', //
    alert_info: {
      count: 0,
      empty_receiver_count: 0,
      failed_count: 0,
      partial_count: 0,
      shielded_count: 0,
      success_count: 0,
    },
    duration: '',
    dimension_message: '',
    overview: {}, // 处理状态数据
    assignee: [],
  };
  actions = []; // 处理记录数据
  total = 0; // 记录数据总条数

  isLoading = false;
  tabShow = false;
  dialog = {
    quickShield: {
      show: false,
    },
    alarmConfirm: {
      show: false,
    },
    logRetrieval: {
      show: false,
    },
    statusDialog: {
      show: false,
    },
    feedback: {
      show: false,
    },
    manualProcess: {
      show: false,
      alertIds: [],
      bizIds: [],
      debugKey: random(8),
      actionIds: [],
      mealInfo: null,
    },
    alarmDispatch: {
      show: false,
      alertIds: [],
      bizIds: [],
    },
  };
  isScrollEnd = false; // 是否滑动到底部
  logRetrieval = {
    show: false,
    isMounted: false,
    isCanClick: false,
    isShowTip: false,
    isJumpDirectly: false, // 是否直接跳转到日志
    indexId: 0,
    indexList: [],
    ip: '0.0.0.0',
  };
  /* 是否已反馈 */
  isFeedback = false;
  /* traceIds 用于展示trace标签页 */
  traceIds = [];
  /* 场景id 用于场景视图标签页 */
  sceneId = '';
  sceneName = '';
  /* 权限校验 */
  authorityConfig = {};
  throttledScroll: () => void = () => {};

  created() {
    this.getDetailData();
  }

  mounted() {
    this.scrollInit();
    this.logRetrieval.isMounted = true;
  }
  beforeRouteLeave(to, from, next) {
    next(() => {
      destroyTimezone();
    });
  }
  beforeDestroy() {
    destroyTimezone();
    this.getScrollElement()?.removeEventListener('scroll', this.throttledScroll);
  }

  @Emit('closeSlider')
  handleCloseSlider() {
    return true;
  }

  /**
   * @description 是否为主机智能异常检测
   */
  get isHostAnomalyDetection() {
    return this.basicInfo?.extra_info?.strategy?.items?.[0]?.algorithms?.[0]?.type === MetricType.HostAnomalyDetection;
  }

  // 判断当前panel是否是Promql类型的 是则不展示aiops指标推荐等功能
  get checkPromqlPanel() {
    const { promql, data_source_label } = this.basicInfo?.extra_info?.strategy?.items?.[0]?.query_configs?.[0] ?? {};
    return promql && data_source_label === 'prometheus';
  }
  /** 是否需要展示右侧的AI相关的视图 */
  get isShowAiopsView() {
    // 2025-07-02 故障详情里的故障诊断内容与告警详情展示冲突，先隐藏右侧AI的相关视图。后续等新版告警详情上线后，按照最新设计稿展示
    return false;
    // return window.enable_aiops_event_center_biz_list?.some?.(id => +id === +this.bkBizId);
  }

  /* 权限校验 */
  async getCheckAllowed() {
    const data = await checkAllowedByActionIds({
      action_ids: authMap,
      bk_biz_id: this.basicInfo.bk_biz_id,
    }).catch(() => []);
    for (const item of data) {
      this.authorityConfig[item.action_id] = !!item.is_allowed;
    }
  }
  // 获取告警详情数据
  async getDetailData() {
    this.isLoading = true;
    const data = await alertDetail({ id: this.id, bk_biz_id: this.bizId }).catch(() => {
      // this.$router.push({ path: '/event' });
    });
    this.isFeedback = await listAlertFeedback({ alert_id: this.id, bk_biz_id: this.bizId })
      .then(res => !!res.length)
      .catch(() => false);
    this.tabShow = true;
    this.$emit('info', data, this.isFeedback);
    if (data) {
      this.basicInfo = data;
      this.bkBizId = data.bk_biz_id || this.bizId;
      await this.getCheckAllowed();
      await this.getTraceInfo();
      await this.getSceneId();
      this.logRetrievalInit();
      this.getHandleListData();
    }
    this.isLoading = false;
  }
  // 获取处理状态数据
  async getHandleListData() {
    const params = {
      bk_biz_id: this.basicInfo.bk_biz_id,
      page: 1,
      page_size: 100,
      alert_ids: [this.id],
      status: ['failure', 'success', 'partial_failure'],
      ordering: ['-create_time'],
      conditions: [{ key: 'parent_action_id', value: [0], method: 'eq' }], // 处理状态数据写死条件
    };
    const { actions, overview, total } = await searchAction(params);
    this.actions = actions;
    this.total = total;
    this.$set(this.basicInfo, 'overview', overview);
  }

  /* 权限校验 */
  judgeOperateAuthority() {
    const actionIds = ['manage_event_v2', 'manage_rule_v2'];
    const isAuth = actionIds.some(key => !!this.authorityConfig[key]);
    if (!isAuth) {
      authorityStore.getAuthorityDetail(actionIds[0]);
      return false;
    }
    return true;
  }

  /**
   * @description: 快捷屏蔽
   * @param {boolean} v
   * @return {*}
   */
  async quickShieldChange(v: boolean) {
    const MANAGE_RULE = 'manage_downtime_v2';
    if (!this.authorityConfig[MANAGE_RULE]) {
      authorityStore.getAuthorityDetail(MANAGE_RULE);
      return;
    }
    const { quickShield } = this.dialog;
    quickShield.show = v;
  }
  /**
   * @description: 告警确认
   * @param {boolean} v
   * @return {*}
   */
  alarmConfirmChange(v: boolean) {
    if (!this.judgeOperateAuthority()) return;
    const { alarmConfirm } = this.dialog;
    alarmConfirm.show = v;
  }

  /** 告警确认完成
   * @description:
   * @param {boolean} v
   * @return {*}
   */
  handleConfirmAfter(v: boolean) {
    if (v) {
      this.basicInfo.is_ack = v;
    }
  }
  /** 快捷屏蔽成功
   * @description:
   * @param {boolean} v
   * @return {*}
   */
  async quickShieldSucces(v: boolean) {
    if (v) {
      this.basicInfo.is_shielded = v;
      alertDetail({ id: this.id }).then(data => {
        this.basicInfo.shield_id = data.shield_id;
      });
    }
  }
  /**
   * @description: 快捷屏蔽时间
   * @param {string} time
   * @return {*}
   */
  handleTimeChange(time: string) {
    this.basicInfo.shield_left_time = time;
  }

  processingStatus(v) {
    this.dialog.statusDialog.show = v;
  }

  /* 手动处理 */
  async handleManualProcess() {
    // 手动处理需要权限判断
    if (!this.judgeOperateAuthority()) return;
    this.dialog.manualProcess.alertIds = [this.basicInfo.id];
    this.dialog.manualProcess.bizIds = [this.basicInfo.bk_biz_id];
    this.manualProcessShowChange(true);
  }

  manualProcessShowChange(v: boolean) {
    this.dialog.manualProcess.show = v;
  }
  /* 手动处理轮询状态 */
  handleDebugStatus(actionIds: number[]) {
    this.dialog.manualProcess.actionIds = actionIds;
    this.dialog.manualProcess.debugKey = random(8);
  }
  handleMealInfo(info) {
    this.dialog.manualProcess.mealInfo = info;
  }
  /* 告警分派 */
  handleAlarmDispatch() {
    if (!this.judgeOperateAuthority()) return;
    this.dialog.alarmDispatch.alertIds = [this.basicInfo.id];
    this.dialog.alarmDispatch.bizIds = [this.basicInfo.bk_biz_id];
    this.dialog.alarmDispatch.show = true;
  }
  handleAlarmDispatchShowChange(v: boolean) {
    this.dialog.alarmDispatch.show = v;
  }

  async logRetrievalInit() {
    const hostMap = ['bk_host_id'];
    const ipMap = ['bk_target_ip', 'ip', 'bk_host_id'];
    const cloudMap = ['bk_target_cloud_id', 'bk_cloud_id', 'bk_host_id'];
    this.logRetrieval.isCanClick = false;
    this.logRetrieval.isJumpDirectly = false;
    // 如果有logIndexId则可直接跳转到日志
    if (this.basicInfo.extend_info?.index_set_id) {
      this.logRetrieval.indexId = this.basicInfo.extend_info?.index_set_id;
      this.logRetrieval.isJumpDirectly = true;
      this.logRetrieval.isCanClick = true;
      return;
    }
    // 是否显示跳转到日志的icon
    this.logRetrieval.isCanClick = this.basicInfo.dimensions.some(item => ipMap.includes(item.key) && item.value);
    if (!this.logRetrieval.isCanClick) return;
    const params: Record<string, any> = {
      bk_biz_id: this.basicInfo.bk_biz_id,
      bk_host_innerip: '0.0.0.0',
      bk_cloud_id: '0',
    };
    for (const item of this.basicInfo.dimensions) {
      if (hostMap.includes(item.key) && item.value) {
        params.bk_host_id = item.value;
      }
      if (cloudMap.includes(item.key) && item.value) {
        params.bk_cloud_id = item.value;
      }
      if (ipMap.includes(item.key) && item.value) {
        params.bk_host_innerip = item.value;
      }
    }
    this.logRetrieval.ip = params.bk_host_innerip;
    this.logRetrieval.indexList = await listIndexByHost(params).catch(() => []);
    // 如果查不到索引集则显示提示
    if (!this.logRetrieval.indexList.length) {
      this.logRetrieval.isShowTip = true;
    }
  }
  handleLogDialogShow(v) {
    this.logRetrieval.show = v;
  }

  /* 判断是否需要展示trace tab页 */
  async getTraceInfo() {
    // eslint-disable-next-line @typescript-eslint/naming-convention
    const { graph_panel } = this.basicInfo;
    /* 只有 time_series + 'bk_monitor'/'custom' 的情况才允许执行graphTraceQuery*/
    const queryConfig = graph_panel?.targets?.[0]?.data?.query_configs?.[0];
    const typeLabels = ['time_series'];
    const sourceLabels = ['bk_monitor', 'custom'];
    const need =
      typeLabels.includes(queryConfig?.data_type_label) && sourceLabels.includes(queryConfig?.data_source_label);
    if (!need) {
      this.traceIds = [];
      return;
    }
    const interval = this.basicInfo.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.agg_interval || 60;
    const { startTime, endTime } = createAutoTimeRange(this.basicInfo.begin_time, this.basicInfo.end_time, interval);
    const params: any = {
      bk_biz_id: this.basicInfo.bk_biz_id,
      id: this.basicInfo.id,
      start_time: dayjs.tz(startTime).unix(),
      end_time: dayjs.tz(endTime).unix(),
    };
    if (graph_panel) {
      const [{ data: queryConfig }] = graph_panel.targets;
      if (queryConfig.extend_metric_fields?.some(item => item.includes('is_anomaly'))) {
        queryConfig.function = { ...queryConfig.function, max_point_number: 0 };
      }
      const data = await graphTraceQuery({ ...queryConfig, ...params }).catch(() => ({ series: [] }));
      const traceIdSet = new Set();
      if (data.series?.length) {
        for (const item of data.series) {
          const idIndex = item.columns.findIndex(c => c === 'bk_trace_id');
          for (const d of item.data_points) {
            if (d[idIndex]) {
              traceIdSet.add(d[idIndex]);
            }
          }
        }
      }
      this.traceIds = Array.from(traceIdSet);
    } else {
      this.traceIds = [];
    }
  }

  /* 获取场景id */
  async getSceneId() {
    let sceneId = '';
    let sceneName = '';
    const resultTableId =
      this.basicInfo.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.result_table_id ||
      this.basicInfo.extend_info?.result_table_id ||
      '';
    const dataLabel =
      this.basicInfo.extra_info?.strategy?.items?.[0]?.query_configs?.[0]?.data_label ||
      this.basicInfo.extend_info?.data_label ||
      '';
    if (resultTableId) {
      const sceneInfo = await getPluginInfoByResultTable({
        result_table_id: resultTableId,
        data_label: dataLabel || undefined,
        bk_biz_id: this.basicInfo.bk_biz_id,
      }).catch(() => ({
        scene_view_id: '',
        scene_view_name: '',
      }));
      sceneId = sceneInfo.scene_view_id || '';
      sceneName = sceneInfo.scene_view_name || '';
    } else {
      sceneId = '';
      sceneName = '';
    }
    this.sceneId = sceneId;
    this.sceneName = sceneName;
  }

  getDialogComponent() {
    const { alarmConfirm, quickShield, feedback } = this.dialog;
    const detail = [
      {
        severity: this.basicInfo?.severity,
        dimension: this.basicInfo?.dimensions || [],
        trigger: this.basicInfo?.description || '--',
        alertId: this.basicInfo.id,
        strategy: {
          id: this.basicInfo?.extra_info?.strategy?.id,
          name: this.basicInfo?.extra_info?.strategy?.name,
        },
      },
    ];
    // EventModuleStore.setDimensionList(this.basicInfo?.dimensions || []);

    return [
      <AlarmConfirm
        key='alarm-confirm'
        bizIds={[this.basicInfo.bk_biz_id]}
        ids={[this.id]}
        show={alarmConfirm.show}
        on-change={this.alarmConfirmChange}
        onConfirm={this.handleConfirmAfter}
      />,
      <QuickShield
        key='quick-shield'
        authority={this.authority}
        bizIds={[this.basicInfo.bk_biz_id]}
        details={detail}
        handleShowAuthorityDetail={this.handleShowAuthorityDetail}
        ids={[this.basicInfo.id]}
        show={quickShield.show}
        on-change={this.quickShieldChange}
        on-succes={this.quickShieldSucces}
        on-time-change={this.handleTimeChange}
      />,
      this.logRetrieval.isMounted ? (
        <LogRetrievalDialog
          key='log-retrieval'
          bizId={this.basicInfo.bk_biz_id}
          indexList={this.logRetrieval.indexList}
          ip={this.logRetrieval.ip}
          show={this.logRetrieval.show}
          showTips={this.logRetrieval.isShowTip}
          onShowChange={this.handleLogDialogShow}
        />
      ) : undefined,
      <HandleStatusDialog
        key='status'
        v-model={this.dialog.statusDialog.show}
        actions={this.actions}
        total={this.total}
      />,
      <Feedback
        key='feedback'
        ids={[this.basicInfo.id]}
        show={feedback.show}
        onChange={this.handleFeedback}
        onConfirm={this.handleFeedBackConfirm}
      />,
      <ManualProcess
        key='manual-process'
        alertIds={this.dialog.manualProcess.alertIds}
        bizIds={this.dialog.manualProcess.bizIds}
        show={this.dialog.manualProcess.show}
        onDebugStatus={this.handleDebugStatus}
        onMealInfo={this.handleMealInfo}
        onShowChange={this.manualProcessShowChange}
      />,
      <ManualDebugStatus
        key='manual-debug-status'
        actionIds={this.dialog.manualProcess.actionIds}
        bizIds={this.dialog.manualProcess.bizIds}
        debugKey={this.dialog.manualProcess.debugKey}
        mealInfo={this.dialog.manualProcess.mealInfo}
      />,
      <AlarmDispatch
        key='alarm-dispatch'
        alertIds={this.dialog.alarmDispatch.alertIds}
        bizIds={this.dialog.alarmDispatch.bizIds}
        show={this.dialog.alarmDispatch.show}
        onShow={this.handleAlarmDispatchShowChange}
      />,
    ];
  }
  getScrollElement() {
    return this.isShowAiopsView ? this.$el.querySelector('.event-detail-aiops') : this.$el;
  }
  scrollInit() {
    this.throttledScroll = throttle(300, this.handleScroll);
    this.$nextTick(() => {
      this.getScrollElement()?.addEventListener('scroll', this.throttledScroll);
    });
  }

  handleScroll(e: any) {
    const { scrollHeight, scrollTop, clientHeight } = e.target;
    this.isScrollEnd = scrollHeight - scrollTop < clientHeight + 1 && scrollHeight - scrollTop > clientHeight - 1;
  }

  /* 反馈 */
  handleFeedback(v: boolean) {
    this.dialog.feedback.show = v;
  }
  handleFeedBackConfirm() {
    this.isFeedback = true;
  }
  /** 渲染绘制告警详情内容 */
  renderDetailContainer() {
    return (
      <div class='container-group'>
        <BasicInfo
          basicInfo={this.basicInfo}
          on-alarm-confirm={this.alarmConfirmChange}
          on-manual-process={this.handleManualProcess}
          on-processing-status={this.processingStatus}
          on-quick-shield={this.quickShieldChange}
          onAlarmDispatch={this.handleAlarmDispatch}
        />
        <TabContainer
          actions={this.actions}
          activeTab={this.activeTab}
          alertId={this.id}
          detail={this.basicInfo}
          isScrollEnd={this.isScrollEnd}
          sceneId={this.sceneId}
          sceneName={this.sceneName}
          show={this.tabShow}
          traceIds={this.traceIds}
        />
      </div>
    );
  }
  /** 判断当前是否需要展示AI相关的内容，需要的话则左右布局，并支持拖拽拉伸 */

  renderLayoutContent() {
    if (this.isLoading) return undefined;
    if (this.isShowAiopsView) {
      return (
        <bk-resize-layout
          class='detail-resize-view'
          auto-minimize={true}
          collapsible={true}
          initial-divide={500}
          max={660}
          min={480}
          placement={'right'}
        >
          <AiopsContainer
            slot='aside'
            detail={this.basicInfo}
            show={true}
          />
          <div
            class='event-detail-aiops'
            slot='main'
          >
            {this.renderDetailContainer()}
          </div>
        </bk-resize-layout>
      );
    }
    return this.renderDetailContainer();
  }

  render() {
    return (
      <div
        style={{
          overflowY: !this.isShowAiopsView ? 'auto' : 'initial',
          height: !this.isShowAiopsView ? '100%' : 'initial',
        }}
        class='event-detail-container'
        v-bkloading={{ isLoading: this.isLoading }}
      >
        {/* 顶部状态栏渲染 */}
        {this.isShowHead && (
          <div class='event-detail-head-container'>
            <EventDetailHead
              basicInfo={this.basicInfo}
              bizId={this.bizId}
              eventId={this.id}
              isFeedback={this.isFeedback}
            />
          </div>
        )}
        {/* 详情主体内容渲染 */}
        {this.renderLayoutContent()}
        {/* 相关的弹框组件渲染 */}
        {this.getDialogComponent()}
      </div>
    );
  }
}
