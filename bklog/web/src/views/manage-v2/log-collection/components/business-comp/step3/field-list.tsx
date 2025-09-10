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

import useLocale from '@/hooks/use-locale';

import './field-list.scss';
/**
 * @file 字段列表
 */
export default defineComponent({
  name: 'FieldList',
  props: {
    data: {
      type: Array,
      default: () => [],
    },
  },
  emits: [''],

  setup(props) {
    const { t } = useLocale();
    console.log(props.data);
    return () => (
      <div class='field-list-main-box'>
        <div class='tab-box'>
          <div class='tab-list'>
            <span class='tab-item is-selected'>{t('可见字段 (8)')}</span>
            <span class='tab-item'>{t('被隐藏字段 (0)')}</span>
          </div>
          <span class='checkbox-box'>
            <bk-checkbox class='mr-5' />
            {t('显示内置字段')}
          </span>
        </div>
        <div class='fields-table'>111</div>
        <div class='example-box'>
          <span class='form-link'>
            <i class='bk-icon icon-plus link-icon add-btn' />
            {t('新增字段')}
          </span>
        </div>
      </div>
    );
  },
});
