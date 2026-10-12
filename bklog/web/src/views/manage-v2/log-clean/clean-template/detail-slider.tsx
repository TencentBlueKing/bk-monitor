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

import { computed, defineComponent, PropType, ref, watch } from 'vue';

import http from '@/api';
import {
  CleanTemplateSnapshot,
  CleanTemplateStatus,
  resolveCleanTemplateDraft,
} from '@/views/manage-v2/utils/clean-template';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import CollectorTable from './collector-table';
import DeleteConfirmPopover from './delete-confirm-popover';
import './detail-slider.scss';
import useTemplateCollectors from './use-template-collectors';

export type DetailTab = 'collectors' | 'fields' | 'settings';

interface DetailField {
  field_name?: string;
  field_type?: string;
  is_analyzed?: boolean;
  is_case_sensitive?: boolean;
  is_delete?: boolean;
  is_time?: boolean;
  option?: {
    time_format?: string;
    time_zone?: number;
  };
  tokenize_on_chars?: string;
  value?: string;
}

interface DetailParams {
  enable_retain_content?: boolean;
  metadata_fields?: Array<{ example?: string; field_name?: string; value?: string }>;
  original_text_is_case_sensitive?: boolean;
  original_text_tokenize_on_chars?: string;
  path_example?: string;
  path_regexp?: string;
  retain_extra_json?: boolean;
  retain_original_text?: boolean;
  record_parse_failure?: boolean;
}

export interface CleanTemplateDetail {
  clean_template_id: number;
  clean_type: string;
  description?: string;
  etl_fields: DetailField[];
  etl_params: DetailParams;
  name: string;
  snapshot?: CleanTemplateSnapshot<string, DetailParams, DetailField> | null;
  status: CleanTemplateStatus;
}

interface DetailTemplateSummary {
  clean_template_id: number;
  clean_type: string;
  description?: string;
  name: string;
  related_index_set_count: number;
  status: CleanTemplateStatus;
}

interface SettingValuePart {
  label?: string;
  value?: string;
}

const CLEAN_TYPE_ICON_MAP: Record<string, string> = {
  bk_log_json: 'bklog-icon bklog-json-fanxuliehua',
  bk_log_delimiter: 'bklog-icon bklog-fengefu',
  bk_log_regexp: 'bklog-icon bklog-zhengzetiqu',
};

