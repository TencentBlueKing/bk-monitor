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
import { useI18n } from 'vue-i18n';

import { getBizRouteHref } from 'monitor-common/utils';
import { storeToRefs } from 'pinia';

import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { IAlertIncidentBrief, IBkFaraProcessItem } from './typing';

import './ai-diagnostic-info-card.scss';
export default defineComponent({
  name: 'AiDiagnosticInfo',
  props: {
    incident: {
      type: Object as PropType<IAlertIncidentBrief | null>,
      default: null,
    },
    bkFaraProcesses: {
      type: Array as PropType<IBkFaraProcessItem[]>,
      default: () => [],
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { bizId } = storeToRefs(useAlarmCenterDetailStore());

    const handleIncidentClick = () => {
      const incidentId = props.incident?.id || props.incident?.incident_id;
      if (!incidentId) return;
      window.open(getBizRouteHref(`/trace/incident/detail/${incidentId}`, bizId.value), '_blank');
    };

    const handleProcessClick = (item: IBkFaraProcessItem) => {
      if (!item.link) return;
      window.open(item.link, '_blank');
    };

    return {
      t,
      handleIncidentClick,
      handleProcessClick,
    };
  },
  render() {
    const incidentName = this.incident?.incident_name || '';
    return (
      <AiHighlightCard
        class='ai-diagnostic-info-card'
        showFavicon={false}
        v-slots={{
          content: () => (
            <div class='ai-diagnostic-info-content'>
              <div class='ai-diagnostic-info-item'>
                <div class='info-item-label'>{this.t('告警原因：')}</div>
                <div class='info-item-content'>
                  被调接口 (trpc.cj.trpc2s.activitiyscvr/SendAwardSync) 服务所在主机 10.0.2.12 网络不通导致
                </div>
              </div>
              {incidentName ? (
                <div class='ai-diagnostic-info-item'>
                  <div class='info-item-label'>{this.t('关联故障：')}</div>
                  <div class='info-item-content'>
                    <span
                      class='link-text'
                      onClick={this.handleIncidentClick}
                    >
                      {incidentName}
                    </span>
                  </div>
                </div>
              ) : undefined}
              <div class='ai-diagnostic-info-item'>
                <div class='info-item-label'>{this.t('处置建议：')}</div>
                <div class='info-item-content'>重启服务器，或联系网络管理员检查服务器网络是否正常</div>
              </div>
              {this.bkFaraProcesses.length ? (
                <div class='ai-diagnostic-info-item'>
                  <div class='info-item-label'>{this.t('处理套餐：')}</div>
                  <div class='info-item-content fara-process-list'>
                    {this.bkFaraProcesses.map(item => (
                      <div
                        key={item.name}
                        class='fara-process'
                      >
                        <span
                          class={['fara-process-name', { 'link-text': Boolean(item.link) }]}
                          onClick={() => this.handleProcessClick(item)}
                        >
                          {item.name}
                        </span>
                        <span class='fara-process-meta'>
                          {`（${item.executeTime || '--'}，${item.executeResult || '--'}）`}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              ) : undefined}
            </div>
          ),
        }}
      />
    );
  },
});
