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

import AddGroupTable from './add-group-table';

import './log-filter.scss';

export default defineComponent({
  name: 'LogFilter',
  props: {
    groupList: {
      type: Array,
      default: () => [],
    },
  },

  emits: ['update:groupList'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const typeKey = ref('separator');
    const groupList = ref([
      {
        fieldindex: '-1',
        word: '111',
        op: '=',
        logic_op: 'and',
      },
    ]);
    const typeList = [
      {
        name: t('字符串'),
        value: 'string',
      },
      {
        name: t('分隔符'),
        value: 'separator',
      },
    ];

    const handleChangeType = type => {
      typeKey.value = type.value;
    };

    const handleAddGroup = data => {
      groupList.value = data;
      emit('update:groupList', data);
    };

    const renderSeparator = () => (
      <div class='separator-box'>
        <div class='separator-box-top'>
          <bk-select class='separator-box-top-select' />
          <bk-button>{t('调试')}</bk-button>
        </div>
        <bk-input
          class='separator-box-bottom'
          placeholder={t('请输入日志样例')}
          type='textarea'
        />
      </div>
    );

    return () => (
      <div class='log-filter-main'>
        <div class='bk-button-group'>
          {typeList.map(type => (
            <bk-button
              key={type.value}
              class={{ 'is-selected': type.value === typeKey.value }}
              size='small'
              on-click={() => handleChangeType(type)}
            >
              {type.name}
            </bk-button>
          ))}
        </div>
        {typeKey.value === 'separator' && renderSeparator()}
        <AddGroupTable
          list={groupList.value || props.groupList}
          on-update={handleAddGroup}
        />
      </div>
    );
  },
});
