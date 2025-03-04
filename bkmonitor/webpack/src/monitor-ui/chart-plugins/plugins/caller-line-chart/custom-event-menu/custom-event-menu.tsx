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

import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';
import base64Svg from 'monitor-common/svg/base64';

import { getCustomEventTagDetails, type ICustomEventDetail, type ICustomEventTagsItem } from '../use-custom';

import type { IPosition } from 'CustomEventMenu';

import './custom-event-menu.scss';
export enum EventTab {
  All = 'all',
  Warning = 'warning',
}
interface IProps {
  /* 位置 */
  position: IPosition;
  /* 事件项 */
  eventItem: ICustomEventTagsItem['items'][number];
}
@Component
export default class CustomEventMenu extends tsc<IProps> {
  /* 位置 */
  @Prop({ required: true, type: Object }) position: IPosition;
  /* 事件项 */
  @Prop({ required: true, type: Object }) eventItem: ICustomEventTagsItem['items'][number];
  menuData: ICustomEventDetail = {};
  activeTab: EventTab = EventTab.Warning;
  loading = false;
  @Watch('eventItem', { deep: true, immediate: true })
  async getCustomEventTagDetails() {
    if (this.position.left && this.position.top && this.eventItem) {
      this.loading = true;
      const data = await getCustomEventTagDetails(
        this.eventItem,
        this.eventItem.count,
        this.eventItem.statistics.Warning > 0
      );
      this.activeTab = this.eventItem.statistics.Warning > 0 ? EventTab.Warning : EventTab.All;
      console.info(data);
      this.menuData = data;
      this.loading = false;
    }
  }

  handleTabChange(tab: EventTab) {
    this.activeTab = tab;
  }
  createTitleRender() {
    if (!this.menuData?.list?.length && !this.menuData.topk) return undefined;
    const { list, time, topk } = this.menuData;
    const data = list || topk;
    if (data?.length === 1) {
      const { 'event.content': eventContent, source } = data[0];
      return (
        <div class='custom-event-menu-title'>
          <span
            style={{ backgroundImage: `url(${base64Svg[source.value?.toLowerCase() || 'bcs']})` }}
            class='event-icon'
          />
          <div class='event-name'>{eventContent.alias}</div>
          <bk-button
            class='detail-btn'
            text
          >
            <i class='icon-monitor icon-xiangqing1 detail-icon' />
            {this.$t('详情')}
          </bk-button>
        </div>
      );
    }
    if (data?.length > 1) {
      const { source } = data[0];
      return (
        <div class='custom-event-menu-title'>
          <span
            style={{ backgroundImage: `url(${base64Svg[source.value?.toLowerCase() || 'bcs']})` }}
            class='event-icon'
          />
          <div class='event-name'>
            <i18n path={'共 {0} 个事件，展示 Top{1}'}>
              <span style='font-weight: bold;color:white;'> {12} </span>
              <span style='font-weight: bold;color:white;'> {5} </span>
            </i18n>
          </div>
          <span
            style='color: #979BA5;'
            class='detail-btn'
          >
            {dayjs(time).format('YYYY-MM-DD HH:mm:ss')}
          </span>
        </div>
      );
    }
  }
  createContentRender() {
    const { list, topk } = this.menuData || {};
    if (list?.length === 1) {
      const {
        'event.content': { detail },
      } = list[0];
      return (
        <div class='custom-event-menu-content'>
          {Object.values(detail).map(item => {
            return (
              <div
                key={item.label}
                class='content-item'
              >
                <div class='content-item-label'>{item.label}:</div>
                <div class={`content-item-value ${item.link ? 'is-url' : ''}`}>{item.alias || item.value}</div>
              </div>
            );
          })}
        </div>
      );
    }
    if (list?.length > 1) {
      return (
        <div class='custom-event-menu-content'>
          {list.map((item, index) => {
            return (
              <div
                key={index}
                class='content-item'
              >
                <span
                  style={{ backgroundImage: `url(${base64Svg[item?.source.value?.toLowerCase() || 'bcs']})` }}
                  class='event-icon'
                />
                <div class='content-item-content'>
                  {item.event_name.alias}
                  <bk-link theme='primary'>（{item.target.alias}）</bk-link>
                </div>
                <i class='icon-monitor icon-xiangqing1 link-icon' />
              </div>
            );
          })}
          {this.createContentMore()}
        </div>
      );
    }
    if (topk?.length) {
      return (
        <div class='custom-event-menu-content'>
          {topk.map((item, index) => {
            return (
              <div
                key={index}
                class='content-progress'
              >
                <div class='progress-title'>
                  <span
                    style={{ backgroundImage: `url(${base64Svg[item?.source.value?.toLowerCase() || 'bcs']})` }}
                    class='event-icon'
                  />
                  {item.event_name.alias}
                  <i class='icon-monitor icon-xiangqing1 link-icon' />
                </div>
                <bk-progress
                  color={this.activeTab === EventTab.Warning ? '#F59500' : '#699DF4'}
                  percent={(item.proportions / 100).toFixed(4)}
                  show-text={false}
                />
              </div>
            );
          })}
          {this.createContentMore()}
        </div>
      );
    }
    return (
      <bk-exception
        class='no-data'
        scene='part'
        type='empty'
      >
        {this.$t('暂无数据')}
      </bk-exception>
    );
  }
  createHeaderRender() {
    if (!this.eventItem.statistics.Warning || !this.loading || !this.menuData?.total) return undefined;
    return (
      <div class='custom-event-menu-header'>
        {[EventTab.Warning, EventTab.All].map(level => {
          return (
            <div
              key={level}
              style={{
                borderTopColor:
                  level !== this.activeTab ? 'rgba(0, 0, 0, 0.4)' : level === EventTab.Warning ? '#F59500' : '#699DF4',
                backgroundColor: level === this.activeTab ? 'transparent' : 'rgba(0, 0, 0, 0.4)',
              }}
              class='header-tab'
              onClick={() => this.handleTabChange(level)}
            >
              {this.$t(level === EventTab.Warning ? '异常事件 (8)' : '全部事件 (81)')}
            </div>
          );
        })}
      </div>
    );
  }
  createContentMore() {
    if (this.menuData?.total < 6) return undefined;
    return (
      <div class='common-more'>
        ...
        <bk-button
          size='small'
          theme='primary'
          text
        >
          {this.$t('更多')}
          <i class='icon-monitor icon-mc-goto' />
        </bk-button>
      </div>
    );
  }
  createLoadingRender() {
    return [
      <div
        key={'title'}
        class='custom-event-menu-title'
      >
        <div
          style='width: 33%'
          class='skeleton-element custom-menu-skeleton'
        />
      </div>,
      <div
        key={'content'}
        class='custom-event-menu-content'
      >
        <div
          style='width: 90%'
          class='skeleton-element custom-menu-skeleton'
        />
        <div
          style='width: 70%'
          class='skeleton-element custom-menu-skeleton'
        />
        <div
          style='width: 50%'
          class='skeleton-element custom-menu-skeleton'
        />
      </div>,
    ];
  }
  render() {
    if (!this.position?.left || !this.position?.top) return undefined;
    return (
      <div
        style={{
          left: `${this.position.left}px`,
          top: `${this.position.top}px`,
        }}
        class='custom-event-menu'
      >
        {this.loading && this.createLoadingRender()}
        {!this.loading && this.createHeaderRender()}
        {!this.loading && this.createTitleRender()}
        {!this.loading && this.createContentRender()}
      </div>
    );
  }
}
