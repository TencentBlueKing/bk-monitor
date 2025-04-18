<!--
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
-->

<template>
  <div
    class="retrieve-detail-input"
    v-bk-clickoutside="handleClickOutside"
  >
    <monaco-detail-input
      ref="editorElement"
      class="king-input-retrieve"
      :value="value"
      data-test-id="dataQuery_input_checkForPhrases"
      @blur="handleBlur"
      @focus="handleFocus"
      @input="handleInput"
      @keydown="handleKeydown"
    />
    <div
      v-if="isKeywordsError"
      class="refresh-keywords"
    >
      <div v-if="!!keywordErrorMessage">
        <span>
          <span class="error-title">{{ $t('语法错误') }}: </span>
          <span class="error-message">{{ keywordErrorMessage }}</span>
        </span>
        <br />
        <span
          v-if="keywordIsResolved"
          @click="handleRefreshKeywords"
        >
          <i18n
            class="error-title"
            path="你可能想输入：{0} 点击 {1}"
          >
            <span class="error-message">{{ resetKeyword }}</span>
            <span class="flex-align-center">
              <span class="refresh-btn">{{ $t('替换') }}</span>
            </span>
          </i18n>
        </span>
      </div>
    </div>
    <!-- 搜索提示 -->
    <ul
      v-if="renderDropdown"
      ref="dropdownRef"
      class="retrieve-dropdown"
      @click="handleClickDropdown"
    >
      <!-- 字段列表 -->
      <template v-if="showFields">
        <li
          v-for="item in fieldList"
          class="list-item field-list-item"
          :key="item"
          @click="handleClickField(item)"
        >
          <div class="item-type-icon">
            <span class="bklog-icon bklog-field"></span>
          </div>
          <div
            class="item-text text-overflow-hidden"
            v-bk-overflow-tips="{ placement: 'right' }"
          >
            {{ item }}
          </div>
          <!-- <div v-bk-overflow-tips="{ placement: 'right' }" class="item-description text-overflow-hidden">
              <i18n path="筛选包含{0}的结果">
                <span class="item-callout">{{ item }}</span>
              </i18n>
            </div> -->
        </li>
      </template>
      <!-- 字段对应值 -->
      <template v-if="showValue">
        <li
          v-for="item in valueList"
          class="list-item value-list-item"
          :key="item"
          @click="handleClickValue(item)"
        >
          <div class="item-type-icon">
            <span class="bklog-icon bklog-value"></span>
          </div>
          <div
            class="item-text text-overflow-hidden"
            v-bk-overflow-tips="{ placement: 'right' }"
          >
            {{ item }}
          </div>
        </li>
      </template>
      <!-- : :* -->
      <template v-if="showColon">
        <li
          class="list-item colon-list-item"
          @click="handleClickColon(':')"
        >
          <div class="item-type-icon">
            <span class="bklog-icon bklog-equal"></span>
          </div>
          <div class="item-text">:</div>
          <div
            class="item-description text-overflow-hidden"
            v-bk-overflow-tips="{ placement: 'right' }"
          >
            <i18n path="{0}某一值">
              <span class="item-callout">{{ $t('等于') }}</span>
            </i18n>
          </div>
        </li>
        <li
          class="list-item colon-list-item"
          @click="handleClickColon(': *')"
        >
          <div class="item-type-icon">
            <span class="bklog-icon bklog-equal"></span>
          </div>
          <div class="item-text">:*</div>
          <div
            class="item-description text-overflow-hidden"
            v-bk-overflow-tips="{ placement: 'right' }"
          >
            <i18n path="{0}任意形式">
              <span class="item-callout">{{ $t('存在') }}</span>
            </i18n>
          </div>
        </li>
        <template v-if="showOperator">
          <template>
            <li
              v-for="(item, key) in operatorSelectList"
              class="list-item continue-list-item"
              :key="key"
              @click="handleClickColon(item.operator)"
            >
              <div class="item-type-icon">
                <span class="bklog-icon bklog-equal"></span>
              </div>
              <div class="item-text">{{ item.operator }}</div>
              <div
                class="item-description text-overflow-hidden"
                v-bk-overflow-tips="{ placement: 'right' }"
              >
                <i18n path="{0}某一值">
                  <span class="item-callout">{{ item.label }}</span>
                </i18n>
              </div>
            </li>
          </template>
        </template>
      </template>
      <!-- AND OR -->
      <template v-if="showContinue">
        <li
          class="list-item continue-list-item"
          @click="handleClickContinue('AND')"
        >
          <div class="item-type-icon">
            <span class="bklog-icon bklog-and"></span>
          </div>
          <div class="item-text">AND</div>
          <div
            class="item-description text-overflow-hidden"
            v-bk-overflow-tips="{ placement: 'right' }"
          >
            <i18n path="需要{0}为真">
              <span class="item-callout">{{ $t('两个参数都') }}</span>
            </i18n>
          </div>
        </li>
        <li
          class="list-item continue-list-item"
          @click="handleClickContinue('OR')"
        >
          <div class="item-type-icon">
            <span class="bklog-icon bklog-and"></span>
          </div>
          <div class="item-text">OR</div>
          <div
            class="item-description text-overflow-hidden"
            v-bk-overflow-tips="{ placement: 'right' }"
          >
            <i18n path="需要{0}为真">
              <span class="item-callout">{{ $t('一个或多个参数') }}</span>
            </i18n>
          </div>
        </li>
      </template>
    </ul>
  </div>
