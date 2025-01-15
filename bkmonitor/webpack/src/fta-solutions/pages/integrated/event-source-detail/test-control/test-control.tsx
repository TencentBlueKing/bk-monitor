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
import { Component, Emit, Model } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import Terminal from 'monitor-pc/pages/plugin-manager/plugin-instance/terminal-instance/terminal-instance';

import './test-control.scss';
/**
 * 测试控件
 */
@Component
export default class TestControl extends tsc<object> {
  @Model('show-change', { default: false, type: Boolean }) show;

  tableData = [
    { input: 'alertid', output: '告警名称：event_name' },
    { input: 'actionid', output: '业务：business_name' },
    { input: 'sendto', output: '目标：target' },
    { input: 'alerttype', output: '级别：serverity' },
    { input: 'eventid', output: '源事件ID：event_id' },
  ];

  @Emit('show-change')
  emitShow() {
    return !this.show;
  }

  protected render() {
    return (
      <div class={['test-control-wrap', { 'test-control-hidden': !this.show }]}>
        <div
          class='test-btn-wrap'
          onClick={this.emitShow}
        >
          {this.$t('测试')}
          <i class='icon-monitor icon-arrow-up' />
        </div>
        <div class='test-control-main'>
          <div class='test-control-content'>
            <div class='content-header'>
              <div class='header-title'>{this.$t('配置项编辑器')}</div>
              <div class='header-btn-wrap'>
                <div class='header-des'>{this.$t('最近10分钟没有获取到数据，请手动测试')}</div>
                <i class='icon-monitor icon-shuaxin' />
                <div class='header-run'>
                  <i class='icon-monitor icon-mc-triangle-down' />
                  {this.$t('执行')}
                </div>
              </div>
            </div>
            <div class='content-main'>
              <div
                class='content-main-left'
                v-monitor-drag={{ minWidth: 100, maxWidth: 868, theme: 'simple' }}
              >
                <Terminal animation={false} />
              </div>
              <div class='content-main-right'>
                <div class='main-right-title'>{this.$t('标准化结果')}</div>
                <table class='right-result-table'>
                  <tbody>
                    <tr>
                      <th class='label'>INPUT</th>
                      <th class='label' />
                      <th class='label'>OUTPUT</th>
                    </tr>
                    {this.tableData.map(item => (
                      <tr>
                        <td class='value'>{item.input}</td>
                        <td class='value gt'>&gt;&gt;</td>
                        <td class='value'>{item.output}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
