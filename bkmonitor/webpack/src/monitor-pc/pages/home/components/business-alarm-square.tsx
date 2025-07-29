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

import { random } from 'monitor-common/utils/utils';

import Square from './square';

import './business-alarm-square.scss';

interface IBusinessAlarmSquareEvents {
  onIsAllNormal?: boolean;
  onSelectedIndex?: number;
}
interface IBusinessAlarmSquareProps {
  isAllNormal: boolean;
  selectedIndex: number;
  squares: any[];
  status: string;
}

@Component({
  name: 'BusinessAlarmSquare',
})
export default class BusinessAlarmSquare extends tsc<IBusinessAlarmSquareProps, IBusinessAlarmSquareEvents> {
  @Prop({ type: Array, default: () => [] }) squares: any[];
  @Prop({ type: String, default: 'serious' }) status: string;
  @Prop({ type: Number, default: 0 }) selectedIndex: number;
  @Prop({ type: Boolean, default: false }) isAllNormal: boolean;

  selected = 0;
  curSquare = null;
  svgMap = {
    uptimecheck: {
      d: 'M0,91.5L0,91.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
      viewBox: '0 0 55 92',
    },
    process: {
      d: 'M0,185.5L0,185.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
      viewBox: '0 0 55 186',
    },
    os: {
      d: 'M0,232.5L0,232.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
      viewBox: '0 0 55 233',
    },
    service: {
      d: 'M0,138.5L0,138.5c15.2,0,27.5-12.3,27.5-27.5V28C27.5,12.8,39.8,0.5,55,0.5h0',
      viewBox: '0 0 55 139',
    },
  };
  colorMap = {
    serious: '#DE6573',
    slight: '#FEBF81',
    unset: '#C4C6CC',
    normal: '#85CFB7',
  };

  svgKey = random(8);

  created() {
    this.selected = this.selectedIndex;
    this.curSquare = this.squares[this.selectedIndex];
  }

  squareClickHandle(index, { status, name }) {
    this.selected = index;
    this.curSquare = { status, name };
    this.handleSelectedIndex(index);
    if (this.isAllNormal) {
      this.handleIsAllNormal(false);
    }
  }

  @Emit('selectedIndex')
  handleSelectedIndex(v: number) {
    return v;
  }
  @Emit('isAllNormal')
  handleIsAllNormal(v: boolean) {
    return v;
  }

  getStyle(h = '92px', t = '-115px', w = '34px', r = '13px') {
    return {
      position: 'absolute',
      width: w,
      height: h,
      right: r,
      top: t,
    };
  }

  get getSvgStyle() {
    const obj = {
      uptimecheck: this.getStyle('140px', '-110px'),
      service: this.getStyle('139px', '-95px'),
      process: this.getStyle('186px', '-106px'),
      os: this.getStyle('139px', '-70px'),
    };
    return obj[this.curSquare.name];
  }

  render() {
    return (
      <div class='square-svg-component'>
        <div class='square-container'>
          {this.squares.map((item, index) => (
            <div
              key={index}
              class={['item', `item-${index}`, { active: index === this.selected }]}
            >
              <Square
                status={item.status}
                onStatusChange={() => this.squareClickHandle(index, item)}
              />
            </div>
          ))}
        </div>
        <div
          style={{ display: !this.isAllNormal ? 'block' : 'none' }}
          class='svg-container'
        >
          <svg style='display: none'>
            <symbol
              id={this.svgKey}
              viewBox={this.svgMap?.[this.curSquare.name]?.viewBox}
            >
              <path
                d={this.svgMap?.[this.curSquare.name]?.d}
                fill='none'
                stroke={this.colorMap[this.curSquare.status]}
                stroke-dasharray='3'
                stroke-width='1.5px'
              />
            </symbol>
          </svg>
          <svg style={{ display: this.selected !== -1 ? 'block' : 'none', ...this.getSvgStyle }}>
            <use xlinkHref={`#${this.svgKey}`} />
          </svg>
        </div>
      </div>
    );
  }
}
