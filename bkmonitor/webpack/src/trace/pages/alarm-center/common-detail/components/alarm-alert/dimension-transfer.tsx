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
import { type PropType, computed, ref as deepRef, defineComponent, shallowRef, watch } from 'vue';

import { Button, Input } from 'bkui-vue';
import { debounce } from 'lodash';

import type { IDimension } from '../../../typings';

import './dimension-transfer.scss';
export default defineComponent({
  name: 'DimensionTransfer',
  props: {
    fields: {
      type: Array as PropType<IDimension[]>,
      default: () => [],
    },
    value: {
      type: Array as PropType<string[]>,
      default: () => [],
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    cancel: () => true,
    confirm: (value: IDimension[]) => Array.isArray(value),
  },
  setup(props, { emit }) {
    const localFields = deepRef<IDimension[]>([]); // 待选列表集合
    /** 待选列表搜索内容 */
    const searchValue = shallowRef('');
    /** 已选列表搜索内容 */
    const searchSelectedValue = shallowRef('');
    /** 已选列表集合 */
    const selectedFields = deepRef<IDimension[]>([]);

    /** 待选列表搜索后的数据 */
    const searchLocalFields = computed(() => {
      return filterFields(searchValue.value, localFields.value);
    });

    /** 已选列表搜索后的数据 */
    const searchSelectedFields = computed(() => {
      return filterFields(searchSelectedValue.value, selectedFields.value);
    });

    watch(
      () => props.show,
      show => {
        if (show) {
          searchValue.value = '';
          searchSelectedValue.value = '';
          const tempSet = new Set(props.value);
          const _localFields = [];
          const selectedFieldsMap = new Map();
          for (const item of props.fields) {
            if (tempSet.has(item.key)) {
              selectedFieldsMap.set(item.key, item);
            } else {
              _localFields.push(item);
            }
          }
          const selected = [];
          for (const v of props.value) {
            const item = selectedFieldsMap.get(v);
            if (item) {
              selected.push(item);
            }
          }

          localFields.value = _localFields;
          selectedFields.value = selected;
        }
      },
      { immediate: true }
    );

    /** 处理待选列表 */
    const handleSetLocalFields = () => {
      const res = [];
      const selectedFieldsKey = new Set(selectedFields.value.map(item => item.key));
      for (const item of props.fields) {
        if (!selectedFieldsKey.has(item.key)) {
          res.push(item);
        }
      }
      localFields.value = res;
    };

    watch(
      () => props.fields,
      () => {
        handleSetLocalFields();
      },
      { immediate: true }
    );

    /** 通用搜索方法 */
    const filterFields = (searchValue: string, fields: IDimension[]) => {
      if (!searchValue) return fields;
      const normalizedSearchValue = String(searchValue).toLocaleLowerCase();
      return fields.filter(item => {
        const { display_key: displayKey, key, display_value: displayValue, value } = item;
        // displayValue、value可能有数值类型
        return (
          displayKey?.toLocaleLowerCase().includes(normalizedSearchValue) ||
          String(displayValue)?.toLocaleLowerCase().includes(normalizedSearchValue) ||
          key?.toLocaleLowerCase().includes(normalizedSearchValue) ||
          String(value)?.toLocaleLowerCase().includes(normalizedSearchValue)
        );
      });
    };

    /** 穿梭框确认事件 */
    const handleConfirm = () => {
      emit('confirm', [...selectedFields.value]);
    };

    /** 穿梭框取消事件 */
    const handleCancel = () => {
      emit('cancel');
    };

    /** 单独添加到已选列表 */
    const handleAdd = (index: number) => {
      const item = JSON.parse(JSON.stringify(searchLocalFields.value[index]));
      selectedFields.value.push(item);
      handleSetLocalFields();
    };

    /** 单独删除已选列表 */
    const handleDelete = (targetItem: IDimension) => {
      selectedFields.value = selectedFields.value.filter(item => item.key !== targetItem.key);
      handleSetLocalFields();
    };

    /** 已选列表全部清除 */
    const handleClearAll = () => {
      selectedFields.value = [];
      localFields.value = props.fields.slice();
    };

    /** 待选列表全部添加 */
    const handleAddAll = () => {
      localFields.value = [];
      selectedFields.value = props.fields.slice();
    };

    /** 同步搜索框内容 */
    const handleSearchValueChange = (value: string, field: string) => {
      console.log(value);
      if (field === 'local') {
        searchValue.value = value;
      } else {
        searchSelectedValue.value = value;
      }
    };

    const debounceHandleSearchValueChange = debounce(handleSearchValueChange, 300);

    const optionRender = (item: IDimension) => {
      return (
        <span
          class='option-name-title'
          v-bk-overflow-tips
        >
          {`${item.display_key || item.key}(${item.display_value || item.value})`}
        </span>
      );
    };

    return {
      localFields,
      searchLocalFields,
      searchValue,
      searchSelectedValue,
      selectedFields,
      searchSelectedFields,
      handleAddAll,
      handleAdd,
      handleClearAll,
      handleDelete,
      handleConfirm,
      handleCancel,
      debounceHandleSearchValueChange,
      optionRender,
    };
  },
  render() {
    return (
      <div class='transfer-component__dimension'>
        <div class='component-top'>
          <div class='component-top-left'>
            <div class='top-header'>
              <span class='header-title'>{`${this.$t('待选列表')}（${this.localFields.length}）`}</span>
              <span
                class='header-btn'
                onClick={this.handleAddAll}
              >
                {this.$t('全部添加')}
              </span>
            </div>
            <div class='content-wrap'>
              <div class='search-wrap'>
                <Input
                  behavior='simplicity'
                  left-icon='bk-icon icon-search'
                  modelValue={this.searchValue}
                  placeholder={this.$t('请输入关键字')}
                  onInput={v => this.debounceHandleSearchValueChange(v, 'local')}
                />
              </div>
              <div class='options-wrap'>
                {this.searchLocalFields.map((item, index) => (
                  <div
                    key={item.key}
                    class='option'
                    onClick={() => this.handleAdd(index)}
                  >
                    {this.optionRender(item)}
                    <span class='icon-monitor icon-back-right' />
                  </div>
                ))}
              </div>
            </div>
          </div>
          <div class='component-top-center'>
            <i class='icon-monitor icon-Transfer' />
          </div>
          <div class='component-top-right'>
            <div class='top-header'>
              <span class='header-title'>{`${this.$t('已选列表')}（${this.selectedFields.length}）`}</span>
              <span
                class='header-btn'
                onClick={this.handleClearAll}
              >
                {this.$t('全部移除')}
              </span>
            </div>
            <div class='content-wrap'>
              <div class='search-wrap'>
                <Input
                  behavior='simplicity'
                  left-icon='bk-icon icon-search'
                  modelValue={this.searchSelectedValue}
                  placeholder={this.$t('请输入关键字')}
                  onInput={v => this.debounceHandleSearchValueChange(v, 'selected')}
                />
              </div>
              <div class='options-wrap'>
                {this.searchSelectedFields.map(item => (
                  <div
                    key={item.key}
                    class='option'
                    onClick={() => this.handleDelete(item)}
                  >
                    {this.optionRender(item)}
                    <span class='icon-monitor icon-mc-close' />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
        <div class='component-bottom'>
          <div class='button-wrap'>
            <Button
              class='mr-8'
              theme='primary'
              onClick={this.handleConfirm}
            >
              {this.$t('确定')}
            </Button>
            <Button onClick={this.handleCancel}>{this.$t('取消')}</Button>
          </div>
        </div>
      </div>
    );
  },
});
