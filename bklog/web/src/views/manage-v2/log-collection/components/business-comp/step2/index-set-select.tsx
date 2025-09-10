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

import { defineComponent, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import AddIndexSet from './add-index-set';

import './index-set-select.scss';

export default defineComponent({
  name: 'IndexSetSelect',
  props: {
    list: {
      type: Array,
      default: () => [],
    },
    value: {
      type: Array,
      default: () => [],
    },
  },

  emits: ['select'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const isAdd = ref(false);
    const addIndexSetRef = ref();
    const selectArr = ref([]);
    const handleAdd = () => {
      isAdd.value = true;
      setTimeout(() => {
        addIndexSetRef.value?.autoFocus?.();
      });
    };
    const handleCancel = () => {
      isAdd.value = false;
    };
    const handleSubmit = () => {
      handleCancel();
      emit('select', selectArr.value);
    };
    const handleSelect = val => {
      selectArr.value = val;
    };
    return () => (
      <bk-select
        class='index-set-select-box'
        value={props.value}
        multiple
        searchable
        onChange={val => handleSelect(val)}
      >
        {(props.list || []).map(option => (
          <bk-option
            id={option.id}
            key={option.id}
            name={option.name}
          />
        ))}
        <div
          class='index-set-select-extension'
          slot='extension'
        >
          {isAdd.value ? (
            <AddIndexSet
              ref={addIndexSetRef}
              isFrom={false}
              on-cancel={handleCancel}
              on-submit={handleSubmit}
            />
          ) : (
            <span on-Click={handleAdd}>
              <i class='bk-icon icon-plus-circle' />
              {t('新增索引集')}
            </span>
          )}
        </div>
      </bk-select>
    );
  },
});
