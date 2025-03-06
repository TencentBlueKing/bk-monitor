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
import { Component, InjectReactive, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import FieldTypeIcon from './field-type-icon';

import type { IDimensionField } from '../typing';

import './explore-kv-list.scss';

interface IExploreKvListProps {
  data: Record<string, any>;
  entitiesMap?: Record<string, any>;
}

@Component
export default class ExploreKvList extends tsc<IExploreKvListProps> {
  @Prop({ default: () => ({}), type: Object }) data: Record<string, any>;
  @Prop({ default: () => ({}), type: Object }) entitiesMap: Record<string, any>;

  @InjectReactive('fieldList') fieldList: IDimensionField[];

  jumpLinkRender(item) {
    const entities = this.entitiesMap[item.name];
    if (!entities) {
      return;
    }
    if (entities?.dependent_fields?.some(field => !this.data[field])) {
      return;
    }

    return (
      <div class='value-jump-link'>
        <span class='jump-link-label'>{entities?.alias || '主机'}</span>
        <i class='icon-monitor icon-mc-goto' />
      </div>
    );
  }

  render() {
    return (
      <div class='explore-kv-list'>
        {this.fieldList.map(item => (
          <div
            key={item.name}
            class='kv-list-item'
          >
            <div class='item-label'>
              <FieldTypeIcon
                class='kv-label-icon'
                type={item.type}
              />
              <span title={item.name}> {item.name}</span>
            </div>
            <div class='item-value'>
              {this.jumpLinkRender(item)}
              <span class='value-text'>{this.data[item.name] ?? '--'}</span>
            </div>
          </div>
        ))}
      </div>
    );
  }
}
