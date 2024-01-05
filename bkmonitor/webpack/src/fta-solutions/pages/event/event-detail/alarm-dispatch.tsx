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

import { assignAlert } from '../../../../monitor-api/modules/action';
import { getNoticeWay } from '../../../../monitor-api/modules/notice_group';

import './alarm-dispatch.scss';

const reasonList = [window.i18n.tc('当前工作安排较多'), window.i18n.tc('不在职责范围内'), window.i18n.tc('无法处理')];

interface IProps {
  show?: boolean;
  alertIds?: (string | number)[];
  bizIds?: (string | number)[];
}
interface IEvents {
  onShow?: boolean;
  onSuccess?: { ids: string[]; users: string[] };
}
@Component
export default class AlarmDispatch extends tsc<IProps, IEvents> {
  @Prop({ default: false, type: Boolean }) show: boolean;
  @Prop({ default: () => [], type: Array }) alertIds: (string | number)[];
  @Prop({ default: () => [], type: Array }) bizIds: (string | number)[];

  users = [];
  noticeWay = [];
  noticeWayList: { label: string; type: string }[] = [];
  reason = '';
  loading = false;

  errorMsg = {
    reason: '',
    users: '',
    notice: ''
  };

  get bkUrl() {
    return `${window.site_url}rest/v2/commons/user/list_users/`;
  }

  @Watch('show')
  async handleShow(v: boolean) {
    if (v) {
      this.loading = true;
      this.handleFocus();
      await this.getNoticeWayList();
      this.loading = false;
    }
  }

  /* 通知方式列表 */
  async getNoticeWayList() {
    if (!this.noticeWayList.length) {
      this.noticeWayList = await getNoticeWay()
        .then(data => data.filter(item => item.type !== 'wxwork-bot'))
        .catch(() => []);
      const noticeWays = this.noticeWayList.map(item => item.type);
      this.noticeWay = this.noticeWay.filter(type => noticeWays.includes(type));
    }
  }

  handleTagClick(tag: string) {
    if (this.reason) {
      this.reason += `，${tag}`;
    } else {
      this.reason += tag;
    }
  }

  handleCancel() {
    this.$emit('show', false);
  }

  async handleSubmit() {
    const validate = this.validator();
    if (validate) {
      // submit
      this.loading = true;
      const data = await assignAlert({
        bk_biz_id: this.bizIds?.[0] || this.$store.getters.bizId,
        alert_ids: this.alertIds,
        appointees: this.users,
        reason: this.reason,
        notice_ways: this.noticeWay
      }).catch(() => null);
      if (data) {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('分派成功')
        });
        this.handleCancel();
        this.handleSuccess();
      }
      this.loading = false;
    }
  }

  @Emit('success')
  handleSuccess() {
    return {
      ids: this.alertIds,
      users: this.users
    };
  }

  validator() {
    if (!this.users.length) {
      this.errorMsg.users = this.$t('输入分派人员') as string;
      return false;
    }
    if (!this.reason) {
      this.errorMsg.reason = this.$t('输入分派原因') as string;
      return false;
    }
    if (!this.noticeWay.length) {
      this.errorMsg.notice = this.$t('选择通知方式') as string;
      return false;
    }
    return true;
  }

  handleFocus() {
    this.errorMsg = {
      reason: '',
      users: '',
      notice: ''
    };
  }

  render() {
    return (
      <bk-dialog
        extCls={'alarm-dispatch-component-dialog'}
        value={this.show}
        width={480}
        mask-close={true}
        header-position='left'
        title={this.$t('告警分派')}
        on-cancel={() => this.$emit('show', false)}
      >
        <div
          class='alarm-dispatch'
          v-bkloading={{ isLoading: this.loading }}
        >
          <div class='tips'>
            <span class='icon-monitor icon-hint'></span>
            {this.$t('您一共选择了{0}条告警', [this.alertIds.length])}
          </div>
          <div class='form-item'>
            <div class='label require'>{this.$t('分派人员')}</div>
            <div
              class='content'
              onClick={this.handleFocus}
            >
              <BkUserSelector
                class='content-user-selector'
                v-model={this.users}
                api={this.bkUrl}
                placeholder={this.$t('输入用户')}
                empty-text={this.$t('搜索结果为空')}
              ></BkUserSelector>
            </div>
            {!!this.errorMsg.users && <div class='err-msg'>{this.errorMsg.users}</div>}
          </div>
          <div class='form-item'>
            <div class='label'>
              <div class='title require'>{this.$t('分派原因')}</div>
              <div class='tags'>
                {reasonList.map(tag => (
                  <span
                    class='tag'
                    onClick={() => this.handleTagClick(tag)}
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </div>
            <div
              class='content mr0'
              onClick={this.handleFocus}
            >
              <bk-input
                v-model={this.reason}
                type={'textarea'}
                row={3}
                maxlength={100}
              ></bk-input>
            </div>
            {!!this.errorMsg.reason && <div class='err-msg'>{this.errorMsg.reason}</div>}
          </div>
          <div class='form-item'>
            <div class='label require'>{this.$t('通知方式')}</div>
            <div
              class='content'
              onClick={this.handleFocus}
            >
              <bk-checkbox-group v-model={this.noticeWay}>
                {this.noticeWayList.map(item => (
                  <bk-checkbox value={item.type}>{item.label}</bk-checkbox>
                ))}
              </bk-checkbox-group>
            </div>
            {!!this.errorMsg.notice && <div class='err-msg'>{this.errorMsg.notice}</div>}
          </div>
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            style={{ 'margin-right': '8px' }}
            onClick={this.handleSubmit}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
        </div>
      </bk-dialog>
    );
  }
}
