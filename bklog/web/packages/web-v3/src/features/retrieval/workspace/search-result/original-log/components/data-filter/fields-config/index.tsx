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

import { Button as TButton } from 'tdesign-vue-next';

import { computed, defineComponent, ref, watch } from 'vue';

import { messageSuccess } from '@/shared/lib/message';
import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import VueDraggable from 'vuedraggable-vue3';
import { preserveVue3ComponentModel } from '@/platform/compat/vue3-component-model';

import { getDefaultDisplayFields } from './default-display-fields';

import './index.scss';

// Isolate native options so this popup does not alter other draggable instances.
// Native Vue.Draggable reads function slots from $slots in its Options render.
// The installed declaration omits the update:modelValue event that 4.1 emits.
type FieldDragInstance = InstanceType<typeof VueDraggable> & {
  $props: InstanceType<typeof VueDraggable>['$props'] & {
    'onUpdate:modelValue'?: (fields: string[]) => void;
  };
};
const FieldDraggable = {...VueDraggable} as typeof VueDraggable &
  (new () => FieldDragInstance) & {compatConfig?: Record<string, unknown>};
preserveVue3ComponentModel(FieldDraggable);
FieldDraggable.compatConfig = {...FieldDraggable.compatConfig, RENDER_FUNCTION: false};

export default defineComponent({
  emits: ["success","cancel"],

  name: 'FieldsConfig',
  setup(_, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const fieldConfigRef = ref();
    const displayFieldNames = ref<string[]>([]); // 展示的字段名
    let cachedDisplayFieldNames: string[] = []; // 缓存的字段名，用于取消时恢复
    const confirmLoading = ref(false);

    const totalFiels = computed(() => store.getters.filteredFieldList);
    const restFieldNames = computed(() =>
      totalFiels.value.map((item: { field_name: any; }) => item.field_name).filter((field: string) => !displayFieldNames.value.includes(field)),
    );
    const disabledRemove = computed(() => displayFieldNames.value.length <= 1);

    const dragOptions = {
      animation: 150,
      tag: 'ul',
      handle: '.bklog-drag-dots',
      'ghost-class': 'sortable-ghost-class',
    };

    watch(
      () => store.state.retrieve.catchFieldCustomConfig,
      config => {
        displayFieldNames.value = getDefaultDisplayFields(store, config.contextDisplayFields);
        cachedDisplayFieldNames = [...displayFieldNames.value];

        setTimeout(() => {
          emit('success', displayFieldNames.value);
        });
      },
      {
        immediate: true,
        deep: true,
      },
    );

    /**
     * 移除某个显示字段
     */
    const removeItem = (index: number) => {
      !disabledRemove.value && displayFieldNames.value.splice(index, 1);
    };
    /**
     * 增加某个字段名
     */
    const addItem = (fieldName: string) => {
      displayFieldNames.value.push(fieldName);
    };

    const handleConfirm = () => {
      confirmLoading.value = true;
      store
        .dispatch('userFieldConfigChange', {
          contextDisplayFields: displayFieldNames.value,
        })
        .then(() => {
          messageSuccess(t('设置成功'));
          cachedDisplayFieldNames = [...displayFieldNames.value];
          emit('success', displayFieldNames.value);
        })
        .finally(() => {
          confirmLoading.value = false;
        });
    };

    const handleCancel = () => {
      displayFieldNames.value = [...cachedDisplayFieldNames];
      emit('cancel');
    };

    expose({
      getDom: () => fieldConfigRef.value,
    });

    return () => (
      <div style='display: none'>
        <div
          ref={fieldConfigRef}
          class='fields-config-tippy'
        >
          <div class='config-title'>{t('设置显示与排序')}</div>
          <div class='field-list-container'>
            <div class='field-list'>
              <div class='list-title'>
                <i18n path='显示字段（已选 {0} 条)'>
                  <span>{displayFieldNames.value.length}</span>
                </i18n>
              </div>
              <FieldDraggable
                {...dragOptions}
                tag='transition-group'
                componentData={{tag: 'ul'}}
                itemKey={(field: string) => field}
                modelValue={displayFieldNames.value}
                onUpdate:modelValue={(newValue: string[]) => {
                  displayFieldNames.value = newValue;
                }}
                v-slots={{
                  item: ({element: field, index}: {element: string; index: number}) => (
                    <li key={index} class='list-item display-item'>
                      <span class='icon bklog-icon bklog-drag-dots'></span>
                      <div class='field_name'>{field}</div>
                      <div
                        class={['operate-button', disabledRemove.value && 'disabled']}
                        onClick={() => removeItem(index)}
                      >
                        {t('删除')}
                      </div>
                    </li>
                  ),
                }}
              />
            </div>
            <div class='field-list'>
              <div class='list-title'>{t('其他字段')}</div>
              <ul>
                {restFieldNames.value.map((field: string, index: string|number|symbol|undefined) => (
                  <li
                    key={index}
                    class='list-item rest-item'
                  >
                    <div class='field_name'>{field}</div>
                    <div
                      class='operate-button'
                      onClick={() => addItem(field)}
                    >
                      {t('添加')}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div class='config-buttons'>
            <TButton
              style='margin-right: 8px'
              loading={confirmLoading.value}
              size='small'
              theme='primary'
              onClick={handleConfirm}
            >
              {t('确定')}
            </TButton>
            <TButton theme="default"
              style='margin-right: 24px'
              size='small'
              onClick={handleCancel}
            >
              {t('取消')}
            </TButton>
          </div>
        </div>
      </div>
    );
  },
});
