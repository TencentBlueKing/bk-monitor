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

import type { IServiceConfig, IFilterCondition } from '../type';

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
  @Prop({ required: true, type: Array, default: () => [] }) filterData: IFilterCondition[];
  @Prop({ required: true, type: Boolean, default: false }) isLoading: boolean;
  symbolList = SYMBOL_LIST;
  toggleKey = '';
  @Emit('search')
  handleSearch() {
    return this.filterData;
  }

  @Emit('reset')
  handleReset() {
    return this.filterData;
  }
  @Emit('change')
  changeSelect(val, item) {
    return { val, item };
  }
  @Emit('toggle')
  handleToggle(isOpen: boolean, key: string) {
    this.toggleKey = key;
    return { isOpen, key };
  }
  render() {
    return (
      <div class='caller-callee-filter'>
        <div class='search-title'>{this.$t('筛选')}</div>
        <div class='search-main'>
          {(this.searchList || []).map((item, ind) => {
            return (
              <div
                key={item.value}
                class='search-item'
              >
                <div class='search-item-label'>
                  <span>{item.text}</span>
                  {this.filterData[ind] && (
                    <bk-select
                      class='item-label-select'
                      v-model={this.filterData[ind].method}
                      clearable={false}
                      list={this.symbolList}
                      size='small'
                      onChange={val => this.changeSelect(val, item)}
                    >
                      {this.symbolList.map(opt => (
                        <bk-option
                          id={opt.value}
                          key={opt.value}
                          name={opt.label}
                        />
                      ))}
                    </bk-select>
                  )}
                </div>
                {this.filterData[ind] && (
                  <bk-select
                    v-model={this.filterData[ind].value}
                    loading={item.value === this.toggleKey && this.isLoading}
                    allow-create
                    collapse-tag
                    display-tag
                    multiple
                    onToggle={(val: boolean) => this.handleToggle(val, item.value)}
                  >
                    {(item.values || []).map(opt => (
                      <bk-option
                        id={opt.value}
                        key={opt.value}
                        name={opt.value}
                      />
                    ))}
                  </bk-select>
                )}
              </div>
            );
          })}
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
