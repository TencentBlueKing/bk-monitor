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

import AnalysisDetailContent from './analysis-detail-content';
import SuspiciousAnalysisGroup from './suspicious-analysis-group';

import './metric-panel.scss';

export default defineComponent({
  name: 'MetricPanel',
  render() {
    return (
      <div class='suspicious-metric-panel'>
        <div class='tips'>
          下面这些指标维度，在过去时间里产生过相似的告警事件，希望能够帮助您进一步分析告警可能原因。
        </div>
        <div class='metric-group-list'>
          <SuspiciousAnalysisGroup>
            {{
              title: () => (
                <div class='group-title'>
                  <span class='group-name'>指标：证书剩余天数（cert_shengyu_days）</span>
                  <span
                    class='link-text detail-link'
                    onClick={e => {
                      e.stopPropagation();
                    }}
                  >
                    <i class='icon-monitor icon-zhibiaojiansuo' />
                    指标检索
                  </span>
                </div>
              ),
              default: () => (
                <AnalysisDetailContent
                  tableData={[
                    { name: '主机名', value: 'VM-156-110-centos' },
                    { name: '目标IP', value: '11.185.157.110' },
                    { name: '管控区域', value: '0' },
                  ]}
                  contentData={[]}
                />
              ),
              footer: () => (
                <div class='footer-content'>
                  <span class='reason'>
                    可疑原因：在（2025-04-16 00:00:00 ～ 2025-04-17 00:00:00）时间段内，告警产生具有相似性。
                  </span>
                </div>
              ),
            }}
          </SuspiciousAnalysisGroup>
        </div>
      </div>
    );
  },
});
