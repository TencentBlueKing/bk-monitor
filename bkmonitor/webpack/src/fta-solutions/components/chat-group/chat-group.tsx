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
import BkUserSelector from '@blueking/user-selector';

import { createChatGroup } from '../../../monitor-api/modules/action';

import './chat-group.scss';

interface IChatGroupProps {
  show?: boolean;
  alarmEventName?: string;
  assignee: string[];
  alertIds: string[];
}
interface IChatGroupEvent {
  onShowChange?: boolean;
}

@Component
export default class ChatGroup extends tsc<IChatGroupProps, IChatGroupEvent> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  // 单个告警事件名称
  @Prop({ type: String, default: '' }) alarmEventName: string;
  // 告警关注人
  @Prop({ type: Array, default: [] }) assignee: string[];
  // 告警ID列表
  @Prop({ type: Array, default: [] }) alertIds: string[];

  isLoading = false;
  isHandler = true; // 告警处理人
  isAlarmLink = false; // 告警事件链接
  isAlarmEvents = false; // 告警事件内容
  isAlarmAnalyze = false; // 告警分析内容
  localValue = [];
  contentType = [];

  @Emit('showChange')
  handleShowChange(v: boolean) {
    return v;
  }

  get bkUrl() {
    // return '/rest/v2/commons/user/list_users/';
    return `${window.site_url}rest/v2/commons/user/list_users/`;
  }

  get title() {
    return this.alertIds.length > 1
      ? this.$t('已经选择了{0}个告警事件,将通过企业微信将相关人员邀请到一个群里面进行讨论', [this.alertIds.length])
      : this.$t('已经选择了{0}告警事件,将通过企业微信将相关人员邀请到一个群里面进行讨论', [this.alarmEventName]);
  }

  @Watch('show')
  handleChangeShow(v: boolean) {
    if (v) {
      if (this.alertIds.length > 1) {
        this.contentType = ['detail_url'];
      } else {
        this.contentType = ['alarm_content'];
      }
      this.localValue.splice(0, this.localValue.length, ...this.assignee);
    }
  }

  handleConfirm() {
    const params = {
      bk_biz_id: this.$store.getters.bizId,
      alert_ids: this.alertIds,
      content_type: this.contentType,
      chat_members: this.localValue
    };
    this.isLoading = true;
    createChatGroup(params)
      .then(data => {
        if (data) {
          this.$bkMessage({
            message: this.$t('拉群成功'),
            theme: 'success'
          });
          this.handleShowChange(false);
        }
      })
      .finally(() => (this.isLoading = false));
  }

  render() {
    return (
      <bk-dialog
        ext-cls='chat-group-dialog-wrap'
        value={this.show}
        mask-close={true}
        header-position='left'
        width={640}
        title={this.$t('一键拉群')}
        on-value-change={this.handleShowChange}
      >
        <div class='header'>
          {/* eslint-disable-next-line @typescript-eslint/no-require-imports */}
          <img
            src={require('../../static/img/we-com.svg')}
            alt=''
          />
          <span>{this.title}</span>
        </div>
        <div class='content'>
          <p class='title'>{this.$t('群聊邀请')}</p>
          <div class='checkbox-group'>
            <bk-checkbox
              value={true}
              disabled
            >
              {this.$t('告警关注人')}
            </bk-checkbox>
            {/* <bk-checkbox value={this.isHandler}>{this.$t('告警处理人')}</bk-checkbox> */}
          </div>
          <BkUserSelector
            class='bk-user-selector'
            v-model={this.localValue}
            api={this.bkUrl}
          />
          <div class='checkbox-group'>
            <bk-checkbox-group v-model={this.contentType}>
              <bk-checkbox value={'detail_url'}>{this.$t('告警事件链接')}</bk-checkbox>
              <bk-checkbox value={'alarm_content'}>{this.$t('告警事件内容')}</bk-checkbox>
              {/* <bk-checkbox value={''}>{this.$t('告警分析内容')}</bk-checkbox> */}
            </bk-checkbox-group>
          </div>
        </div>
        <template slot='footer'>
          <bk-button
            onClick={() => this.handleConfirm()}
            disabled={!this.localValue.length || !this.contentType.length}
            theme='primary'
            loading={this.isLoading}
            style='margin-right: 10px'
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button onClick={() => this.handleShowChange(false)}>{this.$t('取消')}</bk-button>
        </template>
      </bk-dialog>
    );
  }
}
