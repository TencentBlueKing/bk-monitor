/* eslint-disable @typescript-eslint/naming-convention */
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
import { defineComponent } from 'vue';
import { useI18n } from 'vue-i18n';

import { LANGUAGE_COOKIE_KEY, docCookies } from 'monitor-common/utils';

import './legend-popover-content.scss';
const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';
interface LegendItem {
  text: string;
  status: string;
  fullText?: string;
}

export default defineComponent({
  setup() {
    const { t } = useI18n();
    const NODE_TYPE: LegendItem[] = [
      { text: '异常', status: 'error' },
      { text: '正常', status: 'normal' },
    ];

    const TAG_TYPE: LegendItem[] = [
      { text: '未恢复告警', status: 'notRestored' },
      { text: '已恢复...告警', status: 'restored', fullText: '已恢复 / 已解决 / 已失效告警' },
      { text: '根因', status: 'root' },
      { text: '反馈的根因', status: 'feedBackRoot' },
    ];

    const renderLegendItem = (node: LegendItem, isTag = false) => (
      <li key={node.status}>
        <span class='circle-wrap'>
          <span class={['circle', node.status]}>
            {node.status === 'error' && <i class='icon-monitor icon-mc-pod' />}
            {['feedBackRoot', 'root'].includes(node.status) && t('根因')}
            {isTag && ['notRestored', 'restored'].includes(node.status) && <i class='icon-monitor icon-menu-event' />}
          </span>
        </span>
        {isTag ? (
          <span
            class='text-ellipse'
            v-bk-tooltips={{
              disabled: node.status !== 'restored' || isEn,
              content: node.fullText ? t(node.fullText) : '',
            }}
            v-overflowText={{
              text: node.fullText ? t(node.fullText) : t(node.text),
            }}
          >
            {t(node.text)}
          </span>
        ) : (
          <span>{t(node.text)}</span>
        )}
      </li>
    );

    return () => (
      <div class='failure-topo-graph-legend-content'>
        <div class='w-114'>
          <span class='node-type-title'>{t('节点图例')}</span>
          <ul class='node-type mb-small'>
            <li class='node-type-subtitle'>{t('状态')}</li>
            {NODE_TYPE.map(node => renderLegendItem(node))}
          </ul>
          <ul class='node-type custom-mb'>
            <li class='node-type-subtitle'>{t('标签')}</li>
            {TAG_TYPE.map(node => renderLegendItem(node, true))}
          </ul>
        </div>
        <div class='w-114 edge-legend'>
          <span class='node-type-title'>{t('边图例')}</span>
          <ul class='node-type mb-small'>
            <li class='node-type-subtitle'>{t('指向性')}</li>
            <li>
              <span class='line' />
              <span
                class='text-ellipse'
                v-overflowText={{
                  text: t('从属关系'),
                }}
              >
                {t('从属关系')}
              </span>
            </li>
            <li>
              <span class='line arrow' />
              <span>{t('调用关系')}</span>
            </li>
          </ul>
          <ul class='node-type'>
            <li class='node-type-subtitle'>{t('线型')}</li>
            <li>
              <span class='line' />
              <span
                class='text-ellipse'
                v-overflowText={{
                  text: t('无故障传播'),
                }}
              >
                {t('无故障传播')}
              </span>
            </li>
            <li>
              <span class='line dash' />
              <span
                class='text-ellipse'
                v-overflowText={{
                  text: t('故障传播'),
                }}
              >
                {t('故障传播')}
              </span>
            </li>
          </ul>
        </div>
      </div>
    );
  },
});
