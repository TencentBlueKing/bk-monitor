/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils/utils';

import RegexOperation from './components/regex-operation';

import type { IListItem } from '../../components/result-preview';

import './index.scss';

/**
 * 自动分组组件
 * 根据分组规则（正则表达式）自动发现并分组指标
 */
@Component({
  name: 'AutoGroup',
})
export default class AutoGroup extends tsc<any> {
  /** 自动分组列表数据 */
  @Prop({ default: () => [] }) autoList: IListItem[];

  /** 正则表达式列表 */
  regexList: IListItem[] = [];

  /**
   * 监听自动分组列表变化，同步更新正则表达式列表
   * @param newVal 新的自动分组列表数据
   */
  @Watch('autoList', { immediate: true })
  onAutoListChange(newVal: IListItem[]) {
    this.regexList = newVal;
  }

  /**
   * 添加新的正则表达式项
   */
  handleAddItem() {
    const newItem = {
      id: random(8),
      name: '',
    };
    this.regexList.push(newItem);
  }

  /**
   * 删除指定的正则表达式项
   * @param id 要删除的项的唯一标识
   */
  handleDeleteItem(id: string) {
    this.regexList = this.regexList.filter(item => item.id !== id);
    this.$emit('deleteItem', id);
  }

  /**
   * 处理正则表达式输入事件
   * @param data 输入的正则表达式数据
   */
  handleRegexInput(data: IListItem) {
    this.$emit('regexInput', data);
  }

  /**
   * 清空所有选择的正则表达式
   */
  clearSelect() {
    this.regexList = [];
  }

  render() {
    return (
      <div class='auto-group-main'>
        <bk-alert
          style='margin-bottom: 12px;'
          title={this.$t('根据规则自动发现未来新指标，存量指标不生效。')}
          type='info'
        />
        <div class='regex-list-main'>
          {this.regexList.map(item => (
            <RegexOperation
              key={item.id}
              data={item}
              onDelete={this.handleDeleteItem}
              onRegexInput={this.handleRegexInput}
            />
          ))}
          <bk-button
            class='add-item-btn'
            theme='primary'
            text
            onClick={this.handleAddItem}
          >
            <i class='icon-monitor icon-mc-add add-icon' />
            {this.$t('正则表达式')}
          </bk-button>
        </div>
      </div>
    );
  }
}
