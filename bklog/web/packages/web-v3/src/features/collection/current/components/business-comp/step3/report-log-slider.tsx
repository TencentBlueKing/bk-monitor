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

import JsonFormatWrapper from '@/shared/global/json-format-wrapper.vue';

import { defineComponent, ref, watch } from 'vue';
import { overlayRegistry } from '@/shared/global/overlay/overlay-registry.js';
import { Z_INDEX_LAYERS } from '@/shared/global/overlay/z-index-manager.js';
import { Drawer, Button } from 'tdesign-vue-next';

import useLocale from '@/shared/composables/use-locale';

import './report-log-slider.scss';
import { showMessage } from '../../../utils';
/**
 * 上报日志详情
 */
export default defineComponent({
  name: 'ReportLogSlider',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    jsonText: {
      type: Object,
      default: () => ({}),
    },
  },

  emits: ['change'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const zIndex = ref<number>(Z_INDEX_LAYERS.DRAWER);
    watch(() => props.isShow, visible => {
      if (visible) zIndex.value = overlayRegistry.nextZIndex();
    }, { immediate: true });
    // Keep the fallback textarea inside the drawer's focus trap.
    const handleCopy = async (event: MouseEvent) => {
      const text = JSON.stringify(props.jsonText);
      try {
        if (navigator.clipboard?.writeText) {
          await navigator.clipboard.writeText(text);
        } else {
          const textarea = document.createElement('textarea');
          textarea.value = text;
          textarea.style.cssText = 'position:fixed;opacity:0;pointer-events:none;';
          const host = (event.currentTarget as HTMLElement).closest('.t-drawer__content') || document.body;
          host.appendChild(textarea);
          try {
            textarea.focus();
            textarea.select();
            if (!document.execCommand('copy')) throw new Error('copy failed');
          } finally { textarea.remove(); }
        }
        showMessage(t('复制成功'));
      } catch {
        showMessage(t('复制失败'), 'error');
      }
    };
    return () => (
      <Drawer
        size='596px'
        zIndex={zIndex.value}
        drawerClassName='report-log-slider-main'
        visible={props.isShow}
        footer={false}
        closeBtn={true}
        closeOnOverlayClick
        closeOnEscKeydown
        onClose={() => {
          emit('change', false);
        }}
        v-slots={{
          header: () => (
            <div class='report-log-slider-header'>
              <span class='title'>{t('上报日志详情')}</span>
              <Button
                variant='outline'
                disabled={!Object.keys(props.jsonText).length}
                class='copy-btn'
                onClick={handleCopy}
              >
                {t('复制')}
              </Button>
            </div>
          ),
          body: () => props.isShow && (
            <div class='p20 json-text-style'>
              {Object.keys(props.jsonText).length ? (
                <JsonFormatWrapper data={props.jsonText} deep={5} />
              ) : <div class='report-log-empty'>{t('暂无数据')}</div>}
            </div>
          ),
        }}
      />
    );
  },
});
