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

import { copyText } from 'monitor-common/utils/utils';

import ActionDetail from './action-detail';
import EventDetail from './event-detail';
import EventDetailHead from './event-detail-head';

import type { IDetail } from './type';

import './event-detail-slider.scss';

// 事件详情 | 处理记录详情
export type TType = 'eventDetail' | 'handleDetail';
interface IEvent {
  onShowChange?: boolean;
}

interface IEventDetailSlider {
  activeTab?: string;
  bizId: number;
  eventId: string;
  isShow?: boolean;
  type: TType;
}

@Component
export default class EventDetailSlider extends tsc<IEventDetailSlider, IEvent> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: String, default: '' }) eventId: string;
  @Prop({ type: String, default: '' }) activeTab: string;
  @Prop({ type: [Number, String], default: +window.bk_biz_id }) bizId: number;
  @Prop({ default: 'eventDetail', validator: v => ['eventDetail', 'handleDetail'].includes(v) }) type: TType;

  loading = false;
  detailInfo: IDetail = {
    id: '', // 告警id
    bk_biz_id: 0, // 业务id
    alert_name: '', // 告警名称
    first_anomaly_time: 0, // 首次异常事件
    begin_time: 0, // 事件产生事件
    create_time: 0, // 告警产生时间
    is_ack: false, // 是否确认
    is_shielded: false, // 是否屏蔽
    is_handled: false, // 是否已处理
    dimension: [], // 维度信息
    severity: 0, // 严重程度
    status: '',
    description: '', //
    alert_info: {
      count: 0,
      empty_receiver_count: 0,
      failed_count: 0,
      partial_count: 0,
      shielded_count: 0,
      success_count: 0,
    },
    duration: '',
    dimension_message: '',
    overview: {}, // 处理状态数据
    assignee: [],
  };
  /* 是否已反馈 */
  isFeedback = false;

  alertName = '';
  init = false;
  get width() {
    return this.type === 'handleDetail' ? 956 : 1280; // 1047;
  }
  mounted() {
    this.init = true;
  }
  @Emit('showChange')
  emitIsShow(v: boolean) {
    return v;
  }

  // 隐藏详情
  handleHiddenSlider() {
    this.emitIsShow(false);
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

  // 作为新页面打开
  newPageBtn(type: 'action-detail' | 'detail') {
    return (
      <span
        class='new-page-btn'
        onClick={() => this.handleToEventDetail(type, true)}
      >
        <span class='btn-text'>{this.$t('新开页')}</span>
        <span class='icon-monitor icon-fenxiang' />
      </span>
    );
  }

  handleInfo(v, isFeedback) {
    this.detailInfo = v;
    this.isFeedback = isFeedback;
    this.alertName = v.alert_name;
  }

  // 标题
  tplTitle() {
    const tplMap = {
      eventDetail: () => (
        <EventDetailHead
          basicInfo={this.detailInfo}
          bizId={this.bizId}
          eventId={this.eventId}
          isFeedback={this.isFeedback}
          isNewPage={true}
        />
      ),
      handleDetail: () => (
        <div class='title-wrap'>
          <span>{this.$t('处理记录详情')}</span>
          <i
            class='icon-monitor icon-copy-link'
            onClick={() => this.handleToEventDetail('action-detail')}
          />
          {this.newPageBtn('action-detail')}
        </div>
      ),
    };
    return tplMap[this.type]();
  }

  // 内容
  tplContent() {
    const tplMap = {
      eventDetail: () => (
        <EventDetail
          id={this.eventId}
          class='event-detail-content'
          activeTab={this.activeTab}
          bizId={this.bizId}
          isShowHead={false}
          onCloseSlider={() => this.emitIsShow(false)}
          onInfo={this.handleInfo}
        />
      ),
      handleDetail: () => (
        <ActionDetail
          id={this.eventId}
          bizId={this.bizId}
        />
      ),
    };
    return tplMap[this.type]();
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='event-detail-sideslider'
        // transfer={true}
        isShow={this.init && this.isShow}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        width={this.width}
        quick-close={true}
        onHidden={this.handleHiddenSlider}
      >
        <div
          class='sideslider-title'
          slot='header'
        >
          {this.tplTitle()}
        </div>
        <div
          style={{ height: '100%' }}
          slot='content'
          v-bkloading={{ isLoading: this.loading }}
        >
          {this.tplContent()}
        </div>
      </bk-sideslider>
    );
  }
}
