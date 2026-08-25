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

import { computed, defineComponent, ref, watch } from 'vue';

import http from '@/api';
import {
  CleanTemplateSnapshot,
  CleanTemplateStatus,
  resolveCleanTemplateDraft,
} from '@/views/manage-v2/utils/clean-template';
import useLocale from '@/hooks/use-locale';

import { CLEAN_TYPE_MAP, getCleanTypeIcon } from './clean-type';
import type { CleanType } from './clean-type';

import './clean-template-picker.scss';

export interface CleanTemplateField {
  field_name: string;
  field_type: string;
  value?: unknown;
  is_delete: boolean;
  is_built_in: boolean;
  is_analyzed: boolean;
  is_case_sensitive: boolean;
  tokenize_on_chars?: string;
  [key: string]: unknown;
}

export interface CleanTemplate {
  clean_template_id: number;
  name: string;
  clean_type: CleanType;
  etl_params: Record<string, unknown>;
  etl_fields: CleanTemplateField[];
  description?: string;
  bk_biz_id?: number;
  visible_type?: string;
  visible_bk_biz_id?: number[];
  is_deleted?: boolean;
  snapshot?: CleanTemplateSnapshot<CleanType, Record<string, unknown>, CleanTemplateField> | null;
  status: CleanTemplateStatus;
  [key: string]: unknown;
}

const PAGE_SIZE = 10;

