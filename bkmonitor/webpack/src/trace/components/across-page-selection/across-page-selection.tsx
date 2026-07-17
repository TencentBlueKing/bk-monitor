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

import { type PropType, defineComponent, computed, ref } from 'vue';

import { Checkbox, Dropdown } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './across-page-selection.scss';

export const SelectType = {
  UN_SELECTED: 0,
  SELECTED: 1,
  HALF_SELECTED: 2,
  ALL_SELECTED: 3,
} as const;

export type SelectTypeEnum = (typeof SelectType)[keyof typeof SelectType];

export default defineComponent({
  name: 'AcrossPageSelection',
  props: {
    value: {
      type: Number as PropType<SelectTypeEnum>,
      default: SelectType.UN_SELECTED,
    },
  },
  emits: {
    change: (_value: SelectTypeEnum) => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    const isAcrossPageSelected = ref(false);
    const currentSelectType = ref<SelectTypeEnum>(SelectType.UN_SELECTED);

    const isSelected = computed(() => props.value === SelectType.ALL_SELECTED || props.value === SelectType.SELECTED);

    const selectList: { id: SelectTypeEnum; name: string }[] = [
      { id: SelectType.SELECTED, name: t('本页全选') },
      { id: SelectType.ALL_SELECTED, name: t('跨页全选') },
    ];

    const handleSelect = (id: SelectTypeEnum) => {
      currentSelectType.value = id;
      emit('change', id);
      isAcrossPageSelected.value = id === SelectType.ALL_SELECTED;
    };

    const handleChangeValue = (value: boolean | number | string) => {
      if (!value) {
        currentSelectType.value = SelectType.UN_SELECTED;
      }
      emit('change', value ? SelectType.SELECTED : SelectType.UN_SELECTED);
    };

    const handleClearAcrossPageSelect = () => {
      emit('change', SelectType.UN_SELECTED);
      isAcrossPageSelected.value = false;
    };

    return () => (
      <Dropdown
        popoverOptions={{
          placement: 'bottom-start',
          clickContentAutoHide: true,
          extCls: 'across-page-selection-popover',
          offset: { crossAxis: 22, mainAxis: 22 },
        }}
      >
        {{
          default: () => (
            <div class='across-page-selection-component'>
              {isAcrossPageSelected.value ? (
                <div
                  class='across-page-across-selection-main'
                  onClick={handleClearAcrossPageSelect}
                />
              ) : (
                <Checkbox
                  class={{ 'all-checked': props.value === SelectType.ALL_SELECTED }}
                  indeterminate={props.value === SelectType.HALF_SELECTED}
                  modelValue={isSelected.value}
                  onChange={handleChangeValue}
                />
              )}
              <i class='icon-monitor icon-arrow-down selection-trigger' />
            </div>
          ),
          content: () => (
            <Dropdown.DropdownMenu>
              {selectList.map(item => (
                <Dropdown.DropdownItem
                  key={item.id}
                  extCls={currentSelectType.value === item.id ? 'list-item-active' : ''}
                  onClick={() => handleSelect(item.id)}
                >
                  {item.name}
                </Dropdown.DropdownItem>
              ))}
            </Dropdown.DropdownMenu>
          ),
        }}
      </Dropdown>
    );
  },
});