</template>

<script>
  import { debounce } from 'throttle-debounce';

  import MonacoDetailInput from '../search-comp/retrieve-detail-input-editor.tsx';

  export default {
    components: {
      MonacoDetailInput,
    },
    model: {
      event: 'change',
    },
    props: {
      value: {
        type: String,
        required: true,
      },
      retrievedKeyword: {
        type: String,
        default: '*',
      },
      dropdownData: {
        type: Object,
        required: true,
      },
      isAutoQuery: {
        type: Boolean,
        default: false,
      },
      isShowUiType: {
        type: Boolean,
        default: false,
      },
      totalFields: {
        type: Array,
        required: true,
      },
    },
    data() {
      return {
        separator: /AND|OR|and|or/, // 区分查询语句条件
        shouldHandleBlur: true, // blur 时是否触发检索
        showDropdown: false, // 显示下拉
        activeIndex: null, // 下拉列表激活的项目索引
        showFields: false, // 显示下拉可选字段
        showValue: false, // 显示下拉可选值
        showColon: false, // : :*
        showContinue: false, // AND OR
        showOperator: false, // = > >= < <=
        isSearchRecord: false,
        isKeywordsError: false, // 语句是否有误
        keywordErrorMessage: '', // 无法修复的语句的原因
        keywordIsResolved: false, // 语句是否可以被修复
        resetKeyword: '', // 修复过后的语句
        originFieldList: [], // 所有字段列表 ['name', 'age']
        fieldList: [], // 显示字段列表，['name', 'age']
        valueList: [], // 字段可能的值 ['"arman"', '"xxx yyy"'] [18, 22]
        operatorSelectList: [
          {
            operator: '>',
            label: this.$t('大于'),
          },
          {
            operator: '<',
            label: this.$t('小于'),
          },
          {
            operator: '>=',
            label: this.$t('大于或等于'),
          },
          {
            operator: '<=',
            label: this.$t('小于或等于'),
          },
        ],
      };
    },
    computed: {
      renderDropdown() {
        if (this.showValue && this.showDropdown && !this.valueList.length) return false;
        return this.showDropdown && (this.showFields || this.showValue || this.showColon || this.showContinue);
      },
      /** 获取数字类型的字段name */
      getNumTypeFieldList() {
        return this.totalFields
          .filter(item => ['long', 'integer', 'float'].includes(item.field_type))
          .map(item => item.field_name);
      },
      /** 语法检查需要的字段信息 */
      getCheckKeywordsFields() {
        return this.totalFields.map(item => ({
          field_name: item.field_name,
          is_analyzed: item.is_analyzed,
          field_type: item.field_type,
        }));
      },
      /** 所有字段的字段名 */
      totalFieldsNameList() {
        return this.totalFields.map(item => item.field_name);
      },
    },
    watch: {
      showDropdown(val) {
        if (val) {
          this.calculateDropdown();
        } else {
          this.showFields = false;
          this.showValue = false;
          this.showColon = false;
          this.showContinue = false;
          this.fieldList.splice(0);
          this.valueList.splice(0);
        }
      },
      dropdownData: {
        handler(val) {
          // 检索后的日志数据如果字段在字段接口找不到则不展示联想的key
          this.originFieldList = Object.keys(val).filter(v => this.totalFieldsNameList.includes(v));
          if (this.originFieldList.length && this.showDropdown) {
            // 可能字段接口还没返回用户就 focus 了输入框
            this.calculateDropdown();
          }
        },
        deep: true,
      },
    },
    created() {
      this.handleRetrieve = debounce(300, () => this.$emit('retrieve'));
    },
    methods: {
      handleClickDropdown(e) {
        e.stopPropagation();
        this.shouldHandleBlur = false;
        this.clickDropdownTimer && clearTimeout(this.clickDropdownTimer);
        this.clickDropdownTimer = setTimeout(() => {
          this.shouldHandleBlur = true;
        }, 200);
        this.$refs.editorElement.focus();
      },
      handleClickOutside() {
        this.showDropdown = false;
      },
      handleFocus() {
        this.$emit('isCanSearch', false);
        if (this.isSearchRecord) {
          this.$refs.editorElement.blur();
          this.isSearchRecord = false;
          return;
        }

        this.showDropdown = true;
        this.isSearchRecord = false;
      },
      handleInput(val) {
        this.$emit('change', val);
        if (this.originFieldList.length) {
          this.inputTimer && clearTimeout(this.inputTimer);
          this.inputTimer = setTimeout(this.calculateDropdown, 300);
        }
      },
      handleKeydown(e) {
        const { code } = e;
        if (code === 'Escape') {
          this.closeDropdown();
          return;
        }

        const dropdownEl = this.$refs.dropdownRef;
        if (!dropdownEl) {
          if (code === 'NumpadEnter' || code === 'Enter') {
            e.preventDefault();
            this.closeDropdown();
            this.handleRetrieve();
          }
          return;
        }

        const dropdownList = dropdownEl.querySelectorAll('.list-item');
        if (code === 'NumpadEnter' || code === 'Enter') {
          e.preventDefault();
          if (this.activeIndex !== null) {
            // enter 选中下拉选项
            dropdownList[this.activeIndex].click();
          } else {
            // enter 检索
            this.closeDropdown();
          }
        } else if (code === 'ArrowUp') {
          if (this.activeIndex) {
            this.activeIndex -= 1;
          } else {
            this.activeIndex = dropdownList.length - 1;
          }
          this.calculateScroll(true);
        } else if (code === 'ArrowDown') {
          if (this.activeIndex === null || this.activeIndex === dropdownList.length - 1) {
            this.activeIndex = 0;
          } else {
            this.activeIndex += 1;
          }
          this.calculateScroll(false);
        }
        dropdownList.forEach((item, index) => {
          if (index === this.activeIndex) {
            item.classList.add('active');
          } else {
            item.classList.remove('active');
          }
        });
      },
      // 上下键选择项目时滚动到可视区域
      calculateScroll(alignToTop) {
        this.$nextTick(() => {
          // 列表容器
          const containerEl = this.$refs.dropdownRef;
          const containerRect = containerEl.getBoundingClientRect();
          const containerTop = containerRect.top;
          const containerBottom = containerTop + containerRect.height;
          // 激活的列表项
          const itemEl = containerEl.querySelector('.list-item.active');
          const itemRect = itemEl.getBoundingClientRect();
          const itemTop = itemRect.top;
          const itemBottom = itemTop + itemRect.height;
          // 列表项不在容器可视范围
          if (itemTop < containerTop || itemBottom > containerBottom) {
            const currentScrollTop = containerEl.scrollTop;
            if (alignToTop) {
              containerEl.scrollTop = currentScrollTop + itemTop - containerTop;
            } else {
              containerEl.scrollTop = currentScrollTop + itemBottom - containerBottom;
            }
          }
        });
      },
      handleBlur(val) {
        this.$emit('keywordBlurUpdate', this.value);
        setTimeout(() => {
          this.$emit('isCanSearch', true);
        }, 100);
        // 非自动搜索时 鼠标失焦后 判断语句是否出错
        this.blurTimer && clearTimeout(this.blurTimer);
        this.blurTimer = setTimeout(() => {
          if (this.shouldHandleBlur || this.isKeywordsError) this.handleCheckKeywords(val.trim()); // 检查语句是否有错误;
        }, 200);
        // 如果当前有点击收藏且有选择表单模式的key时 监听新输入的检索语句判断
        if (this.isShowUiType) this.$emit('inputBlur', val);

        if (this.isSearchRecord || !this.isAutoQuery) return;
        // blur 时检索
        // 下拉菜单 click 时也会触发 blur 事件，但是不执行检索相关逻辑
        // 下拉菜单 click 事件在 blur 事件触发后 100+ms 后触发
        // 所以 blur 事件回调延迟 200ms 执行，让 click 事件执行后才确认如何执行
        this.blurTimer && clearTimeout(this.blurTimer);
        this.blurTimer = setTimeout(async () => {
          if (this.shouldHandleBlur) {
            // 非点击下拉触发的 blur 事件
            this.showDropdown = false;
            // 自动搜索时 先判断语句是否出错 如果出错 则提示出错原因 且不进行请求
            if (this.retrievedKeyword !== val.trim() || this.isKeywordsError) {
              const isCanSearch = await this.handleCheckKeywords(val.trim());
              if (isCanSearch) this.handleRetrieve();
            }
          } else {
            // 点击了下拉菜单，会再次聚焦
          }
        }, 200);
      },
      handleRefreshKeywords() {
        // 替换语句
        this.$emit('change', this.resetKeyword);
        this.resetKeyword = '';
        this.isKeywordsError = false;
        this.keywordIsResolved = false;
        this.keywordErrorMessage = '';
        this.$emit('isCanSearch', true);
        if (this.isAutoQuery) this.handleRetrieve();
      },
      async handleCheckKeywords(keyword) {
        // 检查检索语句是否有误
        if (keyword === '') keyword = '*';
        try {
          const { data } = await this.$http.request('favorite/checkKeywords', {
            data: {
              keyword,
              fields: this.getCheckKeywordsFields,
            },
          });
          this.isKeywordsError = !data.is_legal;
          this.keywordIsResolved = data.is_resolved;
          this.keywordErrorMessage = data.message;
          this.resetKeyword = data.keyword;
          this.$emit('isCanSearch', data.is_legal);
          return data.is_legal || data.is_resolved;
        } catch (error) {
          return true;
        }
      },
      closeDropdown() {
        this.showDropdown = false;
        this.handleBlur(this.$refs.editorElement.editor.getValue());
      },

      // 根据当前输入关键字计算提示内容
      calculateDropdown() {
        if (!this.originFieldList.length) {
          return;
        }
        const { value } = this;
        const trimValue = value.trim();
        const lastFragments = value.split(this.separator);
        const lastFragment = lastFragments[lastFragments.length - 1];
        // 以 name:"arman" OR age:18 为例，还没开始输入字段
        if (
          !trimValue ||
          trimValue === '*' ||
          /\s+AND\s+$/.test(value) ||
          /\s+OR\s+$/.test(value) ||
          /\s+and\s+$/.test(value) ||
          /\s+or\s+$/.test(value)
        ) {
          this.showWhichDropdown('Fields');
          this.fieldList = [...this.originFieldList];
          return;
        }
        // 开始输入字段【nam】
        const inputField = /^\s*(?<field>[\w.]+)$/.exec(lastFragment)?.groups.field;
        if (inputField) {
          this.fieldList = this.originFieldList.filter(item => {
            if (item.includes(inputField)) {
              if (item === inputField) {
                // 完全匹配字段同时和 : :* 选项
                this.showColon = true;
                this.showOperator = this.isNumTypeField(inputField.trim());
              }
              return true;
            }
          });
          this.showWhichDropdown(this.fieldList.length ? 'Fields' : undefined);
          return;
        }
        // 字段输入完毕【name 】
        if (/^\s*(?<field>[\w.]+)\s*$/.test(lastFragment)) {
          this.showWhichDropdown('Colon');
          this.showOperator = this.isNumTypeField(lastFragment.trim());
          return;
        }
        // 准备输入值【name:】
        const confirmField = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*$/.exec(lastFragment)?.groups.field;
        if (confirmField) {
          const valueMap = this.dropdownData[confirmField];
          if (valueMap) {
            this.showWhichDropdown('Value');
            this.valueList = this.getValueList(valueMap);
          } else {
            this.showWhichDropdown();
            this.valueList.splice(0);
          }
          return;
        }
        // 正在输入值【age:1】注意后面没有空格，匹配字段对应值
        const valueResult = /^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*(?<value>[\S]+)$/.exec(lastFragment);
        if (valueResult) {
          const confirmField = valueResult.groups.field;
          const valueMap = this.dropdownData[confirmField];
          if (valueMap) {
            const inputValue = valueResult.groups.value;
            this.valueList = this.getValueList(valueMap).filter(item => item.includes(inputValue));
            this.showWhichDropdown(this.valueList.length ? 'Value' : undefined);
          } else {
            this.showWhichDropdown();
            this.valueList.splice(0);
          }
          return;
        }
        // 一组条件输入完毕【age:18 】提示继续增加条件 AND OR
        if (/^\s*(?<field>[\w.]+)\s*(:|>=|<=|>|<)\s*(?<value>[\S]+)\s+$/.test(lastFragment)) {
          this.showWhichDropdown('Continue');
          return;
        }
        this.showWhichDropdown();
      },
      /**
       * 显示哪个下拉列表
       * @param {String} [param]
       */
      showWhichDropdown(param) {
        const types = ['Fields', 'Value', 'Colon', 'Continue'];
        for (const type of types) {
          const key = `show${type}`;
          this[key] = type === param;
        }
        this.activeIndex = null;
      },
      /**
       * 获取某个字段可选的值列表
       * @param {Object} valueMap
       * @return {string[]}
       */
      getValueList(valueMap) {
        // if (valueMap.__fieldType === 'string') {
        //   return Object.keys(valueMap).map(item => `"${item}"`);
        // }
        // return Object.keys(valueMap);
        let valueMapList = Object.keys(valueMap);
        if (valueMap.__fieldType === 'string') {
          valueMapList = valueMapList // 清除mark标签
            .map(item => `"${item.replace(/<mark>/g, '').replace(/<\/mark>/g, '')}"`);
        }
        return [...new Set(valueMapList)]; // 清除重复的字段
      },
      /**
       * 选择某个可选字段
       * @param {string} field
       */
      handleClickField(field) {
        this.valueList = this.getValueList(this.dropdownData[field]);
        const currentValue = this.value;
        const trimValue = currentValue.trim();
        if (!trimValue || trimValue === '*') {
          this.$emit('change', `${field} `);
        } else {
          const fragments = currentValue.split(this.separator);
          if (!fragments[fragments.length - 1].trim()) {
            // 可能的情况 【name:"arman" AND \s】
            this.$emit('change', `${currentValue}${field} `);
          } else {
            // 可能的情况【name:"arman" AND ag】【name】
            this.$emit('change', currentValue.replace(/\s*[\w.]+$/, ` ${field} `));
          }
        }
        this.showWhichDropdown('Colon');
        this.showOperator = this.isNumTypeField(field);
      },
      /**
       * 选择 : 或者 :*
       * @param {string} type
       */
      handleClickColon(type) {
        this.$emit('change', `${this.value + type} `);
        this.$nextTick(() => {
          this.calculateDropdown();
        });
      },
      /**
       * 选择某个字段可选值
       * @param {string} value
       */
      handleClickValue(value) {
        // 当前输入值可能的情况 【name:"a】【age:】
        this.$emit(
          'change',
          this.value.replace(/(:|>=|<=|>|<)\s*[\S]*$/, (match1, matchOperator) => {
            return `${matchOperator} ${value} `;
          }),
        );
        this.showWhichDropdown('Continue');
      },
      /**
       * 选择 AND 或者 OR
       * @param {string} type
       */
      handleClickContinue(type) {
        this.$emit('change', `${this.value + type} `);
        this.showWhichDropdown('Fields');
        this.fieldList = [...this.originFieldList];
      },
      /**
       * @desc: 当前是否是数字类型字段
       * @param {string} fieldStr 字段名
       * @returns {boolean}
       */
      isNumTypeField(fieldStr = '') {
        return this.getNumTypeFieldList.includes(fieldStr);
      },
    },
  };
