/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent } from 'vue';

import dayjs from 'dayjs';
import { useI18n } from 'vue-i18n';

import { AlertLevelEnum, AlarmLevelIconMap, AlarmStatusEnum, AlarmStatusIconMap } from '@/pages/alarm-center/typings';

import type { IAlertListItem, IAlertListResult } from '../typing';

import './alert-list-message.scss';

export default defineComponent({
  name: 'AlertListMessage',
  props: {
    content: {
      type: String,
      default: '',
    },
    result: {
      type: Object as PropType<IAlertListResult>,
      required: true,
    },
  },
  setup() {
    const { t } = useI18n();

    /** 告警级别 → 徽标配色 class */
    const SEVERITY_CLASS: Record<number, string> = {
      [AlertLevelEnum.FATAL]: 'is-fatal',
      [AlertLevelEnum.WARNING]: 'is-warning',
      [AlertLevelEnum.REMIND]: 'is-remind',
    };

    const formatBeginTime = (timestamp: number) => dayjs.tz(timestamp).format('YYYY-MM-DD HH:mm:ss');

    const getSeverityClass = (severity: IAlertListItem['severity']) => SEVERITY_CLASS[severity] || '';

    const getSeverityText = (severity: IAlertListItem['severity']) => AlarmLevelIconMap[severity]?.text || '';

    const getStatusMeta = (status: IAlertListItem['status']) =>
      AlarmStatusIconMap[status] || AlarmStatusIconMap[AlarmStatusEnum.ABNORMAL];

    return {
      t,
      formatBeginTime,
      getSeverityClass,
      getSeverityText,
      getStatusMeta,
    };
  },
  render() {
    return (
      <div class='alert-list-message'>
        {this.content ? <p class='alert-list-message-text'>{this.content}</p> : null}
        <div class='alert-list-card'>
          <div class='alert-list-card-title'>{this.t('共 {n} 个告警', { n: this.result.alerts.length })}</div>
          <div class='alert-list-card-list'>
            {this.result.alerts.map(item => {
              const statusMeta = this.getStatusMeta(item.status);
              return (
                <div
                  key={item.id}
                  class='alert-list-item'
                >
                  <div class='alert-list-item-header'>
                    <span class={['alert-list-severity', this.getSeverityClass(item.severity)]}>
                      {this.getSeverityText(item.severity)}
                    </span>
                    <span class='alert-list-item-title'>{item.title}</span>
                  </div>
                  <div class='alert-list-item-fields'>
                    {item.fields.map(field => (
                      <div
                        key={`${item.id}-${field.key}`}
                        class='alert-list-field'
                      >
                        <span class='alert-list-field-key'>{this.t(field.key)}</span>
                        <span class='alert-list-field-value'>{field.value}</span>
                      </div>
                    ))}
                  </div>
                  <div class='alert-list-item-footer'>
                    <span class='alert-list-item-time'>
                      {`${this.formatBeginTime(item.beginTime)} · ${this.t(item.notifyText)}`}
                    </span>
                    <span class='alert-list-item-status'>
                      <i
                        style={{ color: statusMeta.iconColor }}
                        class={['icon-monitor', statusMeta.icon, 'alert-list-item-status-icon']}
                        aria-hidden='true'
                      />
                      <span>{statusMeta.name}</span>
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    );
  },
});
