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
import { computed, defineComponent, inject, KeepAlive, shallowRef, useTemplateRef, watch } from 'vue';

import { Tab } from 'bkui-vue';
import { storeToRefs } from 'pinia';

import { useAlarmCenterDetailStore } from '../../../store/modules/alarm-center-detail';
import { useAlarmBasicInfo } from '../composables/use-alarm-baseinfo';
import { AlarmDetail } from '../typings';
import { ALARM_CENTER_PANEL_TAB_MAP } from '../utils/constant';
import AlarmAlert from './components/alarm-alert/alarm-alert';
import AlarmConfirmDialog from './components/alarm-alert/alarm-confirm-dialog';
import QuickShieldDialog from './components/alarm-alert/quick-shield-dialog';
import AlarmDispatchDialog from './components/alarm-info/alarm-dispatch-dialog';
import AlarmInfo from './components/alarm-info/alarm-info';
import AlarmStatusDialog from './components/alarm-info/alarm-status-dialog';
import ManualDebugStatusDialog from './components/alarm-info/manual-debug-status-dialog';
import ManualProcessDialog from './components/alarm-info/manual-process-dialog';
import AlarmView from './components/alarm-view/alarm-view';
import PanelAlarm from './components/panel-alarm/panel-alarm';
import PanelEvent from './components/panel-event';
import PanelHost from './components/panel-host';
import PanelK8s from './components/panel-k8s';
import PanelLog from './components/panel-log';
// import PanelMetric from './components/panel-metric';
import PanelTrace from './components/panel-trace';

import type { IAuthority } from '@/typings/authority';

import './common-detail.scss';

