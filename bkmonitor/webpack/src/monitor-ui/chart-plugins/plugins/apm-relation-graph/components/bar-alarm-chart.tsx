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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import dayjs from 'dayjs';

import './bar-alarm-chart.scss';

interface IProps {
  itemHeight?: number;
  activeItemHeight?: number;
  showXAxis?: boolean;
  showHeader?: boolean;
}

enum EAlarmType {
  blue = 3,
  gray = 'no_data',
  green = 'no_alarm',
  red = 1,
  yellow = 2,
}

const alarmColorMap = {
  [EAlarmType.blue]: '#699DF4',
  [EAlarmType.gray]: '#EAEBF0',
  [EAlarmType.green]: '#2DCB56',
  [EAlarmType.red]: '#FF5656',
  [EAlarmType.yellow]: '#FFB848',
};

interface IDataItem {
  type: EAlarmType;
  time: number;
}

@Component
export default class BarAlarmChart extends tsc<IProps> {
  @Prop({ type: Number, default: 24 }) itemHeight: number;
  @Prop({ type: Number, default: 32 }) activeItemHeight: number;
  @Prop({ type: Boolean, default: false }) showXAxis: boolean;
  @Prop({ type: Boolean, default: false }) showHeader: boolean;

  localData: IDataItem[] = [
    {
      type: EAlarmType.green,
      time: 1723006950000,
    },
    {
      type: EAlarmType.green,
      time: 1723007100000,
    },
    {
      type: EAlarmType.green,
      time: 1723007250000,
    },
    {
      type: EAlarmType.yellow,
      time: 1723007400000,
    },
    {
      type: EAlarmType.yellow,
      time: 1723007550000,
    },
    {
      type: EAlarmType.yellow,
      time: 1723007700000,
    },
    {
      type: EAlarmType.red,
      time: 1723007850000,
    },
    {
      type: EAlarmType.red,
      time: 1723008000000,
    },
    {
      type: EAlarmType.red,
      time: 1723008150000,
    },
    {
      type: EAlarmType.blue,
      time: 1723008300000,
    },
    {
      type: EAlarmType.blue,
      time: 1723008450000,
    },
    {
      type: EAlarmType.blue,
      time: 1723008600000,
    },
    {
      type: EAlarmType.gray,
      time: 1723008750000,
    },
    {
      type: EAlarmType.gray,
      time: 1723008900000,
    },
    {
      type: EAlarmType.gray,
      time: 1723009050000,
    },
    {
      type: EAlarmType.green,
      time: 1723009200000,
    },
    {
      type: EAlarmType.green,
      time: 1723009350000,
    },
    {
      type: EAlarmType.green,
      time: 1723009500000,
    },
    {
      type: EAlarmType.green,
      time: 1723009650000,
    },
    {
      type: EAlarmType.green,
      time: 1723009800000,
    },
    {
      type: EAlarmType.green,
      time: 1723009950000,
    },
    {
      type: EAlarmType.green,
      time: 1723010100000,
    },
    {
      type: EAlarmType.green,
      time: 1723010250000,
    },
    {
      type: EAlarmType.green,
      time: 1723010400000,
    },
  ];

  curHover = -1;
  curActive = -1;
  xAxis = [];

  created() {
    const len = this.localData.length;
    const start = this.localData[0].time;
    const end = this.localData[len - 1].time;
    const center = this.localData[Math.floor(len / 2)].time;
    this.xAxis = [dayjs(start).format('HH:mm'), dayjs(center).format('HH:mm'), dayjs(end).format('HH:mm')];
  }

  handleMouseEnter(item: IDataItem) {
    this.curHover = item.time;
  }
  handleMouseLeave() {
    this.curHover = -1;
  }
  handleClick(item: IDataItem) {
    if (item.type === EAlarmType.gray) {
      return;
    }
    if (this.curActive === item.time) {
      this.curActive = -1;
      this.curHover = -1;
    } else {
      this.curActive = item.time;
    }
  }

  render() {
    return (
      <div
        style={{
          width: `${this.localData.length * 8 - 2}px`,
        }}
        class='bar-alarm-chart'
      >
        {this.showHeader && (
          <div class='alarm-header-wrap'>
            <div class='header-left'>{this.$slots?.title || ''}</div>
            <div class='header-right'>{this.$slots?.more || ''}</div>
          </div>
        )}
        <div
          style={{
            height: `${this.activeItemHeight}px`,
          }}
          class='alarm-chart-wrap'
        >
          {this.localData.map(item => (
            <div
              key={item.time}
              style={{
                height: `${
                  (this.curHover === item.time && item.type !== EAlarmType.gray) || this.curActive === item.time
                    ? this.activeItemHeight
                    : this.itemHeight
                }px`,
                background: `${alarmColorMap[item.type]}`,
                cursor: item.type !== EAlarmType.gray ? 'pointer' : 'default',
              }}
              class='time-cube'
              onClick={() => this.handleClick(item)}
              onMouseenter={() => this.handleMouseEnter(item)}
              onMouseleave={() => this.handleMouseLeave()}
            />
          ))}
        </div>
        {this.showXAxis && (
          <div class='alarm-footer-wrap'>
            {this.xAxis.map(item => (
              <div
                key={item}
                class='x-axis-item'
              >
                {item}
              </div>
            ))}
          </div>
        )}
      </div>
    );
  }
}
