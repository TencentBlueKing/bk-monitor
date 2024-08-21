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
import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { getVariableValue } from 'monitor-api/modules/grafana';
import { deepClone } from 'monitor-common/utils/utils';

import { NUMBER_CONDITION_METHOD_LIST, STRING_CONDITION_METHOD_LIST } from '../../../constant/constant';

import type { IFilterCondition, IOption } from '../typings';

import './filter-condition.scss';

@Component
export default class FilterCondition extends tsc<IFilterCondition.IProps, IFilterCondition.IEvent> {
  @Ref('filter-condition-content') filterConditionMainRef: HTMLElement;
  @Prop({ default: () => [], type: Array }) groupBy: IFilterCondition.IGroupBy[]; // 维度列表
  @Prop({ default: () => ({}), type: Object }) varParams: IFilterCondition.VarParams;
  @Prop({ default: () => [], type: Array }) value: IFilterCondition.localValue[];

  loading = false;
  popoverInstance = null;
  curTarget = null;

  /** 维度可选值列表缓存 */
  varListCache = new Map();

  /** 已添加条件的值 */
  localValue: IFilterCondition.localValue[] = [];

  /** 当前条件的值 */
  currentValue: IFilterCondition.localValue = {
    key: '',
    method: '',
    value: [],
    condition: 'and',
  };
  /** 当前编辑的索引 */
  currentIndex = 0;
  /** 当前的操作状态 */
  curAddType: IFilterCondition.AddType = 'add';

  /** 操作的可选项 */
  conditionOption: IFilterCondition.IConditonOption[] = [];

  /** 条件值的可选项 */
  valueOption: IOption[] = [];

  /** 不需要值输入框的条件 */
  noNeedValueConditonMap = ['exists', 'does not exists'];

  /** 不同数据类型的维度所需的method不同 */
  @Watch('currentValue.key', { immediate: true })
  getMethodList() {
    const type = this.curGroupByType;
    const methodMap = {
      number: NUMBER_CONDITION_METHOD_LIST,
      string: STRING_CONDITION_METHOD_LIST,
    };
    this.conditionOption = methodMap[type] ?? STRING_CONDITION_METHOD_LIST;
  }

  /** 维度的数据类型 */
  get curGroupByType(): IFilterCondition.GroupbyType {
    return this.groupBy.find(item => item.id === this.currentValue.key)?.type || 'string';
  }

  /** 条件值的提示 */
  get valuePlaceholder() {
    return this.conditionOption.find(item => item.id === this.currentValue.method)?.placeholder;
  }
  /** 不需值输入框 */
  get noNeedValue() {
    return this.noNeedValueConditonMap.includes(this.currentValue.method);
  }
  /** 变量接口的请求参数 */
  get handleVarParams() {
    return {
      type: 'dimension',
      params: {
        ...this.varParams,
        field: this.currentValue.key as string,
        where: [],
        query_string: undefined,
      },
    };
  }

  @Watch('value', { immediate: true })
  valueChange() {
    this.localValue = deepClone(this.value?.filter(item => item.key));
  }
  @Emit('change')
  emitLocalValue() {
    return deepClone(this.localValue);
  }

  mounted() {
    this.$root.$el.addEventListener('click', this.handleDropDownHide);
  }

  beforeDestroy() {
    this.destroyPopoverInstance();
    this.$root.$el.removeEventListener('click', this.handleDropDownHide);
  }

