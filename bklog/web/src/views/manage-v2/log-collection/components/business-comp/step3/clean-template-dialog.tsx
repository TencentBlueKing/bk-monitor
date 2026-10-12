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

import { computed, defineComponent, ref } from 'vue';

import useLocale from '@/hooks/use-locale';

import { getCleanTypeLabel } from './clean-type';
import CleanTemplatePicker from './clean-template-picker';
import type { CleanTemplate, CleanTemplateField } from './clean-template-picker';

import './clean-template-dialog.scss';

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

    /** 当前选中的模板 */
    const currentTemplate = ref<CleanTemplate | null>(null);

    /** 表格展示的字段列表 */
    const tableFields = computed<CleanTemplateField[]>(() => {
      if (!currentTemplate.value) return [];
      return currentTemplate.value.etl_fields?.filter(item => !item.is_delete) ?? [];
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
    const getParticipleText = (row: CleanTemplateField): string => {
      if (row.field_type === 'string' && !row.is_built_in) {
        if (row.is_analyzed) {
          return row.tokenize_on_chars ? row.tokenize_on_chars : t('自然语言分词');
        }
        return t('不分词');
      }
      return t('无需设置');
    };

    /** 获取"大小写敏感"展示文本 */
    const getCaseSensitiveText = (row: CleanTemplateField): string => {
      return row.is_case_sensitive ? t('是') : t('否');
    };

    /** 判断字段是否需要显示大小写敏感 */
    const shouldShowCaseSensitive = (row: CleanTemplateField): boolean => {
      return row.field_type === 'string' && !row.is_built_in && row.is_analyzed;
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
      default: ({ row }: { row: CleanTemplateField }) => (
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
      default: ({ row }: { row: CleanTemplateField }) => {
        if (shouldShowCaseSensitive(row)) {
          return (
            <div class='participle-cell participle-cell--analyzed'>
              <div>{getParticipleText(row)}</div>
              <div>
                {t('大小写敏感')}: {getCaseSensitiveText(row)}
              </div>
            </div>
          );
        }
        return <span class='participle-cell'>{getParticipleText(row)}</span>;
      },
    };

    /** 示例值列插槽 */
    const valueSlot = {
      default: ({ row }: { row: CleanTemplateField }) => (
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
        <div class='clean-template-dialog'>
          <CleanTemplatePicker
            bkBizId={props.bkBizId}
            selectFirstOnLoad={true}
            showCleanTypeTabs={true}
            visible={props.visible}
            on-select={(template: CleanTemplate | null) => (currentTemplate.value = template)}
          />

          {/* 右侧：模板预览 */}
          <div class='template-preview-panel'>
            {currentTemplate.value ? (
              <div class='template-detail'>
                <div class='detail-title'>{t('模板输出字段预览')}</div>
                <div class='detail-meta'>
                  <div class='meta-row'>
                    <span class='meta-label'>{t('模板名称')}</span>
                    <span class='meta-value meta-value-bold'>{currentTemplate.value.name}</span>
                  </div>
                  <div class='meta-row'>
                    <span class='meta-label'>{t('清洗方式')}</span>
                    <span class='meta-value'>{getCleanTypeLabel(currentTemplate.value.clean_type)}</span>
                  </div>
                  <div class='meta-row'>
                    <span class='meta-label'>{t('模板描述')}</span>
                    <span class='meta-value'>{currentTemplate.value.description || '--'}</span>
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
