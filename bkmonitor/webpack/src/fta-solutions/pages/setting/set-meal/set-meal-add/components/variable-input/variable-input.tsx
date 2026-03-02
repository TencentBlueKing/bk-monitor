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
import { Component, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Debounce } from 'monitor-common/utils';
import { xssFilter } from 'monitor-common/utils/xss';
import EmptyStatus from 'monitor-pc/components/empty-status/empty-status';
import {
  getGlobalOffset,
  replaceContent,
  setGlobalOffset,
} from 'monitor-pc/components/retrieval-filter/query-string-utils';

import './variable-input.scss';

interface ITipsListItem {
  group: string;
  groupName?: string;
  id: string;
  name: string;
}
interface IVariableInput {
  placeholder?: string;
  readonly?: boolean;
  tipsList?: ITipsListItem[];
  value?: string;
  onChange?: (val: string) => void;
}

const isVariableName = (val: string) => {
  return !!val && /^\{\{.*?\}\}$/.test(val);
};

@Component
export default class VariableInput extends tsc<IVariableInput> {
  @Model('input', { default: '', type: String }) value: string;
  @Prop({ default: () => [], type: Array }) tipsList: ITipsListItem[];
  @Prop({ default: '', type: String }) placeholder: string;
  @Prop({ default: false, type: Boolean }) readonly: boolean;

  @Ref('select') selectRef: HTMLElement;
  @Ref('searchInput') searchInputRef;

  // 输入框元素
  elEdit: HTMLInputElement = null;
  // 是否激活输入框
  active = false;
  // 输入框当前值
  inputValue = '';
  // 输入框弹出层实例
  popoverInstance = null;
  // 弹出层搜索值
  searchValue = '';
  // 当前输入框光标位置
  curStrIndex = 0;
  // 当前选择的变量索引
  curCursorIndex = 0;
  // 输入框弹出层是否显示
  popoverShow = false;

  get selectList() {
    const list = [];
    const searchValueLower = this.searchValue.toLocaleLowerCase();
    for (const item of this.tipsList) {
      const group = list.find(g => g.group === item.group);
      if (
        !(
          `${item.id.toLocaleLowerCase()}`.includes(searchValueLower) ||
          `${item.name.toLocaleLowerCase()}`.includes(searchValueLower)
        )
      ) {
        continue;
      }
      if (group) {
        group.children.push({
          ...item,
        });
      } else {
        list.push({
          group: item.group,
          groupName: item.groupName,
          children: [
            {
              ...item,
            },
          ],
        });
      }
    }
    return list;
  }

  @Watch('value', { immediate: true })
  handleWatchValue(val: string) {
    if (this.inputValue !== val) {
      this.inputValue = val;
      this.$nextTick(() => {
        this.handleSetInputParse(val, false);
      });
      this.active = false;
    }
  }

  mounted() {
    this.elEdit = this.$el.querySelector('.set-meal-variable-input-content');
    this.handleSetInputParse(this.value, false);
    this.active = false;
  }

  beforeDestroy() {
    this.handleDestroyPopover();
    document.removeEventListener('keydown', this.handleShortcutKey);
  }

  /**
   * @description 处理输入事件
   * @param e
   */
  handleInput(e: InputEvent) {
    const target = e.target as HTMLElement;
    this.inputValue = target.textContent;
    this.handleChange();
  }

  @Debounce(300)
  handleChange() {
    this.handleSetInputParse(this.inputValue);
    this.$emit('input', this.inputValue);
    this.$emit('change', this.inputValue);
    this.dispatch('bk-form-item', 'form-change');
  }

  /**
   * @description 处理键盘事件
   * @param e
   */
  handleKeydown(e: KeyboardEvent) {
    if (['ArrowUp', 'ArrowDown', 'Enter'].includes(e.key)) {
      return;
    }
    if (e.key === '$') {
      this.curStrIndex = getGlobalOffset(this.elEdit);
      setTimeout(() => {
        this.handlePopoverShow();
      }, 400);
    } else {
      this.handleDestroyPopover();
    }
  }

