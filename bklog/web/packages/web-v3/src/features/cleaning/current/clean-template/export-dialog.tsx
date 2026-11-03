
import { Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';
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

import { defineComponent, ref } from 'vue';


import { resolveCleanTemplateDraft } from '@/features/management/manage-v2/utils/clean-template';
import { downJsonFile } from '@/shared/lib/util';
import useLocale from '@/shared/composables/use-locale';
import CleanTemplatePicker from '@/features/collection/current/components/business-comp/step3/clean-template-picker';
import type { CleanTemplate } from '@/features/collection/current/components/business-comp/step3/clean-template-picker';

import './export-dialog.scss';

export default defineComponent({
  name: 'CleanTemplateExportDialog',
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
  emits: ['close'],
  setup(props, { emit }) {
    const { t } = useLocale();
    const selectedTemplate = ref<CleanTemplate | null>(null);
    const exporting = ref(false);

    const handleClose = () => {
      if (!exporting.value) {
        emit('close');
      }
    };

    const handleDialogValueChange = (visible: boolean) => {
      if (!visible) {
        handleClose();
      }
    };

    const handleExport = async () => {
      if (!selectedTemplate.value || exporting.value) {
        return;
      }
      exporting.value = true;
      try {
        const res = await ServicesInstance.clean.templateDetail({
          params: {
            clean_template_id: selectedTemplate.value.clean_template_id,
          },
        });
        if (!res.result || !res.data) {
          return;
        }
        const template = resolveCleanTemplateDraft(res.data as CleanTemplate);
        const exportData = {
          name: template.name,
          description: template.description || '',
          clean_type: template.clean_type,
          etl_params: template.etl_params,
          etl_fields: template.etl_fields,
        };
        downJsonFile(JSON.stringify(exportData, null, 4), `${template.name}.json`);
        emit('close');
      } catch (error) {
        console.warn(error);
      } finally {
        exporting.value = false;
      }
    };

    return () => (
      <bk-dialog
        value={props.visible}
        width={480}
        title={t('导出')}
        header-position='left'
        mask-close={false}
        show-footer={true}
        onValueChange={handleDialogValueChange}
        v-slots={{
          footer: () => (
            <div>
              <TButton
                class='mr-8'
                disabled={!selectedTemplate.value}
                loading={exporting.value}
                theme='primary'
                onClick={handleExport}
              >
                {t('导出')}
              </TButton>
              <TButton
                disabled={exporting.value}
                onClick={handleClose}
              >
                {t('取消')}
              </TButton>
            </div>
          ),
        }}
      >
        <div class='clean-template-export-dialog'>
          <CleanTemplatePicker
            bkBizId={props.bkBizId}
            useDraftConfig={true}
            visible={props.visible}
            onSelect={(template: CleanTemplate | null) => (selectedTemplate.value = template)}
          />
        </div>
      </bk-dialog>
    );
  },
});
