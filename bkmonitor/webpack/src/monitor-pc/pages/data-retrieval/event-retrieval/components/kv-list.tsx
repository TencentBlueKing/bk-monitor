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
import { Component, Emit, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText } from '../../../../../monitor-common/utils/utils';
import { EventRetrievalViewType, IFilterCondition } from '../../typings';

import TextSegmentation from './text-segmentation';

import './kv-list.scss';

interface IProps {
  data: object;
}

interface IEvent {
  onDrillSearch: EventRetrievalViewType.IDrillModel;
}

interface FieldModel {
  field: string;
  hasFilterCondition: boolean;
  value: string;
}

@Component
export default class FieldFiltering extends tsc<IProps, IEvent> {
  @Prop({ default: () => ({}), type: Object }) data: object;

  @InjectReactive({ from: 'eventWhere', default: [] }) eventWhere: IFilterCondition.localValue[];
  @InjectReactive({ from: 'filterConditionList', default: [] }) filterConditionList;

  toolMenuList = [
    { id: 'eq', icon: 'bk-icon icon-enlarge-line search' },
    { id: 'neq', icon: 'bk-icon icon-narrow-line search' },
    { id: 'copy', icon: 'icon icon-monitor icon-mc-copy' }
  ];
  toolMenuTips = {
    eq: '=',
    neq: '!=',
    copy: window.i18n.t('复制')
  };

  @Emit('drillSearch')
  handleDrillSearch(condition: string | IFilterCondition.localValue) {
    return {
      type: typeof condition === 'string' ? 'search' : 'filter',
      condition
    };
  }

  get fieldMap() {
    return Object.entries(this.data).map(([key, value]) => ({
      field: key,
      hasFilterCondition: this.filterConditionList.some(item => item.id === key || item.id === this.transformName(key)),
      value
    }));
  }

  transformName(field: string) {
    return field.startsWith('dimensions.') ? field.split('.')[1] : field;
  }

  /** 判断下钻操作是否可用 */
  isDisableMenu(field: string) {
    const key = field.startsWith('dimensions.') ? field.split('.')[1] : field;
    return ['time'].includes(field) || this.eventWhere.some(item => item.key === key);
  }
  /** 判断添加禁用类名 */
  checkDisable(operate: string, field: FieldModel) {
    const fieldName = this.transformName(field.field);
    if (fieldName === 'time') {
      return {
        disabled: true,
        tooltip: this.$t('不支持查询语句')
      };
    }
    if (operate === 'eq' && this.eventWhere.some(where => where.method === operate && where.key === fieldName)) {
      return {
        disabled: true,
        tooltip: this.$t('已添加过滤条件')
      };
    }
    if (operate === 'neq' && !field.hasFilterCondition) {
      return {
        disabled: true,
        tooltip: this.$t('不支持 != 操作')
      };
    }
    return {
      disabled: false,
      tooltip: `${fieldName} ${this.toolMenuTips[operate]} ${field.value}`
    };
  }

  /** 判断是否是不可操作的字段 */
  handleMenuClick(operate: string, field: FieldModel) {
    const disableMenu = this.checkDisable(operate, field).disabled;
    if (!disableMenu) this.drillMenu(operate, field.value, field);
  }
  /** 事件下钻 */
  drillMenu(operate: string, value: string, field: FieldModel) {
    let drillValue = value;
    const fieldName = this.transformName(field.field);
    switch (operate) {
      case 'eq':
      case 'neq':
        if (field.hasFilterCondition) {
          this.handleDrillSearch({
            condition: 'and',
            method: operate,
            key: fieldName,
            value: [drillValue]
          });
        } else {
          if (fieldName === 'event.content') {
            drillValue = `"${value.replace(/([+\-=&|><!(){}[\]^"~*?\\:/])/g, v => `\\${v}`)}"`;
          }
          this.handleDrillSearch(`${fieldName}: ${drillValue}`);
        }
        break;
      case 'copy':
        copyText(drillValue, msg => {
          this.$bkMessage({
            message: msg,
            theme: 'error'
          });
          return;
        });
        this.$bkMessage({
          message: this.$t('复制成功'),
          theme: 'success'
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
                  class={['icon', option.icon, this.checkDisable(option.id, item).disabled ? 'is-disabled' : '']}
                  v-bk-tooltips={{ content: this.checkDisable(option.id, item).tooltip, delay: 300 }}
                  onClick={() => this.handleMenuClick(option.id, item)}
                ></span>
              ))}
            </div>
            <div class='field-value'>
              <TextSegmentation
                content={String(item.value)}
                fieldType={item.field}
                onMenuClick={({ type, value }) => this.drillMenu(type, value, item)}
              />
            </div>
          </div>
        ))}
      </div>
    );
  }
}
