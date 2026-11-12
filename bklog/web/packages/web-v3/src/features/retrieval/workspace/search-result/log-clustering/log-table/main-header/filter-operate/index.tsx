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

import { Button as TButton, Checkbox as TCheckbox, Input as TInput, Popup as TPopup } from 'tdesign-vue-next';
import { computed, defineComponent, ref, type PropType } from 'vue';
import useLocale from '@/shared/composables/use-locale';
import './index.scss';

type FilterValue = string | number;
export default defineComponent({
  name: 'FilterOperate',
  emits: ['confirm'],
  props: {
    list: {
      type: Array as PropType<{ id: FilterValue; name: string }[]>,
      default: () => [],
    },
    searchable: { type: Boolean, default: true },
    multiple: { type: Boolean, default: true },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const visible = ref(false);
    const keyword = ref('');
    const localValue = ref<FilterValue[]>([]);
    const filteredOptions = computed(() => {
      const search = keyword.value.trim().toLowerCase();
      return props.list.filter((option) => option.name.toLowerCase().includes(search));
    });
    const close = () => {
      visible.value = false;
      keyword.value = '';
    };
    const handleConfirm = () => {
      emit('confirm', [...localValue.value]);
      close();
    };
    const handleReset = () => {
      localValue.value = [];
      emit('confirm', []);
      close();
    };
    const toggle = (id: FilterValue) => {
      if (localValue.value.includes(id)) localValue.value = localValue.value.filter((value) => value !== id);
      else localValue.value = props.multiple ? [...localValue.value, id] : [id];
    };
    expose({
      reset: () => {
        localValue.value = [];
      },
    });
    return () => (
      <TPopup
        visible={visible.value}
        trigger='click'
        placement='bottom-left'
        overlayClassName='cluster-header-filter-popup'
        overlayInnerStyle={{ padding: 0, minWidth: '150px' }}
        onVisibleChange={(value) => {
          visible.value = value;
          if (!value) keyword.value = '';
        }}
        v-slots={{
          content: () => (
            <div
              class='cluster-header-filter-content'
              onKeydown={(event: KeyboardEvent) => {
                if (event.key === 'Escape') {
                  event.stopPropagation();
                  close();
                }
              }}
            >
              {props.searchable && (
                <TInput
                  value={keyword.value}
                  class='cluster-header-filter-search'
                  placeholder={t('输入关键字搜索')}
                  v-slots={{ prefixIcon: () => <log-icon common type='search' /> }}
                  clearable
                  onChange={(value) => {
                    keyword.value = String(value ?? '');
                  }}
                />
              )}
              <div class='cluster-header-filter-options'>
                {filteredOptions.value.map((option) => (
                  <TCheckbox
                    key={option.id}
                    checked={localValue.value.includes(option.id)}
                    onChange={() => toggle(option.id)}
                  >
                    <span class='option-name' title={option.name}>
                      {option.name}
                    </span>
                  </TCheckbox>
                ))}
                {!filteredOptions.value.length && <div class='cluster-header-filter-empty'>{t('暂无数据')}</div>}
              </div>
              <div class='operate-btns'>
                <TButton size='small' theme='primary' variant='text' onClick={handleConfirm}>
                  {t('确定')}
                </TButton>
                <TButton size='small' theme='primary' variant='text' onClick={handleReset}>
                  {t('重置')}
                </TButton>
              </div>
            </div>
          ),
        }}
      >
        <button
          type='button'
          class='cluster-header-filter-trigger'
          aria-label={t('筛选')}
          aria-expanded={visible.value}
          onKeydown={(event: KeyboardEvent) => {
            if (event.key === 'Escape') close();
          }}
        >
          <log-icon
            common
            type='funnel'
            class={{
              'funnel-icon': true,
              'is-funnel-active': localValue.value.length > 0,
            }}
          />
        </button>
      </TPopup>
    );
  },
});
