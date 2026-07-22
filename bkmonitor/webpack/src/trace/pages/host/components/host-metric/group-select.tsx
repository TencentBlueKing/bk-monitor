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

import { type PropType, defineComponent, nextTick, shallowRef, useTemplateRef } from 'vue';

import { Input, Select } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import type { SelectOption } from '../../types/aggregation';

import './group-select.scss';
export default defineComponent({
  name: 'GroupSelect',
  props: {
    groupOptions: {
      type: Array as PropType<SelectOption[]>,
      default: () => [],
    },
    modelValue: {
      type: String,
      default: '',
    },
    disabled: {
      type: Boolean,
      default: false,
    },
    behavior: {
      type: String as PropType<'normal' | 'simplicity'>,
      default: 'normal',
    },
    clearable: {
      type: Boolean,
      default: true,
    },
  },
  emits: {
    change: (_v: string) => true,
    addGroup: (_name: string) => true,
    toggle: (_show: boolean) => true,
  },
  setup(props, { emit, slots, attrs }) {
    const { t } = useI18n();

    const showAddGroupInput = shallowRef(false);
    const batchMoveAddGroupName = shallowRef('');
    const batchMoveAddGroupInputRef = useTemplateRef<InstanceType<typeof Input>>('batchMoveAddGroupInput');

    const handleAddGroupInputChange = (show: boolean) => {
      showAddGroupInput.value = show;
      if (show) {
        nextTick(() => {
          batchMoveAddGroupInputRef.value?.focus();
        });
      } else {
        batchMoveAddGroupName.value = '';
      }
    };

    const handleAddGroup = () => {
      if (!batchMoveAddGroupName.value.trim()) return;
      emit('addGroup', batchMoveAddGroupName.value.trim());
      handleAddGroupInputChange(false);
    };

    return () => (
      <Select
        {...attrs}
        popoverOptions={{
          width: 240,
          extCls: 'add-group-select-popover host-page',
        }}
        behavior={props.behavior}
        clearable={props.clearable}
        disabled={props.disabled}
        modelValue={props.modelValue}
        onChange={(v: string) => emit('change', v)}
        onToggle={(show: boolean) => {
          if (!show) {
            handleAddGroupInputChange(false);
          }
          emit('toggle', show);
        }}
      >
        {{
          trigger: slots.trigger,
          default: () =>
            props.groupOptions.map(item => (
              <Select.Option
                id={item.id}
                key={item.id}
                name={item.name}
              />
            )),
          extension: () =>
            showAddGroupInput.value ? (
              <div class='add-new-group-input'>
                <Input
                  ref='batchMoveAddGroupInput'
                  class='add-group-input'
                  v-model={batchMoveAddGroupName.value}
                  size='small'
                  onEnter={handleAddGroup}
                />
                <i
                  class='icon-monitor icon-mc-check-small'
                  onClick={handleAddGroup}
                />
                <i
                  class='icon-monitor icon-mc-close-copy'
                  onClick={() => {
                    handleAddGroupInputChange(false);
                  }}
                />
              </div>
            ) : (
              <div
                class='add-new-group'
                onClick={() => {
                  handleAddGroupInputChange(true);
                }}
              >
                <i class='icon-monitor icon-jia' />
                <span>{t('新建分组')}</span>
              </div>
            ),
        }}
      </Select>
    );
  },
});
