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

import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { copyText, Debounce } from 'monitor-common/utils';

import QsSelectorSelector from './qs-selector-options';
import { QueryStringEditor } from './query-string-utils';
import {
  type IFavoriteListItem,
  type IFilterField,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  EQueryStringTokenType,
  onClickOutside,
} from './utils';

import './qs-selector.scss';

interface IProps {
  clearKey?: string;
  favoriteList?: IFavoriteListItem[];
  fields: IFilterField[];
  qsSelectorOptionsWidth?: number;
  value?: string;
  // isQsOperateWrapBottom?: boolean;
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onChange?: (v: string) => void;
  onQuery?: (v: string) => void;
}

@Component
export default class QsSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({ type: String, default: '' }) value: string;
  @Prop({ type: Number, default: 0 }) qsSelectorOptionsWidth: number;
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  @Prop({ type: Array, default: () => [] }) favoriteList: IFavoriteListItem[];
  /* 语句模式hover显示的操作是否显示在下方 */
  // @Prop({ type: Boolean, default: false }) isQsOperateWrapBottom: boolean;
  @Prop({ type: String, default: '' }) clearKey: string;

  @Ref('select') selectRef: HTMLDivElement;
  // @Ref('lastPosition') lastPositionRef: HTMLDivElement;
  @Ref('el') elRef: HTMLDivElement;

  localValue = '';
  /* 弹层实例 */
  popoverInstance = null;
  /* 是否弹出选项框 */
  showSelector = false;
  /* 当前需要弹出的选项类型 */
  curTokenType: EQueryStringTokenType = EQueryStringTokenType.key;
  /* 当前输入的文字 */
  search = '';
  /* 主动刷新token列表 */
  tokenRefreshKey = '';
  /* 当前片段的key */
  curTokenField = '';

  queryStringEditor: QueryStringEditor = null;

  // operatePosition = {
  //   top: -26,
  //   left: 0,
  // };

  inputValue = '';
  fieldsMap: Map<string, IFilterField> = new Map();

  onClickOutsideFn = () => {};

  beforeDestroy() {
    this.onClickOutsideFn?.();
    this.destroyPopoverInstance();
    document.removeEventListener('keydown', this.handleKeyDownSlash);
  }

  @Watch('value', { immediate: true })
  handleWatchValue() {
    if (this.localValue !== this.value) {
      this.localValue = this.value;
      this.inputValue = this.value;
      this.handleInit();
    }
  }

  @Debounce(200)
  @Watch('localValue', { immediate: true })
  handleWatchLocalValue() {
    // if (!this.lastPositionRef) return;
    // const left = this.lastPositionRef.offsetLeft;
    // const top = this.lastPositionRef.offsetTop < 14 && !this.isQsOperateWrapBottom ? -26 : this.$el.clientHeight - 2;
    // this.operatePosition = {
    //   top,
    //   left,
    // };
    this.handleAddKeyDownSlash();
  }

  @Watch('fields', { immediate: true })
  handleWatchFields() {
    for (const item of this.fields) {
      this.fieldsMap.set(item.name, item);
    }
  }

  @Watch('clearKey')
  handleWatchClearKey() {
    this.handleClear();
  }
  mounted() {
    this.handleInit();
  }

  handleInit() {
    this.$nextTick(() => {
      if (this.queryStringEditor) {
        this.queryStringEditor.setQueryString(this.localValue);
      } else {
        const el = this.$el.querySelector('.retrieval-filter__qs-selector-component');
        this.queryStringEditor = new QueryStringEditor({
          target: el,
          value: this.localValue,
          popUpFn: this.handlePopUp,
          onSearch: this.handleSearch,
          popDownFn: this.destroyPopoverInstance,
          onChange: this.handleChange,
          onQuery: this.handleQuery,
          onInput: this.handleInput,
          keyFormatter: this.fieldFormatter,
          valueFormatter: this.valueFormatter,
        });
      }
    });
  }

  async handleShowSelect(event: MouseEvent) {
    if (this.popoverInstance) {
      this.destroyPopoverInstance();
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectRef,
      trigger: 'click',
      hideOnClick: false,
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: false,
      interactive: true,
      boundary: 'window',
      distance: 15,
      zIndex: 998,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
    this.showSelector = true;
    this.onClickOutsideFn = onClickOutside(
      [this.$el, document.querySelector('.retrieval-filter__qs-selector-component__popover')],
      () => {
        this.destroyPopoverInstance();
      },
      { once: true }
    );
  }

  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.showSelector = false;
    this.onClickOutsideFn?.();
    this.queryStringEditor?.setIsPopup?.(false);
  }

  /**
   * @description 弹出选项框
   * @param type
   * @param field
   * @returns
   */
  handlePopUp(type, field) {
    let fieldStr = field;
    const regex = /^dimensions\./;
    if (regex.test(field)) {
      fieldStr = field.replace(regex, '');
    }
    if (this.curTokenType === EQueryStringTokenType.condition && type === EQueryStringTokenType.key) {
      this.search = '';
    }
    this.curTokenType = type;
    this.curTokenField = fieldStr;
    const customEvent = {
      target: this.elRef,
    };
    if (this.popoverInstance) {
      this.popoverInstance?.show();
      return;
    }
    this.handleShowSelect(customEvent as any);
  }

  /**
   * @description 下拉选项选择
   * @param str
   */
  handleSelectOption(str: string) {
    this.queryStringEditor.setToken(str, this.curTokenType);
  }

  /**
   * @description 搜索
   * @param value
   */
  handleSearch(value) {
    this.search = value;
  }

  /**
   * @description 输入框的值变化
   * @param str
   */
  handleChange(str: string) {
    this.localValue = str;
    this.$emit('change', str);
  }

  /**
   * @description 查询
   */
  handleQuery() {
    this.popoverInstance?.hide?.();
    this.$emit('query');
  }

  /**
   * @description 选择了收藏项
   * @param value
   */
  handleSelectFavorite(value: string) {
    this.queryStringEditor.setQueryString(value);
    this.handleChange(value);
    this.handleQuery();
  }

  /**
   * @description 清空
   */
  handleClear() {
    this.inputValue = '';
    this.localValue = '';
    this.queryStringEditor.setQueryString('');
    this.handleChange('');
    this.handleQuery();
  }
  /**
   * @description 复制
   */
  handleCopy() {
    copyText(this.localValue, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  handleInput(val) {
    this.inputValue = val.replace(/^\s+|\s+$/g, '');
  }

  /**
   * @description 是否输入了/，如果输入了则弹出选项框
   * @param event
   */
  handleKeyDownSlash(event) {
    if (event.key === '/' && event.target?.tagName !== 'INPUT') {
      this.handlePopUp(EQueryStringTokenType.key, '');
      setTimeout(() => {
        this.queryStringEditor.editorEl?.focus?.();
      }, 300);
      document.removeEventListener('keydown', this.handleKeyDownSlash);
    }
  }
  handleAddKeyDownSlash() {
    if (this.localValue) {
      document.removeEventListener('keydown', this.handleKeyDownSlash);
    } else {
      document.addEventListener('keydown', this.handleKeyDownSlash);
    }
  }

  /**
   * @description
   *  fields 中 is_dimensions=true 的，需要补充 dimensions
   *  dimensions.xxxxx
   * @param field
   * @returns
   */
  fieldFormatter(field: string) {
    const fieldItem = this.fieldsMap.get(field);
    const regex = /^dimensions\./;
    if (fieldItem?.is_dimensions && !regex.test(field)) {
      return `dimensions.${field}`;
    }
    return field;
  }

  /**
   * @description 语句模式 : (等于) 某个值的时候需要将值用双引号包裹

   * @param field
   * @param method
   * @param value
   */
  valueFormatter(field: string, method: string, value: string) {
    const regex = /^".*"$/;
    if (field && method === ':' && !regex.test(value)) {
      return `"${value}"`;
    }
    return value;
  }

  render() {
    return (
      <div
        class='retrieval-filter__qs-selector-component-wrap'
        data-placeholder={
          !this.inputValue && !this.localValue
            ? `/ ${this.$t('快速定位到搜索，请输入关键词，')}log:error AND "name=bklog"`
            : ''
        }
      >
        <div class='retrieval-filter__qs-selector-component' />
        <div
          ref='el'
          class='__bottom__'
        />
        {/* <div class='qs-value-hidden'>
          <div class='qs-value-hidden-text'>
            {this.localValue}
            <span
              ref='lastPosition'
              class='last-position__'
            />
          </div>
        </div> */}

        <div style='display: none;'>
          <div
            ref='select'
            style={{
              ...(this.qsSelectorOptionsWidth ? { width: `${this.qsSelectorOptionsWidth}px` } : {}),
            }}
            class='retrieval-filter__qs-selector-component__popover'
          >
            <QsSelectorSelector
              favoriteList={this.favoriteList}
              field={this.curTokenField}
              fields={this.fields}
              getValueFn={this.getValueFn}
              queryString={this.localValue}
              search={this.search}
              show={this.showSelector}
              type={this.curTokenType}
              onSelect={this.handleSelectOption}
              onSelectFavorite={this.handleSelectFavorite}
            />
          </div>
        </div>
        {/* {!!this.localValue && !this.showSelector && (
          <div
            style={{
              left: `${this.operatePosition.left}px`,
              top: `${this.operatePosition.top}px`,
            }}
            class='qs-operate-wrap'
          >
            <div
              class='operate-btn'
              onClick={this.handleClear}
            >
              <span
                class='icon-monitor icon-a-Clearqingkong'
                v-bk-tooltips={{
                  content: this.$tc('清空'),
                  delay: 300,
                }}
              />
            </div>
            <div
              class='operate-btn'
              v-bk-tooltips={{
                content: this.$tc('复制'),
                delay: 300,
              }}
              onClick={this.handleCopy}
            >
              <span class='icon-monitor icon-mc-copy' />
            </div>
          </div>
        )} */}
      </div>
    );
  }
}
