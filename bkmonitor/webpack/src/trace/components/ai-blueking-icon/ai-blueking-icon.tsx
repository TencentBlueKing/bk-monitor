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
import { type PropType, defineComponent } from 'vue';

import {
  type AIBluekingShortcutId,
  AI_BLUEKING_SHORTCUTS,
  AI_BLUEKING_SHORTCUTS_ID,
} from 'monitor-pc/components/ai-whale/types';
import { useI18n } from 'vue-i18n';

import './ai-blueking-icon.scss';
export default defineComponent({
  name: 'AiBluekingIcon',
  props: {
    shortcutId: {
      type: String as PropType<AIBluekingShortcutId>,
      default: AI_BLUEKING_SHORTCUTS_ID.TRAFFIC_ASSISTANT,
    },
    fillBackFieldMap: {
      type: Object as PropType<Record<string, string>>,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useI18n();
    if (!window.__BK_WEWEB_DATA__?.handleAIBluekingShortcut) {
      return () => null;
    }
    return () => (
      <div
        class='ai-blueking-icon'
        v-tippy={t('AI 小鲸')}
        onClick={() => {
          const shortcut = AI_BLUEKING_SHORTCUTS.find(shortcut => shortcut.id === props.shortcutId);
          if (shortcut) {
            console.log(shortcut, window.__BK_WEWEB_DATA__?.handleAIBluekingShortcut);
            window.__BK_WEWEB_DATA__?.handleAIBluekingShortcut?.({
              ...shortcut,
              components: shortcut.components?.map(component => {
                return {
                  ...component,
                  default: props.fillBackFieldMap?.[component.key] || '',
                };
              }),
            });
          }
        }}
      />
    );
  },
});
