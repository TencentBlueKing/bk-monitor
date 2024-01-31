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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './alert-histogram.scss';

const classMap = {
  0: 'green',
  1: 'red'
};

interface IProps {
  value: {
    level: number;
  }[];
  defaultInterval?: number;
}

@Component
export default class AlertHistogram extends tsc<IProps> {
  @Prop({
    type: Array,
    default: () => []
  })
  value: number[][];

  @Prop({ type: Number, default: 0 }) defaultInterval: number;

  @Ref('time') timeRef: HTMLDivElement;

  /* 监听容器宽度 */
  resizeObserver = null;
  /* 当前容器宽度 */
  width = 0;
  /* 当前显示的数据 */
  localValue: { times: number[]; level: number }[] = [];
  /* pop实例 */
  popInstance = null;
  /* 当前hover的时间 */
  curHoverTime = '';
  cruHoverLevel = 0;

  mounted() {
    this.resizeObserver = new ResizeObserver(entries => {
      for (const entry of entries) {
        // 获取元素的新宽度
        const newWidth = entry.contentRect.width;
        this.width = newWidth;
        this.reduceAccuracy();
      }
    });
    this.resizeObserver.observe(this.$el);
  }

  destroyed() {
    this.resizeObserver.unobserve(this.$el);
  }

  /**
   * @description 降低精度处理
   */
  reduceAccuracy() {
    const max = 6 * 60 + 6;
    const max1 = 6 * 30 + 6;
    let interval = this.defaultInterval;
    if (this.width < max || !!interval) {
      const values = [];
      interval = 2;
      if (this.width < max1) {
        interval = 4;
      }
      let i = 0;
      let tempTime = [];
      let timeValue = [];
      const len = this.value.length;
      this.value.forEach((item, index) => {
        i += 1;
        tempTime.push(item[0]);
        timeValue.push(item[1]);
        if (i === interval) {
          values.push([tempTime, timeValue]);
          tempTime = [];
          timeValue = [];
          i = 0;
        }
        if (index === len - 1 && tempTime.length) {
          values.push([tempTime, timeValue]);
        }
      });
      this.localValue = values.map(item => ({ times: item[0], level: Math.max(...item[1]) }));
    } else {
      this.localValue = this.value.map(item => ({
        times: [item[0]],
        level: item[1]
      }));
    }
  }

  timeStampToStr(time: number) {
    const timeDate = new Date(time);
    const year = timeDate.getFullYear();
    const month = timeDate.getMonth() + 1;
    const date = timeDate.getDate();
    const h = timeDate.getHours();
    const m = timeDate.getMinutes();
    const numStr = num => {
      if (num < 10) {
        return `0${num}`;
      }
      return num;
    };
    return `${year}-${numStr(month)}-${numStr(date)} ${numStr(h)}:${numStr(m)}`;
  }
  /**
   * @description hover
   * @param e
   * @param item
   */
  handleMouseenter(e: Event, item: { times: number[]; level: number }) {
    if (item.times.length > 1) {
      const start = item.times[0];
      const end = item.times[item.times.length - 1];
      this.curHoverTime = `${this.timeStampToStr(start)} ~ ${this.timeStampToStr(end)}`;
    } else {
      this.curHoverTime = this.timeStampToStr(item.times[0]);
    }
    this.cruHoverLevel = item.level;
    this.$nextTick(() => {
      this.popInstance = this.$bkPopover(e.target, {
        content: this.timeRef,
        trigger: 'mouseenter',
        theme: 'light',
        delay: [300, 0],
        arrow: true,
        placement: 'top',
        boundary: 'window'
      });
      this.popInstance?.show();
    });
  }

  handleMouseleave() {
    this.popInstance?.hide?.(0);
    this.popInstance?.destroy?.();
    this.popInstance = null;
  }

  render() {
    return (
      <div class='alert-histogram-component'>
        {this.localValue.map(item => (
          <div
            class={['histogram-item', classMap[item.level]]}
            onMouseenter={e => this.handleMouseenter(e, item)}
            onMouseleave={() => this.handleMouseleave()}
          ></div>
        ))}
        <div style={{ display: 'none' }}>
          <div
            ref='time'
            class='alert-histogram-component-pop-wrap'
          >
            <div>{this.curHoverTime}</div>
            <div>{this.cruHoverLevel > 0 ? this.$t('有告警') : this.$t('无告警')}</div>
          </div>
        </div>
      </div>
    );
  }
}
