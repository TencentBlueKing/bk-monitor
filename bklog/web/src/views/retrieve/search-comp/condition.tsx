/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import {
  Component,
  Emit,
  Prop,
  Watch,
  Ref,
} from 'vue-property-decorator';
import { Switcher, Select, Option, DropdownMenu, TagInput, Button, Checkbox } from 'bk-magic-vue';
import './condition.scss';
import { Debounce } from '../../../common/util';

interface IProps {
}

const INTEGER_MIN_NUMBER = -Math.pow(2, 31) + 1;
const INTEGER_MAX_NUMBER = Math.pow(2, 31) - 1;
const LONG_MIN_NUMBER = -Math.pow(2, 63) + 1;
const LONG_MAX_NUMBER = Math.pow(2, 63) - 1;

@Component
export default class Condition extends tsc<IProps> {
  @Prop({ type: Array, required: true }) operatorList; // 操作列表
  @Prop({ type: Object, required: true }) operatorItem; // 当前操作元素
  @Prop({ type: Boolean, required: true }) isInclude: boolean; // 是否包含
  @Prop({ type: String, required: true }) name: string; // 字段名
  @Prop({ type: String, required: true }) filed: string; // 字段id
  @Prop({ type: String, required: true }) fieldType: string; // 字段的类型
  @Prop({ type: String, required: true }) operatorValue: string; // 操作
  @Prop({ required: true }) inputValue: any; // 搜索框的值
  @Prop({ type: Array, required: true }) filterFields; // 字段下拉列表
  @Prop({ type: String, required: true }) conditionType: string; // 条件类型
  @Prop({ type: Object, required: true }) catchIpChooser: object; // ip 选择器的值
  @Prop({ type: Array, required: true }) valueList; // 输入框的可选数据
  @Prop({ type: Boolean, default: true }) isClearCatchInputStr: boolean; // 输入框的可选数据
  @Ref('tagInput') tagInputRef: TagInput;

  labelHoverStatus = false;
  labelActiveStatus = false;
  conditionTypeActiveStatus = false; // 条件状态
  localFiledID = ''; // 当前字段
  localOperatorValue = ''; // 当前操作符
  localValue = []; // 当前的输入框的值
  isValueChange = false; // 当前输入框没有新值输入时 enter检索判断
  valueChangeTimer = null;
  tagInputValueList = []; // taginput值列表
  matchSwitch = false; // 模糊匹配开关
  catchValue = []; // 切换exists时缓存的值
  catchTagInputStr = '';
  valueScopeMap = { // number类型最大值
    long: {
      max: LONG_MAX_NUMBER,
      min: LONG_MIN_NUMBER,
    },
    integer: {
      max: INTEGER_MAX_NUMBER,
      min: INTEGER_MIN_NUMBER,
    },
  };
  tips = {
    trigger: 'mouseenter',
    theme: 'light',
    allowHtml: true,
    content: '#match-tips-content',
    placement: 'top',
    distance: 9,
  };

  get ipSelectLength() { // 是否有选择ip
    return Object.keys(this.catchIpChooser).length;
  }

  get nodeType() { // 当前选择的ip类型
    return  Object.keys(this.catchIpChooser || [])?.[0] ?? '';
  }

  get nodeCount() { // ip选择的数量
    return this.catchIpChooser[this.nodeType]?.length ?? 0;
  }

  get nodeUnit() { // ip单位
    const nodeTypeTextMap = {
      node_list: window.mainComponent.$t('节点'),
      host_list: window.mainComponent.$t('IP'),
      service_template_list: window.mainComponent.$t('服务模板'),
      set_template_list: window.mainComponent.$t('集群模板'),
      dynamic_group_list: window.mainComponent.$t('动态分组'),
    };
    return nodeTypeTextMap[this.nodeType] || '';
  }

  get inputPlaceholder() {
    return this.operatorItem?.placeholder ?? window.mainComponent.$t('请输入');
  }

  get isHiddenInput() { // 是否隐藏输入框
    return this.getIsExists(this.localOperatorValue);
  }

