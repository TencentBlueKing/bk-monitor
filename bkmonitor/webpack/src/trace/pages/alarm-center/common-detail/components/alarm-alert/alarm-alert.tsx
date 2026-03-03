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
import { type PropType, defineComponent, shallowRef } from 'vue';
import { computed } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

// import AlertMetricsConfig from '../../../components/alarm-table/components/alert-content-detail/alert-content-detail';
import { type AlarmDetail, AlarmStatusIconMap } from '../../../typings';

import './alarm-alert.scss';

export default defineComponent({
  name: 'AlarmAlert',
  props: {
    data: Object as PropType<AlarmDetail>,
  },
  emits: ['alarmConfirm', 'quickShield'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const monitorDataDetail = computed(() => {
      return props.data?.items?.[0];
    });

    const editDataSemantics = shallowRef(false);

    const status = computed(() => {
      if (props.data?.is_shielded && props.data?.status === 'ABNORMAL') return 'SHIELDED_ABNORMAL';
      return props.data?.status || 'ABNORMAL';
    });

    const statusIcon = computed(() => {
      switch (props.data?.status) {
        case 'RECOVERED':
        case 'CLOSED':
          return AlarmStatusIconMap[props.data?.status];
        case 'ABNORMAL': {
          if (!props.data?.is_ack && !props.data?.is_shielded) return AlarmStatusIconMap.ABNORMAL;
          if (props.data?.is_shielded) return AlarmStatusIconMap.SHIELDED_ABNORMAL;
          return {
            ...AlarmStatusIconMap.ABNORMAL,
            name: t('未恢复（已确认）'),
          };
        }
        default:
          return {
            icon: '',
            iconColor: '',
            name: '',
          };
      }
    });

    const renderAlertTips = () => {
      if (status.value === 'CLOSED')
        return <span class='alarm-tips'>{t('在恢复检测周期内无数据上报，告警已失效')}</span>;
      if (status.value === 'SHIELDED_ABNORMAL')
        return (
          <span class='alarm-tips'>
            <span class='shielded-text'>{t('屏蔽时间剩余')}:</span>
            <span class='shielded-duration'>{props.data?.shield_left_time}</span>
          </span>
        );
      return (
        <span class='alarm-tips'>
          <span class='duration-text'>{t('持续时间')}:</span>
          <span class='duration-value'>{props.data?.duration}</span>
        </span>
      );
    };

    /** 告警确认 */
    const handleAlarmConfirm = () => {
      emit('alarmConfirm');
    };

    /** 告警屏蔽 */
    const handleQuickShield = () => {
      emit('quickShield');
    };

    const handleToShield = () => {
      if (!props.data.shield_id?.[0]) return;
      window.open(
        `${location.origin}${location.pathname}?bizId=${props.data.bk_biz_id}/#/trace/alarm-shield/edit/${props.data.shield_id[0]}`
      );
    };

    const handleEditDataSemantics = (value: boolean) => {
      editDataSemantics.value = value;
    };

    const handleEditConfirm = () => {
      editDataSemantics.value = false;
    };

    return {
      t,
      status,
      statusIcon,
      editDataSemantics,
      monitorDataDetail,
      renderAlertTips,
      handleAlarmConfirm,
      handleQuickShield,
      handleToShield,
      handleEditDataSemantics,
      handleEditConfirm,
    };
  },
  render() {
    return (
      <div class={['alarm-center-detail-alarm-alert', this.status]}>
        <span class='status-icon'>
          <i class={['icon-monitor', this.statusIcon.icon]} />
          <span class='status-text'>{this.statusIcon.name}</span>
        </span>
        <div class='separator' />
        <div class='alert-content'>
          {this.data && (
            <span
              class='alarm-content'
              v-overflow-tips
            >
              {this.data?.description},
            </span>
          )}
          {this.data && this.renderAlertTips()}
        </div>

        <div class='tools'>
          {this.status === 'ABNORMAL' && [
            <Button
              key='shield'
              theme='primary'
              text
              onClick={this.handleQuickShield}
            >
              <i class='icon-monitor icon-mc-notice-shield' />
              <span class='btn-text'>{this.t('快捷屏蔽')}</span>
            </Button>,
            !this.data?.is_ack && (
              <Button
                key='confirm'
                size='small'
                theme='primary'
                onClick={this.handleAlarmConfirm}
              >
                {this.t('告警确认')}
              </Button>
            ),
          ]}

          {this.status === 'SHIELDED_ABNORMAL' && (
            <Button
              theme='primary'
              text
              onClick={this.handleToShield}
            >
              <i class='icon-monitor icon-fenxiang' />
              <span class='btn-text'>{this.t('屏蔽策略')}</span>
            </Button>
          )}
        </div>
      </div>
    );
  },
});
