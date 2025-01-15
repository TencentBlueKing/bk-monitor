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

import { copyText } from 'monitor-common/utils/utils';

import TextSegmentation from './text-segmentation';

import type { EventRetrievalViewType } from '../../typings';

import './kv-list.scss';

@Component
export default class FieldFiltering extends tsc<EventRetrievalViewType.IDrill> {
  @Prop({ default: () => ({}), type: Object }) data: object;

  toolMenuList = [
    { id: 'is', icon: 'bk-icon icon-enlarge-line search' },
    { id: 'copy', icon: 'icon icon-monitor icon-mc-copy' },
  ];
  toolMenuTips = {
    is: window.i18n.t('添加查询语句'),
    copy: window.i18n.t('复制'),
    cannot_is: window.i18n.t('不支持查询语句'),
  };

  @Emit('drillSearch')
  handleDrillSearch(keywords: string) {
    return keywords;
  }

  get fieldMap() {
    return Object.entries(this.data).map(([key, value]) => ({
      field: key,
      value,
    }));
  }
  /** 判断下钻操作是否可用 */
  isDisableMenu(field: string) {
    return ['time'].includes(field);
  }
  /** 判断添加禁用类名 */
  checkDisable(operate: string, field: string) {
    return this.isDisableMenu(field) && operate === 'is' ? 'is-disabled' : '';
  }
  /** 获取tips文本 */
  getIconPopover(operate: string, field: string) {
    if (this.isDisableMenu(field) && operate === 'is') return this.toolMenuTips.cannot_is;
    return this.toolMenuTips[operate];
  }
  /** 判断是否是不可操作的字段 */
  handleMenuClick(operate: string, value: string, field: string) {
    const disableMenu = this.isDisableMenu(field) && operate === 'is';
    if (!disableMenu) this.drillMenu(operate, value, field);
  }
  /** 事件下钻 */
  drillMenu(operate: string, value: string, field: string) {
    let drillValue = value;
    switch (operate) {
      case 'is':
        if (field === 'event.content')
          drillValue = `"${value.replace(/([+\-=&|><!(){}[\]^"~*?\\:/])/g, v => `\\${v}`)}"`;
        this.handleDrillSearch(`${field}: ${drillValue}`);
        break;
      case 'copy':
        copyText(drillValue, msg => {
          this.$bkMessage({
            message: msg,
            theme: 'error',
          });
          return;
        });
        this.$bkMessage({
          message: this.$t('复制成功'),
          theme: 'success',
        });
        break;
    }
  }

  render() {
    return (
      <div class='kv-list-wrapper'>
        {this.fieldMap.map(item => (
          <div class='log-item'>
            <div class='field-label'>
              <span title={item.field}>{item.field}</span>
            </div>
            <div class='handle-option-list'>
              {this.toolMenuList.map(option => (
                <span
                  class={`icon ${option.icon} ${this.checkDisable(option.id, item.field)}`}
                  v-bk-tooltips={{ content: this.getIconPopover(option.id, item.field), delay: 300, allowHTML: false }}
                  onClick={() => this.handleMenuClick(option.id, item.value, item.field)}
                />
              ))}
            </div>
            <div class='field-value'>
              <TextSegmentation
                content={String(item.value)}
                fieldType={item.field}
                onMenuClick={({ type, value }) => this.drillMenu(type, value, item.field)}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }
}
