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

/** 主被调 - 左侧筛选 */
import { Component, Prop, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { SYMBOL_LIST } from '../utils';

import type { IServiceConfig } from '../type';

import './caller-callee-filter.scss';

interface ICallerCalleeFilterProps {
  searchList: IServiceConfig[];
  filterData: IServiceConfig[];
}
interface ICallerCalleeFilterEvent {
  onReset?: () => void;
  onChange?: () => void;
  onSearch?: () => void;
}
@Component({
  name: 'CallerCalleeFilter',
  components: {},
})
export default class CallerCalleeFilter extends tsc<ICallerCalleeFilterProps, ICallerCalleeFilterEvent> {
  @Prop({ required: true, type: Array, default: () => [] }) searchList: IServiceConfig[];
  @Prop({ required: true, type: Array, default: () => [] }) filterData: IServiceConfig[];
  symbolList = SYMBOL_LIST;
  @Emit('search')
  handleSearch() {
    return this.filterData;
  }
  @Emit('reset')
  handleReset() {
    this.filterData.map(item => Object.assign(item, { operate: 1, values: [] }));
    return this.filterData;
  }
  @Emit('change')
  changeSelect(val, item) {
    return { val, item };
  }
  render() {
    return (
      <div class='caller-callee-filter'>
        <div class='search-title'>{this.$t('筛选')}</div>
        <div class='search-main'>
          {(this.searchList || []).map((item, ind) => (
            <div
              key={item.label}
              class='search-item'
            >
              <div class='search-item-label'>
                <span>{this.$t(item.name)}</span>
                <bk-select
                  class='item-label-select'
                  v-model={this.filterData[ind].operate}
                  clearable={false}
                  list={this.symbolList}
                  size='small'
                  onChange={val => this.changeSelect(val, item)}
                >
                  {this.symbolList.map(item => (
                    <bk-option
                      id={item.value}
                      key={item.value}
                      name={item.label}
                    />
                  ))}
                </bk-select>
              </div>
              <bk-select
                v-model={this.filterData[ind].values}
                multiple
                searchable
              >
                {(item?.values || []).map(item => (
                  <bk-option
                    id={item}
                    key={item}
                    name={item}
                  />
                ))}
              </bk-select>
            </div>
          ))}
        </div>
        <div class='search-btn-group'>
          <bk-button
            theme='primary'
            onClick={this.handleSearch}
          >
            {this.$t('查询')}
          </bk-button>
          <bk-button onClick={this.handleReset}>{this.$t('重置')}</bk-button>
        </div>
      </div>
    );
  }
}
