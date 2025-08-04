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
import useStore from '@/hooks/use-store';

import { BK_LOG_STORAGE } from '../../../../store/store.type';

import './index.scss';

export default defineComponent({
  setup() {
    const store = useStore();
    const { $t } = useLocale();

    const isWrap = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_LINE_IS_WRAP]);
    const jsonFormatDeep = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT_DEPTH]);
    const isJsonFormat = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_JSON_FORMAT]);
    const isAllowEmptyField = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_ALLOW_EMPTY_FIELD]);
    const showRowIndex = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX]);
    const expandTextView = computed(() => store.state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]);
    const currentSortField = computed(() => store.state.indexItem.sort_list?.[0] || []);
    const isSortShow = computed(() => {
      return requiredFields.includes(currentSortField.value[0]);
    });
    const ascShow = computed(() => {
      const isAsc = currentSortField.value[1] === 'asc';
      return isSortShow.value && isAsc;
    });
    const descShow = computed(() => {
      const isDesc = currentSortField.value[1] === 'desc';
      return isSortShow.value && isDesc;
    });
    const requiredFields = ['gseIndex', 'iterationIndex', 'dtEventTimeStamp'];
    const handleStorageChange = (val, key) => {
      store.commit('updateStorage', { [key]: val });
    };

    const handleJsonFormatDeepChange = val => {
      const value = Number(val);
      const target = value > 15 ? 15 : value < 1 ? 1 : value;
      store.commit('updateStorage', { [BK_LOG_STORAGE.TABLE_JSON_FORMAT_DEPTH]: target });
    };

    const handleShowLogTimeChange = (e, sort) => {
      const target = e.target;
      const sortMap = {
        ascending: 'asc',
        descending: 'desc',
      };
      let timeSort = sortMap[sort];
      if (target.classList.contains('active')) {
        target.classList.remove('active');
        timeSort = null;
      }
      const sortList = timeSort ? [['dtEventTimeStamp', timeSort]] : [];
      const updatedSortList = store.state.indexFieldInfo.sort_list.map(item => {
        if (sortList.length > 0 && item[0] === 'dtEventTimeStamp') {
          return sortList[0];
        } else if (sortList.length === 0 && item[0] === 'dtEventTimeStamp') {
          return ['dtEventTimeStamp', 'desc'];
        }
        return item;
      });
      const temporarySortList = timeSort ? requiredFields.map(item => [item, timeSort]) : [];
      store.commit('updateLocalSort', true);
      store.commit('updateIndexFieldInfo', { sort_list: updatedSortList });
      store.commit('updateIndexItemParams', { sort_list: temporarySortList });
      store.dispatch('requestIndexSetQuery');
    };

    return () => (
      <div class='bklog-v3-storage'>
        <bk-checkbox
          style='margin: 0 12px'
          class='bklog-option-item'
          theme='primary'
          value={showRowIndex.value}
          on-change={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX)}
        >
          <span class='switch-label'>{$t('显示行号')}</span>
        </bk-checkbox>

        <bk-checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          theme='primary'
          value={isWrap.value}
          on-change={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_LINE_IS_WRAP)}
        >
          <span class='switch-label'>{$t('换行')}</span>
        </bk-checkbox>

        <div class='switch-label log-sort'>
          <span class='bklog-option-item'>{$t('日志排序')}</span>
          <span class='bk-table-caret-wrapper'>
            <i
              class={['bk-table-sort-caret', 'ascending', { active: ascShow.value }]}
              v-bk-tooltips={{ content: `${$t('升序')}`, placement: 'right' }}
              on-click={event => handleShowLogTimeChange(event, 'ascending')}
            ></i>
            <i
              class={['bk-table-sort-caret', 'descending', { active: descShow.value }]}
              v-bk-tooltips={{ content: `${$t('降序')}`, placement: 'right' }}
              on-click={event => handleShowLogTimeChange(event, 'descending')}
            ></i>
          </span>
        </div>

        <bk-popover
          extCls='storage-more-popover'
          placement='bottom-start'
          theme='light'
          trigger='click'
        >
          <div class='bklog-option-more'>
            <span
              style='font-size:18px'
              class='bklog-icon bklog-more'
            ></span>
          </div>

          <div
            class='bklog-option-list'
            slot='content'
          >
            <bk-checkbox
              class='bklog-option-item'
              theme='primary'
              value={expandTextView.value}
              on-change={val => handleStorageChange(val, BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW)}
            >
              <span class='switch-label'>{$t('展开长字段')}</span>
            </bk-checkbox>
            <div class='bklog-option-json-format'>
              <bk-checkbox
                style='margin: 0 12px 0 0'
                class='bklog-option-item'
                theme='primary'
                value={isJsonFormat.value}
                on-change={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_JSON_FORMAT)}
              >
                <span class='switch-label'>{$t('JSON 解析')}</span>
              </bk-checkbox>

              {isJsonFormat.value && (
                <bk-input
                  style='margin: 0 12px 0 0'
                  class='json-depth-num json-depth-num-input'
                  max={15}
                  min={1}
                  type='number'
                  value={jsonFormatDeep.value}
                  on-change={handleJsonFormatDeepChange}
                ></bk-input>
              )}
            </div>
            <bk-checkbox
              class='bklog-option-item'
              theme='primary'
              value={isAllowEmptyField.value}
              on-change={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_ALLOW_EMPTY_FIELD)}
            >
              <span class='switch-label'>{$t('展示空字段')}</span>
            </bk-checkbox>
          </div>
        </bk-popover>
      </div>
    );
  },
});
