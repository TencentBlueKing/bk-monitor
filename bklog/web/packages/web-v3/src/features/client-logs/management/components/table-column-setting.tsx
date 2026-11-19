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
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import { Button as TButton, Checkbox as TCheckbox, Popup } from 'tdesign-vue-next';

import { computed, defineComponent, ref, type PropType } from 'vue';

import type { SettingField } from '@/features/management/manage-v2/hooks/use-table-setting';
import { t } from '@/shared/composables/use-locale';
import { useOverlayZIndex } from '@/shared/global/overlay/use-overlay-z-index';

import './table-column-setting.scss';

/** 表格右上角字段显示设置，字段数据由 useTableSetting 提供并持久化。 */
export default defineComponent({
  name: 'ClientLogTableColumnSetting',
  props: {
    fields: {
      type: Array as PropType<SettingField[]>,
      default: () => [],
    },
    selected: {
      type: Array as PropType<SettingField[]>,
      default: () => [],
    },
  },
  emits: ['change'],
  setup(props, { emit }) {
    const visible = ref(false);
    const zIndex = useOverlayZIndex(visible, 'DROPDOWN');
    /** 面板内的临时勾选，确认后才回写并持久化 */
    const draft = ref<string[]>([]);

    const isAllChecked = computed(() => {
      const optionalFields = props.fields.filter(field => !field.disabled);
      return optionalFields.length > 0 && optionalFields.every(field => draft.value.includes(field.id));
    });

    const handleVisibleChange = (value: boolean) => {
      visible.value = value;
      if (value) {
        draft.value = props.selected.map(field => field.id);
      }
    };

    const handleToggleAll = (checked: boolean) => {
      draft.value = props.fields
        .filter(field => (field.disabled ? draft.value.includes(field.id) : checked))
        .map(field => field.id);
    };

    const handleFieldChange = (field: SettingField, checked: boolean) => {
      draft.value = checked
        ? [...new Set([...draft.value, field.id])]
        : draft.value.filter(id => id !== field.id);
    };

    const handleConfirm = () => {
      // 固定列（disabled）不允许取消，始终保留在显示字段中
      emit('change', {
        fields: props.fields.filter(field => field.disabled || draft.value.includes(field.id)),
      });
      visible.value = false;
    };

    return () => (
      <Popup
        visible={visible.value}
        trigger='click'
        placement='bottom-right'
        zIndex={zIndex.value}
        onVisibleChange={handleVisibleChange}
        content={() => (
          <div class='client-log-column-setting'>
            <div class='client-log-column-setting__title'>{t('字段显示设置')}</div>
            <TCheckbox
              checked={isAllChecked.value}
              onChange={handleToggleAll}
            >
              {t('全选')}
            </TCheckbox>
            <div class='client-log-column-setting__fields'>
              {props.fields.map(field => (
                <TCheckbox
                  key={field.id}
                  checked={draft.value.includes(field.id)}
                  disabled={field.disabled}
                  onChange={(checked: boolean) => handleFieldChange(field, checked)}
                >
                  {field.label}
                </TCheckbox>
              ))}
            </div>
            <div class='client-log-column-setting__actions'>
              <TButton
                theme='primary'
                size='small'
                onClick={handleConfirm}
              >
                {t('确定')}
              </TButton>
              <TButton
                variant='outline'
                size='small'
                onClick={() => (visible.value = false)}
              >
                {t('取消')}
              </TButton>
            </div>
          </div>
        )}
      >
        <button
          type='button'
          class='client-log-column-trigger'
          aria-label={t('字段显示设置')}
        >
          <i class='bk-icon icon-cog-shape' />
        </button>
      </Popup>
    );
  },
});
