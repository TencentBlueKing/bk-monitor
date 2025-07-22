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
import { Component, Prop, InjectReactive } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from 'monitor-common/utils/utils';
import { deepClone } from 'monitor-common/utils/utils';
import TemporaryShare from 'monitor-pc/components/temporary-share/temporary-share';

import ChatGroup from '../../../components/chat-group/chat-group';
import Feedback from './feedback';

import type { IChatGroupDialogOptions } from '../typings/event';
import type { IDetail } from './type';

import './event-detail-head.scss';

interface EventDetailHeadProps {
  basicInfo: IDetail;
  eventId: string;
  bizId: number;
  isFeedback?: boolean;
  isNewPage?: boolean;
}

interface IEvent {
  onConfirm?: boolean;
}

@Component({
  name: 'EventDetailHead',
})
export default class EventDetailHead extends tsc<EventDetailHeadProps, IEvent> {
  @Prop({ default: '', type: [String, Number] }) eventId: string;
  @Prop({ type: [Number, String], default: +window.bk_biz_id }) bizId: number;
  @Prop({ type: Object, default: () => ({}) }) basicInfo: IDetail;
  /** 是否已反馈 */
  @Prop({ type: Boolean, default: true }) isFeedback: boolean;
  /** 是否支持打开新页面 */
  @Prop({ type: Boolean, default: false }) isNewPage: boolean;
  // 是否是只读模式
  @InjectReactive('readonly') readonly readonly: boolean;
  /** 一键拉群弹窗 */
  chatGroupDialog: IChatGroupDialogOptions = {
    show: false,
    alertName: '',
    alertIds: [],
    assignee: [],
  };
  feedbackDialog = false;
  // 是否支持一键拉群 todo
  get enableCreateChatGroup() {
    return !!window.enable_create_chat_group;
  }
  /** 右侧操作按钮 */
  get btnGroupObject() {
    return [
      {
        title: window.i18n.tc('拉群'),
        icon: 'icon-we-com',
        handleFn: () => this.handleChatGroup(),
        isShow: this.enableCreateChatGroup,
      },
      {
        title: this.isFeedback ? window.i18n.tc('已反馈') : window.i18n.tc('反馈'),
        icon: 'icon-a-FeedBackfankui',
        handleFn: () => this.handleFeedback(true),
        isShow: true,
      },
      {
        title: window.i18n.tc('新开页'),
        icon: 'icon-a-NewPagexinkaiye',
        handleFn: () => this.handleToEventDetail('detail', true),
        isShow: this.isNewPage,
      },
    ];
  }

  /** 策略详情跳转 */
  toStrategyDetail() {
    // 如果 告警来源 是监控策略就要跳转到 策略详情 。
    if (this.basicInfo.plugin_id === 'bkmonitor') {
      window.open(
        `${location.origin}${location.pathname}?bizId=${this.basicInfo.bk_biz_id}/#/strategy-config/detail/${this.eventId}?fromEvent=true`
      );
    } else if (this.basicInfo.plugin_id) {
      // 否则都新开一个页面并添加 告警源 查询，其它查询项保留。
      const query = deepClone(this.$route.query);
      query.queryString = `告警源 : "${this.basicInfo.plugin_id}"`;
      const queryString = new URLSearchParams(query).toString();
      window.open(`${location.origin}${location.pathname}${location.search}/#/event-center?${queryString}`);
    }
  }
  // 告警级别标签
  getTagComponent(severity) {
    const level = {
      1: { label: this.$t('致命'), className: 'level-tag-fatal', icon: 'icon-danger' },
      2: { label: this.$t('预警'), className: 'level-tag-warning', icon: 'icon-mind-fill' },
      3: { label: this.$t('提醒'), className: 'level-tag-info', icon: 'icon-tips' },
    };
    const className = severity ? level[severity].className : '';
    const label = severity ? level[severity].label : '';
    return (
      <div class={['level-tag', className]}>
        <i class={`icon-monitor ${level[severity]?.icon} sign-icon`} />
        {label}
      </div>
    );
  }
  // 复制事件详情连接
  handleToEventDetail(type: 'action-detail' | 'detail', isNewPage = false) {
    let url = location.href.replace(location.hash, `#/event-center/${type}/${this.eventId}`);
    const { bizId } = this.$store.getters;
    url = url.replace(location.search, `?bizId=${this.bizId || bizId}`);
    if (isNewPage) {
      window.open(url);
      return;
    }
    copyText(url, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }
  /**
   * @description: 一键拉群
   * @return {*}
   */
  handleChatGroup() {
    this.chatGroupDialog.assignee = this.basicInfo.assignee || [];
    this.chatGroupDialog.alertName = this.basicInfo.alert_name;
    this.chatGroupDialog.alertIds.splice(0, this.chatGroupDialog.alertIds.length, this.basicInfo.id);
    this.chatGroupShowChange(true);
  }
  /**
   * @description: 一键拉群弹窗关闭/显示
   * @param {boolean} show
   * @return {*}
   */
  chatGroupShowChange(show: boolean) {
    this.chatGroupDialog.show = show;
  }
  /* 反馈 */
  handleFeedback(v: boolean) {
    this.feedbackDialog = v;
  }
  handleFeedBackConfirm() {
    this.isFeedback = true;
  }

  render() {
    const { severity, alert_name } = this.basicInfo;
    return (
      <div class='event-detail-head-main'>
        {this.getTagComponent(severity)}
        <div class='event-detail-head-content'>
          <span class='event-id'>
            ID: {this.eventId}
            {window.source_app === 'fta' ? (
              <i
                class='icon-monitor icon-copy-link'
                onClick={() => this.handleToEventDetail('detail')}
              />
            ) : (
              <TemporaryShare
                customData={{ eventId: this.eventId }}
                navMode={'share'}
                pageInfo={{ alertName: alert_name }}
              />
            )}
          </span>
          {alert_name ? (
            <span
              class='basic-title-name'
              v-bk-tooltips={{ content: alert_name, allowHTML: false, placements: ['bottom'] }}
            >
              {alert_name}
            </span>
          ) : (
            <div class='skeleton-element' />
          )}

          {!this.readonly && this.basicInfo.plugin_id ? (
            <span
              class='btn-strategy-detail'
              onClick={this.toStrategyDetail}
            >
              <span>{this.$t('来源：{0}', [this.basicInfo.plugin_display_name])}</span>
              <i class='icon-monitor icon-fenxiang icon-float' />
            </span>
          ) : undefined}
        </div>
        <div class='event-detail-head-btn-group'>
          {this.btnGroupObject
            .filter(item => item.isShow)
            .map(item => (
              <div
                class='btn-group-item'
                onClick={item.handleFn}
              >
                <span class={`icon-monitor btn-item-icon ${item.icon}`} />
                <span class='btn-text'>{item.title}</span>
              </div>
            ))}
        </div>
        <ChatGroup
          alarmEventName={this.chatGroupDialog.alertName}
          alertIds={this.chatGroupDialog.alertIds}
          assignee={this.chatGroupDialog.assignee}
          show={this.chatGroupDialog.show}
          onShowChange={this.chatGroupShowChange}
        />
        <Feedback
          key='feedback'
          ids={[this.basicInfo.id]}
          show={this.feedbackDialog}
          onChange={this.handleFeedback}
          onConfirm={this.handleFeedBackConfirm}
        />
      </div>
    );
  }
}
