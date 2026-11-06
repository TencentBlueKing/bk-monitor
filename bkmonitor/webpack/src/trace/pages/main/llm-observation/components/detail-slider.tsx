/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent } from 'vue';

import { Message, Sideslider } from 'bkui-vue';
import { copyText } from 'monitor-common/utils/utils';
import { useI18n } from 'vue-i18n';

import { LLM_DETAIL_SLIDER_Z_INDEX } from '../../constants';
import { beautifyJsonValue, stringifyContent } from '../utils/helpers';
import JsonView from './json-view';

import './detail-slider.scss';

/** 独立查看侧栏内容：文本或 JSON */
export type LlmDetailSliderContent =
  | {
      data: unknown;
      kind: 'json';
      title: string;
    }
  | {
      kind: 'text';
      text: string;
      title: string;
    };

/** 独立查看侧栏：标题、复制、文本 / JSON 正文 */
export default defineComponent({
  name: 'LlmDetailSlider',
  props: {
    detail: {
      type: Object as PropType<LlmDetailSliderContent | null>,
      default: null,
    },
    width: {
      type: Number,
      default: 840,
    },
  },
  emits: {
    close: () => true,
  },
  setup(props, { emit }) {
    const { t } = useI18n();

    /** 关闭独立查看：卸载 Sideslider，避免 teleport 到 body 的 .bk-modal 残留挡点击 */
    const closeDetail = () => {
      emit('close');
    };

    /** 复制侧栏当前文本或 JSON 内容 */
    const handleCopyDetail = () => {
      if (!props.detail) return;
      const text =
        props.detail.kind === 'text' ? props.detail.text : stringifyContent(beautifyJsonValue(props.detail.data));
      copyText(text, (msg: string) => {
        Message({ message: msg, theme: 'error' });
      });
      Message({ message: t('复制成功'), theme: 'success' });
    };

    return () =>
      props.detail ? (
        <Sideslider
          width={props.width}
          extCls='llm-detail-slider'
          isShow={true}
          quickClose={true}
          transfer={true}
          zIndex={LLM_DETAIL_SLIDER_Z_INDEX}
          onClosed={closeDetail}
          onHidden={closeDetail}
          onUpdate:isShow={(val: boolean) => {
            if (!val) closeDetail();
          }}
        >
          {{
            header: () => (
              <div class='llm-detail-slider-header'>
                <span class='llm-detail-slider-title'>{props.detail?.title || ''}</span>
                <div
                  class='llm-detail-slider-copy'
                  onClick={handleCopyDetail}
                >
                  <i class='icon-monitor icon-mc-copy' />
                  <span>{t('复制')}</span>
                </div>
              </div>
            ),
            default: () =>
              props.detail?.kind === 'json' ? (
                <div class='llm-detail-slider-json'>
                  <JsonView
                    data={props.detail.data}
                    showLineNumber={true}
                  />
                </div>
              ) : (
                <pre class='llm-detail-slider-text'>{props.detail?.kind === 'text' ? props.detail.text : ''}</pre>
              ),
          }}
        </Sideslider>
      ) : null;
  },
});