export default defineComponent({
  name: 'AlarmDetail',
  setup() {
    const boxWrapRef = useTemplateRef<HTMLDivElement>('boxWrap');
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { alarmDetail, bizId, alarmId, timeRange, defaultTab } = storeToRefs(alarmCenterDetailStore);
    const currentPanel = shallowRef(alarmDetail.value?.alarmTabList?.[0]?.name);
    const { alarmStatusOverview, alarmStatusActions, alarmStatusTotal } = useAlarmBasicInfo();

    const authority = inject<IAuthority>('authority');
    const judgeOperateAuthority = () => {
      const actionIds = ['MANAGE_EVENT_V2_AUTH', 'MANAGE_ACTION_CONFIG'];
      const isAuth = actionIds.some(key => authority.auth[key]);
      if (!isAuth) {
        authority.showDetail([authority.map.MANAGE_EVENT_V2_AUTH]);
        return false;
      }
      return true;
    };
    /** 告警确认弹窗 */
    const alarmConfirmShow = shallowRef(false);
    /** 快速屏蔽弹窗 */
    const quickShieldShow = shallowRef(false);

    const relatedEventsParams = shallowRef({
      start_time: 0,
      end_time: 0,
    });

    /** 打开告警确认弹窗 */
    const handleShowAlarmConfirm = (show: boolean) => {
      if (!judgeOperateAuthority()) return;
      alarmConfirmShow.value = show;
    };
    /** 告警确认 */
    const handleAlarmConfirm = (val: boolean) => {
      alarmDetail.value = new AlarmDetail({ ...alarmDetail.value, is_ack: val });
    };

    /** 告警屏蔽详情数据 */
    const alarmShieldDetail = computed(() => {
      return [
        {
          severity: alarmDetail.value?.severity,
          dimension: alarmDetail.value?.dimensions || [],
          trigger: alarmDetail.value?.description || '--',
          alertId: alarmDetail.value?.id,
          strategy: {
            id: alarmDetail.value?.extra_info?.strategy?.id,
            name: alarmDetail.value?.extra_info?.strategy?.name,
          },
          bkHostId: alarmDetail.value?.bk_host_id || '',
        },
      ];
    });
    /** 快捷屏蔽窗口 */
    const handleShowQuickShield = (show: boolean) => {
      if (!authority.auth.ALARM_SHIELD_MANAGE_AUTH) {
        authority.showDetail([authority.map.ALARM_SHIELD_MANAGE_AUTH]);
        return false;
      }
      quickShieldShow.value = show;
    };

    /**
     * @description: 快捷屏蔽时间
     * @param {string} time
     * @return {*}
     */
    const handleTimeChange = (time: string) => {
      alarmDetail.value = new AlarmDetail({ ...alarmDetail.value, shield_left_time: time, is_shielded: true });
    };

    /** 告警状态详情 */
    const alarmStatusDetailShow = shallowRef(false);

    /** 手动处理弹窗 */
    const manualProcessShow = shallowRef(false);
    /** 手动处理 */
    const handleManualProcess = () => {
      if (!judgeOperateAuthority()) return;
      manualProcessShow.value = true;
    };

    /** 告警分派弹窗 */
    const alarmDispatchShow = shallowRef(false);
    const handleAlarmDispatch = () => {
      if (!judgeOperateAuthority()) return;
      alarmDispatchShow.value = true;
    };

    const manualDebugShow = shallowRef(false);
    const actionIds = shallowRef([]);
    const mealInfo = shallowRef(null);
    /** 告警debugger */
    const handleDebugStatus = (value: number[]) => {
      actionIds.value = value;
      manualDebugShow.value = true;
    };

    const handleMealInfo = value => {
      mealInfo.value = value;
    };

    const handleRelatedEventsTimeRange = (timeRange: string[]) => {
      relatedEventsParams.value = {
        start_time: Number(timeRange[0]),
        end_time: Number(timeRange[1]),
      };
      currentPanel.value = ALARM_CENTER_PANEL_TAB_MAP.ALARM;
    };

    const handleCurrentPanelChange = v => {
      relatedEventsParams.value = {
        start_time: 0,
        end_time: 0,
      };
      currentPanel.value = v;
    };

    watch(
      () => defaultTab.value,
      newVal => {
        handleCurrentPanelChange(newVal || alarmDetail.value?.alarmTabList?.[0]?.name);
      },
      { immediate: true }
    );

    const getPanelComponent = () => {
      switch (currentPanel.value) {
        case ALARM_CENTER_PANEL_TAB_MAP.VIEW:
          return (
            <AlarmView
              bizId={bizId.value}
              defaultTimeRange={timeRange.value}
              detail={alarmDetail.value}
              onRelatedEventsTimeRange={handleRelatedEventsTimeRange}
            />
          );
        case ALARM_CENTER_PANEL_TAB_MAP.LOG:
          return (
            <PanelLog
              headerAffixedTop={{
                offsetTop: 51,
                container: () => boxWrapRef.value,
              }}
              detail={alarmDetail.value}
            />
          );
        case ALARM_CENTER_PANEL_TAB_MAP.TRACE:
          return <PanelTrace alertId={alarmId.value} />;
        case ALARM_CENTER_PANEL_TAB_MAP.HOST:
          return <PanelHost alertId={alarmId.value} />;
        case ALARM_CENTER_PANEL_TAB_MAP.CONTAINER:
          return <PanelK8s alertId={alarmId.value} />;
        case ALARM_CENTER_PANEL_TAB_MAP.EVENT:
          return <PanelEvent detail={alarmDetail.value} />;
        // case ALARM_CENTER_PANEL_TAB_MAP.METRIC:
        //   return <PanelMetric />;
        case ALARM_CENTER_PANEL_TAB_MAP.ALARM:
          return (
            <PanelAlarm
              detail={alarmDetail.value}
              params={relatedEventsParams.value}
            />
          );
        default:
          return null;
      }
    };

    return () => (
      <div
        ref={'boxWrap'}
        class='alarm-center-detail-box'
      >
        <AlarmAlert
          key='alarm-alert'
          data={alarmDetail.value}
          onAlarmConfirm={() => {
            handleShowAlarmConfirm(true);
          }}
          onQuickShield={() => {
            handleShowQuickShield(true);
          }}
        />
        <AlarmInfo
          key='alarm-info'
          alertActionOverview={alarmStatusOverview.value}
          data={alarmDetail.value}
          onAlarmDispatch={handleAlarmDispatch}
          onAlarmStatusDetailShow={() => {
            alarmStatusDetailShow.value = true;
          }}
          onManualProcess={handleManualProcess}
        />
        <Tab
          class='panel-tab'
          active={currentPanel.value}
          type='unborder-card'
          onUpdate:active={v => handleCurrentPanelChange(v)}
        >
          {alarmDetail.value?.alarmTabList?.map(item => (
            <Tab.TabPanel
              key={item.name}
              label={item.label}
              name={item.name}
            />
          ))}
        </Tab>
        <KeepAlive>{getPanelComponent()}</KeepAlive>
        <AlarmConfirmDialog
          alarmBizId={bizId.value}
          alarmIds={[alarmId.value]}
          show={alarmConfirmShow.value}
          onConfirm={handleAlarmConfirm}
          onUpdate:show={handleShowAlarmConfirm}
        />
        <QuickShieldDialog
          alarmBizId={bizId.value}
          alarmIds={[alarmId.value]}
          alarmShieldDetail={alarmShieldDetail.value}
          show={quickShieldShow.value}
          onTimeChange={handleTimeChange}
          onUpdate:show={handleShowQuickShield}
        />
        <AlarmStatusDialog
          v-model:show={alarmStatusDetailShow.value}
          actions={alarmStatusActions.value}
          total={alarmStatusTotal.value}
        />
        <AlarmDispatchDialog
          v-model:show={alarmDispatchShow.value}
          alarmBizId={bizId.value}
          alarmIds={[alarmId.value]}
        />
        <ManualProcessDialog
          v-model:show={manualProcessShow.value}
          alarmBizId={bizId.value}
          alarmIds={[alarmId.value]}
          onDebugStatus={handleDebugStatus}
          onMealInfo={handleMealInfo}
        />
        <ManualDebugStatusDialog
          v-model:show={manualDebugShow.value}
          actionIds={actionIds.value}
          alarmBizId={bizId.value}
          mealInfo={mealInfo.value}
        />
      </div>
    );
  },
});
