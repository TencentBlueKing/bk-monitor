/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
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
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

import { defineComponent, ref, computed, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import $http from '@/api';
import { CLEAN_TYPE_MAP, getCleanTypeLabel, getCleanTypeIcon } from './clean-type';
import type { CleanType } from './clean-type';

import './clean-template-dialog.scss';

/** 字段项类型 */
type FieldItem = {
  field_name: string;
  field_type: string;
  value?: unknown;
  is_delete: boolean;
  is_built_in: boolean;
  is_analyzed: boolean;
  is_case_sensitive: boolean;
  tokenize_on_chars?: string;
};

/** 清洗模板类型 */
type CleanTemplate = {
  clean_template_id: number;
  name: string;
  clean_type: 'bk_log_json' | 'bk_log_delimiter' | 'bk_log_regexp';
  etl_params: Record<string, unknown>;
  etl_fields: FieldItem[];
  description?: string;
  bk_biz_id?: number;
  visible_type?: string;
  visible_bk_biz_id?: number[];
  is_deleted?: boolean;
};

/**
 * @file 选择清洗模板弹窗
 */
export default defineComponent({
  name: 'CleanTemplateDialog',
  props: {
    visible: {
      type: Boolean,
      default: false,
    },
    bkBizId: {
      type: [Number, String],
      default: '',
    },
  },
  emits: ['close', 'select', 'preview'],
  setup(props, { emit }) {
    const { t } = useLocale();

    const loading = ref(false);
    const templateList = ref<CleanTemplate[]>([]);
    const searchText = ref('');
    /** 实际用于过滤的搜索文本（仅在回车或点击搜索图标时更新） */
    const appliedSearchText = ref('');
    /** 清洗类型筛选，'all' 表示全部；其余对应 clean_type */
    const filterCleanType = ref<'all' | CleanType>('all');
    const selectedTemplateId = ref<number | null>(null);

    /** 分页参数 */
    const PAGE_SIZE = 10;
    const currentPage = ref(1);
    const hasMore = ref(true);
    /** 滚动容器引用 */
    const scrollContainerRef = ref<HTMLElement | null>(null);

    /** 应用搜索：将输入框文本同步到过滤条件，并重新拉取第一页 */
    const handleSearch = () => {
      appliedSearchText.value = searchText.value.trim();
      resetAndFetch();
    };

    /** 清洗类型筛选 tab 选项 */
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

    /** 当前 tab 索引（用于 slider 滑动效果） */
    const activeTabIndex = computed(() => {
      const index = cleanTypeTabs.value.findIndex(tab => tab.value === filterCleanType.value);
      return index < 0 ? 0 : index;
    });

    /** 当前选中的模板 */
    const currentTemplate = computed(() => {
      if (selectedTemplateId.value === null) return null;
      return templateList.value.find(item => item.clean_template_id === selectedTemplateId.value) ?? null;
    });

    /** 表格展示的字段列表 */
    const tableFields = computed<FieldItem[]>(() => {
      if (!currentTemplate.value) return [];
      return currentTemplate.value.etl_fields ?? [];
    });

    /** 格式化字段值用于显示 */
    const formatDisplayValue = (value: unknown): string => {
      if (Array.isArray(value)) {
        return `[ ${value.join(', ')} ]`;
      }
      if (typeof value === 'object' && value !== null) {
        return JSON.stringify(value);
      }
      return String(value ?? '');
    };

    /** 获取"是否分词"展示文本 */
    const getParticipleText = (row: FieldItem): string => {
      if (row.field_type === 'string' && !row.is_built_in) {
        if (row.is_analyzed) {
          return row.tokenize_on_chars ? row.tokenize_on_chars : t('自然语言分词');
        }
        return t('不分词');
      }
      return t('无需设置');
    };

    /** 获取"大小写敏感"展示文本 */
    const getCaseSensitiveText = (row: FieldItem): string => {
      return row.is_case_sensitive ? t('是') : t('否');
    };

    /** 判断字段是否需要显示大小写敏感 */
    const shouldShowCaseSensitive = (row: FieldItem): boolean => {
      return row.field_type === 'string' && !row.is_built_in && row.is_analyzed;
    };

    /**
     * 拉取模板列表
     * 接口过滤字段：keyword（搜索关键词）、clean_type（'all' 时不传该字段）
     * 支持分页，触底加载更多
     * @param isLoadMore 是否为加载更多
     */
    const fetchTemplateList = (isLoadMore = false) => {
      loading.value = true;
      const query: Record<string, unknown> = {
        bk_biz_id: props.bkBizId,
        page: currentPage.value,
        pagesize: PAGE_SIZE,
      };
      // 搜索关键词
      if (appliedSearchText.value) {
        query.keyword = appliedSearchText.value;
      }
      // 过滤字段：clean_type（仅在非 all 时传递）
      if (filterCleanType.value !== 'all') {
        query.clean_type = filterCleanType.value;
      }
      $http
        .request('clean/cleanTemplate', { query })
        .then((res: any) => {
          if (res.data) {
            const list: CleanTemplate[] = Array.isArray(res.data)
              ? res.data
              : (res.data?.list ?? []);
            if (isLoadMore) {
              templateList.value = [...templateList.value, ...list];
            } else {
              templateList.value = list;
              // 仅在非加载更多时默认选中第一个
              selectedTemplateId.value =
                list.length > 0 ? list[0].clean_template_id : null;
            }
            // 判断是否还有更多
            hasMore.value = templateList.value.length < res.data.total;
          } else {
            if (!isLoadMore) {
              templateList.value = [];
              selectedTemplateId.value = null;
            }
            hasMore.value = false;
          }
        })
        .catch(() => {
          if (!isLoadMore) {
            templateList.value = [];
            selectedTemplateId.value = null;
          }
          hasMore.value = false;
        })
        .finally(() => {
          loading.value = false;
        });
    };

    /** 重置分页并重新拉取第一页 */
    const resetAndFetch = () => {
      currentPage.value = 1;
      hasMore.value = true;
      // 重置滚动位置到顶部
      scrollContainerRef.value?.scrollTo({ top: 0, behavior: 'auto' });
      fetchTemplateList(false);
    };

    /** 触底加载更多 */
    const handleScroll = (e: Event) => {
      const el = e.target as HTMLElement;
      if (el.scrollTop + el.clientHeight + 50 >= el.scrollHeight) {
        if (!loading.value && hasMore.value) {
          currentPage.value += 1;
          fetchTemplateList(true);
        }
      }
    };

    /** 每次打开弹窗时重置筛选条件 + 重新拉取数据 */
    watch(
      () => props.visible,
      (val: boolean) => {
        if (val) {
          searchText.value = '';
          appliedSearchText.value = '';
          filterCleanType.value = 'all';
          selectedTemplateId.value = null;
          currentPage.value = 1;
          hasMore.value = true;
          scrollContainerRef.value?.scrollTo({ top: 0, behavior: 'auto' });
          fetchTemplateList(false);
        }
      },
      { immediate: true },
    );

    /** tab 切换：重新调用接口过滤 */
    const handleTabChange = (value: 'all' | CleanType) => {
      if (filterCleanType.value === value) return;
      filterCleanType.value = value;
      selectedTemplateId.value = null;
      resetAndFetch();
    };

    /** 选择模板 */
    const handleSelectTemplate = (item: CleanTemplate) => {
      selectedTemplateId.value = item.clean_template_id;
    };

    /** 关闭弹窗 */
    const handleClose = () => {
      emit('close');
    };

    /** 确定按钮（应用清洗结果） */
    const handleConfirm = () => {
      if (currentTemplate.value) {
        // 浏览清洗结果：关闭当前弹窗并把选中模板抛给父组件
        emit('preview', currentTemplate.value);
      }
      emit('close');
    };

    /** 监听 dialog value 变化 */
    const handleDialogValueChange = (val: boolean) => {
      if (!val) {
        handleClose();
      }
    };

    /** 字段名列插槽 */
    const fieldNameSlot = {
      default: ({ row }: { row: FieldItem }) => (
        <div
          class='field-name-cell'
          v-bk-overflow-tips={row.field_name}
        >
          {row.field_name}
        </div>
      ),
    };

    /** 分词列插槽 */
    const participleSlot = {
      default: ({ row }: { row: FieldItem }) => {
        if (shouldShowCaseSensitive(row)) {
          return (
            <div class='participle-cell participle-cell--analyzed'>
              <div>{getParticipleText(row)}</div>
              <div>{t('大小写敏感')}: {getCaseSensitiveText(row)}</div>
            </div>
          );
        }
        return <span class='participle-cell'>{getParticipleText(row)}</span>;
      },
    };

    /** 示例值列插槽 */
    const valueSlot = {
      default: ({ row }: { row: FieldItem }) => (
        <div
          class='value-cell'
          v-bk-overflow-tips={formatDisplayValue(row.value)}
        >
          {formatDisplayValue(row.value)}
        </div>
      ),
    };

    return () => (
      <bk-dialog
        value={props.visible}
        width={1080}
        title={t('选择清洗模板')}
        header-position='left'
        show-footer={true}
        mask-close={false}
        ok-text={t('浏览清洗结果')}
        on-value-change={handleDialogValueChange}
        on-confirm={handleConfirm}
        on-closed={handleClose}
      >
        <div class='clean-template-dialog' v-bkloading={{ isLoading: loading.value, size: 'mini' }}>
          {/* 左侧：类型 tab + 搜索 + 模板列表 */}
          <div class='template-picker-panel'>
            <div class='clean-type-tabs'>
              <div
                class='tab-slider'
                style={{ transform: `translateX(${activeTabIndex.value * 100}%)` }}
              ></div>
              {cleanTypeTabs.value.map(tab => (
                <div
                  key={tab.value}
                  class={[
                    'tab-item',
                    { active: filterCleanType.value === tab.value },
                  ]}
                  onClick={() => handleTabChange(tab.value)}
                >
                  {tab.icon && <i class={tab.icon} />}
                  {tab.label}
                </div>
              ))}
            </div>

            {/* 搜索框 */}
            <bk-input
              class='search-input'
              value={searchText.value}
              on-input={(val: string) => (searchText.value = val)}
              on-enter={handleSearch}
              on-right-icon-click={handleSearch}
              on-clear={handleSearch}
              placeholder={t('搜索 模板名称、日志类型、适用场景、字段名称')}
              clearable={true}
              right-icon='bk-icon icon-search'
            />

            {/* 模板列表 */}
            <div class='template-list' ref={scrollContainerRef} onScroll={handleScroll}>
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
                  onClick={() => handleSelectTemplate(item)}
                >
                  {/* 左侧：类型 icon 块 */}
                  <div class='template-item-icon-box'>
                    <i class={getCleanTypeIcon(item.clean_type)}></i>
                  </div>
                  {/* 中部：模板名 + 描述 */}
                  <div class='template-item-content'>
                    <div class='template-item-header'>
                      <div
                        class='template-item-name'
                        title={item.name}
                      >
                        {item.name}
                      </div>
                      {/* 右侧：字段数 */}
                      <span class='template-item-count'>
                        <i class='bklog-icon bklog-feature-tezheng' />
                        {(item.etl_fields ?? []).length}
                      </span>
                    </div>
                    <div
                      class='template-item-desc'
                      title={item.description || ''}
                    >
                      {item.description || t('适用于通用日志清洗场景')}
                    </div>
                  </div>
                </div>
              ))}
              {loading.value && hasMore.value && (
                <div class='template-list-loading'>{'loading...'}</div>
              )}
            </div>
          </div>

          {/* 右侧：模板预览 */}
          <div class='template-preview-panel'>
            {currentTemplate.value ? (
              <div class='template-detail'>
                <div class='detail-title'>{t('模板输出字段预览')}</div>
                <div class='detail-meta'>
                  <div class='meta-row'>
                    <span class='meta-label'>{t('模板名称')}</span>
                    <span class='meta-value meta-value-bold'>
                      {currentTemplate.value.name}
                    </span>
                  </div>
                  <div class='meta-row'>
                    <span class='meta-label'>{t('清洗方式')}</span>
                    <span class='meta-value'>{getCleanTypeLabel(currentTemplate.value.clean_type)}</span>
                  </div>
                  <div class='meta-row'>
                    <span class='meta-label'>{t('模板描述')}</span>
                    <span class='meta-value'>
                      {currentTemplate.value.description || '--'}
                    </span>
                  </div>
                </div>
                <bk-table
                  class='fields-table'
                  data={tableFields.value}
                  outer-border={true}
                  max-height={300}
                  size='medium'
                >
                  <bk-table-column
                    label={t('字段名')}
                    prop='field_name'
                    min-width={80}
                    show-overflow-tooltip
                    scopedSlots={fieldNameSlot}
                  />
                  <bk-table-column
                    label={t('类型')}
                    prop='field_type'
                    width={80}
                  />
                  <bk-table-column
                    label={t('分词')}
                    prop='is_analyzed'
                    width={180}
                    scopedSlots={participleSlot}
                  />
                  <bk-table-column
                    label={t('示例值')}
                    prop='value'
                    min-width={100}
                    show-overflow-tooltip
                    scopedSlots={valueSlot}
                  />
                </bk-table>
              </div>
            ) : (
              <bk-exception
                class='empty-exception'
                scene='part'
                type='empty'
              >
                <span>{t('请选择左侧模板')}</span>
              </bk-exception>
            )}
          </div>
        </div>
      </bk-dialog>
    );
  },
});