export default defineComponent({
  name: 'CleanTemplateDetailSlider',
  props: {
    initialTab: {
      type: String as PropType<DetailTab>,
      default: 'fields',
    },
    isShow: {
      type: Boolean,
      default: false,
    },
    template: {
      type: Object as PropType<DetailTemplateSummary | null>,
      default: null,
    },
  },
  emits: ['close', 'delete', 'edit', 'sync'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const activeTab = ref<DetailTab>('fields');
    const isLoading = ref(false);
    const keyword = ref('');
    const detail = ref<CleanTemplateDetail | null>(null);
    const { collectors, isCollectorsLoading, requestCollectors, resetCollectors } = useTemplateCollectors();

    const currentTemplate = computed(() => detail.value ?? props.template);
    const fields = computed(() => detail.value?.etl_fields?.filter(item => !item.is_delete) ?? []);
    const globalsData = computed(() => store.getters['globals/globalsData'] ?? {});
    const canSync = computed(
      () => collectors.value.length > 0 && props.template?.status === 'DRAFT' && !isCollectorsLoading.value,
    );
    const timeField = computed(() => fields.value.find(item => item.is_time));
    const etlParams = computed(() => detail.value?.etl_params ?? {});

    const getCleanTypeName = () => {
      return (
        (globalsData.value.etl_config || []).find(
          (item: { id: string }) => item.id === currentTemplate.value?.clean_type,
        )?.name || '--'
      );
    };
    const getTimeZoneName = (timeZone?: number | string) => {
      return (globalsData.value.time_zone || []).find(
        (item: { id: number | string }) => String(item.id) === String(timeZone),
      )?.name;
    };
    const renderParticiple = (field: DetailField) => {
      if (!field.is_analyzed) {
        return <span>{t('不分词')}</span>;
      }
      return (
        <div class='participle-text'>
          <div>{field.tokenize_on_chars || t('自然语言分词')}</div>
          <div>
            {t('大小写敏感')}: {field.is_case_sensitive ? t('是') : t('否')}
          </div>
        </div>
      );
    };
    const getBooleanText = (value?: boolean) => (value ? t('开启') : t('关闭'));
    const requestDetail = async () => {
      if (!props.template?.clean_template_id) {
        return;
      }
      isLoading.value = true;
      try {
        const res = await http.request('clean/templateDetail', {
          params: { clean_template_id: props.template.clean_template_id },
        });
        detail.value = res.data ? resolveCleanTemplateDraft(res.data as CleanTemplateDetail) : null;
      } catch (error) {
        console.warn(error);
      } finally {
        isLoading.value = false;
      }
    };

    const handleClose = () => emit('close');
    const handleEdit = () => currentTemplate.value && emit('edit', currentTemplate.value);
    const handleSync = () => canSync.value && props.template && emit('sync', props.template);
    const handleDelete = () => {
      currentTemplate.value && emit('delete', currentTemplate.value);
    };

    const renderTabLabel = (icon: string, label: string) => (
      <div class='detail-tab-label'>
        <i class={icon} />
        <span>{label}</span>
      </div>
    );
    const renderFields = () => (
      <div class='detail-card'>
        <bk-table
          data={fields.value}
          border={false}
          outer-border={true}
          header-border={false}
        >
          <bk-table-column
            label={t('字段名')}
            prop='field_name'
            min-width='200'
            show-overflow-tooltip
          />
          <bk-table-column
            label={t('类型')}
            prop='field_type'
            width='120'
          />
          <bk-table-column
            class-name='participle-column'
            label={t('分词')}
            min-width='200'
            scopedSlots={{
              default: ({ row }: { row: DetailField }) => renderParticiple(row),
            }}
          />
          <bk-table-column
            label={t('示例值')}
            prop='value'
            min-width='240'
            show-overflow-tooltip
          />
        </bk-table>
      </div>
    );
    const renderValueParts = (parts: SettingValuePart[]) => (
      <div class='setting-value-parts'>
        {parts.map((part, index) => (
          <span
            key={`${part.label}-${index}`}
            class='setting-value-part'
          >
            {part.label && <span class='setting-value-label'>{part.label}</span>}
            <span>{part.value || '--'}</span>
          </span>
        ))}
      </div>
    );
    const renderSettingRow = (label: string, content: any) => (
      <div class='setting-row'>
        <div class='setting-key'>{label}</div>
        <div class='setting-value'>{content}</div>
      </div>
    );
    const renderSettings = () => {
      const retainOriginalText = Boolean(etlParams.value.retain_original_text);
      const originalTextParts: SettingValuePart[] = [{ value: retainOriginalText ? t('保留') : t('丢弃') }];
      if (retainOriginalText) {
        originalTextParts.push({
          label: `${t('分词符')}：`,
          value: etlParams.value.original_text_tokenize_on_chars || t('自然语言分词'),
        });
        if (etlParams.value.original_text_is_case_sensitive) {
          originalTextParts.push({ value: t('大小写敏感') });
        }
      }

      const enablePathMetadata = Boolean(etlParams.value.path_regexp);
      const pathMetadataParts: SettingValuePart[] = [{ value: getBooleanText(enablePathMetadata) }];
      if (enablePathMetadata) {
        pathMetadataParts.push({
          label: `${t('采集路径分割正则')}：`,
          value: etlParams.value.path_regexp,
        });
      }

      return (
        <div class='detail-card setting-card'>
          {renderSettingRow(t('原始日志'), renderValueParts(originalTextParts))}
          {renderSettingRow(
            t('指定日志时间'),
            timeField.value
              ? renderValueParts([
                  { label: `${t('指定字段')}：`, value: timeField.value.field_name },
                  { label: `${t('时间格式')}：`, value: timeField.value.option?.time_format },
                  { label: `${t('时区选择')}：`, value: getTimeZoneName(timeField.value.option?.time_zone) },
                ])
              : t('日志上报时间'),
          )}
          {renderSettingRow(
            t('失败日志'),
            (etlParams.value.enable_retain_content ?? etlParams.value.record_parse_failure) ? t('保留') : t('丢弃'),
          )}
          {currentTemplate.value?.clean_type === 'bk_log_json' &&
            renderSettingRow(t('JSON 字段动态新增'), getBooleanText(etlParams.value.retain_extra_json))}
          {renderSettingRow(t('路径元数据'), renderValueParts(pathMetadataParts))}
        </div>
      );
    };
    const renderCollectors = () => (
      <div class='detail-card collector-card'>
        <div class='collector-toolbar'>
          <bk-button
            disabled={!canSync.value}
            theme='primary'
            onClick={handleSync}
          >
            {t('一键同步')}
          </bk-button>
          <bk-input
            value={keyword.value}
            placeholder={t('搜索 采集项名称、ID')}
            right-icon='bk-icon icon-search'
            clearable
            on-input={(value: string) => (keyword.value = value)}
          />
        </div>
        <CollectorTable
          data={collectors.value}
          keyword={keyword.value}
        />
      </div>
    );

    watch(
      () => [props.isShow, props.template?.clean_template_id, props.initialTab],
      ([isShow]) => {
        if (!isShow) {
          resetCollectors();
          return;
        }
        activeTab.value = props.initialTab;
        keyword.value = '';
        detail.value = null;
        requestDetail();
        requestCollectors(props.template?.clean_template_id);
      },
    );

    return () => (
      <div class='clean-template-detail-slider-wrapper'>
        <bk-sideslider
          width={960}
          ext-cls='clean-template-detail-slider'
          is-show={props.isShow}
          quick-close={true}
          show-mask={true}
          transfer
          {...{ on: { 'update:isShow': handleClose } }}
        >
          <template slot='header'>{t('清洗模板详情')}</template>
          <template slot='content'>
            <div
              class='clean-template-detail-content'
              v-bkloading={{ isLoading: isLoading.value || isCollectorsLoading.value }}
            >
              <header class='detail-summary'>
                <div class='detail-summary-main'>
                  <div class='detail-type-icon'>
                    <i class={CLEAN_TYPE_ICON_MAP[currentTemplate.value?.clean_type || ''] || 'bk-icon icon-file'} />
                  </div>
                  <div class='detail-summary-text'>
                    <strong title={currentTemplate.value?.name || ''}>{currentTemplate.value?.name || '--'}</strong>
                    <span>
                      <b>[{getCleanTypeName()}]</b> {currentTemplate.value?.description || '--'}
                    </span>
                  </div>
                </div>
                <div class='detail-actions'>
                  <bk-button
                    icon='edit-line'
                    onClick={handleEdit}
                  >
                    {t('编辑')}
                  </bk-button>
                  <DeleteConfirmPopover
                    templateName={currentTemplate.value?.name || '--'}
                    on-confirm={handleDelete}
                  >
                    <bk-button icon='delete'>{t('删除')}</bk-button>
                  </DeleteConfirmPopover>
                </div>
              </header>
              <bk-tab
                class='detail-tabs'
                active={activeTab.value}
                type='unborder-card'
                label-height={42}
                on-tab-change={(value: DetailTab) => (activeTab.value = value)}
              >
                <bk-tab-panel
                  name='fields'
                  label={t('输出字段')}
                  renderLabel={() => renderTabLabel('bklog-icon bklog-feature-tezheng', t('输出字段'))}
                >
                  {activeTab.value === 'fields' && renderFields()}
                </bk-tab-panel>
                <bk-tab-panel
                  name='settings'
                  label={t('高级设置')}
                  renderLabel={() => renderTabLabel('bklog-icon bklog-configuration', t('高级设置'))}
                >
                  {activeTab.value === 'settings' && renderSettings()}
                </bk-tab-panel>
                <bk-tab-panel
                  name='collectors'
                  label={t('关联采集项')}
                  renderLabel={() =>
                    renderTabLabel('bklog-icon bklog-link-guanlian', `${t('关联采集项')} (${collectors.value.length})`)
                  }
                >
                  {activeTab.value === 'collectors' && renderCollectors()}
                </bk-tab-panel>
              </bk-tab>
            </div>
          </template>
        </bk-sideslider>
      </div>
    );
  },
});
