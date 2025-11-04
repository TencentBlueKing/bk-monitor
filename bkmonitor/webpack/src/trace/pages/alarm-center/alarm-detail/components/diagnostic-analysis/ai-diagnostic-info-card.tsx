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
import { defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import AiHighlightCard from '../../../components/ai-highlight-card/ai-highlight-card';

import './ai-diagnostic-info-card.scss';
export default defineComponent({
  name: 'AiDiagnosticInfo',
  setup() {
    const { t } = useI18n();

    return {
      t,
    };
  },
  render() {
    return (
      <AiHighlightCard
        class='ai-diagnostic-info-card'
        v-slots={{
          content: () => (
            <div class='ai-diagnostic-info-content'>
              <div class='ai-diagnostic-info-item'>
                <div class='info-item-label'>{this.t('告警问题：')}</div>
                <div class='info-item-content'>
                  当前服务 (activity-microservices.msgcenter) 调用接口(trpc.cj.trpc2s.activitiyscvr/SendAwardSync)
                  的成功率为 <span class='bold'>65%</span>
                </div>
              </div>
              <div class='ai-diagnostic-info-item'>
                <div class='info-item-label'>{this.t('告警原因：')}</div>
                <div class='info-item-content'>
                  被调接口 (trpc.cj.trpc2s.activitiyscvr/SendAwardSync) 服务所在主机 10.0.2.12 网络不通导致
                </div>
              </div>
              <div class='ai-diagnostic-info-item'>
                <div class='info-item-label'>{this.t('关联故障：')}</div>
                <div class='info-item-content'>
                  <span class='link-text'>【Pod】BcsPod(activity-10111-deployment-bys)引起的故障</span>
                </div>
              </div>
              <div class='ai-diagnostic-info-item'>
                <div class='info-item-label'>{this.t('处理建议：')}</div>
                <div class='info-item-content'>我是一个文本占位</div>
              </div>
              <div class='ai-diagnostic-info-item'>
                <div class='info-item-label'>{this.t('处理经验：')}</div>
                <div class='info-item-content'>重启服务器 或 联系驻场维修检查服务器网络是否正常</div>
              </div>
            </div>
          ),
        }}
        faviconSize={32}
        title={`${this.t('诊断概率：85%')}：`}
      />
    );
  },
});