export default defineComponent({
  name: 'CleanTemplatePicker',
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    bkBizId: {
      type: [Number, String],
      default: '',
    },
    showCleanTypeTabs: {
      type: Boolean,
      default: false,
    },
    selectFirstOnLoad: {
      type: Boolean,
      default: false,
    },
    useDraftConfig: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['select'],
  setup(props, { emit }) {
    const { t } = useLocale();

    const loading = ref(false);
    const templateList = ref<CleanTemplate[]>([]);
    const searchText = ref('');
    const appliedSearchText = ref('');
    const filterCleanType = ref<'all' | CleanType>('all');
    const selectedTemplateId = ref<number | null>(null);
    const currentPage = ref(1);
    const hasMore = ref(true);
    const scrollContainerRef = ref<HTMLElement | null>(null);

    const cleanTypeTabs = computed(() => [
      { label: t('全部日志类型'), value: 'all' as const, icon: '' },
      {
        label: t(CLEAN_TYPE_MAP.bk_log_json.label),
        value: 'bk_log_json' as const,
        icon: CLEAN_TYPE_MAP.bk_log_json.icon,
      },
      {
        label: t(CLEAN_TYPE_MAP.bk_log_delimiter.label),
        value: 'bk_log_delimiter' as const,
        icon: CLEAN_TYPE_MAP.bk_log_delimiter.icon,
      },
      {
        label: t(CLEAN_TYPE_MAP.bk_log_regexp.label),
        value: 'bk_log_regexp' as const,
        icon: CLEAN_TYPE_MAP.bk_log_regexp.icon,
      },
    ]);

    const activeTabIndex = computed(() => {
      const index = cleanTypeTabs.value.findIndex(tab => tab.value === filterCleanType.value);
      return index < 0 ? 0 : index;
    });

    const updateSelection = (template: CleanTemplate | null) => {
      selectedTemplateId.value = template?.clean_template_id ?? null;
      emit('select', template);
    };

    const fetchTemplateList = async (isLoadMore = false) => {
      loading.value = true;
      const query: Record<string, unknown> = {
        bk_biz_id: props.bkBizId,
        page: currentPage.value,
        pagesize: PAGE_SIZE,
      };
      if (appliedSearchText.value) {
        query.keyword = appliedSearchText.value;
      }
      if (props.showCleanTypeTabs && filterCleanType.value !== 'all') {
        query.clean_type = filterCleanType.value;
      }

      try {
        const res = await http.request('clean/cleanTemplate', { query });
        const sourceList: CleanTemplate[] = Array.isArray(res.data) ? res.data : (res.data?.list ?? []);
        const list = props.useDraftConfig ? sourceList.map(resolveCleanTemplateDraft) : sourceList;
        if (isLoadMore) {
          templateList.value = [...templateList.value, ...list];
        } else {
          templateList.value = list;
          updateSelection(props.selectFirstOnLoad ? (list[0] ?? null) : null);
        }
        const total = Array.isArray(res.data) ? list.length : (res.data?.total ?? 0);
        hasMore.value = templateList.value.length < total;
      } catch {
        if (!isLoadMore) {
          templateList.value = [];
          updateSelection(null);
        }
        hasMore.value = false;
      } finally {
        loading.value = false;
      }
    };

    const resetAndFetch = () => {
      currentPage.value = 1;
      hasMore.value = true;
      scrollContainerRef.value?.scrollTo({ top: 0, behavior: 'auto' });
      fetchTemplateList(false);
    };

    const handleSearch = () => {
      appliedSearchText.value = searchText.value.trim();
      resetAndFetch();
    };

    const handleScroll = (event: Event) => {
      const element = event.target as HTMLElement;
      if (element.scrollTop + element.clientHeight + 50 >= element.scrollHeight) {
        if (!loading.value && hasMore.value) {
          currentPage.value += 1;
          fetchTemplateList(true);
        }
      }
    };

    const handleTabChange = (value: 'all' | CleanType) => {
      if (filterCleanType.value === value) {
        return;
      }
      filterCleanType.value = value;
      updateSelection(null);
      resetAndFetch();
    };

    watch(
      () => props.visible,
      (visible) => {
        if (!visible) {
          return;
        }
        searchText.value = '';
        appliedSearchText.value = '';
        filterCleanType.value = 'all';
        currentPage.value = 1;
        hasMore.value = true;
        updateSelection(null);
        scrollContainerRef.value?.scrollTo({ top: 0, behavior: 'auto' });
        fetchTemplateList(false);
      },
      { immediate: true },
    );

    return () => (
      <div
        class='clean-template-picker'
        v-bkloading={{ isLoading: loading.value && currentPage.value === 1, size: 'mini' }}
      >
        {props.showCleanTypeTabs && (
          <div class='clean-type-tabs'>
            <div
              class='tab-slider'
              style={{ transform: `translateX(${activeTabIndex.value * 100}%)` }}
            />
            {cleanTypeTabs.value.map(tab => (
              <div
                key={tab.value}
                class={['tab-item', { active: filterCleanType.value === tab.value }]}
                onClick={() => handleTabChange(tab.value)}
              >
                {tab.icon && <i class={tab.icon} />}
                {tab.label}
              </div>
            ))}
          </div>
        )}

        <bk-input
          class='search-input'
          value={searchText.value}
          on-input={(value: string) => (searchText.value = value)}
          on-enter={handleSearch}
          on-right-icon-click={handleSearch}
          on-clear={handleSearch}
          placeholder={t('搜索 模板名称')}
          clearable={true}
          right-icon='bk-icon icon-search'
        />

        <div
          ref={scrollContainerRef}
          class='template-list'
          onScroll={handleScroll}
        >
          {templateList.value.length === 0 && !loading.value && (
            <bk-exception
              class='empty-exception'
              scene='part'
              type='empty'
            >
              <span>{t('暂无数据')}</span>
            </bk-exception>
          )}
          {templateList.value.map(item => (
            <div
              key={item.clean_template_id}
              class={{
                'template-item': true,
                'is-selected': selectedTemplateId.value === item.clean_template_id,
              }}
              onClick={() => updateSelection(item)}
            >
              <div class='template-item-icon-box'>
                <i class={getCleanTypeIcon(item.clean_type)} />
              </div>
              <div class='template-item-content'>
                <div class='template-item-header'>
                  <div
                    class='template-item-name'
                    title={item.name}
                  >
                    {item.name}
                  </div>
                  <span class='template-item-count'>
                    <i class='bklog-icon bklog-feature-tezheng' />
                    {(item.etl_fields ?? []).filter(field => !field.is_delete).length}
                  </span>
                </div>
                {item.description && (
                  <div
                    class='template-item-desc'
                    title={item.description}
                  >
                    {item.description}
                  </div>
                )}
              </div>
            </div>
          ))}
          {loading.value && currentPage.value > 1 && (
            <div class='template-list-loading'>{'loading...'}</div>
          )}
        </div>
      </div>
    );
  },
});
