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

import { defineComponent } from 'vue';

import { t } from '@/hooks/use-locale';

import './log-keyword-setting.scss';

export default defineComponent({
  name: 'LogKeywordSetting',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  setup(props) {
    // 任务名称插槽
    const taskNameSlot = {
      default: ({ row }) => (
        <bk-button
          text
          theme='primary'
          class='name-button'
        >
          {row.taskName}
        </bk-button>
      ),
    };

    // 创建人插槽
    const creatorSlot = {
      default: ({ row }) => <bk-user-display-name user-id={row.creator}></bk-user-display-name>,
    };

    // 跳转链接插槽
    const jumpLinkSlot = {
      default: () => (
        <bk-button
          text
          theme='primary'
        >
          {t('前往')}
        </bk-button>
      ),
    };

    return () => (
      <div class='log-keyword-setting'>
        <bk-button
          theme='primary'
          class='new-button'
          title={t('新建')}
        >
          {t('新建')}
        </bk-button>
        <bk-table data={props.data}>
          <bk-table-column
            label={t('任务名称')}
            prop='taskName'
            min-width='120'
            scopedSlots={taskNameSlot}
          />
          <bk-table-column
            label={t('正则表达式')}
            prop='regex'
            min-width='200'
          />
          <bk-table-column
            label={t('类型')}
            prop='type'
            width='120'
          />
          <bk-table-column
            label={t('创建人')}
            prop='creator'
            min-width='120'
            scopedSlots={creatorSlot}
          />
          <bk-table-column
            label={t('跳转链接')}
            prop='jumpLink'
            width='120'
            scopedSlots={jumpLinkSlot}
          />
          <bk-table-column
            label={t('操作')}
            width='150'
          >
            <bk-button
              text
              theme='primary'
              class='mr16'
            >
              {t('编辑')}
            </bk-button>
            <bk-button
              text
              theme='primary'
            >
              {t('删除')}
            </bk-button>
          </bk-table-column>
        </bk-table>
      </div>
    );
  },
});