  get isHaveCompared() { // 是否有对比操作
    return ['<', '<=', '>', '>='].includes(this.localOperatorValue);
  }

  get getInputLength() { // 是否是对比的操作 如果是 则值限制只能输入1个
    return this.isHaveCompared ? 1 : -1;
  }

  get isShowMatchSwitcher() { // 是否展示模糊匹配
    return Boolean(this.operatorItem?.wildcard_operator);
  }

  @Watch('operatorValue', { immediate: true })
  watchOperator(val: string) {
    if (this.conditionType === 'ip-select') return;
    this.localOperatorValue = val;
    this.matchSwitch = this.localOperatorValue === this.operatorItem.wildcard_operator;
  }

  @Watch('inputValue', { immediate: true })
  watchValue(val: any) {
    if (this.conditionType === 'ip-select') return;
    this.localValue = val;
  }

  @Watch('valueList', { immediate: true })
  watchValueList(val) {
    if (!val.length) {
      this.tagInputValueList = [];
      return;
    }

    this.tagInputValueList = val.map(item => ({
      id: item.toString(),
      name: item.toString(),
    }));
  }

  @Debounce(100)
  @Watch('isClearCatchInputStr')
  watchClearCatchInputStr() {
    /** 检索时，清空输入框内缓存的字符串 */
    this.catchTagInputStr = '';
  }

  @Emit('delete')
  handleDelete(type: string) {
    return type;
  }

  @Emit('isIncludeChange')
  handleIsIncludeChange(v: boolean) {
    return v;
  }

  @Emit('filedChange')
  emitFiledChange(v) {
    return v;
  }

  @Debounce(100)
  @Emit('inputChange')
  emitInputChange(v: string) {
    return v;
  }

  @Debounce(300)
  @Emit('additionValueChange')
  handleAdditionChange(newReplaceObj: object, isQuery = true) {
    return { newReplaceObj, isQuery };
  }

  @Emit('ipChange')
  handleIpChange() {};

  mounted() {
    // tagInput组件没有监听input keydown的事件只能从ref里监听
    // enter时 如果有输入的值 则不进行检索 如果无改变值 enter则进行检索
    !!this.tagInputRef && (this.tagInputRef.$refs.input.onkeyup = (v) => {
      if (v.code === 'Enter' || v.code === 'NumpadEnter') {
        if (this.localValue.length && !this.isValueChange) {
          this.handleAdditionChange({ value: this.localValue });
        }
      }
    });
  }


  handleFiledChange() { // 字段改变
    this.emitFiledChange(this.localFiledID);
  }

  handleFiledSelectChange(isOpen: boolean) {
    this.labelActiveStatus = isOpen; // 不论打开或关闭，将已选择的值置底
    if (isOpen) {
      this.localFiledID = this.filed;
    } else {
      if (this.localFiledID !== this.filed) this.handleFiledChange();
    }
  }

  setLabelHoverStatus(status: boolean) {
    this.labelHoverStatus = status;
  }


  handleValueChange(val: Array<string>) {
    this.isValueChange = true;
    clearTimeout(this.valueChangeTimer);
    this.valueChangeTimer = setTimeout(() => {
      this.isValueChange = false;
    }, 500); // 这个是enter检索判断
    if (!val.length) {
      this.handleAdditionChange({ value: [] });
      return;
    }
    const newVal = val[val.length - 1];
    if (['integer', 'long'].includes(this.fieldType)) {
      const matchList = newVal.match(/[-+]?[0-9]*\.?[0-9]+/g); // 获取有效的数字
      if (!matchList) { // 没有数字 直接不改值
        this.localValue.splice(this.localValue.length - 1, 1);
        return;
      }
      const matchVal = Number(matchList.join(',')); // 拿到数字的值进行一个大小对比
      this.localValue[this.localValue.length - 1] = this.getResetValue(matchVal, this.fieldType);  // 判断数字最大值 超出则使用最大值
    }

    this.handleAdditionChange({ value: this.localValue });
  }

