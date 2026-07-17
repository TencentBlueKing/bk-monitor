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

import { defineComponent } from 'vue';

import { Button, Input } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './host-list-toolbar.scss';

export default defineComponent({
  name: 'HostListToolbar',
  props: {
    /** 关键字搜索值 */
    keyword: {
      type: String,
      default: '',
    },
    /** 是否已勾选主机（决定复制 IP 是否可用） */
    hasSelection: {
      type: Boolean,
      default: false,
    },
    /** 高级过滤是否展开（控制漏斗按钮高亮） */
    filterExpanded: {
      type: Boolean,
      default: false,
    },
  },
  emits: {
    keywordChange: (_v: string) => true,
    search: () => true,
    copyIp: () => true,
    compare: () => true,
    toggleFilter: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    return () => (
      <div class='host-list-toolbar'>
        <div class='host-list-toolbar__buttons'>
          {/* 指标对比：本期占位，勾选主机后激活的能力后续接入 */}
          {/* <Button
            v-bk-tooltips={{ content: t('功能开发中'), delay: 300 }}
            disabled
          >
            {t('指标对比')}
          </Button> */}
          <Button
            disabled={!props.hasSelection}
            onClick={() => emit('copyIp')}
          >
            {t('复制IP')}
          </Button>
        </div>
        <div class='host-list-toolbar__search'>
          <Input
            class='host-list-toolbar__keyword'
            modelValue={props.keyword}
            placeholder={t('输入关键字，模糊搜索')}
            type='search'
            clearable
            onClear={() => emit('keywordChange', '')}
            onEnter={() => emit('search')}
            onInput={(v: string) => emit('keywordChange', v)}
          />
          <Button
            class={['host-list-toolbar__filter-btn', { 'is-active': props.filterExpanded }]}
            v-bk-tooltips={{ content: t('高级筛选'), delay: 300 }}
            onClick={() => emit('toggleFilter')}
          >
            <i class='icon-monitor icon-filter' />
          </Button>
        </div>
      </div>
    );
  },
});
