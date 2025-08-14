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

import { type ICustomEventDetail, type IEventTagsItem, getCustomEventTagDetails } from '../use-custom';

import type { IPosition } from 'CustomEventMenu';

import './custom-event-menu.scss';
export enum EventTab {
  All = 'all',
  Warning = 'warning',
}
interface IProps {
  /* 事件项 */
  eventItem: Partial<IEventTagsItem>;
  /* 位置 */
  position: IPosition;
}
@Component
export default class CustomEventMenu extends tsc<IProps> {
  /* 位置 */
  @Prop({ required: true, type: Object }) position: IPosition;
  /* 事件项 */
  @Prop({ required: true, type: Object }) eventItem: Partial<IEventTagsItem>;

  warningData: ICustomEventDetail = {};
  allData: ICustomEventDetail = {};
  activeTab: EventTab = EventTab.Warning;
  loading = false;
  get menuData(): ICustomEventDetail {
    return this.activeTab === EventTab.Warning ? this.warningData : this.allData;
  }
  @Watch('eventItem', { deep: true, immediate: true })
  async getCustomEventTagDetails() {
    if (this.position.left && this.position.top && this.eventItem) {
      this.loading = true;
      const { Warning, All } = await getCustomEventTagDetails({
        app_name: this.eventItem.app_name,
        service_name: this.eventItem.service_name,
        query_configs: [
          {
            data_source_label: 'bk_apm',
            data_type_label: 'event',
            table: 'builtin',
            filter_dict: {},
            where: this.eventItem.where || [],
            query_string: '*',
            group_by: [],
            interval: this.eventItem.interval,
          },
        ],
        expression: 'a',
        start_time: this.eventItem.start_time,
      });
      this.warningData = Warning;
      this.allData = All;
      this.activeTab = this.warningData?.total > 0 ? EventTab.Warning : EventTab.All;
      this.loading = false;
    }
  }

