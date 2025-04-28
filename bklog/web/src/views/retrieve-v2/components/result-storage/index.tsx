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
import useStore from '@/hooks/use-store';
import useLocale from '@/hooks/use-locale';

import './index.scss';

export default defineComponent({
  setup() {
    const store = useStore();
    const { $t } = useLocale();

    const isWrap = computed(() => store.state.storage.tableLineIsWrap);
    const jsonFormatDeep = computed(() => store.state.storage.tableJsonFormatDepth);
    const isJsonFormat = computed(() => store.state.storage.tableJsonFormat);
    const isAllowEmptyField = computed(() => store.state.storage.tableAllowEmptyField);
    const showRowIndex = computed(() => store.state.storage.tableShowRowIndex);
    const expandTextView = computed(() => store.state.storage.isLimitExpandView);

    const handleStorageChange = (val, key) => {
      store.commit('updateStorage', { [key]: val });
    };

    const handleJsonFormatDeepChange = val => {
      const value = Number(val);
      const target = value > 15 ? 15 : value < 1 ? 1 : value;
      store.commit('updateStorage', { tableJsonFormatDepth: target });
    };

    return () => (
      <div class='bklog-v3-storage'>
        <bk-checkbox
          style='margin: 0 12px'
          class='bklog-option-item'
          value={showRowIndex.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'tableShowRowIndex')}
        >
          <span class='switch-label'>{$t('显示行号')}</span>
        </bk-checkbox>
        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={expandTextView.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'isLimitExpandView')}
        >
          <span class='switch-label'>{$t('展开长字段')}</span>
        </bk-checkbox>
        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={isWrap.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'tableLineIsWrap')}
        >
          <span class='switch-label'>{$t('换行')}</span>
        </bk-checkbox>

        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={isJsonFormat.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'tableJsonFormat')}
        >
          <span class='switch-label'>{$t('JSON 解析')}</span>
        </bk-checkbox>

        {isJsonFormat.value && (
          <bk-input
            style='margin: 0 12px 0 0'
            class='json-depth-num'
            max={15}
            min={1}
            value={jsonFormatDeep.value}
            type='number'
            on-change={handleJsonFormatDeepChange}
          ></bk-input>
        )}

        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          value={isAllowEmptyField.value}
          theme='primary'
          on-change={val => handleStorageChange(val, 'tableAllowEmptyField')}
        >
          <span class='switch-label'>{$t('展示空字段')}</span>
        </bk-checkbox>
      </div>
    );
  },
});
