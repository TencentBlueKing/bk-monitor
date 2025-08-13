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

import { copyText } from 'monitor-common/utils';

import { isEn } from '../../i18n/lang';
import AutoWidthInput from './auto-width-input';
import KvTag from './kv-tag';
import UiSelectorOptions from './ui-selector-options';
import {
  type IFilterField,
  type IFilterItem,
  type IGetValueFnParams,
  type IWhereValueOptionsItem,
  ECondition,
  EFieldType,
  EMethod,
} from './utils';

import './ui-selector.scss';

interface IProps {
  clearKey?: string;
  fields: IFilterField[];
  value?: IFilterItem[];
  getValueFn?: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  onChange?: (v: IFilterItem[]) => void;
}

@Component
export default class UiSelector extends tsc<IProps> {
  @Prop({ type: Array, default: () => [] }) fields: IFilterField[];
  @Prop({
    type: Function,
    default: () =>
      Promise.resolve({
        count: 0,
        list: [],
      }),
  })
  getValueFn: (params: IGetValueFnParams) => Promise<IWhereValueOptionsItem>;
  @Prop({ type: Array, default: () => [] }) value: IFilterItem[];
  @Prop({ type: String, default: '' }) clearKey: string;
  @Ref('selector') selectorRef: HTMLDivElement;

  /* 是否显示弹出层 */
  showSelector = false;
  /* tag列表 */
  localValue: IFilterItem[] = [];
  /* 弹层实例 */
  popoverInstance = null;
  /* 当亲编辑项 */
  updateActive = -1;
  // /* 是否显示输入框 */
  // showInput = false;
  /* 输入框的值 */
  inputValue = '';
  /* 是否聚焦 */
  inputFocus = false;

  @Watch('value', { immediate: true })
  handleWatchValue() {
    const valueStr = JSON.stringify(this.value);
    const localValueStr = JSON.stringify(this.localValue);
    if (valueStr !== localValueStr) {
      this.localValue = JSON.parse(valueStr);
    }
  }

  @Watch('clearKey')
  handleWatchClearKey() {
    this.handleClear();
  }

  mounted() {
    document.addEventListener('keydown', this.handleKeyDownSlash);
  }
  beforeDestroy() {
    document.removeEventListener('keydown', this.handleKeyDownSlash);
  }

  async handleShowSelect(event: MouseEvent) {
    if (this.popoverInstance) {
      this.destroyPopoverInstance();
      return;
    }
    this.popoverInstance = this.$bkPopover(event.target, {
      content: this.selectorRef,
      trigger: 'click',
      placement: 'bottom-start',
      theme: 'light common-monitor',
      arrow: true,
      interactive: true,
      boundary: 'window',
      distance: 20,
      zIndex: 998,
      animation: 'slide-toggle',
      followCursor: false,
      onHidden: () => {
        this.destroyPopoverInstance();
        document.addEventListener('keydown', this.handleKeyDownSlash);
      },
    });
    await this.$nextTick();
    this.popoverInstance?.show();
    this.showSelector = true;
  }
  destroyPopoverInstance() {
    this.popoverInstance?.hide?.();
    this.popoverInstance?.destroy?.();
    this.popoverInstance = null;
    this.showSelector = false;
  }

  handleAdd(event: MouseEvent) {
    event.stopPropagation();
    this.updateActive = -1;
    const customEvent = {
      ...event,
      target: event.currentTarget,
    };
    this.handleShowSelect(customEvent);
    this.hideInput();
  }

  /**
   * @description 点击弹层取消
   */
  handleCancel() {
    this.destroyPopoverInstance();
    this.hideInput();
  }
  /**
   * @description 点击弹层确认
   */
  handleConfirm(value: IFilterItem) {
    const localValue = JSON.parse(JSON.stringify(this.localValue));
    if (value) {
      if (this.updateActive > -1) {
        localValue.splice(this.updateActive, 1, value);
      } else {
        localValue.push(value);
      }
    }
    this.localValue = localValue;
    this.destroyPopoverInstance();
    this.hideInput();
    // setTimeout(() => {
    //   this.handleClickComponent();
    // }, 300);
    this.handleChange();
  }

  /**
   * @description 删除tag
   * @param index
   */
  handleDeleteTag(index: number) {
    this.localValue.splice(index, 1);
    this.handleChange();
    this.handleCancel();
  }

  /**
   * @description 编辑tag
   * @param event
   * @param index
   */
  handleUpdateTag(event: MouseEvent, index: number) {
    event.stopPropagation();
    this.updateActive = index;
    const customEvent = {
      ...event,
      target: event.currentTarget,
    };
    this.handleShowSelect(customEvent);
    this.hideInput();
  }

  /**
   * @description 隐藏tag
   * @param index
   */
  handleHideTag(index: number) {
    let hide = false;
    if (typeof this.localValue[index]?.hide === 'boolean') {
      hide = !this.localValue[index].hide;
    } else {
      hide = true;
    }
    this.localValue.splice(index, 1, {
      ...this.localValue[index],
      hide,
    });
    this.handleChange();
  }

