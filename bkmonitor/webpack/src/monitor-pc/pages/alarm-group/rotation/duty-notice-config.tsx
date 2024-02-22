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
import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SetMealAddStore from '../../../../fta-solutions/store/modules/set-meal-add';
import { isEnFn } from '../../../utils/index';
import SimpleDayPick from '../duty-arranges/simple-day-pick';

import { IDutyListItem } from './typing';

import './duty-notice-config.scss';

const typeList = [
  { label: window.i18n.t('按周'), value: 'week' },
  { label: window.i18n.t('按月'), value: 'month' }
];
const timeTypeList = [
  { label: isEnFn() ? 'Week(s)' : '周', value: 'week' },
  { label: isEnFn() ? 'Day(s)' : '天', value: 'day' }
];

const weekList = [
  { label: window.i18n.t('周一'), value: 1 },
  { label: window.i18n.t('周二'), value: 2 },
  { label: window.i18n.t('周三'), value: 3 },
  { label: window.i18n.t('周四'), value: 4 },
  { label: window.i18n.t('周五'), value: 5 },
  { label: window.i18n.t('周六'), value: 6 },
  { label: window.i18n.t('周日'), value: 7 }
];

/**
 * @description 默认表单数据
 * @returns
 */
export const initData = () => ({
  isSend: false,
  sendType: 'week',
  week: 1,
  month: 1,
  sendTime: '00:00',
  nearDay: 7,
  rtxId: '',
  needNotice: false,
  startNum: 1,
  timeType: 'week',
  rotationId: []
});

interface IProps {
  renderKey?: string;
  value?: any;
  dutyList?: IDutyListItem[];
  onChange?: (_v) => void;
}

@Component
export default class DutyNoticeConfig extends tsc<IProps> {
  @Prop({ default: '', type: String }) renderKey: string;
  @Prop({ default: () => initData(), type: Object }) value;
  @Prop({ default: () => [], type: Array }) dutyList: IDutyListItem[];

  formData = initData();

  errrMsg = {
    sendTime: '',
    sendContent: '',
    sendChat: '',
    rules: ''
  };

  get chatTipName() {
    const name = SetMealAddStore.noticeWayList.find(item => item.type === 'wxwork-bot')?.name || '';
    return name;
  }

  /**
   * @description 初始化
   */
  created() {
    this.formData = { ...this.value };
  }

  /**
   * @description 更新数据
   */
  @Watch('renderKey')
  handleWatch() {
    this.formData = { ...this.value };
  }
  @Emit('change')
  handleChange() {
    Object.keys(this.errrMsg).forEach(key => {
      this.errrMsg[key] = '';
    });
    return this.formData;
  }

  validate() {
    return new Promise((resolve, _reject) => {
      if (this.formData.isSend) {
        if (!this.formData.rtxId) {
          this.errrMsg.sendChat = this.$t('请输入企业微信群ID') as string;
        }
        if ((this.formData.rtxId || '').split(',').some(str => str.length !== 32)) {
          this.errrMsg.sendChat = this.$t('请确保企业微信群ID为32个字符') as string;
        }
        if (!this.formData.sendTime) {
          this.errrMsg.sendTime = this.$t('请输入发送时间') as string;
        }
      }
      if (this.formData.needNotice) {
        if (!this.formData.rotationId.length) {
          this.errrMsg.rules = this.$t('请输入轮值规则') as string;
        }
      }
      resolve(!Object.keys(this.errrMsg).some(key => !!this.errrMsg[key]));
    });
  }

