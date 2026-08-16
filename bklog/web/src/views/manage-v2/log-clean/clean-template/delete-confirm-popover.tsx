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

import { defineComponent } from 'vue';

import BklogPopover from '@/components/bklog-popover';
import useLocale from '@/hooks/use-locale';

import './delete-confirm-popover.scss';

interface PopoverRef {
  hide: () => void;
}

export default defineComponent({
  name: 'CleanTemplateDeleteConfirmPopover',
  props: {
    templateName: {
      type: String,
      required: true,
    },
  },
  emits: ['confirm'],
  setup(props, { emit, slots }) {
    const { t } = useLocale();
    let popoverRef: PopoverRef | null = null;

    const handleCancel = () => {
      popoverRef?.hide();
    };

    const handleConfirm = () => {
      handleCancel();
      // 先关闭 Popover，确保 document click listener 已移除，再通知调用方执行删除。
      setTimeout(() => emit('confirm'), 0);
    };

    const renderContent = () => (
      <div class='delete-confirm-popover-content'>
        <div class='delete-confirm-popover-icon'>
          <i class='bklog-icon bklog-alert-2' />
        </div>
        <div class='delete-confirm-popover-main'>
          <div class='delete-confirm-popover-title'>{t('确定删除该清洗模板？')}</div>
          <div class='delete-confirm-popover-row'>
            <span class='row-label'>{t('模板名称：')}</span>
            <span class='row-value'>{props.templateName}</span>
          </div>
          <div class='delete-confirm-popover-desc'>
            {t('删除模板后，原来关联的采集项，将实例化为手动配置的清洗规则。')}
          </div>
          <div class='delete-confirm-popover-footer'>
            <bk-button
              theme='danger'
              size='small'
              on-click={handleConfirm}
            >
              {t('删除')}
            </bk-button>
            <bk-button
              size='small'
              on-click={handleCancel}
            >
              {t('取消')}
            </bk-button>
          </div>
        </div>
      </div>
    );

    return () => (
      <BklogPopover
        ref={(popover: any) => {
          popoverRef = popover as PopoverRef | null;
        }}
        trigger='click'
        options={
          {
            appendTo: document.body,
            hideOnClick: false,
            interactive: true,
            maxWidth: 'none',
            placement: 'bottom-end',
            theme: 'bklog-light',
            arrow: false,
          } as any
        }
        content={renderContent}
      >
        {slots.default?.()}
      </BklogPopover>
    );
  },
});
