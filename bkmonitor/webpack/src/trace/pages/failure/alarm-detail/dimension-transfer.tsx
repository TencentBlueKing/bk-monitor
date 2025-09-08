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
import { computed, defineComponent, reactive, ref, watch } from 'vue';

import { Button, Input } from 'bkui-vue';
import { debounce } from 'throttle-debounce';
import { useI18n } from 'vue-i18n';

import type { IDimensionItem } from '../types';

import './dimension-transfer.scss';

export default defineComponent({
  name: 'ResidentSettingTransfer',
  props: {
    fields: {
      type: Array as () => IDimensionItem[],
      default: () => [],
    },
    value: {
      type: Array as () => string[],
      default: () => [],
    },
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['cancel', 'confirm'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const state = reactive({
      localFields: [] as IDimensionItem[], // 待选列表集合
      searchValue: '', // 待选列表搜索内容
      searchSelectedValue: '', // 已选列表搜索内容
      selectedFields: [] as IDimensionItem[], // 已选列表集合
    });

    // 待选列表搜索后的数据
    const searchLocalFields = computed(() => filterFields(state.searchValue, state.localFields));

    // 已选列表搜索后的数据
    const searchSelectedFields = computed(() => filterFields(state.searchSelectedValue, state.selectedFields));

    // 通用搜索方法
    const filterFields = (searchValue: string, fields: IDimensionItem[]) => {
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

    // 处理待选列表
    const handleSetLocalFields = () => {
      const localFields = [];
      const selectedFields = new Set(state.selectedFields.map(item => item.key));
      for (const item of props.fields) {
        if (!selectedFields.has(item.key)) {
          localFields.push(item);
        }
      }
      state.localFields = localFields;
    };

    // 单独添加到已选列表
    const handleAdd = (index: number) => {
      const item = JSON.parse(JSON.stringify(searchLocalFields.value[index]));
      state.selectedFields.push(item);
      handleSetLocalFields();
    };

    // 单独删除已选列表
    const handleDelete = (targetItem: IDimensionItem) => {
      state.selectedFields = state.selectedFields.filter(item => item.key !== targetItem.key);
      handleSetLocalFields();
    };

    // 已选列表全部清除
    const handleClearAll = () => {
      state.selectedFields = [];
      state.localFields = [...props.fields];
    };

    // 待选列表全部添加
    const handleAddAll = () => {
      state.localFields = [];
      state.selectedFields = [...props.fields];
    };

    // 同步搜索框内容
    const handleSearchValueChange = debounce(300, (value: string, field: string) => {
      if (field === 'local') {
        state.searchValue = value;
      } else {
        state.searchSelectedValue = value;
      }
    });

    // 穿梭框确认事件
    const handleConfirm = () => {
      emit('confirm', state.selectedFields);
    };

    // 穿梭框取消事件
    const handleCancel = () => {
      emit('cancel');
    };

    // 监听 show 变化
    watch(
      () => props.show,
      show => {
        if (show) {
          state.searchValue = '';
          state.searchSelectedValue = '';
          const tempSet = new Set(props.value);
          const selectedFields = [];
          const localFields = [];
          const selectedFieldsMap = new Map();
          for (const item of props.fields) {
            if (tempSet.has(item.key)) {
              selectedFields.push(item);
              selectedFieldsMap.set(item.key, item);
            } else {
              localFields.push(item);
            }
          }
          const selected = [];
          for (const v of props.value) {
            const item = selectedFieldsMap.get(v);
            if (item) {
              selected.push(item);
            }
          }
          state.localFields = localFields;
          state.selectedFields = selected;
        }
      },
      { immediate: true }
    );

    // 监听 fields 变化
    watch(
      () => props.fields,
      () => {
        handleSetLocalFields();
      },
      { immediate: true }
    );

    return () => {
      const optionRender = (item: IDimensionItem) => (
        <span
          class='option-name-title'
          v-overflow-tips={{
            content: `${item.display_key || item.key}(${item.display_value || item.value})`,
            placement: 'top',
          }}
        >
          {`${item.display_key || item.key}(${item.display_value || item.value})`}
        </span>
      );

      return (
        <div class='transfer-component__dimension'>
          <div class='component-top'>
            <div class='component-top-left'>
              <div class='top-header'>
                <span class='header-title'>
                  {t('待选列表')}（{state.localFields.length}）
                </span>
                <span
                  class='header-btn'
                  onClick={handleAddAll}
                >
                  {t('全部添加')}
                </span>
              </div>
              <div class='content-wrap'>
                <div class='search-wrap'>
                  <Input
                    v-model={state.searchValue}
                    v-slots={{
                      prefix: () => (
                        <span class='search-icon'>
                          <span class='icon-monitor icon-mc-search' />
                        </span>
                      ),
                    }}
                    behavior='simplicity'
                    placeholder={t('请输入关键字')}
                    onChange={v => handleSearchValueChange(v, 'local')}
                  />
                </div>
                <div class='options-wrap'>
                  {searchLocalFields.value.map((item, index) => (
                    <div
                      key={item.key}
                      class='option'
                      onClick={() => handleAdd(index)}
                    >
                      {optionRender(item)}
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
                <span class='header-title'>
                  {t('已选列表')}（{state.selectedFields.length}）
                </span>
                <span
                  class='header-btn'
                  onClick={handleClearAll}
                >
                  {t('全部移除')}
                </span>
              </div>
              <div class='content-wrap'>
                <div class='search-wrap'>
                  <Input
                    v-model={state.searchSelectedValue}
                    v-slots={{
                      prefix: () => (
                        <span class='search-icon'>
                          <span class='icon-monitor icon-mc-search' />
                        </span>
                      ),
                    }}
                    behavior='simplicity'
                    placeholder={t('请输入关键字')}
                    onChange={v => handleSearchValueChange(v, 'selected')}
                  />
                </div>
                <div class='options-wrap'>
                  {searchSelectedFields.value.map(item => (
                    <div
                      key={item.key}
                      class='option'
                      onClick={() => handleDelete(item)}
                    >
                      {optionRender(item)}
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
                onClick={handleConfirm}
              >
                {t('确定')}
              </Button>
              <Button onClick={handleCancel}>{t('取消')}</Button>
            </div>
          </div>
        </div>
      );
    };
  },
});
