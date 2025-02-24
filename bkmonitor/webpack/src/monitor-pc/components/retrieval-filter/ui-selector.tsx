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

import KvTag from './kv-tag';
import UiSelectorOptions from './ui-selector-options';
import {
  ECondition,
  EMethod,
  type IFilterField,
  EFieldType,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
} from './utils';

import './ui-selector.scss';

interface IProps {
  fields: IFilterField[];
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
}

@Component
export default class UiSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  @Ref('selector') selectorRef: HTMLDivElement;

  showSelector = false;

  localValue = [
    {
      key: { id: 'key001', name: 'key001' },
      value: [{ id: 'cls-f6cqrjth', name: 'cls-f6cqrjth' }],
      method: { id: EMethod.eq, name: '=' },
      condition: { id: ECondition.and, name: 'AND' },
      hide: false,
    },
    {
      key: { id: 'key001', name: 'key002' },
      value: [{ id: 'cls-f6cqrjth', name: 'cls-f6cqrjth' }],
      method: { id: EMethod.eq, name: '=' },
      condition: { id: ECondition.and, name: 'AND' },
      hide: false,
    },
    {
      key: { id: 'key002', name: 'key002' },
      value: [
        { id: 'cls-f6cqrjth', name: 'cls-f6cqrjth' },
        { id: 'cls-f6cqrjth11zxcvzxcvasdf', name: 'cls-f6cqrjth11zxcvzxcvasdf' },
        { id: 'cls-f6cqrjth11asdfasdfasdfasdfasdf', name: 'cls-f6cqrjth11asdfasdfasdfasdfasdf' },
        { id: 'cls-f6cqrjth11asdfasdfasdfasdfasdfasdfasdf', name: 'cls-f6cqrjth11asdfasdfasdfasdfasdfasdfasdf' },
      ],
      method: { id: EMethod.include, name: '包含' },
      condition: { id: ECondition.and, name: 'AND' },
      hide: false,
    },
    {
      key: { id: 'key002', name: 'key003' },
      value: [
        { id: 'cls-f6cqrjth', name: 'cls-f6cqrjth' },
        { id: 'cls-f6cqrjth11zxcvzxcvasdf', name: 'cls-f6cqrjth11zxcvzxcvasdf' },
        { id: 'cls-f6cqrjth11asdfasdfasdfasdfasdf', name: 'cls-f6cqrjth11asdfasdfasdfasdfasdf' },
        { id: 'cls-f6cqrjth11asdfasdfasdfasdfasdfasdfasdf', name: 'cls-f6cqrjth11asdfasdfasdfasdfasdfasdfasdf' },
      ],
      method: { id: EMethod.include, name: '包含' },
      condition: { id: ECondition.and, name: 'AND' },
      hide: false,
    },
    {
      key: { id: 'key002', name: 'key001' },
      value: [
        { id: 'cls-f6cqrjth', name: 'cls-f6cqrjth' },
        { id: 'cls-f6cqrjth11zxcvzxcvasdf', name: 'cls-f6cqrjth11zxcvzxcvasdf' },
        { id: 'cls-f6cqrjth11asdfasdfasdfasdfasdf', name: 'cls-f6cqrjth11asdfasdfasdfasdfasdf' },
        { id: 'cls-f6cqrjth11asdfasdfasdfasdfasdfasdfasdf', name: 'cls-f6cqrjth11asdfasdfasdfasdfasdfasdfasdf' },
      ],
      method: { id: EMethod.include, name: '包含' },
      condition: { id: ECondition.and, name: 'AND' },
      hide: false,
    },
  ];

  popoverInstance = null;

  async handleShowSelect(event: MouseEvent) {
    if (this.popoverInstance) {
      this.destroyPopoverInstance();
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectorRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: true,
      interactive: true,
      boundary: 'window',
      distance: 20,
      zIndex: 998,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
    this.showSelector = true;
  }
  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.showSelector = false;
  }

  handleAdd(event: MouseEvent) {
    const customEvent = {
      ...event,
      target: event.currentTarget,
    };
    this.handleShowSelect(customEvent);
  }

  /**
   * @description 点击弹层取消
   */
  handleCancel() {
    this.destroyPopoverInstance();
  }
  /**
   * @description 点击弹层确认
   */
  handleConfirm() {
    this.destroyPopoverInstance();
  }

  render() {
    return (
      <div class='retrieval-filter__ui-selector-component'>
        <div
          class='add-btn'
          onClick={this.handleAdd}
        >
          <span class='icon-monitor icon-mc-add' />
          <span class='add-text'>{this.$t('添加条件')}</span>
        </div>
        {this.localValue.map((item, index) => (
          <KvTag
            key={`${index}_kv`}
            value={item}
          />
        ))}
        <div style='display: none;'>
          <div ref='selector'>
            <UiSelectorOptions
              fields={[
                {
                  type: EFieldType.all,
                  name: '*',
                  alias: this.$tc('全文检索'),
                  is_option_enabled: false,
                  supported_operations: [],
                },
                ...this.fields,
              ]}
              getValueFn={this.getValueFn}
              onCancel={this.handleCancel}
              onConfirm={this.handleConfirm}
            />
          </div>
        </div>
      </div>
    );
  }
}
