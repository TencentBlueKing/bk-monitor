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
import { defineComponent, ref, computed } from 'vue';

import AIBlueking from '@blueking/ai-blueking/vue2';

import { random } from '../common/util';
import { AI_BLUEKING_SHORTCUTS } from './ai-type';

import './ai-assistant.scss';
import '@blueking/ai-blueking/dist/vue2/style.css';

interface IRowSendData {
  space_uid: string;
  index_set_id: string;
  log: string;
  query?: string;
  context_count?: number;
  index: number;
  type: string;
}
export default defineComponent({
  setup(_props, { expose }) {
    const aiBlueking = ref<InstanceType<typeof AIBlueking> | null>(null);

    let chatid = random(10);

    const isShow = ref(false);

    const apiUrl = `${window.AJAX_URL_PREFIX || '/api/v1'}ai_assistant`;
    const shortcuts = computed(() => {
      return [...AI_BLUEKING_SHORTCUTS];
    });

    // 暂停聊天
    const handleStop = () => {
      aiBlueking.value?.handleStop();
    };

    const hiddenAiAssistant = () => {
      isShow.value = false;
      aiBlueking.value?.hide?.();
    };

    const displayAiAssistant = () => {
      isShow.value = true;
    };

    const setAiStart = (sendMsg = false, args: IRowSendData) => {
      chatid = random(10);
      if (sendMsg) {
        aiBlueking.value?.handleShow();
        aiBlueking.value?.addNewSession().finally(() => {
          const shortcut = structuredClone(AI_BLUEKING_SHORTCUTS[0]);
          shortcut.components.forEach(comp => {
            const value = args[comp.key];
            if (value) {
              comp.default = typeof value === 'object' ? JSON.stringify(value).replace(/<\/?mark>/gim, '') : value;
            }
          });

          aiBlueking.value?.handleShortcutClick?.({ shortcut, source: 'popup' });
        });
      }
    };

    const showAiAssistant = (sendMsg = false, args: IRowSendData) => {
      if (isShow.value && chatid) {
        handleStop();
        setTimeout(() => {
          setAiStart(sendMsg, args);
        });
        return;
      }

      setAiStart(sendMsg, args);
    };

    const handleShortcutFilter = () => {
      return false;
    };

    /**
     * 推送消息
     * @param msg
     */
    const sendMessage = (msg: string) => {
      if (!isShow.value) {
        aiBlueking.value?.handleShow();
      }

      aiBlueking.value?.handleSendMessage(msg);
    };

    /**
     * 设置引用文本
     * @param text
     */
    const setCiteText = (text: string) => {
      if (!isShow.value) {
        aiBlueking.value?.handleShow();
      }

      aiBlueking.value?.setCiteText(text);
    };

    expose({
      open: showAiAssistant,
      close: hiddenAiAssistant,
      sendMessage,
      setCiteText,
    });

    return () => (
      <div class='ai-blueking-wrapper'>
        <AIBlueking
          ref={aiBlueking}
          requestOptions={{
            beforeRequest: data => {
              return {
                ...data,
                headers: {
                  ...(data?.headers || {}),
                  Traceparent: `00-${random(32, 'abcdef0123456789')}-${random(16, 'abcdef0123456789')}-01`,
                },
              };
            },
          }}
          enablePopup={false}
          hideNimbus={true}
          prompts={[]}
          shortcutFilter={handleShortcutFilter}
          shortcuts={shortcuts.value}
          showHistoryIcon={false}
          url={apiUrl}
          onClose={hiddenAiAssistant}
          onShow={displayAiAssistant}
        />
      </div>
    );
  },
});