  /**
   * @description 清空
   */
  handleClear(event?: MouseEvent) {
    event?.stopPropagation?.();
    this.localValue = [];
    this.updateActive = -1;
    this.hideInput();
    this.handleChange();
  }

  /**
   * @description 复制
   * @param event
   */
  handleCopy(event: MouseEvent) {
    event.stopPropagation();
    const str = this.localValue
      .map(item => {
        const value =
          item.value.length > 1
            ? `(${item.value.map(v => `"${v.id || '*'}"`).join(' AND ')})`
            : `"${item.value?.[0]?.id || '*'}"`;
        return `${item.key.id} : ${value}`;
      })
      .join(' AND ');
    copyText(str, msg => {
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

  /**
   * @description 点击组件
   */
  handleClickComponent(event?: MouseEvent) {
    event?.stopPropagation();
    this.updateActive = -1;
    // this.showInput = true;
    this.inputFocus = true;
    const el = this.$el.querySelector('.kv-placeholder');
    const customEvent = {
      ...event,
      target: el,
    };
    this.handleShowSelect(customEvent);
  }

  handleBlur() {
    this.inputFocus = false;
    if (!this.inputValue) {
      this.hideInput();
    }
  }

  hideInput() {
    this.inputFocus = false;
    // this.showInput = false;
    this.inputValue = '';
  }
  handleInput(v: string) {
    this.inputValue = v;
  }

  handleEnter() {
    if (this.inputValue) {
      this.localValue.push({
        key: {
          id: '*',
          name: this.$tc('全文'),
        },
        value: [{ id: this.inputValue, name: this.inputValue }],
        method: { id: EMethod.include, name: this.$tc('包含') },
        condition: { id: ECondition.and, name: 'AND' },
      });
      this.inputValue = '';
      this.destroyPopoverInstance();
      setTimeout(() => {
        this.handleClickComponent();
      }, 50);
      this.handleChange();
    }
  }

  handleChange() {
    this.$emit('change', this.localValue);
  }

  handleKeyDownSlash(event) {
    if (event.key === '/' && !this.inputValue && !this.showSelector && event.target?.tagName !== 'INPUT') {
      event.preventDefault();
      this.handleClickComponent();
      document.removeEventListener('keydown', this.handleKeyDownSlash);
    }
  }

  render() {
    return (
      <div
        class='retrieval-filter__ui-selector-component'
        onClick={this.handleClickComponent}
      >
        <div
          class='add-btn'
          onClick={this.handleAdd}
        >
          <span class='icon-monitor icon-mc-add' />
          <span class='add-text'>{this.$t('添加条件')}</span>
        </div>
        {this.localValue.map((item, index) => (
          <KvTag
            key={`${index}_kv`}
            value={item}
            onDelete={() => this.handleDeleteTag(index)}
            onHide={() => this.handleHideTag(index)}
            onUpdate={event => this.handleUpdateTag(event, index)}
          />
        ))}
        <div class={['kv-placeholder', { 'is-en': isEn }]}>
          <AutoWidthInput
            height={40}
            isFocus={this.inputFocus}
            placeholder={`${this.$t('快捷键 / ，请输入...')}`}
            value={this.inputValue}
            onBlur={this.handleBlur}
            onEnter={this.handleEnter}
            onInput={this.handleInput}
          />
          {/* <div class='kv-placeholder'>
          {this.showInput ? (
            <AutoWidthInput
              height={40}
              isFocus={this.inputFocus}
              value={this.inputValue}
              onBlur={this.handleBlur}
              onEnter={this.handleEnter}
              onInput={this.handleInput}
            />
          ) : (
            <span class='placeholder-text'>{`/ ${this.$t('快速定位到搜索，请输入关键词...')}`}</span>
          )} */}
          {/* {!!this.localValue.length && !this.showSelector && (
            <div class='hover-btn-wrap'>
              <div
                class='operate-btn'
                v-bk-tooltips={{
                  content: this.$tc('清空'),
                  delay: 300,
                }}
                onClick={this.handleClear}
              >
                <span class='icon-monitor icon-a-Clearqingkong' />
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
        <div style='display: none;'>
          <div ref='selector'>
            <UiSelectorOptions
              fields={[
                {
                  type: EFieldType.all,
                  name: '*',
                  alias: this.$tc('全文检索'),
                  is_option_enabled: false,
                  supported_operations: [],
                },
                ...this.fields,
              ]}
              getValueFn={this.getValueFn}
              keyword={this.inputValue}
              show={this.showSelector}
              value={this.localValue?.[this.updateActive]}
              onCancel={this.handleCancel}
              onConfirm={this.handleConfirm}
            />
          </div>
        </div>
      </div>
    );
  }
}