</script>

<style lang="scss" scoped>
  @import '../../../scss/mixins/scroller';

  .retrieve-detail-input {
    position: relative;

    .refresh-keywords {
      margin-top: 4px;
      font-size: 12px;

      .error-message {
        color: #ea3636;
      }

      .error-title {
        color: #63656e;
      }

      .refresh-btn {
        color: #3a84ff;
        cursor: pointer;
      }
    }

    .retrieve-dropdown {
      position: absolute;
      z-index: 99;
      width: 100%;
      max-height: 360px;
      margin-top: 4px;
      overflow: auto;
      background: #fff;
      border: 1px solid #dcdee5;
      border-radius: 2px;
      box-shadow: 0 2px 6px 0 rgba(0, 0, 0, 0.1);

      @include scroller(#ccc);

      .list-item {
        display: flex;
        align-items: center;
        font-size: 12px;
        line-height: 32px;
        background-color: #fff;

        .item-type-icon {
          display: flex;
          align-items: center;
          justify-content: center;
          width: 32px;
          height: 32px;

          .bklog-icon {
            font-size: 16px;
          }
        }

        .item-text {
          flex: 1;
          min-width: 150px;
          padding: 0 8px;
          font-family: 'Roboto Mono', Consolas, Menlo, Courier, monospace;
          color: #63656e;
        }

        .item-description {
          flex: 2;
          margin-left: 24px;
          color: #979ba5;

          .item-callout {
            padding: 0 4px;
            font-family: 'Roboto Mono', Consolas, Menlo, Courier, monospace;
            color: #313238;
            background-color: #f4f6fa;
          }
        }

        &:hover,
        &.active {
          background-color: #f4f6fa;

          .item-text {
            color: #313238;
          }

          .item-callout {
            background-color: #fff;
          }
        }

        &:hover {
          cursor: pointer;
          background-color: #eaf3ff;
        }
      }

      /* 字段 icon 样式 */
      .field-list-item.list-item {
        .item-type-icon {
          color: #936501;
          background-color: #fef6e6;
        }

        &:hover,
        &.active {
          .item-type-icon {
            color: #010101;
            background-color: #fdedcc;
          }
        }
      }

      /* 值 icon 样式 */
      .value-list-item.list-item {
        /* stylelint-disable-next-line no-descending-specificity */
        .item-type-icon {
          color: #02776e;
          background-color: #e6f2f1;
        }

        &:hover,
        &.active {
          .item-type-icon {
            color: #010101;
            background-color: #cce5e3;
          }
        }
      }

      /* AND OR icon 样式 */
      .continue-list-item.list-item {
        /* stylelint-disable-next-line no-descending-specificity */
        .item-type-icon {
          color: #7c609e;
          background-color: #f2e6f6;
        }

        &:hover,
        &.active {
          .item-type-icon {
            color: #000;
            background-color: #e4cced;
          }
        }
      }

      /* : :* icon 样式 */
      .colon-list-item.list-item {
        /* stylelint-disable-next-line no-descending-specificity */
        .item-type-icon {
          color: #006bb4;
          background-color: #e6f0f8;
        }

        &:hover,
        &.active {
          .item-type-icon {
            color: #000;
            background-color: #cce1f0;
          }
        }
      }

      .history-title-item.list-item {
        cursor: default;
        background-color: #fff;
        border-top: 1px solid #dcdee5;

        .item-text {
          color: #979ba5;
        }
      }
    }

    .flex-align-center {
      display: inline-flex;
      align-items: center;
    }
  }
</style>
