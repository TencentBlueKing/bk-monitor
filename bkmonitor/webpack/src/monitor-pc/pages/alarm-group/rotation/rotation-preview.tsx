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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { dutyDataConversion, getCalendarOfNum, getDutyPlansDetails, IDutyData, IDutyPlansItem } from './utils';

import './rotation-preview.scss';

interface IProps {
  value?: any;
  alarmGroupId?: string | number;
  dutyPlans?: any[];
  previewDutyRules?: any[];
  onStartTimeChange?: (v: string) => void;
  onInitStartTime?: (v: string) => void;
}

@Component
export default class RotationPreview extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) value: any[];
  @Prop({ type: [Number, String], default: '' }) alarmGroupId: string | number;
  /* 轮值历史 */
  @Prop({ default: () => [], type: Array }) dutyPlans: any[];
  /* 当前预览接口数据 用于展示明细 */
  @Prop({ default: () => [], type: Array }) previewDutyRules: {
    duty_plans: IDutyPlansItem[];
  }[];

  @Ref('previewContent') previewContentRef: HTMLDivElement;
  @Ref('userTip') userTipRef: HTMLDivElement;
  /* 是否展示未排班 */
  showNoData = true;
  /* 是否展开 */
  isExpan = true;
  // 预览数据
  dutyData: IDutyData = {
    dates: getCalendarOfNum(),
    data: [],
    freeTimes: [],
    overlapTimes: []
  };
  /* 用户组tip */
  popoverInstance = null;
  popover = {
    users: '',
    time: ''
  };
  /* 容器宽度 */
  containerWidth = 1000;
  observer = null;
  showDetail = false;
  /* 当前明细/历史标题 */
  detailTitle = '';
  detailDutyPlans = [];

  startTime = '';

  created() {
    this.dutyData = dutyDataConversion(this.dutyData);
    this.startTime = `${this.dutyData.dates[0].year}-${this.dutyData.dates[0].month}-${this.dutyData.dates[0].day} 00:00:00`;
    this.$emit('initStartTime', this.startTime);
  }
  mounted() {
    this.observer = new ResizeObserver(entries => {
      entries.forEach(entry => {
        const { width } = entry.contentRect;
        this.containerWidth = width;
      });
    });
    this.observer.observe(this.previewContentRef);
  }

  @Watch('value', { immediate: true })
  handleWatchValue(value) {
    this.dutyData = dutyDataConversion({
      ...this.dutyData,
      data: value
    });
  }
  /**
   * @description 展开预览
   */
  handleExpan() {
    this.isExpan = !this.isExpan;
  }
  /**
   * @description 用户组tip
   * @param e
   * @param data
   */
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
      interactive: true
    });
    this.popoverInstance?.show(100);
  }
  @Emit('startTimeChange')
  handleStartTimeChange() {
    this.startTime = `${this.dutyData.dates[0].year}-${this.dutyData.dates[0].month}-${this.dutyData.dates[0].day} 00:00:00`;
    return this.startTime;
  }
  /**
   * @description 上一个周期
   */
  handlePreChange() {
    const preDayDate = this.dutyData.dates[0];
    const preDay =
      new Date(`${preDayDate.year}-${preDayDate.month}-${preDayDate.day}`).getTime() - 8 * 24 * 60 * 60 * 1000;
    this.dutyData = dutyDataConversion({
      ...this.dutyData,
      dates: getCalendarOfNum(7, preDay)
    });
    this.handleStartTimeChange();
  }
  /**
   * @description 下一个周期
   */
  handleNextChange() {
    const preDayDate = this.dutyData.dates[6];
    const preDay = new Date(`${preDayDate.year}-${preDayDate.month}-${preDayDate.day}`).getTime();
    this.dutyData = dutyDataConversion({
      ...this.dutyData,
      dates: getCalendarOfNum(7, preDay)
    });
    this.handleStartTimeChange();
  }
  /**
   * @description 显示排班明细和轮值历史
   * @param v
   */
  async handleShowDetail(v: boolean, title, isHistory = false) {
    this.showDetail = v;
    this.detailTitle = title;
    if (!v) {
      return;
    }
    let dutyPlans = [];
    if (!!this.alarmGroupId) {
      dutyPlans = this.dutyPlans;
    } else if (!isHistory) {
      this.previewDutyRules.forEach(item => {
        dutyPlans.push(...item.duty_plans);
      });
    }
    this.detailDutyPlans = getDutyPlansDetails(dutyPlans, isHistory);
    // this.detailDutyPlans = (
    //   isHistory
    //     ? this.dutyPlans.filter(d => new Date(d.start_time).getTime() < new Date().getTime())
    //     : this.dutyPlans.filter(d => new Date(d.finished_time).getTime() > new Date().getTime())
    // ).map(d => ({
    //   startTime: d?.start_time || '--',
    //   endTime: d?.finished_time || '--',
    //   users: (d?.users?.map(u => u.display_name) || []).join('、 ')
    // }));
  }

  getOverlapStyleTop(verticalRange: number[]) {
    const heights = this.dutyData.data.map(item => 64 + item.maxRow * 22);
    let top = 0;
    let height = 0;
    heights.forEach((h, index) => {
      if (index <= verticalRange[0]) {
        top += h;
      }
      if (index > verticalRange[0] && index < verticalRange[1]) {
        height += h;
      }
    });
    return {
      top: `${top - 21}px`,
      height: `${height + 42}px`
    };
  }

  render() {
    return (
      <div class='alarm-group-rotation-preview-component'>
        <div
          class='header-wrap'
          onClick={this.handleExpan}
        >
          <span class={['icon-monitor icon-mc-triangle-down', { expan: this.isExpan }]}></span>
          <span class='ml-8'>{this.$t('排班预览')}</span>
          <span
            onClick={(e: Event) => {
              e.stopPropagation();
            }}
          >
            <bk-switcher
              class='ml-24'
              v-model={this.showNoData}
              theme='primary'
              size='small'
            ></bk-switcher>
          </span>
          <span class='ml-6'>{this.$t('显示未排班')}</span>
          <span
            class='text-btn mr-24 ml-auto'
            onClick={(e: Event) => {
              e.stopPropagation();
              this.handleShowDetail(true, this.$t('排班明细'));
            }}
          >
            <span class='icon-monitor icon-mc-detail mr-6'></span>
            <span>{this.$t('排班明细')}</span>
          </span>
          <span
            class='text-btn'
            onClick={(e: Event) => {
              e.stopPropagation();
              this.handleShowDetail(true, this.$t('轮值历史'), true);
            }}
          >
            <span class='icon-monitor icon-lishijilu mr-6'></span>
            <span>{this.$t('轮值历史')}</span>
          </span>
        </div>
        <div class={['preview-content', { expan: this.isExpan }]}>
          <div class='preview-content-left'>
            <div class='left-header'>{this.$t('轮值规则')}</div>
            <div class='left-content'>
              {this.dutyData.data.map((item, index) => (
                <div
                  class='left-content-item'
                  style={{
                    height: `${64 + item.maxRow * 22}px`
                  }}
                  key={index}
                >
                  <span v-bk-overflow-tips>{item.name}</span>
                </div>
              ))}
            </div>
          </div>
          <div
            class='preview-content-right'
            ref='previewContent'
          >
            <div class='right-header'>
              {this.dutyData.dates.map((item, index) => (
                <div
                  class='right-header-item'
                  key={index}
                >{`${item.month}-${item.day}`}</div>
              ))}
              <div
                class='pre-btn'
                onClick={this.handlePreChange}
              >
                <span class='icon-monitor icon-arrow-left'></span>
              </div>
              <div
                class='next-btn'
                onClick={this.handleNextChange}
              >
                <span class='icon-monitor icon-arrow-right'></span>
              </div>
            </div>
            <div class='right-content'>
              {this.dutyData.data.map((row, rowIndex) => (
                <div
                  class='row-content'
                  style={{
                    height: `${64 + row.maxRow * 22}px`
                  }}
                  key={rowIndex}
                >
                  {this.dutyData.dates.map((_col, colIndex) => (
                    <div
                      class='col-content'
                      key={`${rowIndex}_${colIndex}`}
                    ></div>
                  ))}
                  {row.data
                    .filter(duty => duty.range[1] - duty.range[0] !== 0)
                    .map((duty, dutyIndex) => (
                      <div
                        class='user-item'
                        key={dutyIndex}
                        style={{
                          top: `${21 + duty.row * 22}px`,
                          width: `${
                            (duty?.isStartBorder ? -1 : 0) + this.containerWidth * (duty.range[1] - duty.range[0])
                          }px`,
                          left: `${(duty?.isStartBorder ? 1 : 0) + this.containerWidth * duty.range[0]}px`
                        }}
                        onMouseenter={(event: Event) => this.handleMouseenter(event, duty.other)}
                      >
                        <div
                          class='user-header'
                          style={{ background: duty.color }}
                        ></div>
                        <div
                          class='user-content'
                          style={{ color: duty.color }}
                        >
                          <span>{duty.users.map(u => u.name || u.id).join(',')}</span>
                        </div>
                      </div>
                    ))}
                </div>
              ))}
              {this.showNoData &&
                this.dutyData.freeTimes.map((item, index) => (
                  <div
                    key={`free_${index}`}
                    class='free-col'
                    style={{
                      width: `${this.containerWidth * (item.range[1] - item.range[0])}px`,
                      left: `${this.containerWidth * item.range[0]}px`
                    }}
                    onMouseenter={(event: Event) => this.handleMouseenter(event, { time: item.timeStr })}
                  ></div>
                ))}
              {this.dutyData.overlapTimes.map((item, index) => (
                <div
                  key={`overlap_${index}`}
                  class='overlap-col'
                  style={{
                    ...this.getOverlapStyleTop(item.verticalRange),
                    // top: `${(item.verticalRange[0] + 1) * 64 - 21}px`,
                    // height: `${(item.verticalRange[1] - item.verticalRange[0] + 1) * 64 - 86}px`,
                    width: `${this.containerWidth * (item.range.range[1] - item.range.range[0])}px`,
                    left: `${this.containerWidth * item.range.range[0]}px`
                  }}
                  onMouseenter={(event: Event) =>
                    this.handleMouseenter(event, {
                      time: item.range.timeStr,
                      users: this.$t('时间段冲突，优先执行节假日排班')
                    })
                  }
                ></div>
              ))}
            </div>
          </div>
        </div>
        <bk-sideslider
          isShow={this.showDetail}
          width={640}
          transfer={true}
          extCls={'rotation-preview-side'}
          quickClose={true}
          title={this.detailTitle}
          before-close={() => this.handleShowDetail(false, '')}
        >
          <div slot='content'>
            {this.detailDutyPlans.length ? (
              this.detailDutyPlans.map((item, index) => (
                <div
                  class='content-item'
                  key={index}
                >
                  <span class='item-left'>{`${item.startTime} ～ ${item.endTime}`}</span>
                  <span class='item-right'>{item.users}</span>
                </div>
              ))
            ) : (
              <div>{this.$t('暂无数据')}</div>
            )}
          </div>
        </bk-sideslider>
        <div style={{ display: 'none' }}>
          <div
            class='duty-preview-component-user-item-tip'
            ref='userTip'
          >
            <div class='time'>{this.popover.time}</div>
            <div class='users'>{this.popover.users}</div>
          </div>
        </div>
      </div>
    );
  }
}
