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

import { computed, defineComponent } from 'vue';

import { Button } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import './host-list-selection-tips.scss';

export default defineComponent({
  name: 'HostListSelectionTips',
  props: {
    /** 已选择数量 */
    selectedCount: {
      type: Number,
      default: 0,
    },
  },
  emits: {
    /** 清除所有选择 */
    clearAll: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 是否显示 tips 条 */
    const isVisible = computed(() => props.selectedCount > 0);

    return () => (
      <div
        class='host-list-selection-tips'
        v-show={isVisible.value}
      >
        <i18n-t
          class='tips-text'
          keypath='已选择{0}台主机'
          tag='span'
        >
          <span class='space-count'> {props.selectedCount} </span>
        </i18n-t>
        <Button
          class='tips-action'
          theme='primary'
          text
          onClick={() => emit('clearAll')}
        >
          {t('清除所有数据')}
        </Button>
      </div>
    );
  },
});
