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

import { Component, Emit, Prop, Watch, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Select, Option, DropdownMenu, TagInput, Button, Checkbox } from 'bk-magic-vue';

import { Debounce, xssFilter } from '../../../common/util';

import './condition.scss';

// 使用 Number 类型处理的 32 位整数范围是安全的
const INTEGER_MIN_NUMBER = -2_147_483_648;
const INTEGER_MAX_NUMBER = 2_147_483_647;
// 使用 BigInt 类型来处理 64 位整数范围，避免精度丢失
const LONG_MIN_NUMBER = -9223372036854775808n;
const LONG_MAX_NUMBER = 9223372036854775807n;

interface ITextTypeOperatorData {
  andOrVal?: string;
  operatorVal?: string;
  matchVal?: boolean;
}

@Component
export default class Condition extends tsc<object> {
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
  /** 且/或样式激活状态 */
  andOrTypeActiveStatus = false;
  valueScopeMap = {
    // number类型最大值
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

  /** 或和且下拉选择列表 */
  andOrList = [
    {
      id: 'or',
      name: window.mainComponent.$t('或'),
    },
    {
      id: 'and',
      name: window.mainComponent.$t('且'),
    },
  ];

  get ipSelectLength() {
    // 是否有选择ip
    return Object.keys(this.catchIpChooser).length;
  }

  get nodeType() {
    // 当前选择的ip类型
    return Object.keys(this.catchIpChooser || [])?.[0] ?? '';
  }

  get nodeCount() {
    // ip选择的数量
    return this.catchIpChooser[this.nodeType]?.length ?? 0;
  }

  get nodeUnit() {
    // ip单位
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

  get isHiddenInput() {
    // 是否隐藏输入框
    return this.getIsExists(this.localOperatorValue);
  }

  get isHaveCompared() {
    // 是否有对比操作
    return ['<', '<=', '>', '>='].includes(this.localOperatorValue);
  }

  get getInputLength() {
    // 是否是对比的操作 如果是 则值限制只能输入1个
    return this.isHaveCompared ? 1 : -1;
  }

  get isShowMatchSwitcher() {
    // 是否展示模糊匹配
    return Boolean(this.operatorItem?.wildcard_operator);
  }

  /** 是否是text类型字段 */
  get isTextField() {
    return this.fieldType === 'text';
  }

  /** 是否展示且/或下拉框 */
  get isShowAndOrSelect() {
    return this.isTextField && !['exists', 'does not exists'].includes(this.operatorValue);
  }

  /** 当前text字段类型操作符对应且/或的值 */
  get getAndOrValue() {
    if (['contains match phrase', '=~', 'not contains match phrase', '!=~'].includes(this.operatorValue)) {
      return 'or';
    }
    return 'and';
  }

  @Watch('operatorValue', { immediate: true })
  watchOperator(val: string) {
    if (this.conditionType === 'ip-select') {
      return;
    }
    if (this.isTextField) {
      this.matchSwitch = ['&!=~', '!=~', '&=~', '=~'].includes(val);
      // 判断选中的是否是存在、不存在 如果是 则直接给操作符赋值
      if (this.getIsExists(val)) {
        this.localOperatorValue = val;
      } else {
        // 区分包含，不包含情况下的 且/或 通配符
        this.localOperatorValue = ['contains match phrase', '=~', 'all contains match phrase', '&=~'].includes(val)
          ? 'contains match phrase'
          : 'not contains match phrase';
      }
    } else {
      this.matchSwitch = val === this.operatorItem.wildcard_operator;
      this.localOperatorValue = val;
    }
  }

  @Watch('inputValue', { immediate: true })
  watchValue(val: any) {
    if (this.conditionType === 'ip-select') {
      return;
    }
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
  handleIpChange() {}

  mounted() {
    // tagInput组件没有监听input keydown的事件只能从ref里监听
    // enter时 如果有输入的值 则不进行检索 如果无改变值 enter则进行检索
    !!this.tagInputRef &&
      (this.tagInputRef.$refs.input.onkeyup = v => {
        if ((v.code === 'Enter' || v.code === 'NumpadEnter') && this.localValue.length && !this.isValueChange) {
          this.handleAdditionChange({ value: this.localValue });
        }
      });
  }

  handleFiledChange() {
    // 字段改变
    this.emitFiledChange(this.localFiledID);
  }

  handleFiledSelectChange(isOpen: boolean) {
    this.labelActiveStatus = isOpen; // 不论打开或关闭，将已选择的值置底
    if (isOpen) {
      this.localFiledID = this.filed;
    } else if (this.localFiledID !== this.filed) {
      this.handleFiledChange();
    }
  }

  setLabelHoverStatus(status: boolean) {
    this.labelHoverStatus = status;
  }

  handleValueChange(val: string[]) {
    this.isValueChange = true;
    clearTimeout(this.valueChangeTimer);
    this.valueChangeTimer = setTimeout(() => {
      this.isValueChange = false;
    }, 500); // 这个是enter检索判断
    if (!val.length) {
      this.handleAdditionChange({ value: [] });
      return;
    }
    const newVal = val.at(-1);
    if (['integer', 'long'].includes(this.fieldType)) {
      const matchList = newVal.match(/[-+]?[0-9]*\.?[0-9]+/g); // 获取有效的数字
      if (!matchList) {
        // 没有数字 直接不改值
        this.localValue.splice(this.localValue.length - 1, 1);
        return;
      }
      // 注意这里取决于是否需要处理BigInt，如果值可能会很大，使用BigInt，否则使用Number
      const matchVal = this.fieldType === 'long' ? BigInt(matchList.join('')) : Number(matchList.join(''));
      this.localValue[this.localValue.length - 1] = this.getResetValue(matchVal, this.fieldType); // 判断数字最大值 超出则使用最大值
    }

    this.handleAdditionChange({ value: this.localValue });
  }

  /**
   * @desc: 数字类型大小对比
   * @param {BigInt | Number} value 对比的值
   * @param {String} numberType 对比的字段类型
   * @returns {String} 返回数字的字符串
   */
  getResetValue(value: bigint | number, numberType = 'integer') {
    const valMap = this.valueScopeMap[numberType];
    const maxVal = valMap.max;
    const minVal = valMap.min;

    if (value > maxVal) {
      return String(maxVal);
    }
    if (value < minVal) {
      return String(minVal);
    }
    return String(value);
  }

  // 当有对比的操作时 值改变
  handleValueBlur(val: string) {
    if (val !== '' && this.isHaveCompared) {
      this.localValue = [val];
    }
    this.emitInputChange(this.catchTagInputStr);
    this.catchTagInputStr = '';
  }

  /** 清空所有值 */
  handleValueRemoveAll() {
    // 点击查询按钮后需把失焦回填对象清空 否则没聚焦到输入框直接点清空的时候又会携带失焦对象里的值
    this.emitInputChange('');
    this.localValue = [];
    this.handleAdditionChange({ value: [] });
  }

  /** 选中数据时，清空缓存的输入字符 */
  handleValueSelect() {
    this.catchTagInputStr = '';
    this.emitInputChange('');
  }

  /**
   * @desc: 更新操作元素和操作符
   * @param {boolean} operatorItem 操作符元素
   */
  handleOperateChange(operatorItem: any) {
    if (operatorItem.operator === this.localOperatorValue) {
      return;
    } // 选择相同 不请求
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
    if (isCompared) {
      this.localValue = this.localValue[0] ? [this.localValue[0]] : [];
    } // 多输入的值变为单填时 拿下标为0的值
    const isQuery = !!this.localValue.length || isExists; // 值不为空 或 存在与不存在 的情况下才自动检索请求
    let newOperator = operatorItem.operator;
    if (this.isTextField && !isExists) {
      newOperator = this.getTextOperator({ operatorVal: operatorItem.operator });
    }
    this.handleAdditionChange(
      {
        value: isExists ? [''] : queryValue, // 更新值
        operatorItem, // 更新操作元素
        operator: newOperator, // 更新操作符
      },
      isQuery,
    );
  }

  /**
   * @desc: 切换且/或过滤条件
   * @param {string} id
   */
  handleAndOrChange(id: string) {
    const newOperator = this.getTextOperator({ andOrVal: id });
    this.handleAdditionChange({ operator: newOperator }, false); // 更新操作符
  }

  /**
   * @desc: 更新模糊匹配
   * @param {boolean} matchStatus 模糊匹配开关值
   */
  handleMatchChange(matchStatus: boolean) {
    const { wildcard_operator: wildcardOperator, operator } = this.operatorItem;
    let newOperator = '';
    if (this.isTextField) {
      newOperator = this.getTextOperator({ matchVal: matchStatus });
    } else {
      newOperator = matchStatus ? wildcardOperator : operator;
    }
    this.handleAdditionChange({ operator: newOperator }, false); // 更新操作符
  }

  getIsExists(operator: string) {
    return ['exists', 'does not exists', 'is true', 'is false'].includes(operator);
  }

  /** 获取text类型操作符所需的值 */
  getTextOperator(textTypeOperatorData: ITextTypeOperatorData) {
    const { andOrVal, operatorVal, matchVal } = textTypeOperatorData;
    const andORor = andOrVal ? andOrVal : this.getAndOrValue;
    const operatorValue = operatorVal ? operatorVal : this.operatorItem.operator;
    const isMatch = typeof matchVal === 'boolean' ? matchVal : this.matchSwitch;
    let filterOperatorValueStr = '';
    // 首先判断是且还是或 如果是且则先加一个and
    filterOperatorValueStr = andORor === 'and' ? 'and ' : '';
    // 然后判断是包含还是不包含操作符
    filterOperatorValueStr += operatorValue === 'contains match phrase' ? 'is ' : 'is not ';
    // 最后判断是否有开打开通配符
    filterOperatorValueStr += isMatch ? 'match' : '';
    return filterOperatorValueStr.trim();
  }

  /**
   * @desc: 是否连续两次更新的操作符都是存在或不存在
   * @param {String} newOperator 新操作符
   * @returns {Boolean} 是否两次都是存在或不存在
   */
  getIsContinuousExists(newOperator) {
    return this.getIsExists(newOperator) && this.getIsExists(this.localOperatorValue);
  }

  tpl(node, _ctx, highlightKeyword) {
    const parentClass = 'bk-selector-node';
    const textClass = 'text';
    const innerHtml = `${highlightKeyword(node.id)}`;
    return (
      <div
        class={parentClass}
        title={node.id}
      >
        <span
          class={textClass}
          domPropsInnerHTML={xssFilter(innerHtml)}
        />
      </div>
    );
  }

  render() {
    return (
      <div>
        {/* 字段名称、条件、删除、是否参与 */}
        <div class='head-row'>
          <div class='cascader'>
            <span
              class={{
                label: true,
                'label-hover': this.labelHoverStatus,
                'label-active': this.labelActiveStatus,
                'label-disabled': !this.isInclude,
              }}
            >
              {this.name}
            </span>
            {
              <div
                onMouseout={() => this.setLabelHoverStatus(false)}
                onMouseover={() => this.setLabelHoverStatus(true)}
              >
                <Select
                  class='inquire-cascader'
                  v-model={this.localFiledID}
                  disabled={!this.isInclude}
                  popover-min-width={400}
                  searchable
                  onToggle={this.handleFiledSelectChange}
                >
                  {this.filterFields.map(option => (
                    <Option
                      id={option.id}
                      key={option.id}
                      v-bk-tooltips={{
                        content: option.disabledContent,
                        placement: 'right',
                        disabled: !option.disabled,
                      }}
                      disabled={option.disabled}
                      name={option.fullName}
                    />
                  ))}
                </Select>
              </div>
            }
          </div>
          <DropdownMenu
            style='margin-right: 4px;'
            disabled={!this.isInclude}
            placement='bottom-start'
            trigger='click'
            onHide={() => (this.conditionTypeActiveStatus = false)}
            onShow={() => (this.conditionTypeActiveStatus = true)}
          >
            <div slot='dropdown-trigger'>
              {/* 这里是 操作符 选择器 */}
              {this.conditionType === 'filed' && (
                <span
                  class={{
                    'condition-type': true,
                    'condition-type-active': this.conditionTypeActiveStatus,
                    'condition-type-disabled': !this.isInclude,
                  }}
                >
                  {this.operatorItem.label}
                </span>
              )}
            </div>
            <ul
              class='bk-dropdown-list'
              slot='dropdown-content'
            >
              {this.operatorList.map(item => (
                <li
                  key={item}
                  onClick={() => this.handleOperateChange(item)}
                >
                  {item.label}
                </li>
              ))}
            </ul>
          </DropdownMenu>
          {this.isShowAndOrSelect && (
            <DropdownMenu
              style='margin-right: 4px;'
              disabled={!this.isInclude}
              placement='bottom-start'
              trigger='click'
              onHide={() => (this.andOrTypeActiveStatus = false)}
              onShow={() => (this.andOrTypeActiveStatus = true)}
            >
              <div slot='dropdown-trigger'>
                {/* 这里是 操作符 选择器 */}
                {this.conditionType === 'filed' && (
                  <span
                    class={{
                      'condition-type': true,
                      'and-or-type': true,
                      'condition-type-active': this.andOrTypeActiveStatus,
                      'condition-type-disabled': !this.isInclude,
                    }}
                  >
                    {this.getAndOrValue === 'or' ? this.$t('或') : this.$t('且')}
                  </span>
                )}
              </div>
              <ul
                class='bk-dropdown-list'
                slot='dropdown-content'
              >
                {this.andOrList.map(item => (
                  <li
                    key={item.id}
                    onClick={() => this.handleAndOrChange(item.id)}
                  >
                    {item.name}
                  </li>
                ))}
              </ul>
            </DropdownMenu>
          )}
          {
            <span
              class={{
                'vague-match': true,
                'show-checkbox': this.isShowMatchSwitcher,
              }}
            >
              <Checkbox
                disabled={!this.isInclude}
                size='small'
                theme='primary'
                value={this.matchSwitch}
                onChange={() => this.handleMatchChange(!this.matchSwitch)}
              >
                <span
                  class='match-title'
                  v-bk-tooltips={this.tips}
                >
                  {this.$t('使用通配符')}
                </span>
              </Checkbox>
            </span>
          }
          <i
            class='bk-icon icon-delete'
            onClick={() => this.handleDelete(this.conditionType)}
          />
          <i
            class={['bk-icon include-icon', `${this.isInclude ? 'icon-eye' : 'icon-eye-slash'}`]}
            v-bk-tooltips={{
              content: this.isInclude ? this.$t('参与查询') : this.$t('不参与查询'),
              delay: 200,
            }}
            onClick={() => this.handleIsIncludeChange(!this.isInclude)}
          />
        </div>
        {this.conditionType === 'filed' && !this.isHiddenInput && (
          <TagInput
            ref='tagInput'
            style='margin-top: 4px;'
            v-model={this.localValue}
            content-width={340}
            data-test-id='addConditions_input_valueFilter'
            list={this.tagInputValueList}
            max-data={this.getInputLength}
            placeholder={this.inputPlaceholder}
            tpl={this.tpl}
            trigger='focus'
            allow-auto-match
            allow-create
            free-paste
            onBlur={this.handleValueBlur}
            onChange={this.handleValueChange}
            onInputchange={v => (this.catchTagInputStr = v)}
            onRemoveAll={this.handleValueRemoveAll}
            onSelect={this.handleValueSelect}
          />
        )}
        {this.conditionType === 'ip-select' && (
          <div id='ip-filter-container'>
            {this.ipSelectLength ? (
              <Button
                class='add-ip-button'
                text
                onClick={() => this.handleIpChange()}
              >
                <i18n path='已选择 {0} 个{1}'>
                  <span>{this.nodeCount}</span>
                  <span>{this.nodeUnit}</span>
                </i18n>
              </Button>
            ) : (
              <Button
                class='add-ip-button'
                text
                onClick={() => this.handleIpChange()}
              >
                <i class='bk-icon icon-plus' />
                <span>{this.$t('添加目标')}</span>
              </Button>
            )}
          </div>
        )}
        <div v-show={false}>
          <div id='match-tips-content'>
            <div class='detail'>{this.$t('支持使用通配符 * 和 ? 进行匹配：')}</div>
            <div class='title'>{this.$t('* 表示匹配多个（包括 0 个）任意字符')}</div>
            <div class='detail'>{this.$t('例：a*d 可匹配 ad、abcd、a123d')}</div>
            <div class='title'>{this.$t('? 表示匹配单个任意字符')}</div>
            <div class='detail'>{this.$t('例：a?d 可匹配 abd、a1d')}</div>
          </div>
        </div>
      </div>
    );
  }
}