  handleTabChange(tab: EventTab) {
    this.activeTab = tab;
  }
  createApmEventExploreHref(startTime: number, eventName = '', defaultWhere: Record<string, any>[] = []) {
    const targets = [
      {
        data: {
          query_configs: [
            {
              result_table_id: 'builtin',
              data_type_label: 'event',
              data_source_label: 'apm',
              where: eventName
                ? [
                    {
                      key: 'event_name',
                      condition: 'and',
                      value: [eventName],
                      method: 'eq',
                    },
                    ...this.eventItem.where,
                    ...defaultWhere,
                  ]
                : [],
              query_string: '',
              group_by: [],
              filter_dict: {},
            },
          ],
        },
      },
    ];
    const query = {
      sceneId: 'apm_service',
      sceneType: 'overview',
      dashboardId: 'service-default-event',
      from: ((startTime || this.eventItem.start_time) * 1000).toString(),
      to: `${((startTime || this.eventItem.start_time) + this.eventItem.interval) * 1000}`,
      'filter-app_name': this.eventItem.app_name,
      'filter-service_name': this.eventItem.service_name,
      targets: JSON.stringify(targets),
    };
    const { href } = this.$router.resolve({
      path: this.$route.path,
      query,
    });
    window.open(location.href.replace(location.hash, href), '_blank');
  }
  handleListGotoEventDetail(event: MouseEvent, item: ICustomEventDetail['list'][number]) {
    event.preventDefault();
    this.createApmEventExploreHref(+item.time?.value / 1000, item.event_name.value, [
      { key: 'time', value: [item.time?.value], method: 'eq', condition: 'and' },
    ]);
  }
  handleTopKGotoEventDetail(event: MouseEvent, item: ICustomEventDetail['topk'][number]) {
    event.preventDefault();
    this.createApmEventExploreHref(this.menuData.time, item.event_name.value);
  }
  createTitleRender() {
    if (!this.menuData?.list?.length && !this.menuData.topk) return undefined;
    const { list, time, topk } = this.menuData;
    const data = list || topk;
    if (list?.length === 1) {
      const { event_name, source } = data[0];
      return (
        <div class='custom-event-menu-title'>
          <span
            style={{ backgroundImage: `url(${base64Svg[source.value?.toLowerCase() || 'bcs']})` }}
            class='event-icon'
            v-bk-tooltips={{ content: source.alias }}
          />
          <div class='event-name'>{event_name.alias}</div>
          <span
            class='detail-btn is-url'
            v-bk-tooltips={{
              content: this.$t('查看事件详情'),
              allowHTML: false,
            }}
            onMousedown={e => this.handleListGotoEventDetail(e, list[0])}
          >
            <i class='icon-monitor icon-xiangqing1 detail-icon' />
            {this.$t('详情')}
          </span>
        </div>
      );
    }
    if (data?.length > 0) {
      // const { source } = data[0];
      return (
        <div class='custom-event-menu-title'>
          <div class='event-name'>
            {list?.length > 0 ? (
              <i18n path={'共 {0} 个事件，展示 Top{1}'}>
                <span style='font-weight: bold;color:#313238;'> {this.menuData.total} </span>
                <span style='font-weight: bold;color:#313238;'> {data.length} </span>
              </i18n>
            ) : (
              <i18n path={'共 {0} 个事件，已按事件名汇总'}>
                <span style='font-weight: bold;color:#313238;'> {this.menuData.total} </span>
              </i18n>
            )}
          </div>
          <span
            style='color: #979BA5;'
            class='detail-btn'
          >
            {dayjs(time * 1000).format('YYYY-MM-DD HH:mm:ss')}
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
                <div class={'content-item-value'}>
                  {item.url ? (
                    <span
                      class='is-url'
                      onMousedown={() => window.open(item.url, '_blank')}
                    >
                      {item.alias || item.value}
                    </span>
                  ) : (
                    item.alias || item.value
                  )}
                </div>
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
                  v-bk-tooltips={{ content: item?.source.alias }}
                />
                <div class='content-item-content'>
                  {item.event_name.alias}
                  <span
                    class='is-url '
                    v-bk-tooltips={{
                      content: this.$t('查看资源'),
                      allowHTML: false,
                    }}
                    onMousedown={() => item.target.url && window.open(item.target.url, '_blank')}
                  >
                    （{item.target.alias}）
                  </span>
                </div>
                <i
                  class='icon-monitor icon-xiangqing1 link-icon'
                  v-bk-tooltips={{
                    content: this.$t('查看事件详情'),
                    allowHTML: false,
                  }}
                  onMousedown={e => this.handleListGotoEventDetail(e, item)}
                />
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
                    v-bk-tooltips={{ content: item?.source.alias }}
                  />
                  {item.event_name.alias}
                  <span class='proportions-num'>{item.count}</span>
                  <i
                    style={{ marginLeft: '0px' }}
                    class='icon-monitor icon-xiangqing1 link-icon'
                    v-bk-tooltips={{
                      content: this.$t('查看事件详情'),
                      allowHTML: false,
                    }}
                    onMousedown={e => this.handleTopKGotoEventDetail(e, item)}
                  />
                </div>
                <bk-progress
                  color={this.activeTab === EventTab.Warning ? '#F59500' : '#3A84FF'}
                  percent={Math.max(+(item.proportions / 100).toFixed(2), 0.01)}
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
    if (!this.warningData?.total || this.loading || !this.menuData?.total) return undefined;
    return (
      <div class='custom-event-menu-header'>
        {[EventTab.Warning, EventTab.All].map(level => {
          return (
            <div
              key={level}
              style={{
                borderTopColor:
                  level !== this.activeTab ? '#F0F1F5' : level === EventTab.Warning ? '#F59500' : '#3A84FF',
                backgroundColor: level === this.activeTab ? 'transparent' : '#F0F1F5',
              }}
              class='header-tab'
              onMousedown={() => this.handleTabChange(level)}
            >
              {level === EventTab.Warning
                ? this.$t('异常事件 ({0})', [this.warningData.total || 0])
                : this.$t('全部事件 ({0})', [this.allData.total])}
            </div>
          );
        })}
      </div>
    );
  }
  createContentMore() {
    if (this.menuData?.list?.length >= this.menuData.total && this.menuData?.topk?.length >= this.menuData.total)
      return undefined;
    return (
      <div
        class='common-more'
        onMousedown={e => {
          e.preventDefault();
          this.createApmEventExploreHref(this.menuData.time);
        }}
      >
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
