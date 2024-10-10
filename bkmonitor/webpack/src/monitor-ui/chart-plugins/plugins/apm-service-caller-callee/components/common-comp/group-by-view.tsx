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

import { Component, Prop, Emit } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { LIMIT_TYPE_LIST } from '../../utils';

import type { IServiceConfig } from '../../type';

import './group-by-view.scss';
interface IGroupByViewProps {
  searchList: IServiceConfig[];
}
interface IGroupByViewEvent {
  onChange: () => void;
}
@Component({
  name: 'GroupByView',
  components: {},
})
export default class GroupByView extends tsc<IGroupByViewProps, IGroupByViewEvent> {
  @Prop({ required: true, type: Array, default: () => [] }) searchList: IServiceConfig[];
  limitTypeList = LIMIT_TYPE_LIST;
  isShowPicker = false;
  changedValue = [];
  limitFilter = {
    value: '10',
    position: 'top',
    key: 'request',
  };
  limitType = 1;
  handleAdd() {
    this.isShowPicker = true;
  }
  @Emit('change')
  handleChange() {
    this.isShowPicker = false;
    return {
      value: this.changedValue,
      data: this.showKeyList,
    };
  }
  get showKeyList() {
    return this.searchList.filter(item => this.changedValue.includes(item.label)).map(item => item.name);
  }
  // 选中key值
  chooseSelect(item) {
    const { label } = item;
    const isHas = this.changedValue.includes(label);
    if (isHas) {
      this.changedValue = this.changedValue.filter(val => val !== label);
    } else {
      this.changedValue.push(label);
    }
    this.changedValue = [...new Set(this.changedValue)];
  }
  renderTagView() {
    const len = this.showKeyList.length;
    if (len > 2) {
      const list = this.showKeyList.slice(0, 2);
      return (
        <div>
          {list.map(item => (
            <bk-tag key={item}>{item}</bk-tag>
          ))}
          <bk-tag v-bk-tooltips={this.showKeyList.slice(2).join('、')}> +{len - 2}</bk-tag>
        </div>
      );
    }
    return this.showKeyList.map(item => <bk-tag key={item}>{item}</bk-tag>);
  }
  @Emit('filter')
  handleChangeLimit() {
    return this.limitFilter;
  }
  render() {
    return (
      <div class='group-by-view'>
        <div class='group-by-tag-view'>
          {!this.isShowPicker && this.changedValue.length > 0 && this.renderTagView()}
        </div>
        {this.isShowPicker ? (
          <bk-popover
            ext-cls='group-by-selector'
            arrow={false}
            placement='bottom'
            theme='light'
            trigger='click'
            onHide={this.handleChange}
          >
            <div
              class='group-by-select'
              title={this.showKeyList.join(',')}
            >
              {this.showKeyList.join(',')}
              <i class='icon-monitor icon-arrow-down' />
            </div>
            <div
              class='group-by-select-list'
              slot='content'
            >
              {this.searchList.map(option => {
                const isActive = this.changedValue.includes(option.label);
                return (
                  <div
                    key={option.label}
                    class={['group-by-select-item', { active: isActive }]}
                    onClick={() => this.chooseSelect(option)}
                  >
                    {option.name}
                    {isActive && <i class='icon-monitor icon-mc-check-small' />}
                  </div>
                );
              })}
            </div>
          </bk-popover>
        ) : (
          <span
            class='group-by-add'
            onClick={this.handleAdd}
          >
            <i class='icon-monitor icon-plus-line' />
          </span>
        )}
        {this.changedValue.length > 0 && !this.isShowPicker && (
          <div class='limit-selector'>
            <span>limit</span>
            <bk-select
              style='width: 150px;'
              ext-cls='ml-8'
              v-model={this.limitFilter.key}
              behavior='simplicity'
              clearable={false}
              onChange={this.handleChangeLimit}
            >
              {this.limitTypeList.map(option => (
                <bk-option
                  id={option.id}
                  key={option.id}
                  name={option.name}
                />
              ))}
            </bk-select>
            <bk-select
              style='width: 90px;'
              ext-cls='ml-8'
              v-model={this.limitFilter.position}
              behavior='simplicity'
              clearable={false}
              onChange={this.handleChangeLimit}
            >
              <bk-option
                id={'top'}
                key={'top'}
                name={'top'}
              />
              <bk-option
                id={'bottom'}
                key={'bottom'}
                name={'bottom'}
              />
            </bk-select>
            <bk-input
              style='width: 150px;'
              class='ml-8'
              v-model={this.limitFilter.value}
              behavior='simplicity'
              min={1}
              type='number'
              onChange={this.handleChangeLimit}
            />
          </div>
        )}
      </div>
    );
  }
}
