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

import { computed, defineComponent, nextTick, onUnmounted, shallowRef, useTemplateRef, watch } from 'vue';

import { promiseTimeout, useDebounceFn, useEventListener } from '@vueuse/core';
import { Button, Checkbox, Input, Radio, Select } from 'bkui-vue';
import { random } from 'monitor-common/utils';
import { detectOperatingSystem } from 'monitor-common/utils/navigator';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../empty-status/empty-status';
import TimeConsuming from './time-consuming';
import {
  type IFilterField,
  type IFilterItem,
  type IValue,
  type TGetValueFn,
  ECondition,
  EFieldType,
  EMethod,
  UI_SELECTOR_OPTIONS_EMITS,
  UI_SELECTOR_OPTIONS_PROPS,
} from './typing';
import {
  DEFAULT_GROUP_RELATION,
  DURATION_KEYS,
  EXISTS_KEYS,
  fieldTypeMap,
  GROUP_RELATION_KEY,
  isNumeric,
  NOT_VALUE_METHODS,
  WILDCARD_KEY,
} from './utils';
import ValueTagSelector from './value-tag-selector';

import './ui-selector-options.scss';

export default defineComponent({
  name: 'UiSelectorOptions',
  props: UI_SELECTOR_OPTIONS_PROPS,
  emits: UI_SELECTOR_OPTIONS_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();
    const elRef = useTemplateRef<HTMLDivElement>('el');
    // const searchInputRef = useTemplateRef<InstanceType<typeof Input>>('searchInput');
    const valueSelectorRef = useTemplateRef<HTMLDivElement>('valueSelector');
    const allInputRef = useTemplateRef<HTMLDivElement>('allInput');
    const searchValue = shallowRef('');
    const searchLocalFields = shallowRef<IFilterField[]>([]);
    const cursorIndex = shallowRef(0);
    const checkedItem = shallowRef<IFilterField>(null);
    const queryString = shallowRef('');
    const method = shallowRef('');
    const values = shallowRef([]);
    const rightRefreshKey = shallowRef(random(8));
    const rightFocus = shallowRef(false);
    const cacheCheckedName = shallowRef('');
    const isMacSystem = shallowRef(false);

    const wildcardItem = computed(() =>
      checkedItem.value?.supported_operations
        ?.find(item => item.value === method.value)
        ?.options?.find(item => item.name === WILDCARD_KEY)
    );
    const groupRelationItem = computed(() =>
      checkedItem.value?.supported_operations
        ?.find(item => item.value === method.value)
        ?.options?.find(item => item.name === GROUP_RELATION_KEY)
    );
    const isWildcard = shallowRef(wildcardItem.value?.default || false);
    const groupRelation = shallowRef(groupRelationItem.value?.default || DEFAULT_GROUP_RELATION);
    /* 耗时字段数据 */
    const timeConsumingValue = shallowRef({
      key: '',
      method: '',
      value: [],
    });
    /* 是否为数字类型 */
    const isTypeInteger = computed(() => checkedItem.value?.type === EFieldType.integer);
    /* 是否输入了非数字 */
    const isIntegerError = computed(() => (isTypeInteger.value ? values.value.some(v => !isNumeric(v.id)) : false));
    const valueSelectorFieldInfo = computed(() => {
      return {
        field: checkedItem.value?.name,
        alias: checkedItem.value?.alias,
        isEnableOptions: !!checkedItem.value?.isEnableOptions,
        methods:
          checkedItem.value?.supported_operations?.map(item => ({
            id: item.value,
            name: item.alias,
            placeholder: item?.placeholder || '',
            wildcardOperator: item?.wildcard_operator || '',
          })) || [],
        type: checkedItem.value?.type,
      };
    });
    const placeholderStr = computed(() => {
      return checkedItem.value?.supported_operations?.find(item => item.value === method.value)?.placeholder || '';
    });
    /* 是否选择了耗时 */
    const isDurationKey = computed(() => {
      return DURATION_KEYS.includes(checkedItem.value?.name);
    });
    /* 是否选择了无需检索值的操作符 */
    const notValueOfMethod = computed(() => {
      return NOT_VALUE_METHODS.includes(method.value);
    });

    const enterSelectionDebounce = useDebounceFn((isFocus = false) => {
      enterSelection(isFocus);
    }, 500);
    const handleSearchChangeDebounce = useDebounceFn(() => {
      handleSearchChange();
    }, 300);

    let cleanup = () => {};

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
          init();
          if (props.value) {
            const id = props.value.key.id;
            let index = -1;
            for (const item of props.fields) {
              index += 1;
              if (item.name === id) {
                const checkedItem = structuredClone(item);
                handleCheck(
                  checkedItem,
                  props.value.method.id,
                  props.value.value,
                  {
                    isWildcard: !!props.value?.options?.is_wildcard,
                    groupRelation: props.value?.options?.group_relation,
                  },
                  true
                );
                setTimeout(() => {
                  updateSelection(index);
                }, 300);

                break;
              }
            }
          } else {
            // handleCheck(props.fields[0]);
            // 需要等待popover 动画执行完毕 300ms
            // setTimeout(() => {
            //   searchInputRef.value?.focus();
            // }, 300);
          }
        } else {
          cleanup?.();
        }
      },
      { immediate: true }
    );

    onUnmounted(() => {
      cleanup?.();
    });

    function init() {
      isMacSystem.value = detectOperatingSystem() === 'macOS';
      cleanup = useEventListener(window, 'keydown', handleKeydownEvent);
    }

    function initData() {
      searchValue.value = '';
      cursorIndex.value = 0;
      checkedItem.value = null;
      queryString.value = '';
      method.value = '';
      values.value = [];
      isWildcard.value = false;
      groupRelation.value = DEFAULT_GROUP_RELATION;
      rightFocus.value = false;
      cacheCheckedName.value = '';
      timeConsumingValue.value = {
        key: '',
        method: 'between',
        value: [],
      };
      handleSearchChange();
    }

    function handleCheck(
      item: IFilterField,
      methodP = '',
      value = [],
      options = {
        isWildcard: false,
        groupRelation: '',
      },
      isFocus = false
    ) {
      checkedItem.value = structuredClone(item);
      values.value = value || [];
      /* 耗时字段特殊处理 */
      if (isDurationKey.value) {
        // method.value = 'between';
        timeConsumingValue.value = {
          key: item.name,
          method: methodP || 'between',
          value: (value || []).map(item => item.id),
        };
      } else {
        method.value = methodP || item?.supported_operations?.[0]?.value || '';
      }
      isWildcard.value = options?.isWildcard || false;
      groupRelation.value = options?.groupRelation || DEFAULT_GROUP_RELATION;
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
      cursorIndex.value = index;
    }

    async function handleConfirm() {
      if (isDurationKey.value) {
        await promiseTimeout(300);
      } else {
        await promiseTimeout(50);
      }
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
      if (
        EXISTS_KEYS.includes(method.value) ||
        values.value.length ||
        (isDurationKey.value && timeConsumingValue.value.value.length)
      ) {
        const methodName = checkedItem.value.supported_operations.find(item => item.value === method.value)?.alias;
        const opt = {};
        if (isWildcard.value) {
          opt[WILDCARD_KEY] = true;
        }
        if (groupRelation.value) {
          opt[GROUP_RELATION_KEY] = groupRelation.value;
        }
        const value: IFilterItem = {
          key: { id: checkedItem.value.name, name: checkedItem.value.alias },
          method: { id: method.value as any, name: methodName || '=' },
          value: values.value,
          condition: { id: ECondition.and, name: 'AND' },
          options: opt,
        };
        /* 耗时字段特殊处理 */
        if (isDurationKey.value) {
          if (timeConsumingValue.value.value.length) {
            value.method = { id: timeConsumingValue.value.method as EMethod, name: timeConsumingValue.value.method };
            value.value = timeConsumingValue.value.value.map(item => ({ id: item, name: item }));
            emit('confirm', value);
          }
          return;
        }
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
    function handleTimeConsumingValueChange(v) {
      timeConsumingValue.value = v;
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
          updateSelection(cursorIndex.value);
          // enterSelectionDebounce();
          break;
        }

        case 'ArrowDown': {
          event.preventDefault();
          cursorIndex.value += 1;
          if (cursorIndex.value > searchLocalFields.value.length) {
            cursorIndex.value = 0;
          }
          updateSelection(cursorIndex.value);
          // enterSelectionDebounce();
          break;
        }
        case 'Enter': {
          event.preventDefault();
          enterSelectionDebounce(true);
          break;
        }
      }
    }
    function isElementVisible(element: HTMLElement, container: HTMLElement) {
      const elementRect = element?.getBoundingClientRect();
      const containerRect = container?.getBoundingClientRect();
      if (elementRect && containerRect) {
        return elementRect.top >= containerRect.top && elementRect.bottom <= containerRect.bottom;
      }
      return true;
    }
    function updateSelection(index: number) {
      nextTick(() => {
        const listEl = elRef.value?.querySelector('.component-top-left .options-wrap');
        const el = listEl?.children?.[index];
        if (el) {
          if (!isElementVisible(el as HTMLElement, listEl as HTMLElement)) {
            el.scrollIntoView(false);
          }
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
          handleCheck(item, '', [], defaultOptions(), isFocus);
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
    /**
     * 获取通配符操作符
     * @param {boolean} isSearch - 是否为搜索模式
     * @returns {string} 返回通配符操作符
     * @description 根据搜索模式获取对应的通配符操作符:
     * - 非搜索模式: 返回 method.value 或默认值 'equal'
     * - 搜索模式: 从 valueSelectorFieldInfo 中匹配对应方法的 wildcardOperator,
     *   如未找到则返回第一个方法的 wildcardOperator 或默认值 'equal'
     */
    function getWildcardOperator(isSearch = false) {
      let operator = '';
      if (!isSearch) {
        operator = method.value || 'equal';
        return operator;
      }
      for (const m of valueSelectorFieldInfo.value.methods) {
        if (method.value === m.id) {
          operator = m?.wildcardOperator;
          break;
        }
      }
      if (!operator) {
        operator = valueSelectorFieldInfo.value.methods?.[0]?.wildcardOperator || 'equal';
      }
      return operator;
    }
    /**
     * 代理获取值的函数，用于处理搜索查询和数据过滤
     * @param {Object} params - 查询参数对象
     * @param {string} params.search - 搜索关键词
     * @param {number} params.limit - 限制返回结果数量
     * @param {string} params.field - 查询字段名
     * @returns {Promise<any>} 返回一个Promise，解析为查询结果数据
     *                         如果查询失败，返回空结果 {count: 0, list: []}
     */
    function getValueFnProxy(params: { field: string; limit: number; search: string }): any | TGetValueFn {
      return new Promise((resolve, _reject) => {
        props
          .getValueFn({
            where: params.search
              ? [
                  {
                    key: params.field,
                    method: getWildcardOperator(!!params.search),
                    value: [params.search],
                    condition: ECondition.and,
                    options: {
                      is_wildcard: true,
                    },
                  },
                ]
              : [],
            fields: [params.field],
            limit: params.limit,
            isInit__: params?.isInit__ || false,
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

    function defaultOptions() {
      return structuredClone({
        isWildcard: wildcardItem.value?.default || false,
        groupRelation: groupRelationItem.value?.default || DEFAULT_GROUP_RELATION,
      }) as any;
    }

    function handleClearSearch() {
      searchValue.value = '';
      handleSearchChange();
    }

    function handleMethodChange(value) {
      if (NOT_VALUE_METHODS.includes(value)) {
        values.value = [];
        groupRelation.value = groupRelationItem.value?.default || DEFAULT_GROUP_RELATION;
        isWildcard.value = wildcardItem.value?.default || false;
      }
    }

    return {
      checkedItem,
      queryString,
      method,
      wildcardItem,
      groupRelationItem,
      isWildcard,
      groupRelation,
      rightRefreshKey,
      valueSelectorFieldInfo,
      values,
      searchValue,
      isIntegerError,
      searchLocalFields,
      cursorIndex,
      isMacSystem,
      placeholderStr,
      timeConsumingValue,
      notValueOfMethod,
      isDurationKey,
      getValueFnProxy,
      handleValueChange,
      handleTimeConsumingValueChange,
      handleValueSelectorBlur,
      handleSelectorFocus,
      handleSearchChangeDebounce,
      handleCheck,
      handleConfirm,
      handleCancel,
      defaultOptions,
      handleClearSearch,
      handleMethodChange,
      t,
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
            <div class='form-item-label mt-16'>{this.t('检索内容')}</div>
            <div class='form-item-content mt-8'>
              <Input
                ref={'allInput'}
                v-model={this.queryString}
                placeholder={this.t('请输入')}
                rows={15}
                type={'textarea'}
              />
            </div>
          </div>,
        ];
      }
      return this.checkedItem
        ? [
            !this.isDurationKey && (
              <div
                key={'method'}
                class='form-item mt-34'
              >
                <div class='form-item-label'>{this.t('条件')}</div>
                <div class='form-item-content mt-6'>
                  <Select
                    ext-cls={'method-select'}
                    v-model={this.method}
                    popoverOptions={{
                      boundary: 'parent',
                    }}
                    clearable={false}
                    onChange={this.handleMethodChange}
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
              </div>
            ),
            !this.notValueOfMethod && (
              <>
                <div
                  key={'value'}
                  class={['form-item', this.isDurationKey ? 'mt-34' : 'mt-16']}
                >
                  <div class='form-item-label'>
                    <span class='left'>{this.t('检索值')}</span>
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
                    {this.isDurationKey ? (
                      <TimeConsuming
                        key={this.rightRefreshKey}
                        fieldInfo={
                          {
                            field: this.checkedItem.name,
                          } as any
                        }
                        styleType={'form'}
                        value={this.timeConsumingValue}
                        onChange={this.handleTimeConsumingValueChange}
                      />
                    ) : (
                      <ValueTagSelector
                        key={this.rightRefreshKey}
                        ref='valueSelector'
                        fieldInfo={this.valueSelectorFieldInfo}
                        getValueFn={this.getValueFnProxy}
                        placeholder={''}
                        value={this.values}
                        autoFocus
                        onChange={this.handleValueChange}
                        onSelectorBlur={this.handleValueSelectorBlur}
                        onSelectorFocus={this.handleSelectorFocus}
                      />
                    )}
                  </div>
                  {this.isIntegerError ? <div class='error-msg'>{this.t('仅支持输入数值类型')}</div> : undefined}
                </div>
                {!!this.groupRelationItem && (
                  <div
                    key='group_relation'
                    class='form-item mt-16'
                  >
                    <div class='form-item-label'>{this.groupRelationItem?.label || '组件关系'}</div>
                    <div class='form-item-content mt-6'>
                      <Radio.Group v-model={this.groupRelation}>
                        {this.groupRelationItem?.children?.map(g => (
                          <Radio
                            key={g.value}
                            label={g.value}
                          />
                        ))}
                      </Radio.Group>
                    </div>
                  </div>
                )}
              </>
            ),
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
                clearable={true}
                placeholder={this.t('请输入关键字')}
                stopPropagation={false}
                onClear={this.handleSearchChangeDebounce}
                onInput={this.handleSearchChangeDebounce}
              >
                {{
                  prefix: () => <span class='icon-monitor icon-mc-search' />,
                }}
              </Input>
            </div>
            <div class='options-wrap'>
              {this.searchLocalFields.length ? (
                this.searchLocalFields.map((item, index) => {
                  // const { title, subtitle } = getTitleAndSubtitle(item.alias);
                  const title = item.alias;
                  const subtitleStr = item.name;
                  return (
                    <div
                      key={item.name}
                      class={[
                        'option',
                        { checked: this.checkedItem?.name === item.name },
                        { cursor: index === this.cursorIndex },
                      ]}
                      onClick={() => {
                        this.handleCheck(item, '', [], this.defaultOptions(), true);
                      }}
                    >
                      <span
                        style={{
                          background: fieldTypeMap[item.type]?.bgColor || fieldTypeMap.other.bgColor,
                          color: fieldTypeMap[item.type]?.color || fieldTypeMap.other.color,
                        }}
                        class='option-icon'
                      >
                        <span class={[fieldTypeMap[item.type]?.icon || fieldTypeMap.other.icon, 'option-icon-icon']} />
                      </span>
                      <span
                        class='option-name-title'
                        v-overflow-tips
                      >
                        {title}
                      </span>
                      {!!subtitleStr && (
                        <span
                          class='option-name-subtitle'
                          v-overflow-tips
                        >
                          （{subtitleStr}）
                        </span>
                      )}
                    </div>
                  );
                })
              ) : (
                <EmptyStatus
                  type={this.searchValue ? 'search-empty' : 'empty'}
                  onOperation={this.handleClearSearch}
                />
              )}
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
            <span class='desc-item-name'>{this.t('移动光标')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>Enter</span>
            <span class='desc-item-name'>{this.t('选中')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>Esc</span>
            <span class='desc-item-name'>{this.t('收起查询')}</span>
          </span>
          <span class='desc-item'>
            <span class='desc-item-box'>{`${this.isMacSystem ? 'Cmd' : 'Ctrl'}+Enter`}</span>
            <span class='desc-item-name'>{this.t('提交查询')}</span>
          </span>
          <div class='operate-btns'>
            <Button
              class='mr-8'
              disabled={this.isIntegerError}
              theme='primary'
              onClick={() => {
                this.handleConfirm();
              }}
            >
              {`${this.t('确定')} ${this.isMacSystem ? 'Cmd' : 'Ctrl'} + Enter`}
            </Button>
            <Button onClick={() => this.handleCancel()}>{`${this.t('取消')}`}</Button>
          </div>
        </div>
      </div>
    );
  },
});
