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

import { copyText } from '../../../../monitor-common/utils/utils';
import TemporaryShare from '../../../../monitor-pc/components/temporary-share/temporary-share';

import ActionDetail from './action-detail';
import EventDetail from './event-detail';

import './event-detail-slider.scss';

interface IEventDetailSlider {
  isShow?: boolean;
  eventId: string;
  type: TType;
  activeTab?: string;
  bizId: number;
}
interface IEvent {
  onShowChange?: boolean;
}

// 事件详情 | 处理记录详情
export type TType = 'eventDetail' | 'handleDetail';

@Component
export default class EventDetailSlider extends tsc<IEventDetailSlider, IEvent> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ type: String, default: '' }) eventId: string;
  @Prop({ type: String, default: '' }) activeTab: string;
  @Prop({ type: [Number, String], default: +window.bk_biz_id }) bizId: number;
  @Prop({ default: 'eventDetail', validator: v => ['eventDetail', 'handleDetail'].includes(v) }) type: TType;

  loading = false;

  alertName = '';

  get width() {
    return this.type === 'handleDetail' ? 956 : 1280; // 1047;
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
  handleToEventDetail(type: 'detail' | 'action-detail', isNewPage = false) {
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
        theme: 'error'
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success'
    });
  }

  // 作为新页面打开
  newPageBtn(type: 'detail' | 'action-detail') {
    return (
      <span
        class='new-page-btn'
        onClick={() => this.handleToEventDetail(type, true)}
      >
        <span class='btn-text'>{this.$t('新开页')}</span>
        <span class='icon-monitor icon-fenxiang'></span>
      </span>
    );
  }

  handleInfo(v) {
    this.alertName = v.alert_name;
  }

  // 标题
  tplTitle() {
    const tplMap = {
      eventDetail: () => (
        <div class='title-wrap'>
          <span>{this.$t('告警详情')}</span>
          <span class='event-id'>{this.eventId}</span>
          {window.source_app === 'fta' ? (
            <i
              class='icon-monitor icon-copy-link'
              onClick={() => this.handleToEventDetail('detail')}
            ></i>
          ) : (
            <TemporaryShare
              navMode={'share'}
              customData={{ eventId: this.eventId }}
              pageInfo={{ alertName: this.alertName }}
            />
          )}
          {this.newPageBtn('detail')}
        </div>
      ),
      handleDetail: () => (
        <div class='title-wrap'>
          <span>{this.$t('处理记录详情')}</span>
          <i
            class='icon-monitor icon-copy-link'
            onClick={() => this.handleToEventDetail('action-detail')}
          ></i>
          {this.newPageBtn('action-detail')}
        </div>
      )
    };
    return tplMap[this.type]();
  }

  // 内容
  tplContent() {
    const tplMap = {
      eventDetail: () => (
        <EventDetail
          class='event-detail-content'
          id={this.eventId}
          bizId={this.bizId}
          activeTab={this.activeTab}
          onCloseSlider={() => this.emitIsShow(false)}
          onInfo={this.handleInfo}
        ></EventDetail>
      ),
      handleDetail: () => <ActionDetail id={this.eventId}></ActionDetail>
    };
    return tplMap[this.type]();
  }

  render() {
    return (
      <bk-sideslider
        ext-cls='event-detail-sideslider'
        // transfer={true}
        isShow={this.isShow}
        {...{ on: { 'update:isShow': this.emitIsShow } }}
        quick-close={true}
        width={this.width}
        onHidden={this.handleHiddenSlider}
      >
        <div
          slot='header'
          class='sideslider-title'
        >
          {this.tplTitle()}
        </div>
        <div
          slot='content'
          v-bkloading={{ isLoading: this.loading }}
        >
          {this.tplContent()}
        </div>
      </bk-sideslider>
    );
  }
}