  /**
   * @desc: 数字类型大小对比
   * @param {Number} value 对比的值
   * @param {String} numberType 对比的字段类型
   * @returns {String} 返回数字的字符串
   */
  getResetValue(value: number, numberType = 'integer') {
    const valMap = this.valueScopeMap[numberType];
    if (value > valMap.max) return String(valMap.max);
    if (value < valMap.min) return String(valMap.min);
    return String(value);
  }

  // 当有对比的操作时 值改变
  handleValueBlur(val: string) {
    if (val !== '' && this.isHaveCompared) this.localValue = [val];
    this.emitInputChange(this.catchTagInputStr);
    this.catchTagInputStr = '';
    // if (this.localValue.length) {
    //   this.handleAdditionChange({ value: this.localValue });
    // }
  }

  handleValueRemoveAll() {
    this.localValue = [];
    this.handleAdditionChange({ value: [] });
  }

  /**
   * @desc: 更新操作元素和操作符
   * @param {boolean} operatorItem 操作符元素
   */
  handleOperateChange(operatorItem: any) {
    if (operatorItem.operator === this.localOperatorValue) return; // 选择相同 不请求
    let queryValue = this.localValue;
    const isExists = this.getIsExists(operatorItem.operator); // 是否有存在
    const isContinuousExists = this.getIsContinuousExists(operatorItem.operator); // 连续点击两次存在或不存在时 不用改变缓存的值;
    const oldOperatorIsExists = this.getIsExists(this.localOperatorValue); // 旧操作符是否是包含和不包含
    const isCompared = ['<', '<=', '>', '>='].includes(operatorItem.operator);
    if (isExists && !isContinuousExists) {
      this.catchValue = this.localValue;
    } else if (oldOperatorIsExists) {
      queryValue = this.catchValue;
    }
    if (isCompared) this.localValue = this.localValue[0] ? [this.localValue[0]] : []; // 多输入的值变为单填时 拿下标为0的值
    const isQuery = !!this.localValue.length || isExists; // 值不为空 或 存在与不存在 的情况下才自动检索请求
    this.handleAdditionChange(
      {
        value: isExists ? [''] : queryValue,  // 更新值
        operatorItem,  // 更新操作元素
        operator: operatorItem.operator,  // 更新操作符
      },
      isQuery,
    );
  }

  /**
   * @desc: 更新模糊匹配
   * @param {boolean} matchStatus 模糊匹配开关值
   */
  handleMatchChange(matchStatus: boolean) {
    const { wildcard_operator: wildcardOperator, operator } = this.operatorItem;
    const newOperator = matchStatus ? wildcardOperator : operator;
    this.handleAdditionChange({ operator: newOperator }, false);  // 更新操作符
  }

  getIsExists(operator: string) {
    return ['exists', 'does not exists'].includes(operator);
  }

  /**
   * @desc: 是否连续两次更新的操作符都是存在或不存在
   * @param {String} newOperator 新操作符
   * @returns {Boolean} 是否两次都是存在或不存在
   */
  getIsContinuousExists(newOperator) {
    return this.getIsExists(newOperator) && this.getIsExists(this.localOperatorValue);
  }

  tpl(node, ctx, highlightKeyword) {
    const parentClass = 'bk-selector-node';
    const textClass = 'text';
    const innerHtml = `${highlightKeyword(node.id)}`;
    return (
        <div class={parentClass} title={node.id}>
            <span class={textClass} domPropsInnerHTML={innerHtml}></span>
        </div>
    );
  }

