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
import { computed, defineComponent, KeepAlive } from 'vue';
import { shallowRef } from 'vue';

import { Tab } from 'bkui-vue';
import { storeToRefs } from 'pinia';

import { useAlarmCenterDetailStore } from '../../../store/modules/alarm-center-detail';
import { useAlarmBasicInfo } from '../composables/use-alarm-baseinfo';
import { AlarmDetail } from '../typings';
import { ALARM_CENTER_PANEL_TAB_MAP } from '../utils/constant';
import AlarmAlert from './components/alarm-alert/alarm-alert';
import AlarmConfirmDialog from './components/alarm-alert/alarm-confirm-dialog';
import QuickShieldDialog from './components/alarm-alert/quick-shield-dialog';
import AlarmInfo from './components/alarm-info';
import AlarmView from './components/alarm-view/alarm-view';
import PanelAlarm from './components/panel-alarm';
import PanelContainer from './components/panel-container';
import PanelEvent from './components/panel-event';
import PanelHost from './components/panel-host';
import PanelLink from './components/panel-link';
import PanelLog from './components/panel-log';
import PanelMetric from './components/panel-metric';

import './common-detail.scss';

export default defineComponent({
  name: 'AlarmDetail',
  setup() {
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { alarmDetail, loading, bizId, alarmId } = storeToRefs(alarmCenterDetailStore);
    const { alertActionOverview } = useAlarmBasicInfo();
    /** 告警确认弹窗 */
    const alarmConfirmShow = shallowRef(false);
    /** 快速屏蔽弹窗 */
    const quickShieldShow = shallowRef(false);
    const currentPanel = shallowRef(alarmCenterDetailStore.alarmDetail?.alarmTabList?.[0]?.label);

    const handleAlarmConfirm = (val: boolean) => {
      alarmDetail.value = new AlarmDetail({ ...alarmDetail.value, is_ack: val });
    };

    /** 告警屏蔽详情 */
    const alarmShieldDetail = computed(() => {
      return [
        {
          severity: alarmCenterDetailStore.alarmDetail?.severity,
          dimension: alarmCenterDetailStore.alarmDetail?.dimensions || [],
          trigger: alarmCenterDetailStore.alarmDetail?.description || '--',
          alertId: alarmCenterDetailStore.alarmDetail?.id,
          strategy: {
            id: alarmCenterDetailStore.alarmDetail?.extra_info?.strategy?.id,
            name: alarmCenterDetailStore.alarmDetail?.extra_info?.strategy?.name,
          },
          bkHostId: alarmCenterDetailStore.alarmDetail?.bk_host_id || '',
        },
      ];
    });

    /**
     * @description: 快捷屏蔽时间
     * @param {string} time
     * @return {*}
     */
    const handleTimeChange = (time: string) => {
      alarmDetail.value = new AlarmDetail({ ...alarmDetail.value, shield_left_time: time });
    };

    const quickShieldSuccess = (v: boolean) => {
      if (v) {
        alarmCenterDetailStore.getAlertDetailData(alarmId.value);
      }
    };

    const getPanelComponent = () => {
      switch (currentPanel.value) {
        case ALARM_CENTER_PANEL_TAB_MAP.VIEW:
          return <AlarmView />;
        case ALARM_CENTER_PANEL_TAB_MAP.LOG:
          return <PanelLog detail={alarmCenterDetailStore.alarmDetail} />;
        case ALARM_CENTER_PANEL_TAB_MAP.TRACE:
          return <PanelLink />;
        case 'host':
          return <PanelHost detail={alarmCenterDetailStore.alarmDetail} />;
        case 'container':
          return <PanelContainer />;
        case 'event':
          return <PanelEvent detail={alarmCenterDetailStore.alarmDetail} />;
        case 'metric':
          return <PanelMetric />;
        case 'alarm':
          return <PanelAlarm />;
        default:
          return null;
      }
    };

    return () => (
      <div class='alarm-center-detail-box'>
        <AlarmAlert
          data={alarmCenterDetailStore.alarmDetail}
          onAlarmConfirm={() => {
            alarmConfirmShow.value = true;
          }}
          onQuickShield={() => {
            quickShieldShow.value = true;
          }}
        />
        {loading.value ? (
          <div class='alarm-basic-info' />
        ) : (
          <AlarmInfo
            alertActionOverview={alertActionOverview.value}
            data={alarmCenterDetailStore.alarmDetail}
          />
        )}
        <Tab
          class='panel-tab'
          active={currentPanel.value}
          type='unborder-card'
          onUpdate:active={v => {
            currentPanel.value = v;
          }}
        >
          {alarmCenterDetailStore.alarmDetail?.alarmTabList?.map(item => (
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
          onUpdate:show={v => {
            alarmConfirmShow.value = v;
          }}
        />
        <QuickShieldDialog
          alarmBizId={bizId.value}
          alarmIds={[alarmId.value]}
          alarmShieldDetail={alarmShieldDetail.value}
          show={quickShieldShow.value}
          onSuccess={quickShieldSuccess}
          onTimeChange={handleTimeChange}
          onUpdate:show={v => {
            quickShieldShow.value = v;
          }}
        />
      </div>
    );
  },
});
