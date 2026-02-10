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

import { computed, defineComponent } from 'vue';

import useLocale from '@/hooks/use-locale';

import { OPERATOR_SELECT_LIST } from '../../../utils';

import './add-group-table.scss';

export default defineComponent({
  name: 'AddGroupTable',
  props: {
    list: {
      type: Array,
      default: () => [[], []],
    },
    activeType: {
      type: String,
      default: 'match',
    },
  },

  emits: ['update'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const length = computed(() => props.list.length);
    /** 是否是字符串类型 */
    const isMatchType = computed(() => props.activeType === 'match');
    /**
     * 操作符列表
     */
    const operatorShowSelectList = computed(() => {
      const showSelect = structuredClone(OPERATOR_SELECT_LIST);
      for (const el of showSelect) {
        if (isMatchType.value && el.id === 'include') {
          el.id = '=';
        }
        if (!isMatchType.value && el.id === 'eq') {
          el.id = '=';
        }
      }
      return showSelect;
    });
    const handleAddGroup = () => {
      emit('update', [...props.list, []]);
    };
    const handleDelGroup = ind => {
      if (length.value === 1) {
        return;
      }
      const nextList = [...props.list];
      nextList.splice(ind, 1);
      emit('update', nextList);
    };

    const handleAdd = item => {
      console.log(item);
    };
    const handleDel = (item, index) => {
      console.log(item, index);
    };
    const renderTableItem = (item, index) => (
      <div class='table-box-item'>
        {!isMatchType.value && <bk-input class='item-default' />}
        <div class='item-default'>
          <bk-select class='item-select'>
            {(operatorShowSelectList.value || []).map(option => (
              <bk-option
                id={option.id}
                key={option.id}
                name={option.name}
              />
            ))}
          </bk-select>
        </div>
        <bk-input
          class='item-default'
          value={item.word}
        />
        <div class='item-tool btns-group'>
          <span
            class='bk-icon icon-plus-circle-shape icons'
            on-Click={() => handleAdd(item)}
          />
          <span
            class='bk-icon icon-minus-circle-shape icons'
            on-Click={() => handleDel(item, index)}
          />
        </div>
      </div>
    );
    const renderTableBox = (item, ind) => (
      <div class='table-box'>
        <div class='table-box-header'>
          {t('第{num}组', { num: ind + 1 })}
          <i
            class={{
              'bklog-icon bklog-log-delete del-icons': true,
              'is-disabled': length.value === 1,
            }}
            on-Click={() => handleDelGroup(ind)}
          />
        </div>
        <div class='table-box-main'>
          <div class='table-box-head'>
            {!isMatchType.value && <div class='item-default'>{t('过滤参数')}</div>}
            <div class='item-default'>{t('操作符')}</div>
            <div class='item-default'>Value</div>
            <div class='item-tool'>{t('操作')}</div>
          </div>
          <div>{renderTableItem(item, ind)}</div>
          <div>{renderTableItem(item, ind)}</div>
        </div>
      </div>
    );
    return () => (
      <div class='add-group-table-main'>
        {props.list.map((item, ind) => renderTableBox(item, ind))}
        <div
          class='add-btn'
          on-Click={handleAddGroup}
        >
          <i class='bk-icon icon-plus-line icons' />
          {t('新增过滤组')}
        </div>
      </div>
    );
  },
});