  /**
   * @description 处理输入值解析
   * @param val 输入值
   * @param isFocus 是否聚焦到输入框
   * @param getVariables 回调函数，用于获取变量列表
   */
  handleSetInputParse(val: string, isFocus = true, getVariables?: (val: string[]) => void) {
    const matches = val.match(/\{\{.*?\}\}|.+?(?=\{\{|$)/g)?.filter(item => item) || [];
    const variables = [];
    const str = matches
      .map(item => {
        if (isVariableName(item)) {
          variables.push(item);
          return `<span style="color: #E54488;">${xssFilter(item)}</span>`;
        }
        return xssFilter(item);
      })
      .join('');
    getVariables?.(variables);
    if (isFocus) {
      replaceContent(this.elEdit, str);
    } else {
      this.elEdit.innerHTML = str;
    }
  }

  /**
   * @description 处理聚焦事件
   */
  handleFocus() {
    this.active = true;
    this.dispatch('bk-form-item', 'form-focus');
  }

  /**
   * @description 处理失焦事件
   */
  handleBlur() {
    this.active = false;
    this.dispatch('bk-form-item', 'form-blur');
  }

  /**
   * @description 处理弹出层显示事件
   */
  handlePopoverShow() {
    if (!this.popoverInstance) {
      this.popoverInstance = this.$bkPopover(this.$el, {
        content: this.selectRef,
        arrow: false,
        trigger: 'trigger',
        interactive: true,
        placement: 'bottom-start',
        theme: 'light set-meal-variable-input-component-pop',
        maxWidth: 540,
        distance: 4,
        duration: [200, 0],
        onHide: () => {
          document.removeEventListener('keydown', this.handleShortcutKey);
          this.curCursorIndex = -1;
          this.searchValue = '';
          this.popoverShow = false;
        },
      });
    }
    // 显示
    this.popoverInstance.show(100);
    document.addEventListener('keydown', this.handleShortcutKey);
    this.popoverShow = true;
    // this.handleSetFocus(this.curCursorIndex);
    setTimeout(() => {
      this.searchInputRef?.focus?.();
    }, 200);
  }

  /**
   * @description 处理弹出层隐藏事件
   */
  handleDestroyPopover(): void {
    if (this.popoverInstance) {
      this.popoverInstance.hide(0);
      this.popoverInstance.destroy?.();
      this.popoverInstance = null;
      document.removeEventListener('keydown', this.handleShortcutKey);
      this.curCursorIndex = -1;
      this.searchValue = '';
      this.popoverShow = false;
    }
  }

  /**
   * @description 触发事件
   * @param componentName 组件名称
   * @param eventName 事件名称
   */
  dispatch(componentName: string, eventName: string) {
    let parent = this.$parent || this.$root;
    let name = parent.$options.name;

    while (parent && (!name || name !== componentName)) {
      parent = parent.$parent;

      if (parent) {
        name = parent.$options.name;
      }
    }
    if (parent) {
      parent.$emit(eventName);
    }
  }

  /**
   * @description 处理选择事件
   * @param item 选中项
   */
  handleSelect(item: ITipsListItem) {
    const value = `{{${item.id}}}`;
    this.inputValue = `${this.inputValue.slice(0, this.curStrIndex)}${value}${this.inputValue.slice(this.curStrIndex + 1)}`;
    this.handleChange();
    this.handleDestroyPopover();
    // 移动光标到选中项的末尾
    setTimeout(() => {
      setGlobalOffset(this.elEdit, `${this.inputValue.slice(0, this.curStrIndex)}${value}`.length);
    }, 400);
  }

  /**
   * @description 处理快捷键事件
   * @param e 键盘事件
   */
  handleShortcutKey(e: KeyboardEvent) {
    if (!this.popoverShow) {
      return;
    }
    const len = this.selectList.reduce((pre, cur) => pre + cur.children.length, 0);
    if (e.key === 'ArrowUp') {
      e.preventDefault();
      if (this.curCursorIndex > 0) {
        this.curCursorIndex--;
      } else {
        this.curCursorIndex = len - 1;
      }
      this.handleSetFocus(this.curCursorIndex);
    } else if (e.key === 'ArrowDown') {
      e.preventDefault();
      if (this.curCursorIndex < len - 1) {
        this.curCursorIndex++;
      } else {
        this.curCursorIndex = 0;
      }
      this.handleSetFocus(this.curCursorIndex);
    } else if (e.key === 'Enter') {
      e.preventDefault();
      let index = -1;
      for (const item of this.selectList) {
        for (const child of item.children) {
          index++;
          if (index === this.curCursorIndex) {
            this.handleSelect(child);
            break;
          }
        }
      }
    }
  }

  /**
   * @description 处理设置焦点事件
   * @param index 索引
   */
  handleSetFocus(index: number) {
    if (this.selectList.length) {
      const groupListEl = this.selectRef.querySelector('.group-list');
      const itemList = groupListEl.querySelectorAll('.group-item-child');
      itemList.forEach((item, i) => {
        if (i === index) {
          item?.focus?.();
        }
      });
    }
  }

  handleClearSearch() {
    this.searchValue = '';
  }

  render() {
    return (
      <div class='set-meal-variable-input-component'>
        <div
          class='set-meal-variable-input-content'
          contenteditable={true}
          data-placeholder={this.inputValue ? '' : this.placeholder || this.$t('输入')}
          spellcheck={false}
          onBlur={this.handleBlur}
          onFocus={this.handleFocus}
          onInput={this.handleInput}
          onKeydown={this.handleKeydown}
        />
        <div
          style={{
            display: 'none',
          }}
        >
          <div
            ref='select'
            class='set-meal-variable-input-component-pop'
          >
            <bk-input
              ref='searchInput'
              class='search-input'
              v-model={this.searchValue}
              behavior='simplicity'
              left-icon='bk-icon icon-search'
              placeholder={this.$t('请输入关键字')}
            />
            <div class='group-list'>
              {this.selectList.length ? (
                this.selectList.map(item => (
                  <div
                    key={item.group}
                    class='group-item'
                  >
                    <div class='group-item-title'>{`${item.groupName}(${item.children.length})`}</div>
                    {item.children.map((child, index) => (
                      <div
                        key={`${child.id}-${index}`}
                        class='group-item-child'
                        tabindex={0}
                        onClick={() => this.handleSelect(child)}
                      >
                        <div class='group-item-child-id'>{child.id}</div>
                        <div class='group-item-child-name'>{child.name}</div>
                      </div>
                    ))}
                  </div>
                ))
              ) : (
                <EmptyStatus
                  type={this.searchValue ? 'search-empty' : 'empty'}
                  onOperation={this.handleClearSearch}
                />
              )}
            </div>
          </div>
        </div>
      </div>
    );
  }
}
