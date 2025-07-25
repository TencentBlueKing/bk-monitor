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

import _ from 'lodash';

import KeyValueSelector from '../commom/key-value-selector';

import './index.scss';

interface IEmit {
  onChange: (value: IProps['data']) => void;
}

interface IProps {
  data: {
    alias: string;
    key: string;
    method: string;
    value: string[];
  }[];
}

@Component
export default class FilterConditions extends tsc<IProps, IEmit> {
  @Prop({ type: Array, required: true }) readonly data: IProps['data'];

  handleChange(payload: IProps['data'][number]) {
    const latestValue = [...this.data];
    const index = _.findIndex(latestValue, item => item.key === payload.key);
    latestValue.splice(index, 1, payload);

    this.$emit('change', latestValue);
  }

  render() {
    return (
      <div class='filter-conditions-common-list'>
        {this.data.map(dimensionItem => (
          <KeyValueSelector
            key={dimensionItem.key}
            class='selector-item'
            data={dimensionItem}
            onChange={this.handleChange}
          />
        ))}
        {this.data.length > 0 && (
          <router-link
            style='color: #3a84ff;'
            to={{
              name: 'custom-detail-timeseries',
              params: {
                id: this.$route.params.id,
                activeTab: 'dimension',
              },
            }}
            target='_blank'
          >
            <span class='filter-conditions-setting'>
              {this.$t('设置')}
              <i class='icon-monitor icon-mc-goto setting-icon' />
            </span>
          </router-link>
        )}
        {this.data.length < 1 && (
          <i18n path='(暂未设置常驻筛选，请前往 {0} 设置)'>
            <router-link
              style='color: #3a84ff;'
              to={{
                name: 'custom-detail-timeseries',
                params: {
                  id: this.$route.params.id,
                  activeTab: 'dimension',
                },
              }}
              target='_blank'
            >
              {this.$t('维度管理')}
            </router-link>
          </i18n>
        )}
      </div>
    );
  }
}
