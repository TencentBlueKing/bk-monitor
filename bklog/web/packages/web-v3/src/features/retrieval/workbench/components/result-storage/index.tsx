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

import { includesValue } from '@/shared/utils/typed-record';

import { computed, defineComponent, ref, watch } from 'vue';

import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';
import { Popup, Checkbox, InputNumber, Button, MessagePlugin } from 'tdesign-vue-next';
import { toWorkerMessage } from '@/shared/lib/worker-message';
import 'tdesign-vue-next/es/style/index.css';
import { BK_LOG_STORAGE } from '../../../../../app/state/store.type.ts';

import BkLogPopover from '@/shared/ui/bklog-popover/index';
import RetrieveHelper, { RetrieveEvent } from '@/features/retrieval/retrieve-helper';
import TableSort from '../../result-comp/update/table-sort.vue';
import { isEqual } from 'lodash-es';
import './index.scss';

const IS_SORT_TIME_SHOW = !window.__IS_MONITOR_APM__ && !window.__IS_MONITOR_TRACE__;

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
    const isShowSourceField = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_SOURCE_FIELD]);
    const isShowCollectorField = computed(() => store.state.storage[BK_LOG_STORAGE.TABLE_SHOW_COLLECTOR_FIELD]);
    const isUnionSearch = computed(() => store.getters.isUnionSearch);
    const isSceneMode = computed(() => store.getters.isSceneMode);
    const isFormatDate = computed(() => store.state.isFormatDate);

    const sortStatus = ref<undefined | 'asc' | 'desc'>(undefined);

    // 切换检索模式时，重置排序状态
    watch(
      () => store.state.indexItem?.retrieve_type,
      () => {
        sortStatus.value = undefined;
        store.commit('updateState', { dateTimeSort: false, dateTimeSortList: [] });
      },
    );

    const userSortFields = computed(() => store.state.indexFieldInfo?.user_custom_config?.sortList ?? []);
    const defaultSortFields = computed(() =>
      (store.state.indexFieldInfo?.default_sort_list ?? []).map(([field, order]) => [field, order ?? 'desc']),
    );
    const localSortFields = computed(() => {
      return userSortFields.value.length ? userSortFields.value : defaultSortFields.value;
    });

    const showSortSetting = ref(false);
    const displaySortFields = ref([]);
    const tableSortRef = ref(null);
    const fieldsSettingPopperRef = ref(null);

    const tippyOptions: any = {
      arrow: false,
      hideOnClick: false,
      trigger: 'click',
      interactive: true,
      placement: 'bottom-start',
      theme: 'light',
      onShow: () => {
        let sortList = structuredClone(toWorkerMessage(localSortFields.value));
        if (sortStatus.value !== undefined) {
          sortList = sortList.map((item: unknown[]) => [item[0], sortStatus.value]);
        }
        displaySortFields.value = sortList;
        showSortSetting.value = true;
      },
      onHide: () => {
        showSortSetting.value = false;
      },
    };

    const handleConfirm = async () => {
      const updateSortList = tableSortRef.value?.shadowSort;
      if (!updateSortList?.length) {
        MessagePlugin.warning({ content: $t('至少需要配置一个排序字段') });
        return;
      }
      const oldSortList = userSortFields.value;
      const isSortListChanged = !isEqual(oldSortList, updateSortList);

      fieldsSettingPopperRef.value?.hide();

      store.commit('updateState', { localSort: false });

      await store.dispatch('userFieldConfigChange', {
        sortList: updateSortList,
      });

      if (isSortListChanged) {
        await store.dispatch('requestIndexSetFieldInfo');
        await store.dispatch('requestIndexSetQuery');
        RetrieveHelper.fire(RetrieveEvent.SORT_LIST_CHANGED);
      }
    };

    const handleCancel = () => {
      fieldsSettingPopperRef.value?.hide();
    };

    const handleBeforeHide = (e: { target: { closest: (arg0: string) => any; }; }) => {
      if (e.target?.closest?.('.bklog-v3-popover-tag')) {
        return false;
      }
      return true;
    };

    const handleStorageChange = (val: boolean, key: BK_LOG_STORAGE) => {
      store.commit('updateStorage', { [key]: val });
    };

    const handleJsonFormatDeepChange = (val: unknown) => {
      const value = Number(val);
      const target = value > 15 ? 15 : value < 1 ? 1 : value;
      store.commit('updateStorage', { [BK_LOG_STORAGE.TABLE_JSON_FORMAT_DEPTH]: target });
    };

    const handleFormatDate = (val: boolean) => {
      store.commit('updateState', { isFormatDate: val });
    };
    const handleShowLogTimeChange = async (target?: 'asc' | 'desc') => {
      if (target !== undefined) {
        // 点击箭头直接指定排序方向，再次点击已激活的箭头则取消排序
        sortStatus.value = sortStatus.value === target ? undefined : target;
      } else {
        // 点击文字区域，按 undefined → asc → desc → undefined 循环切换
        const sortOrderSequence: Array<undefined | 'asc' | 'desc'> = [undefined, 'asc', 'desc'];
        const currentIndex = sortOrderSequence.indexOf(sortStatus.value);
        const nextIndex = (currentIndex + 1) % sortOrderSequence.length;
        sortStatus.value = sortOrderSequence[nextIndex];
      }

      let sortList = localSortFields.value;
      if (sortStatus.value !== undefined) {
        sortList = localSortFields.value.map((item: unknown[]) => [item[0], sortStatus.value]);
      }
      displaySortFields.value = sortList;
      store.commit('updateState', {
        dateTimeSort: includesValue(['asc', 'desc'], sortStatus.value),
        dateTimeSortList: sortList,
      });
      await store.dispatch('requestIndexSetFieldInfo');
      await store.dispatch('requestIndexSetQuery', { defaultSortList: sortList });
      RetrieveHelper.fire(RetrieveEvent.SORT_LIST_CHANGED, sortList);
    };

    return () => (
      <div class='bklog-v3-storage'>
        {IS_SORT_TIME_SHOW && (
          <div class='switch-label log-sort'>
            <div
              class='sort-time'
              onClick={() => handleShowLogTimeChange()}
              v-log-tooltip={{
                content:
                  sortStatus.value === 'desc'
                    ? $t('当前降序(点击切换)')
                    : sortStatus.value === 'asc'
                      ? $t('当前升序(点击切换)')
                      : $t('点击切换排序'),
                placement: 'top',
              }}
            >
              <span class='bklog-option-item'>{$t('日志排序')}</span>
              <span class='bk-table-caret-wrapper'>
                <i
                  class={['bk-table-sort-caret', 'ascending', { active: sortStatus.value === 'asc' }]}
                  onClick={event => {
                    event.stopPropagation();
                    handleShowLogTimeChange('asc');
                  }}
                />
                <i
                  class={['bk-table-sort-caret', 'descending', { active: sortStatus.value === 'desc' }]}
                  onClick={event => {
                    event.stopPropagation();
                    handleShowLogTimeChange('desc');
                  }}
                />
              </span>
            </div>
            <span class='sort-separator' />
            <BkLogPopover
              ref={fieldsSettingPopperRef}
              options={tippyOptions}
              trigger='click'
              beforeHide={handleBeforeHide}
              contentClass='bklog-sort-setting-popover-content'
              content={() => (
                <div class='sort-setting-content'>
                  <div class='sort-setting-title'>{$t('排序字段设置')}</div>
                  <TableSort
                    ref={tableSortRef}
                    class='sort-setting-list'
                    initData={displaySortFields.value}
                    shouldRefresh={showSortSetting.value}
                  />
                  <div class='sort-setting-actions'>
                    <Button
                      theme='primary'
                      size='small'
                      class='mr8'
                      onClick={handleConfirm}
                    >
                      {$t('确定')}
                    </Button>
                    <Button
                      size='small'
                      onClick={handleCancel}
                    >
                      {$t('取消')}
                    </Button>
                  </div>
                </div>
              )}
            >
              <div
                class='sort-setting'
                v-log-tooltip={{ content: `${$t('设置排序字段')}`, placement: 'top' }}
              >
                <span class='icon bklog-icon bklog-shezhi sort-setting-icon' />
              </div>
            </BkLogPopover>
          </div>
        )}
        <Checkbox
          style='margin: 0 12px 0 12px'
          class='bklog-option-item'
          theme='primary'
          checked={showRowIndex.value}
          onChange={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_SHOW_ROW_INDEX)}
        >
          <span class='switch-label'>{$t('显示行号')}</span>
        </Checkbox>

        <Checkbox
          style='margin: 0 12px 0 0'
          class='bklog-option-item'
          theme='primary'
          checked={isWrap.value}
          onChange={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_LINE_IS_WRAP)}
        >
          <span class='switch-label'>{$t('换行')}</span>
        </Checkbox>

        {isUnionSearch.value && !isSceneMode.value && (
          <Checkbox
            style='margin: 0 12px 0 0'
            class='bklog-option-item'
            theme='primary'
            checked={isShowSourceField.value}
            onChange={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_SHOW_SOURCE_FIELD)}
          >
            <span class='switch-label'>{$t('日志来源')}</span>
          </Checkbox>
        )}

        <Popup
          overlayClassName='storage-more-popover'
          placement='bottom-left'
          trigger='click'
          v-slots={{
            content: () => (
              <div class='bklog-option-list'>
                <Checkbox
                  class='bklog-option-item'
                  theme='primary'
                  checked={expandTextView.value}
                  onChange={val => handleStorageChange(val, BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW)}
                >
                  <span class='switch-label'>{$t('展开长字段')}</span>
                </Checkbox>
                <div class='bklog-option-json-format'>
                  <Checkbox
                    style='margin: 0 12px 0 0'
                    class='bklog-option-item'
                    theme='primary'
                    checked={isJsonFormat.value}
                    onChange={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_JSON_FORMAT)}
                  >
                    <span class='switch-label'>{$t('JSON 解析')}</span>
                  </Checkbox>

                  {isJsonFormat.value && (
                    <InputNumber
                      style='margin: 0 12px 0 0'
                      class='json-depth-num json-depth-num-input'
                      max={15}
                      min={1}
                      value={jsonFormatDeep.value}
                      onChange={handleJsonFormatDeepChange}
                    />
                  )}
                </div>
                <Checkbox
                  class='bklog-option-item'
                  theme='primary'
                  checked={isAllowEmptyField.value}
                  onChange={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_ALLOW_EMPTY_FIELD)}
                >
                  <span class='switch-label'>{$t('展示空字段')}</span>
                </Checkbox>
                <Checkbox
                  style='margin: 0 12px 0 0'
                  class='bklog-option-item'
                  theme='primary'
                  checked={isFormatDate.value}
                  onChange={val => handleFormatDate(val)}
                >
                  <span class='switch-label'>{$t('时间格式化')}</span>
                </Checkbox>
                {isSceneMode.value && (
                  <Checkbox
                    style='margin: 8px 12px 0 0'
                    class='bklog-option-item'
                    theme='primary'
                    checked={isShowCollectorField.value}
                    onChange={val => handleStorageChange(val, BK_LOG_STORAGE.TABLE_SHOW_COLLECTOR_FIELD)}
                  >
                    <span class='switch-label'>{$t('来源采集项')}</span>
                  </Checkbox>
                )}
              </div>
            ),
          }}
        >
          <div class='bklog-option-more'>
            <span
              style='font-size:18px'
              class='bklog-icon bklog-more'
            />
          </div>
        </Popup>
      </div>
    );
  },
});