  render() {
    return (
      <div>
        {/* 字段名称、条件、删除、是否参与 */}
        <div class="head-row">
          <div class='cascader'>
            <span
              class={{
                label: true,
                'label-hover': this.labelHoverStatus,
                'label-active': this.labelActiveStatus,
                'label-disabled': !this.isInclude,
              }}
              >{this.name}</span>
            {
              <div
                onMouseover={() => this.setLabelHoverStatus(true)}
                onMouseout={() => this.setLabelHoverStatus(false)}>
                <Select
                  searchable
                  v-model={this.localFiledID}
                  class='inquire-cascader'
                  disabled={!this.isInclude}
                  popover-min-width={400}
                  onToggle={this.handleFiledSelectChange}
                >
                {
                  this.filterFields.map(option => (
                    <Option
                      v-bk-tooltips={{
                        content: option.disabledContent,
                        placement: 'right',
                        disabled: !option.disabled,
                      }}
                      key={option.id}
                      id={option.id}
                      name={option.fullName}
                      disabled={option.disabled}>
                    </Option>
                  ))
                }
                </Select>
              </div>
            }
          </div>
          <DropdownMenu
            disabled={!this.isInclude}
            trigger="click"
            placement="bottom-start"
            style="margin-right: 4px;"
            onShow={() => this.conditionTypeActiveStatus = true}
            onHide={() => this.conditionTypeActiveStatus = false}
          >
            <div slot="dropdown-trigger">
            {/* 这里是 操作符 选择器 */}
            {
              this.conditionType === 'filed' && <span class={{
                'condition-type': true,
                'condition-type-active': this.conditionTypeActiveStatus,
                'condition-type-disabled': !this.isInclude,
              }}>{this.operatorItem.label}</span>
            }
            </div>
            <ul class="bk-dropdown-list"  slot="dropdown-content">
              {this.operatorList.map(item => (
                <li onClick={() => this.handleOperateChange(item)}>
                  {item.label}
                </li>
              ))}
            </ul>
          </DropdownMenu>
          {
            <span
              class={{
                'vague-match': true,
                'show-checkbox': this.isShowMatchSwitcher,
              }}>
              <Checkbox
                value={this.matchSwitch}
                size="small"
                theme="primary"
                disabled={!this.isInclude}
                onChange={() => this.handleMatchChange(!this.matchSwitch)}>
                  <span v-bk-tooltips={this.tips} class="match-title">{this.$t('使用通配符')}</span>
              </Checkbox>
            </span>
          }
          <i class='bk-icon icon-delete' onClick={() => this.handleDelete(this.conditionType)}></i>
          <Switcher
            v-bk-tooltips={{
              content: !this.isInclude ? this.$t('点击后，参与查询') : this.$t('点击后，不参与查询'),
              delay: 200,
            }}
            value={this.isInclude}
            size="small"
            theme="primary"
            onChange={() => this.handleIsIncludeChange(!this.isInclude)}></Switcher>
        </div>
        {
          (this.conditionType === 'filed' && !this.isHiddenInput) && <TagInput
            style="margin-top: 4px;"
            ref="tagInput"
            free-paste
            content-width={340}
            v-model={this.localValue}
            data-test-id="addConditions_input_valueFilter"
            allow-create
            allow-auto-match
            tpl={this.tpl}
            placeholder={this.inputPlaceholder}
            list={this.tagInputValueList}
            max-data={this.getInputLength}
            onChange={this.handleValueChange}
            onBlur={this.handleValueBlur}
            onRemoveAll={this.handleValueRemoveAll}
            onInputchange={v => this.catchTagInputStr = v}
            trigger="focus">
          </TagInput>
        }
        {
          this.conditionType === 'ip-select' && <div class="ip-filter-container">
            {
              !this.ipSelectLength
                ? <Button text class="add-ip-button" onClick={() => this.handleIpChange()}>
                <i class='bk-icon icon-plus'></i>
                <span>{this.$t('添加目标')}</span>
              </Button>
                : <Button text class="add-ip-button" onClick={() => this.handleIpChange()}>
                <i18n path="已选择 {0} 个{1}">
                  <span>{ this.nodeCount }</span>
                  <span>{ this.nodeUnit }</span>
                </i18n>
            </Button>
            }
          </div>
        }
        <div v-show={false}>
          <div id="match-tips-content">
            <div class="detail">{this.$t('支持使用通配符 * 和 ? 进行匹配：')}</div>
            <div class="title">{this.$t('* 表示匹配多个（包括 0 个）任意字符')}</div>
            <div class="detail">{this.$t('例：a*d 可匹配 ad、abcd、a123d')}</div>
            <div class="title">{this.$t('? 表示匹配单个任意字符')}</div>
            <div class="detail">{this.$t('例：a?d 可匹配 abd、a1d')}</div>
          </div>
        </div>
      </div>
    );
  }
}
