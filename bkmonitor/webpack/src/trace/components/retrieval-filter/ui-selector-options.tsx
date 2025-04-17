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

import { defineComponent, shallowRef, computed, watch, useTemplateRef, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

import { useEventListener, useDebounceFn } from '@vueuse/core';
import { Select, Checkbox, Input, Button } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { detectOperatingSystem } from 'monitor-common/utils/navigator';

import {
  ECondition,
  EFieldType,
  EMethod,
  fieldTypeMap,
  type IFilterField,
  type IFilterItem,
  type IValue,
  type TGetValueFn,
  UI_SELECTOR_OPTIONS_EMITS,
  UI_SELECTOR_OPTIONS_PROPS,
} from './typing';
import { getTitleAndSubtitle, isNumeric } from './utils';
import ValueTagSelector from './value-tag-selector';

import './ui-selector-options.scss';

export default defineComponent({
  name: 'UiSelectorOptions',
  props: UI_SELECTOR_OPTIONS_PROPS,
  emits: UI_SELECTOR_OPTIONS_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();
    const $el = useTemplateRef<HTMLDivElement>('el');
    const searchInputRef = useTemplateRef('searchInput');
    const valueSelectorRef = useTemplateRef<HTMLDivElement>('valueSelector');
    const allInputRef = useTemplateRef<HTMLDivElement>('allInput');

    const searchValue = shallowRef('');
    const searchLocalFields = shallowRef<IFilterField[]>([]);
    const cursorIndex = shallowRef(0);
    const checkedItem = shallowRef<IFilterField>(null);
    const queryString = shallowRef('');
    const method = shallowRef('');
    const values = shallowRef([]);
    const isWildcard = shallowRef(false);
    const rightRefreshKey = shallowRef(random(8));
    const rightFocus = shallowRef(false);
    const cacheCheckedName = shallowRef('');
    const isMacSystem = shallowRef(false);

    const wildcardItem = computed(
      () => checkedItem.value?.supported_operations?.find(item => item.value === method.value)?.options
    );
    const isTypeInteger = computed(() => checkedItem.value?.type === EFieldType.integer);
    const isIntegerError = computed(() => (isTypeInteger.value ? values.value.some(v => !isNumeric(v.id)) : false));
    const valueSelectorFieldInfo = computed(() => {
      return {
        field: checkedItem.value?.name,
        alias: checkedItem.value?.alias,
        isEnableOptions: !!checkedItem.value?.is_option_enabled,
        methods: checkedItem.value.supported_operations.map(item => ({
          id: item.value,
          name: item.alias,
        })),
        type: checkedItem.value?.type,
      };
    });

    const enterSelectionDebounce = useDebounceFn((isFocus = false) => {
      enterSelection(isFocus);
    }, 500);
    const handleSearchChangeDebounce = useDebounceFn(() => {
      handleSearchChange();
    }, 300);

    init();
    watch(
      () => props.fields,
      () => {
        handleSearchChange();
      },
      { immediate: true }
    );
    watch(
      () => props.show,
      val => {
        if (!val) {
          initData();
        }
        if (val) {
          if (props.value) {
            const id = props.value.key.id;
            for (const item of props.fields) {
              if (item.name === id) {
                const checkedItem = JSON.parse(JSON.stringify(item));
                handleCheck(
                  checkedItem,
                  props.value.method.id,
                  props.value.value,
                  !!props.value?.options?.is_wildcard,
                  true
                );
                break;
              }
            }
          } else {
            handleCheck(props.fields[0]);
            setTimeout(() => {
              searchInputRef.value?.focus();
            }, 300);
          }
        }
      },
      { immediate: true }
    );

    function init() {
      isMacSystem.value = detectOperatingSystem() === 'macOS';
      useEventListener(document, 'keydown', handleKeydownEvent);
    }

    function initData() {
      searchValue.value = '';
      cursorIndex.value = 0;
      checkedItem.value = null;
      queryString.value = '';
      method.value = '';
      values.value = [];
      isWildcard.value = false;
      rightFocus.value = false;
      cacheCheckedName.value = '';
      handleSearchChange();
    }

    function handleCheck(item: IFilterField, method$ = '', value = [], isWildcard$ = false, isFocus = false) {
      checkedItem.value = JSON.parse(JSON.stringify(item));
      values.value = value || [];
      method.value = method$ || item?.supported_operations?.[0]?.value || '';
      isWildcard.value = isWildcard$;
      const index = searchLocalFields.value.findIndex(f => f.name === item.name) || 0;
      if (checkedItem.value.name === '*') {
        queryString.value = value[0]?.id || '';
      } else {
        if (cacheCheckedName.value !== item.name) {
          rightRefreshKey.value = random(8);
        }
        cacheCheckedName.value = item.name;
        if (isFocus) {
          nextTick(() => {
            valueSelectorRef.value?.focusFn?.();
            rightFocus.value = true;
          });
        }
      }
      console.log(index);
      cursorIndex.value = index;
    }

    function handleConfirm() {
      if (checkedItem.value.name === '*' && queryString.value) {
        const value: IFilterItem = {
          key: { id: checkedItem.value.name, name: t('全文') },
          method: { id: EMethod.include, name: t('包含') },
          value: [{ id: queryString.value, name: queryString.value }],
          condition: { id: ECondition.and, name: 'AND' },
        };
        emit('confirm', value);

        return;
      }
      if (values.value.length) {
        const methodName = checkedItem.value.supported_operations.find(item => item.value === method.value)?.alias;
        const value: IFilterItem = {
          key: { id: checkedItem.value.name, name: checkedItem.value.alias },
          method: { id: method.value as any, name: methodName || '=' },
          value: values.value,
          condition: { id: ECondition.and, name: 'AND' },
          options: isWildcard.value
            ? {
                is_wildcard: true,
              }
            : undefined,
        };
        emit('confirm', value);
      } else {
        emit('confirm', null);
      }
    }
    function handleCancel() {
      emit('cancel');
    }
    function handleValueChange(v: IValue[]) {
      values.value = v;
    }

    function handleKeydownEvent(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        event.preventDefault();
        handleCancel();
      } else if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
        event.preventDefault();
        if (!isIntegerError.value) {
          handleConfirm();
        }
        return;
      }
      if (rightFocus.value) {
        return;
      }
      switch (event.key) {
        case 'ArrowUp': {
          // 按下上箭头键
          event.preventDefault();
          cursorIndex.value -= 1;
          if (cursorIndex.value < 0) {
            cursorIndex.value = searchLocalFields.value.length - 1;
          }
          updateSelection();
          enterSelectionDebounce();
          break;
        }

        case 'ArrowDown': {
          event.preventDefault();
          cursorIndex.value += 1;
          if (cursorIndex.value > searchLocalFields.value.length) {
            cursorIndex.value = 0;
          }
          updateSelection();
          enterSelectionDebounce();
          break;
        }
        case 'Enter': {
          event.preventDefault();
          enterSelectionDebounce(true);
          break;
        }
      }
    }
    function updateSelection() {
      nextTick(() => {
        const listEl = $el.value.querySelector('.component-top-left .options-wrap');
        const el = listEl?.children?.[cursorIndex.value];
        if (el) {
          el.scrollIntoView(false);
        }
      });
    }
    function enterSelection(isFocus = false) {
      const item = searchLocalFields.value[cursorIndex.value];
      if (item) {
        if (item.name === '*') {
          if (!props.keyword) allInputRef.value?.focus();
        } else {
          queryString.value = '';
          handleCheck(item, '', [], false, isFocus);
        }
      }
    }
    function handleSearchChange() {
      cursorIndex.value = -1;
      if (!searchValue.value) {
        searchLocalFields.value = props.fields.slice();
      } else {
        searchLocalFields.value = props.fields.filter(item => {
          if (!searchValue.value) {
            return true;
          }
          if (item.alias.toLocaleLowerCase().includes(searchValue.value.toLocaleLowerCase())) {
            return true;
          }
          if (item.name.toLocaleLowerCase().includes(searchValue.value.toLocaleLowerCase())) {
            return true;
          }
          return false;
        });
      }
    }
    function handleValueSelectorBlur() {
      rightFocus.value = false;
    }
    function handleSelectorFocus() {
      rightFocus.value = true;
    }
    function getValueFnProxy(params: { search: string; limit: number; field: string }): any | TGetValueFn {
      return new Promise((resolve, _reject) => {
        props
          .getValueFn({
            where: [
              {
                key: params.field,
                method: 'include',
                value: [params.search || ''],
                condition: ECondition.and,
                options: {
                  is_wildcard: true,
                },
              },
            ],
            fields: [params.field],
            limit: params.limit,
          })
          .then(data => {
            resolve(data);
          })
          .catch(() => {
            resolve({
              count: 0,
              list: [],
            });
          });
      });
    }

    return {
      checkedItem,
      queryString,
      method,
      wildcardItem,
      isWildcard,
      rightRefreshKey,
      valueSelectorFieldInfo,
      values,
      searchValue,
      isIntegerError,
      searchLocalFields,
      cursorIndex,
      isMacSystem,
      getValueFnProxy,
      handleValueChange,
      handleValueSelectorBlur,
      handleSelectorFocus,
      handleSearchChangeDebounce,
      handleCheck,
      handleConfirm,
      handleCancel,
    };
  },
  render() {
    const rightRender = () => {
      if (this.checkedItem?.name === '*') {
        return [
          <div
            key={'all'}
            class='form-item'
          >
            <div class='form-item-label mt-16'>{this.$t('检索内容')}</div>
            <div class='form-item-content mt-8'>
              <Input
                ref={'allInput'}
                v-model={this.queryString}
                placeholder={this.$t('请输入')}
                rows={15}
                type={'textarea'}
              />
            </div>
          </div>,
        ];
      }
      return this.checkedItem
        ? [
            <div
              key={'method'}
              class='form-item mt-34'
              // onClick={e => e.stopPropagation()}
            >
              <div class='form-item-label'>{this.$t('条件')}</div>
              <div class='form-item-content mt-6'>
                <Select
                  ext-cls={'method-select'}
                  v-model={this.method}
                  popover-options={{
                    appendTo: 'parent',
                  }}
                  clearable={false}
                >
                  {this.checkedItem.supported_operations.map(item => (
                    <Select.Option
                      id={item.value}
                      key={item.value}
                      name={item.alias}
                    />
                  ))}
                </Select>
              </div>
            </div>,
            <div
              key={'value'}
              class='form-item mt-16'
            >
              <div class='form-item-label'>
                <span class='left'>{this.$t('检索值')}</span>
                {!!this.wildcardItem && (
                  <span class='right'>
                    <Checkbox
                      v-model={this.isWildcard}
                      // onChange={this.handleIsWildcardChange}
                    >
                      {this.wildcardItem?.label || '使用通配符'}
                    </Checkbox>
                  </span>
                )}
              </div>
              <div class='form-item-content mt-6'>
                <ValueTagSelector
                  key={this.rightRefreshKey}
                  ref='valueSelector'
                  fieldInfo={this.valueSelectorFieldInfo}
                  getValueFn={this.getValueFnProxy}
                  value={this.values}
                  autoFocus
                  onChange={this.handleValueChange}
                  onSelectorBlur={this.handleValueSelectorBlur}
                  onSelectorFocus={this.handleSelectorFocus}
                />
              </div>
              {this.isIntegerError ? <div class='error-msg'>{this.$tc('仅支持输入数值类型')}</div> : undefined}
            </div>,
          ]
        : undefined;
    };
    return (
      <div
        ref='el'
        class='vue3_retrieval-filter__ui-selector-options-component'
      >
        <div class='component-top'>
          <div class='component-top-left'>
            <div class='search-wrap'>
              <Input
                ref='searchInput'
                v-model={this.searchValue}
                behavior='simplicity'
                placeholder={this.$t('请输入关键字')}
                onChange={this.handleSearchChangeDebounce}
              >
                {{
                  prefix: () => <span class='icon-monitor icon-mc-search' />,
                }}
              </Input>
            </div>
            <div class='options-wrap'>
              {this.searchLocalFields.map((item, index) => {
                const { title, subtitle } = getTitleAndSubtitle(item.alias);
                return (
                  <div
                    key={item.name}
                    class={[
                      'option',
                      { checked: this.checkedItem?.name === item.name },
                      { cursor: index === this.cursorIndex },
                    ]}
                    onClick={() => {
                      this.handleCheck(item, '', [], false, true);
                    }}
                  >
                    <span
                      style={{
                        background: fieldTypeMap[item.type].bgColor,
                        color: fieldTypeMap[item.type].color,
                      }}
                      class='option-icon'
                    >
                      <span class={[fieldTypeMap[item.type].icon, 'option-icon-icon']} />
                    </span>
                    <span class='option-name-title'>{title}</span>
                    {!!subtitle && <span class='option-name-subtitle'>（{subtitle}）</span>}
                  </div>
                );
              })}
            </div>
          </div>
          <div class='component-top-right'>{rightRender()}</div>
        </div>
        <div class='component-bottom'>
          <span class='desc-item'>
            <span class='desc-item-icon mr-2'>
              <span class='icon-monitor icon-mc-arrow-down up' />
            </span>
            <span class='desc-item-icon'>
              <span class='icon-monitor icon-mc-arrow-down' />
            </span>
            <span class='desc-item-name'>{this.$t('移动光标')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>Enter</span>
            <span class='desc-item-name'>{this.$t('选中')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>Esc</span>
            <span class='desc-item-name'>{this.$t('收起查询')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>{`${this.isMacSystem ? 'Cmd' : 'Ctrl'}+Enter`}</span>
            <span class='desc-item-name'>{this.$t('提交查询')}</span>
          </span>
          <div class='operate-btns'>
            <Button
              class='mr-8'
              disabled={this.isIntegerError}
              theme='primary'
              onClick={() => this.handleConfirm()}
            >
              {`${this.$t('确定')} ${this.isMacSystem ? 'Cmd' : 'Ctrl'} + Enter`}
            </Button>
            <Button onClick={() => this.handleCancel()}>{`${this.$t('取消')}`}</Button>
          </div>
        </div>
      </div>
    );
  },
});
