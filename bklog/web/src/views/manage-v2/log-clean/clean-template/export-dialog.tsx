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

import http from '@/api';
import { downJsonFile } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import CleanTemplatePicker from '@/views/manage-v2/log-collection/components/business-comp/step3/clean-template-picker';
import type { CleanTemplate } from '@/views/manage-v2/log-collection/components/business-comp/step3/clean-template-picker';

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
        const res = await http.request('clean/templateDetail', {
          params: {
            clean_template_id: selectedTemplate.value.clean_template_id,
          },
        });
        if (!res.result || !res.data) {
          return;
        }
        const template = res.data as CleanTemplate;
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
        on-value-change={handleDialogValueChange}
        scopedSlots={{
          footer: () => (
            <div>
              <bk-button
                class='mr-8'
                disabled={!selectedTemplate.value}
                loading={exporting.value}
                theme='primary'
                on-click={handleExport}
              >
                {t('导出')}
              </bk-button>
              <bk-button
                disabled={exporting.value}
                on-click={handleClose}
              >
                {t('取消')}
              </bk-button>
            </div>
          ),
        }}
      >
        <div class='clean-template-export-dialog'>
          <CleanTemplatePicker
            bkBizId={props.bkBizId}
            visible={props.visible}
            on-select={(template: CleanTemplate | null) => (selectedTemplate.value = template)}
          />
        </div>
      </bk-dialog>
    );
  },
});
