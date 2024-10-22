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

import { Component, Prop, Emit, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { LIMIT_TYPE_LIST } from '../../utils';

import type { IServiceConfig } from '../../type';

import './group-by-view.scss';
interface IGroupByViewProps {
  searchList: IServiceConfig[];
  groupBy?: string[];
}
interface IGroupByViewEvent {
  onChange?: (val: string[]) => void;
}
@Component({
  name: 'GroupByView',
  components: {},
})
export default class GroupByView extends tsc<IGroupByViewProps, IGroupByViewEvent> {
  @Prop({ required: true, type: Array, default: () => [] }) searchList: IServiceConfig[];
  @Prop({ type: Array, default: () => [] }) groupBy: string[];

  /* groupBy已选项tag */
  groupBySelectedTags: IServiceConfig[] = [];
  /* groupBy已选项key */
  groupBySelectedKey = [];
  /* groupBy可选项  */
  groupByList: IServiceConfig[] = [];
  /* 是否显示选择器 */
  isShowPicker = false;

  limitTypeList = LIMIT_TYPE_LIST;
  limitFilter = {
    value: '10',
    position: 'top',
    key: 1,
  };
  limitType = 1;

  @Watch('groupBy', { immediate: true })
  handleWatchGroupBy() {
    if (JSON.stringify(this.groupBySelectedKey) !== JSON.stringify(this.groupBy)) {
      this.groupBySelectedKey = [...this.groupBy];
      const groupByTags = [];
      const groupBySet = new Set(this.groupBy);
      this.groupByList = this.searchList.map(item => {
        const checked = groupBySet.has(item.label);
        if (checked) {
          groupByTags.push(item);
        }
        return {
          ...item,
          checked: checked,
        };
      });
      this.groupBySelectedTags = groupByTags;
    }
  }

  @Watch('searchList', { immediate: true })
  handleWatchSearchList() {
    const groupBySet = new Set(this.groupBy);
    this.groupByList = this.searchList.map(item => ({
      ...item,
      checked: groupBySet.has(item.label),
    }));
  }
  @Emit('change')
  emitChange() {
    return this.groupBySelectedKey;
  }

  handleChange() {
    const groupByKey = [];
    const groupByTags = [];
    for (const item of this.groupByList) {
      if (item.checked) {
        groupByKey.push(item.label);
        groupByTags.push(item);
      }
    }
    this.groupBySelectedKey = groupByKey;
    this.groupBySelectedTags = groupByTags;
  }

  @Emit('filter')
  handleChangeLimit() {
    return this.limitFilter;
  }
  /**
   * @description 展示选择器
   */
  handleAdd() {
    this.isShowPicker = true;
  }
  /**
   * @description 选中
   * @param item
   */
  chooseSelect(item) {
    item.checked = !item.checked;
    this.handleChange();
  }
  /* 收起groupBy选择 */
  handleHide() {
    this.isShowPicker = false;
    this.emitChange();
  }

  renderTagView() {
    const len = this.groupBySelectedTags.length;
    if (len > 2) {
      const list = this.groupBySelectedTags.slice(0, 2);
      return (
        <div>
          {list.map(item => (
            <bk-tag key={item.label}>{item.name}</bk-tag>
          ))}
          <bk-tag
            v-bk-tooltips={this.groupBySelectedTags
              .slice(2)
              .map(item => item.name)
              .join('、')}
          >
            {' '}
            +{len - 2}
          </bk-tag>
        </div>
      );
    }
    return this.groupBySelectedTags.map(item => <bk-tag key={item.label}>{item.name}</bk-tag>);
  }

  render() {
    return (
      <div class='apm-service-caller-callee-group-by-view'>
        <div class='group-by-tag-view'>
          {!this.isShowPicker && this.groupBySelectedKey.length > 0 && this.renderTagView()}
        </div>
        {this.isShowPicker ? (
          <bk-popover
            ext-cls='apm-service-caller-callee-group-by-selector'
            arrow={false}
            placement='bottom'
            theme='light'
            trigger='click'
            onHide={this.handleHide}
          >
            <div
              class='group-by-select'
              title={this.groupBySelectedTags.map(item => item.name).join(',')}
            >
              {this.groupBySelectedTags.map(item => item.name).join(',')}
              <i class='icon-monitor icon-arrow-down' />
            </div>
            <div
              class='group-by-select-list'
              slot='content'
            >
              {this.groupByList.map(option => {
                return (
                  <div
                    key={option.label}
                    class={['group-by-select-item', { active: option.checked }]}
                    onClick={() => this.chooseSelect(option)}
                  >
                    {option.name}
                    {option.checked && <i class='icon-monitor icon-mc-check-small' />}
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
        {this.groupBySelectedKey.length > 0 && !this.isShowPicker && (
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
