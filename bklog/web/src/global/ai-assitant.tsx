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
import { type AIBluekingShortcut, AI_BLUEKING_SHORTCUTS, AI_BLUEKING_SHORTCUTS_ID } from './ai-type';

import './ai-assistant.scss';
import '@blueking/ai-blueking/dist/vue2/style.css';

interface IRowSendData {
  space_uid: string;
  index_set_id: string;
  log_data: unknown;
  query: string;
  index: number;
  type: string;
}
export default defineComponent({
  setup(_props, { expose, emit }) {
    const aiBlueking = ref<InstanceType<typeof AIBlueking> | null>(null);

    const prompts = ref([]);
    let chatid = random(10);

    const isShow = ref(false);
    const aiFixedLinkArgs = { index: null, id: null };
    const cachedArgs: Partial<IRowSendData> = {};

    const apiUrl = `${window.AJAX_URL_PREFIX || '/api/v1'}ai_assistant`;
    const shortcuts = computed(() => {
      return [...AI_BLUEKING_SHORTCUTS];
    });

    const getFixedRow = () => {
      return `<div data-ai="{ type: 'button', data: '[${aiFixedLinkArgs.index}, ${aiFixedLinkArgs.id}]' }" class="ai-clickable" >
          <div class="bklog-ai-row-title">分析当前日志:</div>
          <div class="bklog-ai-row-content">
            ${Object.keys(cachedArgs.log_data ?? {})
              .slice(0, 100)
              .map(key => {
                return `<span class="bklog-ai-cell-label">${key}:</span><span class="bklog-ai-cell-text">${JSON.stringify(cachedArgs.log_data[key])}</span>`;
              })
              .join('')}
          </div>
        </div >`;
    };

    // 外部调用启动首次聊天
    const handleSendRowAi = () => {
      aiBlueking.value?.handleSendMessage?.(getFixedRow());
    };

    // 暂停聊天
    const handleStop = () => {
      aiBlueking.value?.handleStop();
    };

    const hiddenAiAssistant = () => {
      isShow.value = false;
      aiBlueking.value?.hide?.();
    };

    const handleClose = () => {
      isShow.value = false;
      handleStop();
      chatid = null;
      emit('close');
    };

    const displayAiAssistant = () => {
      isShow.value = true;
      aiBlueking.value?.handleShow?.();
    };

    const setAiStart = (sendMsg = false, args: IRowSendData) => {
      chatid = random(10);
      displayAiAssistant();
      if (sendMsg) {
        args.type = 'log_interpretation';
        Object.assign(cachedArgs, args);
        Object.assign(aiFixedLinkArgs, { index: args.index, id: chatid });
        handleSendRowAi();
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

    const triggerShortcut = (shortcut: AIBluekingShortcut) => {
      if (shortcut?.id) {
        displayAiAssistant();
        aiBlueking.value?.handleShortcutClick?.({ shortcut, source: 'popup' });
      }
    };
    const handleShortcutFilter = (shortcut: AIBluekingShortcut, selectedText: string) => {
      // trace 分析判断
      if (shortcut.id === AI_BLUEKING_SHORTCUTS_ID.TRACING_ANALYSIS) {
        return !!selectedText?.match(/^[0-9a-f]{32}$/);
      }
      if (shortcut.id === AI_BLUEKING_SHORTCUTS_ID.PROFILING_ANALYSIS) {
        return false;
      }
      return true;
    };
    const handleShortcutClick = () => {};

    expose({
      open: showAiAssistant,
      close: hiddenAiAssistant,
      shortcutClick: triggerShortcut,
    });

    return () => (
      <AIBlueking
        ref={aiBlueking}
        enable-popup={true}
        hideNimbus={true}
        prompts={prompts.value}
        shortcutFilter={handleShortcutFilter}
        shortcuts={shortcuts.value}
        url={apiUrl}
        on-close={handleClose}
        on-shortcut-click={handleShortcutClick}
      />
    );
  },
});
