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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import {
  type ICalendarData,
  type ICalendarDataUser,
  calendarDataConversion,
  getCalendarNew,
} from '../../../../trace/pages/rotation/components/calendar-preview';

import './rotation-calendar-preview.scss';

interface IProps {
  value?: ICalendarDataUser[];
}

@Component
export default class RotationCalendarPreview extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: ICalendarDataUser[];
  @Ref('content') contentRef;
  @Ref('userTip') userTipRef: HTMLDivElement;

  curCalendarData: ICalendarData = {
    users: [],
    data: getCalendarNew().map(item => ({
      dates: item,
      data: [],
    })),
  };

  weekList = [
    window.i18n.t('周日'),
    window.i18n.t('周一'),
    window.i18n.t('周二'),
    window.i18n.t('周三'),
    window.i18n.t('周四'),
    window.i18n.t('周五'),
    window.i18n.t('周六'),
  ];

  containerWidth = 1000;

  observer = null;

  popover = {
    users: [],
    time: '',
  };
  popoverInstance = null;

  created() {
    this.observer = new ResizeObserver(entries => {
      entries.forEach(entry => {
        const { width } = entry.contentRect;
        this.containerWidth = width;
      });
    });

    this.curCalendarData = calendarDataConversion(this.curCalendarData);
  }
  mounted() {
    this.observer.observe(this.contentRef);
  }

  @Watch('value')
  handleWatchValue(value) {
    this.curCalendarData.users = value;
    this.curCalendarData = calendarDataConversion(this.curCalendarData);
  }

  async handleMouseenter(e: Event, data) {
    this.popover.time = data.time;
    this.popover.users = data.users;
    this.popoverInstance?.hide(100);
    this.popoverInstance?.destroy();
    this.popoverInstance = null;
    await this.$nextTick();
    this.popoverInstance = this.$bkPopover(e.target, {
      content: this.userTipRef,
      placement: 'top',
      width: this.popover.time.length > 30 ? 215 : 160,
      boundary: 'window',
      theme: 'light',
      arrow: true,
      interactive: true,
    });
    this.popoverInstance?.show(100);
  }

  render() {
    return (
      <div
        ref='content'
        class='rotation-calendar-preview-component'
      >
        <div class='calendar-header'>
          {this.weekList.map(item => (
            <span
              key={String(item)}
              class='week-item'
            >
              {item}
            </span>
          ))}
        </div>
        <div class='calendar-content'>
          {this.curCalendarData.data.map((item, index) => (
            <div
              key={index}
              style={{
                height: `${120 + (item.maxRow >= 2 ? item.maxRow - 2 : 0) * 22}px`,
              }}
              class='week-row'
            >
              {item.dates.map(date => (
                <div
                  key={date.day}
                  class='day-col'
                >
                  <div
                    class={[
                      'day-label',
                      {
                        check: date.isCurDay,
                        other: date.isOtherMonth,
                      },
                    ]}
                  >
                    {date.day === 1 && !date.isCurDay ? this.$t('{0}月', [date.month + 1]) : date.day}
                  </div>
                </div>
              ))}
              {item.data.map((data, _index) =>
                !!data.users.length ? (
                  <div
                    style={{
                      top: `${48 + data.row * 22}px`,
                      width: `${
                        (data?.isStartBorder ? -1 : 0) + this.containerWidth * (data.range[1] - data.range[0])
                      }px`,
                      left: `${(data?.isStartBorder ? 1 : 0) + this.containerWidth * data.range[0]}px`,
                    }}
                    class='user-item'
                    onMouseenter={(event: Event) => this.handleMouseenter(event, data.other)}
                  >
                    <div
                      style={{ background: data.color }}
                      class='user-header'
                    />
                    <div
                      style={{ color: data.color }}
                      class='user-content'
                    >
                      <span>
                        {data.users.map((u, index, arr) => [
                          <bk-user-display-name user-id={u.name} />,
                          index !== arr.length - 1 && ',',
                        ])}
                      </span>
                    </div>
                  </div>
                ) : (
                  <div
                    style={{
                      width: `${
                        (data?.isStartBorder ? -1 : 0) + this.containerWidth * (data.range[1] - data.range[0])
                      }px`,
                      left: `${(data?.isStartBorder ? 1 : 0) + this.containerWidth * data.range[0]}px`,
                    }}
                    class='user-item no-user'
                    onMouseenter={(event: Event) => this.handleMouseenter(event, data.other)}
                  />
                )
              )}
            </div>
          ))}
        </div>
        <div style={{ display: 'none' }}>
          <div
            ref='userTip'
            class='rotation-calendar-preview-component-user-item-pop'
          >
            <div class='user-item'>
              <div class='time'>{this.popover.time}</div>
              <div class='users'>
                {this.popover.users.map((u, index, arr) => [
                  `${u.id}(`,
                  <bk-user-display-name user-id={u.name} />,
                  ')',
                  index !== arr.length - 1 && ',',
                ])}
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
