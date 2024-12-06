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

import type { FieldFilteringType, FieldListType, FieldValue, IFilterCondition } from '../typings';

import './field-list.scss';
/** 维度值记录排名前5 */
const TOP_NUM = 5;
@Component
export default class FieldList extends tsc<FieldListType.IProp, FieldListType.IEvent> {
  @Prop({ type: Array, default: () => [] }) value: FieldValue[];
  @Prop({ type: Boolean, default: false }) allowDisplay; // 允许控制显示隐藏
  @Prop({ default: 0, type: Number }) total: number; // 记录总数

  /** 展开字段的key */
  expandedData = [];

  /**
   * @description: 切换字段的显示、隐藏
   * @param {Event} evt 点击事件
   * @param {FieldValue} item 单条字段数据
   * @return {*}
   */
  @Emit('checkedChange')
  handleFieldChecked(evt: Event, item: FieldValue, index: number) {
    evt.stopPropagation();
    // item.checked = !item.checked
    return {
      index,
      checked: !item.checked,
      field: item.field,
    };
  }

  /**
   * @description: 添加为过滤条件
   * @param {FieldListType.AddConditionType} method 添加条件的method
   * @return {IFilterCondition.localValue}
   */
  @Emit('addCondition')
  handleAddConditon(
    method: FieldListType.AddConditionType,
    item: FieldValue,
    val: FieldFilteringType.IFieldValue
  ): IFilterCondition.localValue {
    return {
      key: item.field,
      method,
      value: [val.id],
      condition: 'and',
    };
  }

  /**
   * @description: 处理维度别名
   */
  handleAlias(key: string) {
    const aliasMap = {
      event_name: this.$t('事件名'),
      target: this.$t('目标'),
    };
    return aliasMap[key] ?? key;
  }
  render() {
    const titleSlot = (item: FieldValue, index: number) => (
      <div class={['collapse-item-title', { 'is-expanded': this.expandedData.includes(item.key) }]}>
        <span class='title-left'>
          <i class={['icon-monitor', 'icon-mc-triangle-down', { active: this.expandedData.includes(item.key) }]} />
          {/* <span class="type-icon">#</span> */}
          <span class='field-name'>{this.handleAlias(item.field)}</span>
          <span class='field-value-count'>({item.total})</span>
        </span>
        <span class='title-center' />
        {this.allowDisplay ? (
          <span
            class='display-btn'
            onClick={evt => this.handleFieldChecked(evt, item, index)}
          >
            {this.$t(item.checked ? '隐藏' : '展示')}
          </span>
        ) : undefined}
      </div>
    );
    const contentSlot = (item: FieldValue) => {
      // 统计排名前五的数量
      const count = item.dimensions.reduce((total, cur, index) => {
        if (index < TOP_NUM) {
          return total + cur.count;
        }
        return total;
      }, 0);
      return (
        <div class={['field-list-item-content']}>
          <div class='field-list-item-desc'>
            {this.$t('{0}/{1} 条记录中数量排名前 {2} 的数', [count, this.total, TOP_NUM])}
          </div>
          {item.dimensions.map((val, i) => {
            if (!item.showMore && i + 1 > TOP_NUM) return undefined;
            return (
              <div
                key={val.id || i}
                class='val-percent-item'
              >
                <div class='val-percent-progress'>
                  <div class='val-percent-text'>
                    <span class='field'>{val.id || '--'}</span>
                    <span class='percent'>{val.percent}%</span>
                  </div>
                  <bk-progress
                    percent={val.percent / 100}
                    show-text={false}
                    size='small'
                    stroke-width={6}
                    theme='success'
                  />
                </div>
                <i
                  class='icon-monitor icon-jia'
                  onClick={() => this.handleAddConditon('eq', item, val)}
                />
                <i
                  class='icon-monitor icon-jian'
                  onClick={() => this.handleAddConditon('neq', item, val)}
                />
              </div>
            );
          })}
          {item.dimensions.length > 5 ? (
            <div class='link-btn'>
              <span
                class='btn-more'
                onClick={() => (item.showMore = true)}
              >
                {this.$t('更多')}
              </span>
              {/* <span class="btn-grafana">{this.$t('查看仪表盘')}<i class="icon-monitor icon-mc-link"></i></span> */}
            </div>
          ) : undefined}
        </div>
      );
    };
    return (
      <bk-collapse
        class='collapse-wrap collapse-wrap-event'
        vModel={this.expandedData}
      >
        {this.value.map((item, index) => (
          <bk-collapse-item
            key={item.key}
            class={['collapse-item', { 'is-empty': !item.dimensions?.length }]}
            scopedSlots={{
              default: () => titleSlot(item, index),
              content: () => contentSlot(item),
            }}
            disabled={!item.dimensions?.length}
            name={item.key}
          />
        ))}
      </bk-collapse>
    );
  }
}
