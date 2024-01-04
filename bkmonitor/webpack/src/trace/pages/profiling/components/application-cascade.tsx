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
import { defineComponent, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Form, Input, Popover } from 'bkui-vue';

import './application-cascade.scss';

export default defineComponent({
  name: 'ApplicationCascade',
  setup() {
    const { t } = useI18n();

    const showPopover = ref(false);
    function handlePopoverShowChange({ isShow }) {
      showPopover.value = isShow;
    }

    const localValue = reactive({
      first: 1,
      second: 1,
      hasData: true
    });
    function handleFirstClick(val) {
      localValue.first = val.id;
      localValue.hasData = val.children.length > 0;
    }
    function handleSecondClick(val) {
      localValue.first = val.id;
      localValue.hasData = false;
    }

    const list = {
      hasData: [
        { id: 1, name: 'app1', desc: 'app123', children: [{ id: 7, name: 'load-generator' }] },
        { id: 2, name: 'rideshare-app', desc: 'app123', children: [{ id: 8, name: 'ride-sharing-app' }] }
      ],
      noData: [
        { id: 3, name: 'nodata', desc: 'app123', children: [] },
        { id: 4, name: 'nodata2', desc: 'app123', children: [] }
      ]
    };

    return {
      t,
      list,
      showPopover,
      localValue,
      handleFirstClick,
      handleSecondClick,
      handlePopoverShowChange
    };
  },
  render() {
    return (
      <div class='application-cascade-component'>
        <Popover
          placement='bottom-start'
          arrow={false}
          theme='light application-cascade-popover'
          trigger='click'
          onAfterShow={val => this.handlePopoverShowChange(val)}
          onAfterHidden={val => this.handlePopoverShowChange(val)}
        >
          {{
            default: () => (
              <div class={['trigger-wrap', this.showPopover ? 'active' : '']}>
                <Input placeholder={this.t('选择应用/服务')}>
                  {{ suffix: () => <span class='icon-monitor icon-arrow-down'></span> }}
                </Input>
              </div>
            ),
            content: () => (
              <div class='application-cascade-popover-content'>
                <div class='search-wrap'>
                  <i class='icon-monitor icon-mc-search search-icon'></i>
                  <Input
                    class='search-input'
                    placeholder={this.t('输入关键字')}
                  ></Input>
                </div>
                <div class='select-wrap'>
                  <div class='first panel'>
                    <div class='group-title'>{this.t('有数据应用')}</div>
                    <div class='group-wrap'>
                      {this.list.hasData.map(item => (
                        <div
                          class={{ 'group-item': true, active: item.id === this.localValue.first }}
                          onClick={() => this.handleFirstClick(item)}
                          key={item.id}
                        >
                          <div class='left'>
                            <i class='icon-monitor icon-mc-menu-apm'></i>
                            <span class='name'>{item.name}</span>
                            <span class='desc'>{item.desc}</span>
                          </div>
                          <i class='icon-monitor icon-arrow-right'></i>
                        </div>
                      ))}
                    </div>
                    <div class='group-title'>{this.t('无数据应用')}</div>
                    {this.list.noData.map(item => (
                      <div
                        class={{ 'group-item': true, active: item.id === this.localValue.first }}
                        onClick={() => this.handleFirstClick(item)}
                      >
                        <i class='icon-monitor icon-mc-menu-apm'></i>
                        <span class='name'>{item.name}</span>
                      </div>
                    ))}
                  </div>
                  <div class='second panel'>
                    {this.localValue.hasData ? (
                      <div class='has-data-wrap'>
                        <div class='group-item active'>
                          <i class='icon-monitor icon-mc-grafana-home'></i>
                          <span class='name'>ride-sharing-app</span>
                        </div>
                        <div class='group-item'>
                          <i class='icon-monitor icon-mc-grafana-home'></i>
                          <span class='name'>ride-sharing-app</span>
                        </div>
                      </div>
                    ) : (
                      <div class='no-data-wrap'>
                        <Form labelWidth={100}>
                          <Form.FormItem label={this.t('应用名')}>trace_agg_scene</Form.FormItem>
                          <Form.FormItem label={this.t('应用别名')}>应用1</Form.FormItem>
                          <Form.FormItem label={this.t('描述')}>我是描述我是描述我是描述</Form.FormItem>
                          <Form.FormItem label='Token'>
                            <span class='password'>●●●●●●●●●●</span>
                            <Button
                              text
                              theme='primary'
                            >
                              {this.t('点击查看')}
                            </Button>
                          </Form.FormItem>
                        </Form>
                        <div class='btn'>
                          <span>{this.t('Profile 接入指引')}</span>
                          <i class='icon-monitor icon-fenxiang'></i>
                        </div>
                        <div class='btn'>
                          <span>{this.t('查看应用')}</span>
                          <i class='icon-monitor icon-fenxiang'></i>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
                <div class='footer-wrap'>
                  <div class='jump-btn'>
                    <i class='icon-monitor icon-jia'></i>
                    <span class=''>{this.t('新增接入')}</span>
                  </div>
                </div>
              </div>
            )
          }}
        </Popover>
      </div>
    );
  }
});
