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

import type { IGroupData } from '../strategy-config-list/group';

import './filter-panel-popover.scss';

interface IProps {
  showFiled: string[];
  list: IGroupData[];
}

interface IEmits {
  onFilterFieldChange: (fields: string[]) => void;
  onFilterFieldOrderChange: (originIndex: number, targetIndex: number) => void;
}

@Component
export default class FilterPanelPopover extends tsc<IProps, IEmits> {
  @Prop({ default: () => [] }) showFiled!: string[];
  @Prop({ default: () => [] }) list!: IGroupData[];

  show = false;
  localShowFiled = [];

  handleFilterPopoverChange(show: boolean) {
    if (!show) {
      this.$emit('filterFieldChange', this.localShowFiled);
    } else {
      this.localShowFiled = this.showFiled;
    }
    this.show = show;
  }

  handleDragstart(e: DragEvent, index: number) {
    e.dataTransfer.setData('dragIndex', String(index));
  }

  handleDrop(e: DragEvent, index: number) {
    const dragIndex = e.dataTransfer.getData('dragIndex');
    this.$emit('filterFieldOrderChange', dragIndex, index);
  }

  handleDragover(e: DragEvent) {
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
              {this.list.map((item, index) => (
                <li
                  key={item.id}
                  class='field-list-item'
                  draggable
                  onDragover={e => this.handleDragover(e)}
                  onDragstart={e => this.handleDragstart(e, index)}
                  onDrop={e => this.handleDrop(e, index)}
                >
                  <bk-checkbox value={item.id}>{item.name}</bk-checkbox>
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
