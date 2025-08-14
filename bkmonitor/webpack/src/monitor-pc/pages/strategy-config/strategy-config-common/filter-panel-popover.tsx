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

import type { IGroupData } from '../strategy-config-list/group';

import './filter-panel-popover.scss';

interface IEmits {
  onFilterFieldChange: (fields: { order: number[]; showFields: string[] }) => void;
}

interface IProps {
  list: IGroupData[];
  showFields: string[];
}

@Component
export default class FilterPanelPopover extends tsc<IProps, IEmits> {
  @Prop({ default: () => [] }) showFields!: string[];
  @Prop({ default: () => [] }) list!: IGroupData[];

  show = false;
  localShowFiled = [];
  localList = [];

  dragStartIndex = -1;
  dragOverIndex = -1;

  @Watch('list', { immediate: true })
  handleListChange(newVal: IGroupData[]) {
    this.localList = newVal.map((item, index) => ({ ...item, order: index }));
  }

  @Watch('showFields', { immediate: true })
  handleShowFiledChange(newVal: string[]) {
    this.localShowFiled = newVal;
  }

  handleFilterPopoverChange(show: boolean) {
    if (!show) {
      this.$emit('filterFieldChange', {
        showFields: this.localShowFiled,
        order: this.localList.map(item => item.order),
      });
    }
    this.show = show;
  }

  handleDragstart(index: number) {
    this.dragStartIndex = index;
  }

  handleDrop(index: number) {
    const origin = this.localList[this.dragStartIndex];
    this.localList[this.dragStartIndex] = this.localList[index];
    this.localList[index] = origin;
    this.localList = [...this.localList];
    this.dragOverIndex = -1;
  }

  handleDragover(e: DragEvent, index: number) {
    this.dragOverIndex = this.dragStartIndex === index ? -1 : index;
    e.preventDefault();
  }

  render() {
    return (
      <bk-popover
        ext-cls='strategy-config-filter-popover'
        placement='bottom-end'
        tippy-options={{ trigger: 'click', theme: 'light', arrow: false }}
        on-hide={() => {
          this.handleFilterPopoverChange(false);
        }}
        on-show={() => {
          this.handleFilterPopoverChange(true);
        }}
      >
        <div
          class={{
            'icon-monitor': true,
            'icon-setting': true,
            'filter-popover-trigger': true,
            active: this.show,
          }}
        />
        <div
          class='filter-popover-content'
          slot='content'
        >
          <div class='title'>{this.$t('字段设置')}</div>
          <bk-checkbox-group v-model={this.localShowFiled}>
            <ul class='field-list'>
              {this.localList.map((item, index) => (
                <li
                  key={item.id}
                  class={{
                    'field-list-item': true,
                    'drag-target-item': index === this.dragOverIndex,
                  }}
                  draggable
                  onDragover={e => this.handleDragover(e, index)}
                  onDragstart={() => this.handleDragstart(index)}
                  onDrop={() => this.handleDrop(index)}
                >
                  <bk-checkbox
                    disabled={this.localShowFiled.length === 1 && this.localShowFiled.includes(item.id)}
                    value={item.id}
                  >
                    {item.name}
                  </bk-checkbox>
                  <i class='icon-monitor icon-mc-tuozhuai' />
                </li>
              ))}
            </ul>
          </bk-checkbox-group>
        </div>
      </bk-popover>
    );
  }
}