  render() {
    function formItemBig(label: string | any, content: any, cls?: string) {
      return (
        <div class={['form-item-big', cls]}>
          <span class='form-item-label'>{label}</span>
          <span class='form-item-content'>{content}</span>
        </div>
      );
    }
    function formItem(label: string | any, content: any, cls?: string, err?) {
      return (
        <div class={['form-item', cls]}>
          <span class={['form-item-label', { en: isEnFn() }]}>{label}</span>
          <div>
            <span class='form-item-content'>{content}</span>
            {!!err && <div class='err-msg'>{err}</div>}
          </div>
        </div>
      );
    }
    return (
      <div class='rotation-config-duty-notice-config'>
        {formItemBig(
          this.$t('排班表发送'),
          <bk-switcher
            v-model={this.formData.isSend}
            size='small'
            theme='primary'
            onChange={() => this.handleChange()}
          ></bk-switcher>
        )}
        {formItem(
          this.$t('发送时间'),
          [
            <bk-select
              v-model={this.formData.sendType}
              clearable={false}
              class='mr-8'
              onChange={() => this.handleChange()}
            >
              {typeList.map(item => (
                <bk-option
                  key={item.value}
                  id={item.value}
                  name={item.label}
                ></bk-option>
              ))}
            </bk-select>,
            this.formData.sendType === 'week' ? (
              <bk-select
                v-model={this.formData.week}
                class='width-200 mr-8'
                clearable={false}
                onChange={() => this.handleChange()}
              >
                {weekList.map(item => (
                  <bk-option
                    key={item.value}
                    id={item.value}
                    name={item.label}
                  ></bk-option>
                ))}
              </bk-select>
            ) : (
              <SimpleDayPick
                multiple={false}
                class='width-200 mr-8'
                value={this.formData.month as any}
                onChange={v => {
                  this.formData.month = v as any;
                  this.handleChange();
                }}
              ></SimpleDayPick>
            ),
            <bk-time-picker
              class='width-200'
              v-model={this.formData.sendTime}
              format={'HH:mm'}
              onChange={() => {
                setTimeout(() => {
                  this.handleChange();
                }, 100);
              }}
            ></bk-time-picker>
          ],
          'mt-16',
          this.errrMsg.sendTime
        )}
        {formItem(
          this.$t('发送内容'),
          [
            <bk-input
              v-model={this.formData.nearDay}
              class='width-148 mr-8'
              type='number'
              min={0}
              onInput={() => this.handleChange()}
            >
              <div
                slot='prepend'
                class='input-left'
              >
                {this.$t('未来')}
              </div>
            </bk-input>,
            <span class='content-text'>{this.$t('天的排班结果')}</span>
          ],
          'mt-16',
          this.errrMsg.sendContent
        )}
        {formItem(
          this.$t('企业微信群ID'),
          [
            <bk-input
              class='width-488 mr-12'
              v-model={this.formData.rtxId}
              onChange={() => this.handleChange()}
            ></bk-input>,
            <span
              class='icon-monitor icon-tips'
              v-bk-tooltips={{
                content: this.$t(
                  "获取会话ID方法:<br/>1.群聊列表右键添加群机器人: {name}<br/>2.手动 @{name} 并输入关键字'会话ID'<br/>3.将获取到的会话ID粘贴到输入框，使用逗号分隔",
                  { name: this.chatTipName }
                ),
                boundary: 'window',
                placements: ['top'],
                allowHTML: true
              }}
            ></span>
          ],
          'mt-16',
          this.errrMsg.sendChat
        )}
        {formItemBig(
          this.$t('个人轮值通知'),
          <bk-switcher
            v-model={this.formData.needNotice}
            size='small'
            theme='primary'
            onChange={() => this.handleChange()}
          ></bk-switcher>,
          'mt-24'
        )}
        {formItem(
          this.$t('值班开始前'),
          [
            <bk-input
              v-model={this.formData.startNum}
              class='mr-8 width-168'
              type='number'
              min={0}
              onInput={() => this.handleChange()}
            >
              <div
                slot='append'
                class='input-right-select'
              >
                <bk-select
                  v-model={this.formData.timeType}
                  clearable={false}
                  onChange={() => this.handleChange()}
                >
                  {timeTypeList.map(item => (
                    <bk-option
                      key={item.value}
                      id={item.value}
                      name={item.label}
                    ></bk-option>
                  ))}
                </bk-select>
              </div>
            </bk-input>,
            <span class='content-text'>{this.$t('收到通知')}</span>
          ],
          'mt-16'
        )}
        {formItem(
          this.$t('指定轮值规则'),
          <bk-select
            class='width-305'
            v-model={this.formData.rotationId}
            multiple
            clearable={false}
            searchable
            onChange={() => this.handleChange()}
          >
            {this.dutyList.map(item => (
              <bk-option
                id={item.id}
                key={item.id}
                name={item.name}
              >
                <span>{item.name}</span>
                <span
                  style={{
                    'margin-left': '8px',
                    color: '#c4c6cc'
                  }}
                >
                  {item.category === 'regular' ? this.$t('固定值班') : this.$t('交替轮值')}
                </span>
              </bk-option>
            ))}
          </bk-select>,
          'mt-16',
          this.errrMsg.rules
        )}
      </div>
    );
  }
}
