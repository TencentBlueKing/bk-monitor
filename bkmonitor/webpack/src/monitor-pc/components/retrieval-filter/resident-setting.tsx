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

import ResidentSettingTransfer from './resident-setting-transfer';
import SettingKvSelector from './setting-kv-selector';
import { defaultWhereItem, type IFilterField, type IWhereItem } from './utils';

import './resident-setting.scss';
interface IProps {
  fields: IFilterField[];
}

interface ILocalValue {
  field: IFilterField;
  value: IWhereItem;
}

@Component
export default class ResidentSetting extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Ref('selector') selectorRef: HTMLDivElement;
  popoverInstance = null;

  localValue: ILocalValue[] = [];

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
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 15,
      zIndex: 998,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  handleShowSettingTransfer(event: MouseEvent) {
    event.stopPropagation();
    this.handleShowSelect({
      target: this.$el,
    } as any);
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
  handleConfirm(fields: IFilterField[]) {
    this.localValue = fields.map(item => ({
      field: item,
      value: defaultWhereItem({
        key: item.name,
      }),
    }));
    this.destroyPopoverInstance();
  }

  render() {
    return (
      <div class='retrieval-filter__resident-setting-component'>
        <span
          class='left-btn'
          onClick={this.handleShowSettingTransfer}
        >
          <span class='icon-monitor icon-setting' />
          <span class='setting-text'>{this.$t('设置筛选')}</span>
        </span>
        <div class='right-content'>
          {this.localValue.length ? (
            this.localValue.map((item, index) => (
              <SettingKvSelector
                key={index}
                class='mb-4 mr-4'
                field={item.field}
                value={item.value}
              />
            ))
          ) : (
            <span class='placeholder-text'>{`（${this.$t('暂未设置常驻筛选，请点击左侧设置按钮')}）`}</span>
          )}
        </div>
        <div style='display: none;'>
          <div ref='selector'>
            <ResidentSettingTransfer
              fields={this.fields}
              onConfirm={this.handleConfirm}
            />
          </div>
        </div>
      </div>
    );
  }
}
