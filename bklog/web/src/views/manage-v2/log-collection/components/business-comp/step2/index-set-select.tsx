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

import { defineComponent, onMounted, ref, type PropType } from 'vue';

import useLocale from '@/hooks/use-locale';

import { useOperation } from '../../../hook/useOperation';
import AddIndexSet from './add-index-set';

import type { IListItemData } from '../../../type';

import './index-set-select.scss';

export default defineComponent({
  name: 'IndexSetSelect',
  props: {
    list: {
      type: Array as PropType<IListItemData[]>,
      default: () => [],
    },
    value: {
      type: Array as PropType<number[]>,
      default: () => [],
    },
  },

  emits: ['select'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const { indexGroupLoading, getIndexGroupList } = useOperation();
    const isAdd = ref(false);
    const addIndexSetRef = ref();
    const selectArr = ref<number[]>([]);
    const list = ref<IListItemData[]>([]);
    /**
     * 新增
     */
    const handleAdd = () => {
      isAdd.value = true;
      setTimeout(() => {
        addIndexSetRef.value?.autoFocus?.();
      });
    };

    const getData = () => {
      getIndexGroupList((data: { list: IListItemData[] }) => {
        list.value = data.list;
      });
    };
    const handleCancel = () => {
      isAdd.value = false;
    };
    const handleSubmit = () => {
      handleCancel();
      getData();
    };
    const handleSelect = (val: number[]) => {
      selectArr.value = val;
      emit('select', selectArr.value);
    };
    onMounted(() => {
      getData();
    });
    return () => (
      <bk-select
        class='index-set-select-box'
        loading={indexGroupLoading.value}
        value={props.value}
        display-tag
        multiple
        searchable
        onChange={val => handleSelect(val)}
      >
        {(list.value || []).map((option: IListItemData) => (
          <bk-option
            id={option.index_set_id}
            key={option.index_set_id}
            name={option.index_set_name}
          />
        ))}
        <div
          class='index-set-select-extension'
          slot='extension'
          on-Click={handleAdd}
        >
          {isAdd.value ? (
            <AddIndexSet
              ref={addIndexSetRef}
              isAdd={true}
              isFrom={false}
              on-cancel={handleCancel}
              on-submit={handleSubmit}
            />
          ) : (
            <span>
              <i class='bk-icon icon-plus-circle' />
              {t('新增索引集')}
            </span>
          )}
        </div>
      </bk-select>
    );
  },
});
