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
import { defineComponent } from 'vue';
import { shallowRef } from 'vue';
import { computed } from 'vue';

import { Tab } from 'bkui-vue';
import { storeToRefs } from 'pinia';
import { useI18n } from 'vue-i18n';

import { useAlarmCenterDetailStore } from '../../../store/modules/alarm-center-detail';
import { useAlarmBasicInfo } from '../composables/use-alarm-baseinfo';
import AlarmAlert from './components/alarm-alert';
import AlarmConfirmDialog from './components/alarm-confirm-dialog';
import AlarmInfo from './components/alarm-info';
import PanelAlarm from './components/panel-alarm';
import PanelContainer from './components/panel-container';
import PanelEvent from './components/panel-event';
import PanelHost from './components/panel-host';
import PanelLink from './components/panel-link';
import PanelLog from './components/panel-log';
import PanelMetric from './components/panel-metric';
import PanelView from './components/panel-view';

import './index.scss';

export default defineComponent({
  name: 'DetailCommon',
  setup() {
    const { t } = useI18n();
    const alarmCenterDetailStore = useAlarmCenterDetailStore();
    const { alarmDetail, loading, bizId, alarmId } = storeToRefs(alarmCenterDetailStore);

    const { alertActionOverview } = useAlarmBasicInfo();

    const alarmConfirmShow = shallowRef(false);

    const panelTabList = [
      {
        label: t('视图'),
        name: 'view',
      },
      {
        label: t('日志'),
        name: 'log',
      },
      {
        label: t('调用链'),
        name: 'link',
      },
      {
        label: t('主机'),
        name: 'host',
      },
      {
        label: t('容器'),
        name: 'container',
      },
      {
        label: t('关联事件'),
        name: 'event',
      },
      {
        label: t('相关性指标'),
        name: 'metric',
      },
      {
        label: t('收敛的告警'),
        name: 'alarm',
      },
    ];

    const currentPanel = shallowRef(panelTabList[0].name);

    const panelCom = computed(() => {
      const comMap = {
        view: PanelView,
        log: PanelLog,
        link: PanelLink,
        host: PanelHost,
        container: PanelContainer,
        event: PanelEvent,
        metric: PanelMetric,
        alarm: PanelAlarm,
      };

      return comMap[currentPanel.value];
    });

    const handleAlarmConfirm = (val: boolean) => {
      alarmDetail.value = {
        ...alarmDetail.value,
        is_ack: val,
      };
    };

    return () => (
      <div class='alarm-center-detail-box'>
        <AlarmAlert
          data={alarmDetail.value}
          onAlarmConfirm={() => {
            alarmConfirmShow.value = true;
          }}
          onQuickShield={() => {}}
        />
        {loading.value ? (
          <div class='alarm-basic-info' />
        ) : (
          <AlarmInfo
            alertActionOverview={alertActionOverview.value}
            data={alarmDetail.value}
          />
        )}
        <Tab
          class='panel-tab'
          v-model:active={currentPanel.value}
          type='unborder-card'
        >
          {panelTabList.map(item => (
            <Tab.TabPanel
              key={item.name}
              label={item.label}
              name={item.name}
            />
          ))}
        </Tab>
        <panelCom.value detail={alarmDetail.value} />

        <AlarmConfirmDialog
          alarmBizId={bizId.value}
          alarmIds={[alarmId.value]}
          show={alarmConfirmShow.value}
          onConfirm={handleAlarmConfirm}
          onUpdate:show={v => {
            alarmConfirmShow.value = v;
          }}
        />
      </div>
    );
  },
});
