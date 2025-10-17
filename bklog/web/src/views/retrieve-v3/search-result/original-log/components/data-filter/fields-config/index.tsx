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

import { computed, defineComponent, ref, watch } from 'vue';

import { messageSuccess } from '@/common/bkmagic';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import VueDraggable from 'vuedraggable';

import './index.scss';

export default defineComponent({
  name: 'FieldsConfig',
  components: {
    VueDraggable,
  },
  setup(_, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const fieldConfigRef = ref();
    const displayFieldNames = ref<string[]>([]); // 展示的字段名
    const confirmLoading = ref(false);

    const pageVisibleFields = computed(() => store.state.visibleFields.map(item => item.field_name));
    const totalFiels = computed(() => store.state.indexFieldInfo.fields);
    const totalFieldNames = computed(() => totalFiels.value.map(item => item.field_name));
    const restFieldNames = computed(() =>
      totalFieldNames.value.filter(field => !displayFieldNames.value.includes(field)),
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
        const fields = config.contextDisplayFields;
        if (fields?.length > 0) {
          displayFieldNames.value = fields;
        } else {
          // 优先展示log字段
          if (totalFieldNames.value.includes('log')) {
            displayFieldNames.value = ['log'];
            return;
          }
          // 其次展示text类型字段
          const textTypeFields = totalFiels.value.filter(item => item.field_type === 'text');
          if (textTypeFields.length > 0) {
            displayFieldNames.value = textTypeFields.map(item => item.field_name);
            return;
          }
          // 最后用页面可见字段兜底
          displayFieldNames.value = pageVisibleFields.value;
        }
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
          emit('success', displayFieldNames.value);
        })
        .finally(() => {
          confirmLoading.value = false;
        });
    };

    const handleCancel = () => {
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
              <vue-draggable
                {...dragOptions}
                value={displayFieldNames.value}
              >
                <transition-group>
                  {displayFieldNames.value.map((field, index) => (
                    <li
                      key={index}
                      class='list-item display-item'
                    >
                      <span class='icon bklog-icon bklog-drag-dots'></span>
                      <div class='field_name'>{field}</div>
                      <div
                        class={['operate-button', disabledRemove.value && 'disabled']}
                        on-click={() => removeItem(index)}
                      >
                        {t('删除')}
                      </div>
                    </li>
                  ))}
                </transition-group>
              </vue-draggable>
            </div>
            <div class='field-list'>
              <div class='list-title'>{t('其他字段')}</div>
              <ul>
                {restFieldNames.value.map((field, index) => (
                  <li
                    key={index}
                    class='list-item rest-item'
                  >
                    <div class='field_name'>{field}</div>
                    <div
                      class='operate-button'
                      on-click={() => addItem(field)}
                    >
                      {t('添加')}
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          <div class='config-buttons'>
            <bk-button
              style='margin-right: 8px'
              loading={confirmLoading.value}
              size='small'
              theme='primary'
              on-click={handleConfirm}
            >
              {t('确定')}
            </bk-button>
            <bk-button
              style='margin-right: 24px'
              size='small'
              on-click={handleCancel}
            >
              {t('取消')}
            </bk-button>
          </div>
        </div>
      </div>
    );
  },
});
