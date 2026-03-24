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

import './log-panel.scss';

export default defineComponent({
  name: 'LogPanel',
  render() {
    return (
      <div class='suspicious-log-panel'>
        <div class='log-group-list'>
          <SuspiciousAnalysisGroup>
            {{
              title: () => (
                <div class='group-title'>
                  <span class='group-name'>日志内容摘要</span>
                  <span
                    class='link-text'
                    onClick={e => {
                      e.stopPropagation();
                    }}
                  >
                    <i class='icon-monitor icon-xiangqing1' />
                    日志详情
                  </span>
                </div>
              ),
              default: () => (
                <AnalysisDetailContent
                  contentData={[
                    {
                      title: '运维视角分析',
                      value: [
                        '这条日志表明在指定时间，systemd 系统管理器启动了一个新的会话(session 723423)，并且这个会话是以 root 用户身份运行的。这是一个正常的系统操作日志，通常用于记录用户登录或系统服务的启动。',
                      ],
                    },
                    {
                      title: '研发视角分析',
                      value: [
                        '从研发的角度看，这条日志显示了一个新的会话被创建，可能是由于用户登录或者某个需要 root 权限的服务启用。这本身是一个正常的操作，不需要特别的关心。',
                      ],
                    },
                    {
                      title: '结论',
                      value: [
                        '这条日志记录的是一个正常的系统事件，即一个新的会话被创建并且是以 root 用户身份运行的。没有发现任何异常或错误信息。',
                      ],
                    },
                  ]}
                  tableData={[
                    { name: '服务器IP', value: '10.0.34.2' },
                    { name: '时间戳', value: '172234452（对应时间 2024年4月20日 19:22:02）' },
                    { name: '主机ID', value: '603242' },
                    { name: '日志路径', value: '/var/log/messages' },
                    { name: '日志信息', value: 'systemd: Started Session 2334 of user root' },
                  ]}
                />
              ),
            }}
          </SuspiciousAnalysisGroup>
        </div>
      </div>
    );
  },
});
