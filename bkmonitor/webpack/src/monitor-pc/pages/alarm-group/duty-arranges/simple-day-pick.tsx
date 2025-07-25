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

import './simple-day-pick.scss';

const defaultDays = () => {
  const list = [];
  for (let i = 1; i < 32; i++) {
    list.push({ value: i, active: false });
  }
  return list;
};

interface IDay {
  active: boolean;
  value: number;
}

interface IEvents {
  onChange?: number | number[];
}

interface IProps {
  list?: IDay[];
  multiple?: boolean;
  value?: number | number[];
}

@Component
export default class SimpleDayPick extends tsc<IProps, IEvents> {
  /* 可选列表 */
  @Prop({ default: () => defaultDays(), type: Array }) list: IDay[];
  @Prop({ default: () => [], type: [Array, Number] }) value: number | number[];
  @Prop({ default: true, type: Boolean }) multiple: boolean;
  @Ref('dayPicker') dayPickerRef: HTMLDivElement;

  /* 列表包含状态 */
  localList: IDay[] = [];
  popoverInstances = null;
  /* 已选中的值 */
  activeList = [];
  datePickerValues = new Set();

  /* 是否按住了shift */
  isDownShift = false;

  /* 当前鼠标停留的位置 */
  hoverItem = 0;

  @Watch('value')
  handleValue(v: number[]) {
    if (this.multiple) {
      this.activeList = v;
    } else {
      this.activeList = [v];
    }
    this.localList.forEach(item => {
      item.active = this.activeList.includes(item.value);
    });
  }

  created() {
    this.localList = this.list;
    if (this.multiple) {
      this.activeList = this.value as number[];
    } else {
      this.activeList = [this.value];
    }
    this.datePickerValues = new Set();
    this.localList.forEach(item => {
      item.active = this.activeList.includes(item.value);
      if (item.active) {
        this.datePickerValues.add(item.value);
      }
    });
  }

  /* 弹层 */
  handlePopover() {
    this.$nextTick(() => {
      this.popoverInstances = this.$bkPopover(this.$el, {
        content: this.dayPickerRef,
        trigger: 'manual',
        arrow: false,
        placement: 'bottom-start',
        theme: 'light common-monitor',
        maxWidth: 280,
        distance: 5,
        duration: [275, 0],
        interactive: true,
        followCursor: false,
        flip: true,
        flipBehavior: ['bottom', 'top'],
        flipOnUpdate: true,
        onHidden: () => {
          this.popoverInstances.hide(0);
          this.popoverInstances.destroy();
          this.popoverInstances = null;
          this.removeShiftEventEvent();
        },
      });
      this.popoverInstances.show();
      this.addShiftEventEvent();
    });
  }

  /* 选中 */
  handleSelectDate(event: Event, item: IDay) {
    event.stopPropagation();
    if (this.multiple) {
      /* 按住shift时多选 */
      if (this.isDownShift) {
        this.datePickerValues = new Set();
        const obj = this.firstAndLast();
        const { firstItem } = obj;
        const { lastItem } = obj;
        const setState = (v: IDay) => {
          v.active = true;
          this.datePickerValues.add(v.value);
        };
        this.localList.forEach(v => {
          if (firstItem === 0) {
            if (v.value <= this.hoverItem) setState(v);
          } else {
            if (firstItem <= this.hoverItem) {
              if (v.value <= this.hoverItem && v.value >= firstItem) setState(v);
            } else if (lastItem >= this.hoverItem) {
              if (v.value >= this.hoverItem && v.value <= lastItem) setState(v);
            }
          }
        });
      } else {
        item.active = !item.active;
        if (this.datePickerValues.has(item.value)) {
          this.datePickerValues.delete(item.value);
        } else {
          this.datePickerValues.add(item.value);
        }
      }
      this.activeList = Array.from(this.datePickerValues).sort((a: number, b: number) => a - b);
      this.handleChange(this.activeList);
    } else {
      if (!item.active) {
        item.active = !item.active;
      }
      this.activeList = [item.value];
      this.datePickerValues = new Set();
      this.datePickerValues.add(item.value);
      this.handleChange(this.activeList[0]);
    }
  }

  /* 清除选中的值 */
  handleClearMonthList() {
    this.activeList = [];
    this.datePickerValues = new Set();
    this.localList.forEach(item => {
      item.active = false;
    });
    this.handleChange(this.activeList);
  }

  @Emit('change')
  handleChange(value: number[]) {
    return value;
  }

  /* 按住shift可全选 */
  addShiftEventEvent() {
    document.addEventListener('keydown', this.shiftEventDown);
    document.addEventListener('keyup', this.shiftEventUp);
  }
  removeShiftEventEvent() {
    document.removeEventListener('keydown', this.shiftEventDown);
    document.removeEventListener('keyup', this.shiftEventUp);
    this.isDownShift = false;
  }
  shiftEventDown(event) {
    if (!this.multiple) return;
    if (event.keyCode === 16) {
      this.isDownShift = true;
    }
  }
  shiftEventUp(event) {
    if (!this.multiple) return;
    if (event.keyCode === 16) {
      this.isDownShift = false;
    }
  }

  /* 当前hover的元素 */
  handleMouseenter(item: IDay) {
    this.hoverItem = item.value;
  }
  handleMouseleave() {
    this.hoverItem = 0;
  }

  /* 按住shift时的样式 */
  getItemStyle(item: IDay) {
    let style = {};
    const obj = this.firstAndLast();
    const { firstItem } = obj;
    const { lastItem } = obj;
    const setStyle = () => {
      if (item.active) {
        style = {};
      } else {
        style = {
          background: '#f0f1f5',
        };
      }
    };
    if (this.isDownShift) {
      if (firstItem === 0) {
        if (item.value < this.hoverItem) setStyle();
      } else {
        if (firstItem < this.hoverItem) {
          if (item.value < this.hoverItem && item.value > firstItem) setStyle();
        } else if (lastItem > this.hoverItem) {
          if (item.value > this.hoverItem && item.value < lastItem) setStyle();
        }
      }
    }
    return style;
  }

  firstAndLast() {
    const obj = {
      firstItem: 0,
      lastItem: 0,
    };
    this.localList.forEach(v => {
      if (obj.firstItem === 0 && v.active) {
        obj.firstItem = v.value;
      }
      if (v.active) {
        obj.lastItem = v.value;
      }
    });
    return obj;
  }

  render() {
    return (
      <div
        class='simple-day-pick-component'
        onClick={this.handlePopover}
      >
        {this.activeList.length ? (
          <span class='list'>{this.activeList.join('、')}</span>
        ) : (
          <span class='list placeholder'>{this.$t('选择每月时间范围')}</span>
        )}
        <i class={['bk-icon', 'icon-angle-down', { 'up-arrow': !!this.popoverInstances }]} />
        {this.activeList.length ? (
          <i
            class='bk-select-clear bk-icon icon-close'
            onClick={this.handleClearMonthList}
          />
        ) : undefined}
        <div style={{ display: 'none' }}>
          <ul
            ref='dayPicker'
            class='duty-arranges-date-list-wrapper'
          >
            {this.localList.map((item, index) => (
              <li
                key={index}
                style={this.getItemStyle(item)}
                class={['item', { active: item.active }]}
                onClick={(event: Event) => this.handleSelectDate(event, item)}
                onMouseenter={() => this.handleMouseenter(item)}
                onMouseleave={() => this.handleMouseleave()}
              >
                <span>{item.value}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    );
  }
}