  /**
   * @description: 注册条件弹层
   * @param {*} target 触发的目标
   */
  registerDropDown(target: HTMLElement) {
    this.popoverInstance = this.$bkPopover(target, {
      content: this.filterConditionMainRef,
      trigger: 'manual',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: true,
      hideOnClick: false,
      interactive: true,
      boundary: 'window',
      // offset: -1,
      distance: 20,
      zIndex: 1000,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.curTarget = null;
      },
    });
    this.curTarget = target;
  }
  /**
   * @description: 显示添加条件弹层
   * @param {HTMLElement} target 出发弹层的目标元素
   */
  async handleDropDownShow(target: HTMLElement) {
    if (target.isSameNode(this.curTarget)) return this.handleDropDownHide();
    this.destroyPopoverInstance();
    this.registerDropDown(target as HTMLElement);
    await this.$nextTick();
    this.popoverInstance?.show();
  }

  /**
   * @description: 隐藏添加条件弹层
   */
  handleDropDownHide() {
    this.popoverInstance?.hide?.();
  }

  /**
   * @description: 添加/编辑条件
   * @param {Event} evt
   */
  async handleShowAddCondition(evt: Event, type: IFilterCondition.AddType, index?: number) {
    evt.stopPropagation();
    const val = this.localValue[index];
    this.curAddType = type;
    type === 'add' && this.initCurValue();
    if (type === 'edit') {
      this.currentValue = deepClone(val);
      this.currentIndex = index;
    }
    this.handleGetVarList();
    this.handleDropDownShow(evt.currentTarget as HTMLElement);
  }
  // 清除popover实例
  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
  }

  /**
   * @description: 初始化条件弹出层的值
   */
  initCurValue() {
    this.currentValue = {
      key: this.groupBy[0]?.id,
      method: (this.conditionOption[0]?.id as string) || 'eq',
      value: [],
      condition: 'and',
    };
  }

  /**
   * @description: 新增/编辑一条条件
   */
  handleAddCondition() {
    setTimeout(() => {
      const validatePass = !!this.currentValue.value.length;
      if (!validatePass && !this.noNeedValue) {
        this.$bkMessage({ theme: 'error', message: this.$t('输入完整的过滤条件') });
        return;
      }
      this.curAddType === 'add' && this.localValue.push(this.currentValue);
      if (this.curAddType === 'edit') {
        const newVal = JSON.stringify(this.currentValue);
        const oldVal = JSON.stringify(this.localValue[this.currentIndex]);
        newVal !== oldVal && this.$set(this.localValue, this.currentIndex, this.currentValue);
      }
      this.emitLocalValue();
      this.initCurValue();
      this.handleDropDownHide();
    }, 200);
  }

  /**
   * @description: 处理条件的展示名
   * 对应的可选列表不存在当前id, 则返回输入id
   * @param {number} id
   * @param {IOption} options
   * @return {string} 返回展示名
   */
  findOptionName(id: number | string, options: IOption[]) {
    return options.find(item => item.id === id)?.name || id;
  }

  /**
   * @description: 删除一条条件
   * @param {Event} evt 点击事件
   * @param {number} index 数据索引
   */
  handleDeleteCondition(evt: Event, index: number) {
    evt.stopPropagation();
    this.localValue.splice(index, 1);
    this.emitLocalValue();
    this.destroyPopoverInstance();
  }

  /**
   * @description: 获取当前维度的可选值
   */
  handleGetVarList() {
    const key = JSON.stringify(this.handleVarParams.params);
    const valueCache = this.varListCache.get(key);
    if (valueCache) {
      this.valueOption = valueCache;
    } else {
      this.loading = true;
      getVariableValue(this.handleVarParams)
        .then(res => {
          this.valueOption =
            res?.map(item => ({
              id: item.value,
              name: item.label,
            })) || [];
          this.valueOption.push({
            id: '',
            name: this.$t('- 空 -'),
          });
          this.varListCache.set(key, this.valueOption);
        })
        .finally(() => {
          this.loading = false;
        });
    }
  }

  handleFieldSelected() {
    this.currentValue.value = [];
    this.handleGetVarList();
  }
  // value变化时触发
  async handleValueChange(values: string[]) {
    const hasEmpty = values?.length > 1 && values.some(v => v === '');
    if (hasEmpty) {
      if (this.currentValue.value?.some(v => v === '')) {
        this.currentValue.value = values.filter(Boolean);
        return;
      }
      this.currentValue.value = [''];
      return;
    }
    this.currentValue.value = values;
  }
  render() {
    return (
      <div class='filter-condition-wrapper'>
        <div class='filter-conditon-ref'>
          <span class='filter-title'>{this.$t('过滤条件')}</span>
          <span
            class='filter-ref-btn'
            onClick={evt => this.handleShowAddCondition(evt, 'add')}
          >
            {this.$t('添加条件')}
          </span>
        </div>
        <ul class='selected-condition-list'>
          {this.localValue.map((item, index) => (
            <li
              key={index}
              class='selected-condition-item'
              onClick={evt => this.handleShowAddCondition(evt, 'edit', index)}
            >
              <span
                class='selected-condition-label'
                v-bk-overflow-tips
              >
                {this.findOptionName(item.key, this.groupBy)}
              </span>
              <span
                class='selected-condition-condition'
                v-bk-overflow-tips
              >
                {this.findOptionName(item.method, this.conditionOption)}
              </span>
              <span
                class='selected-condition-value'
                v-bk-overflow-tips
              >
                {item.value
                  .map(val =>
                    this.findOptionName(
                      val,
                      this.varListCache.get(val) || [
                        {
                          id: '',
                          name: this.$t(' - 空 -'),
                        },
                      ]
                    )
                  )
                  .join(',')}
              </span>
              <i
                class='icon-monitor icon-mc-close'
                onClick={evt => this.handleDeleteCondition(evt, index)}
              />
            </li>
          ))}
        </ul>
        <div style='display: none;'>
          <div
            ref='filter-condition-content'
            class='filter-condition-content'
            v-bkloading={{ isLoading: this.loading }}
          >
            <div class='filter-condition-main'>
              <div class='filter-title'>{this.$t('过滤条件')}</div>
              <div class='filter-select-wrap'>
                <span class='filter-select filter-select-label'>
                  <div class='select-label'>{this.$t('字段')}</div>
                  <bk-select
                    key={JSON.stringify(this.groupBy)}
                    vModel={this.currentValue.key}
                    clearable={false}
                    allow-create
                    onSelected={this.handleFieldSelected}
                  >
                    {this.groupBy.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </bk-select>
                </span>
                <span class='filter-select filter-select-condition'>
                  <div class='select-label'>{this.$t('操作')}</div>
                  <bk-select
                    vModel={this.currentValue.method}
                    clearable={false}
                  >
                    {this.conditionOption.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </bk-select>
                </span>
                {!this.noNeedValue ? (
                  <span class='filter-select filter-select-value'>
                    <div class='select-label'>{this.$t('值')}</div>
                    <bk-tag-input
                      list={this.valueOption}
                      placeholder={this.valuePlaceholder}
                      trigger='focus'
                      value={this.currentValue.value}
                      allow-auto-match
                      allow-create
                      on-change={this.handleValueChange}
                    />
                    {/* <bk-tag-input
              key={`value-${index}-${item.key}-${JSON.stringify(this.dimensionsValueMap[item.key] || [])}`}
              class='condition-item condition-item-value'
              content-width={getPopoverWidth(this.getValueOptions(item), 20, 190)}
              list={this.getValueOptions(item)}
              paste-fn={v => this.handlePaste(v, item)}
              trigger='focus'
              value={item.value}
              allow-auto-match
              allow-create
              has-delete-icon
              on-change={(v: string[]) => this.handleValueChange(item, v)}
            />, */}
                  </span>
                ) : undefined}
              </div>
            </div>
            <div class='filter-condition-btn'>
              <bk-button
                theme='primary'
                onClick={this.handleAddCondition}
              >
                {this.$t('确定')}
              </bk-button>
              <bk-button onClick={this.handleDropDownHide}>{this.$t('取消')}</bk-button>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
