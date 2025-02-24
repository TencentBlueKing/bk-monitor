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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { resize } from 'monitor-pc/components/ip-selector/common/observer-directive';

import type { IInfo } from './types';

import './troubleshooting-collapse.scss';

interface IProps {
  layoutActive?: number;
  needLayout?: boolean;
  showCollapse?: boolean;
  title?: string;
  info?: IInfo;
}

@Component({
  directives: {
    resize,
  },
})
export default class AiopsTroubleshootingCollapse extends tsc<IProps> {
  infoConfig = {
    alert_name: {
      label: '故障名称',
      // renderFn: severity => getSeverity(severity)
    },
    status: {
      label: '故障状态',
      // renderFn: status => (
      //   <span class={`info-status ${status}`}>
      //     <i class={`icon-monitor icon-${TREE_SHOW_ICON_LIST.status[status]}`} />
      //     {statusEnum.value[status]}
      //   </span>
      // ),
    },
    time: { label: '持续时间' },
    bk_biz_name: { label: '影响业务' },
    metric: { label: '故障总结' },
    assignee: { label: '处置指引' },
  };
  detail = {
    alert_name: 'alert_name',
    status: 'status',
    time: 'time',
    bk_biz_name: 'bk_biz_name',
    metric: '根因和影响范围（结合图谱的实体回答：服务、模块），触发告警情况文本文本文本文本。',
    assignee: '该故障内您共有 3 个未恢复告警待处理，建议处理指引XXXXXXXXX XXXXXXX。',
  };
  render() {
    return (
      <div class='aiops-troubleshooting'>
        <div class='aiops-troubleshooting-info'>
          <div class='info-title'>{this.$t('故障详情')}</div>
          {Object.keys(this.infoConfig).map(key => {
            const info = this.infoConfig[key];
            return (
              <div
                key={key}
                class='info-item'
              >
                <span class='info-label'>{this.$t(info.label)}：</span>
                <span class='info-txt'>
                  {info?.renderFn ? info.renderFn(this.detail[key]) : this.detail[key] || '--'}
                </span>
              </div>
            );
          })}
        </div>
        <div class='aiops-troubleshooting-topo'></div>
      </div>
    );
  }
}
