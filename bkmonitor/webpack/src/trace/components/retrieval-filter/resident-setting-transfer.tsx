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

import { computed, defineComponent, shallowRef, useTemplateRef, watch } from 'vue';

import { useDebounceFn } from '@vueuse/core';
import { Button, Input, Message } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import EmptyStatus from '../empty-status/empty-status';
import { type IFilterField, RESIDENT_SETTING_TRANSFER_EMITS, RESIDENT_SETTING_TRANSFER_PROPS } from './typing';
import { fieldTypeMap, triggerShallowRef } from './utils';

import './resident-setting-transfer.scss';

export default defineComponent({
  name: 'ResidentSettingTransfer',
  props: RESIDENT_SETTING_TRANSFER_PROPS,
  emits: RESIDENT_SETTING_TRANSFER_EMITS,
  setup(props, { emit }) {
    const { t } = useI18n();
    const searchRef = useTemplateRef<HTMLDivElement>('search');

    const localFields = shallowRef<IFilterField[]>([]);
    const searchValue = shallowRef('');
    const selectedFields = shallowRef<IFilterField[]>([]);
    const dragOverIndex = shallowRef(-1);

    const handleSearchValueChangeDebounce = useDebounceFn(val => {
      handleSearchValueChange(val);
    }, 300);

    const searchLocalFields = computed(() => {
      if (!searchValue.value) {
        return localFields.value;
      }
      return localFields.value.filter(item => {
        const $searchValue = searchValue.value.toLocaleLowerCase();
        if (item.name.toLocaleLowerCase().includes($searchValue)) {
          return true;
        }
        if (item.alias.toLocaleLowerCase().includes($searchValue)) {
          return true;
        }
        return false;
      });
    });

    watch(
      () => props.show,
      val => {
        if (val) {
          searchValue.value = '';
          dragOverIndex.value = -1;
          const tempSet = new Set(props.value);
          const $selectedFields = [];
          const $localFields = [];
          const selectedFieldsMap = new Map();
          for (const item of props.fields) {
            if (tempSet.has(item.name)) {
              $selectedFields.push(item);
              selectedFieldsMap.set(item.name, item);
            } else {
              $localFields.push(item);
            }
          }
          const selected = [];
          for (const v of props.value) {
            const item = selectedFieldsMap.get(v);
            if (item) {
              selected.push(item);
            }
          }
          localFields.value = $localFields;
          selectedFields.value = selected;
          searchRef.value?.focus();
        }
      },
      { immediate: true }
    );
    watch(
      () => props.fields,
      () => {
        handleSetLocalFields();
      },
      { immediate: true }
    );

    function handleCheck(index: number) {
      if (selectedFields.value.length >= 10) {
        Message({
          theme: 'error',
          message: t('添加失败， 最多仅支持添加10个常驻筛选项'),
        });
        return;
      }
      const name = searchLocalFields.value[index].name;
      const delIndex = localFields.value.findIndex(item => item.name === name);
      const item = structuredClone(localFields.value[delIndex]);
      localFields.value.splice(delIndex, 1);
      selectedFields.value.push(item);
      triggerShallowRef(localFields);
      triggerShallowRef(selectedFields);
    }
    function handleConfirm() {
      emit('confirm', selectedFields.value);
    }
    function handleCancel() {
      emit('cancel');
    }
    function handleSetLocalFields() {
      const $localFields = [];
      const $selectedFields = new Set(selectedFields.value.map(item => item.name));
      for (const item of props.fields) {
        if (!$selectedFields.has(item.name)) {
          $localFields.push(item);
        }
      }
      localFields.value = $localFields;
    }
    function handleDelete(event, index) {
      event.stopPropagation();
      selectedFields.value.splice(index, 1);
      handleSetLocalFields();
    }
    function handleDragStart(event, index) {
      event.dataTransfer.effectAllowed = 'move';
      // 设置自定义数据保存拖动项的索引
      event.dataTransfer.setData('drag-index', index);
    }
    function handleDragOver(event, _index) {
      // 阻止默认行为，允许 drop
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      dragOverIndex.value = _index;
    }
    function handleDrop(event, dropIndex) {
      event.preventDefault();
      dragOverIndex.value = -1;
      const dragIndex = event.dataTransfer.getData('drag-index');
      if (dragIndex === '') return;
      const fromIndex = Number.parseInt(dragIndex, 10);
      // 如果拖动位置和放置位置相同，则无需操作
      if (fromIndex === dropIndex) return;
      // 从数组中移除拖动项，并在目标位置插入
      const movedItem = selectedFields.value.splice(fromIndex, 1)[0];
      selectedFields.value.splice(dropIndex, 0, movedItem);
      triggerShallowRef(selectedFields);
    }
    function handleClear() {
      selectedFields.value = [];
      localFields.value = props.fields.slice();
    }
    function handleAllAdd() {
      localFields.value = [];
      selectedFields.value = props.fields.slice();
    }
    function handleSearchValueChange(value: string) {
      searchValue.value = value;
    }

    return {
      searchValue,
      localFields,
      searchLocalFields,
      selectedFields,
      dragOverIndex,
      handleConfirm,
      handleCancel,
      handleDragOver,
      handleDragStart,
      handleDelete,
      handleDrop,
      handleClear,
      handleCheck,
      handleAllAdd,
      handleSearchValueChangeDebounce,
      handleSearchValueChange,
      t,
    };
  },
  render() {
    const optionRender = (item: IFilterField) => {
      return [
        <span
          key={'01'}
          style={{
            background: (fieldTypeMap?.[item.type] || fieldTypeMap.other)?.bgColor,
            color: (fieldTypeMap?.[item.type] || fieldTypeMap.other)?.color,
          }}
          class='option-icon'
        >
          {item.name === '*' ? (
            <span class='option-icon-xing'>*</span>
          ) : (
            <span class={[(fieldTypeMap?.[item.type] || fieldTypeMap.other)?.icon, 'option-icon-icon']} />
          )}
        </span>,
        <span
          key={'02'}
          class='option-name-title'
          v-overflow-tips
        >
          {item.alias}
        </span>,
        !!item.name && (
          <span
            class='option-name-subtitle'
            v-overflow-tips
          >
            （{item.name}）
          </span>
        ),
      ];
    };
    return (
      <div class='vue3_retrieval-filter__resident-setting-transfer-component'>
        <div class='component-top'>
          <div class='component-top-left'>
            <div class='top-header'>
              <span class='header-title'>{`${this.t('待选列表')}（${this.localFields.length}）`}</span>
              {/* <span
                class='header-btn'
                onClick={this.handleAllAdd}
              >
                {this.t('全部添加')}
              </span> */}
            </div>
            <div class='content-wrap'>
              <div class='search-wrap'>
                <Input
                  ref='search'
                  behavior='simplicity'
                  clearable={true}
                  left-icon='bk-icon icon-search'
                  modelValue={this.searchValue}
                  placeholder={this.t('请输入关键字')}
                  onClear={() => this.handleSearchValueChange('')}
                  onInput={this.handleSearchValueChangeDebounce}
                />
              </div>
              <div class='options-wrap'>
                {this.searchLocalFields.length ? (
                  this.searchLocalFields.map((item, index) => (
                    <div
                      key={item.name}
                      class={'option check-type'}
                      onClick={() => this.handleCheck(index)}
                    >
                      {optionRender(item)}
                      <span class='icon-monitor icon-back-right' />
                    </div>
                  ))
                ) : (
                  <EmptyStatus
                    type={this.searchValue ? 'search-empty' : 'empty'}
                    onOperation={() => this.handleSearchValueChange('')}
                  />
                )}
              </div>
            </div>
          </div>
          <div class='component-top-right'>
            <div class='top-header'>
              <span class='header-title'>{`${this.t('常驻筛选')}（${this.selectedFields.length}）`}</span>
              <span
                class='header-btn'
                onClick={this.handleClear}
              >
                {this.t('清空')}
              </span>
            </div>
            <div class='content-wrap'>
              {this.selectedFields.map((item, index) => (
                <div
                  key={item.name}
                  class={{
                    option: true,
                    'drag-type': true,
                    'drag-over': this.dragOverIndex === index,
                  }}
                  draggable={true}
                  onDragover={event => this.handleDragOver(event, index)}
                  onDragstart={event => this.handleDragStart(event, index)}
                  onDrop={event => this.handleDrop(event, index)}
                >
                  <span class='icon-monitor icon-mc-tuozhuai' />
                  {optionRender(item)}
                  <span
                    class='icon-monitor icon-mc-close-fill'
                    onClick={event => this.handleDelete(event, index)}
                  />
                </div>
              ))}
            </div>
          </div>
        </div>
        <div class='component-bottom'>
          <div class='button-wrap'>
            <Button
              class='mr-8'
              theme='primary'
              onClick={() => this.handleConfirm()}
            >
              {this.t('确定')}
            </Button>
            <Button onClick={() => this.handleCancel()}>{this.t('取消')}</Button>
          </div>
        </div>
      </div>
    );
  },
});
