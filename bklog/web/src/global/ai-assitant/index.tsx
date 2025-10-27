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
import { defineComponent, nextTick, ref } from 'vue';

import AIBlueking from '@blueking/ai-blueking/vue2';

import { random } from '@/common/util';
import { AI_BLUEKING_QUERY_STRING, AI_BLUEKING_SHORTCUTS } from './ai-type';

import '@blueking/ai-blueking/dist/vue2/style.css';
import { isEqual } from 'lodash-es';
import './ai-assistant.scss';

export interface IRowSendData {
  space_uid: string;
  index_set_id: string;
  log: string;
  query?: string;
  context_count?: number;
  index: number;
  type: string;
}

export interface IQueryStringSendData {
  index_set_id: string;
  description: string;
  domain: string;
  fields: string;
}

export interface IAssitantOptions {
  defaultWidth: number;
  defaultHeight: number;
  defaultTop: number;
  defaultLeft: number;
  draggable: boolean;
  title: string;
  maxWidth?: number | string;
  defaultChatInputPosition?: 'bottom' | undefined;
  showCompressionIcon?: boolean;
  showMoreIcon?: boolean;
  showNewChatIcon?: boolean;
  showHistoryIcon?: boolean;
}

export type IAssitantOptionsType = 'log_analysis' | 'query_string_generate';

export interface IAssitantInstance {
  open: (_sendMsg: boolean, _args: IRowSendData) => void;
  close: () => void;
  sendMessage: (_msg: string) => void;
  setCiteText: (_text: string) => void;
  show: () => void;
  updateOptions: (
    _options: Partial<IAssitantOptions>,
    _type: IAssitantOptionsType,
  ) => Promise<boolean>;
  getOptions: () => IAssitantOptions;
  isShown: () => boolean;
  setPosition: (
    _x?: number,
    _y?: number,
    _width?: number,
    _height?: number,
  ) => void;
  queryStringShowAiAssistant: (_args: IQueryStringSendData) => void;
}

export default defineComponent({
  setup(_props, { expose, emit }) {
    const aiBlueking = ref<InstanceType<typeof AIBlueking> | null>(null);

    let chatid = random(10);

    const isShow = ref(false);
    const isUpdated = ref(true);

    const defaultOptions = {
      defaultWidth: 400,
      defaultHeight: undefined,
      defaultTop: 0,
      defaultLeft: undefined,
      draggable: true,
      title: undefined,
      defaultChatInputPosition: undefined,
      maxWidth: 1000,
      showCompressionIcon: true,
      showMoreIcon: true,
      showNewChatIcon: true,
      showHistoryIcon: true,
    };

    const aiAssitantOptions = ref<IAssitantOptions>({ ...defaultOptions });

    const apiUrl = `${window.AJAX_URL_PREFIX || '/api/v1'}ai_assistant`;
    const shortcuts = ref<any[]>([...AI_BLUEKING_SHORTCUTS]);

    // 暂停聊天
    const handleStop = () => {
      aiBlueking.value?.handleStop();
    };

    const hiddenAiAssistant = () => {
      aiBlueking.value?.handleClose?.();
    };

    const handleClose = () => {
      isShow.value = false;
      emit('close');
    };

    const handleShow = () => {
      isShow.value = true;
      emit('show');
    };

    /**
     * 设置AI助手开始
     * @param sendMsg 是否发送消息
     * @param args 消息内容
     */
    const setAiStart = (sendMsg = false, args: IRowSendData) => {
      chatid = random(10);
      if (sendMsg) {
        aiBlueking.value?.handleShow(undefined, { isTemporary: true }).then(() => {
          const shortcut = structuredClone(AI_BLUEKING_SHORTCUTS[0]);
          shortcut.components.forEach((comp) => {
            const value = args[comp.key];
            if (value) {
              comp.default = typeof value === 'object'
                ? JSON.stringify(value).replace(/<\/?mark>/gim, '')
                : value;
            }
          });

          aiBlueking.value?.handleShortcutClick?.({
            shortcut,
            source: 'popup',
          });
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
        aiBlueking.value?.handleShow(undefined, { isTemporary: true });
      }

      aiBlueking.value?.handleSendMessage(msg);
    };

    /**
     * 设置引用文本
     * @param text
     */
    const setCiteText = (text: string) => {
      if (!isShow.value) {
        aiBlueking.value?.handleShow(undefined, { isTemporary: true });
      }

      aiBlueking.value?.setCiteText(text);
    };

    const isSameOptions = (options: Partial<IAssitantOptions> = {}) => {
      return isEqual(aiAssitantOptions.value, options);
    };

    /**
     * 更新选项
     * @param options 选项
     * @param type 类型 log_analysis 日志解读，query_string_generate 自然语言转查询语句
     * @returns
     */
    const updateOptions = (
      options: Partial<IAssitantOptions> = {},
      type: IAssitantOptionsType = 'log_analysis',
    ) => {
      if (type === 'query_string_generate') {
        shortcuts.value = [...AI_BLUEKING_QUERY_STRING];
      } else {
        shortcuts.value = [...AI_BLUEKING_SHORTCUTS];
      }

      const newOptions = {
        ...defaultOptions,
        ...options,
      };

      if (isSameOptions(newOptions)) {
        return Promise.resolve(true);
      }

      isUpdated.value = false;
      isShow.value = false;

      return new Promise((resolve) => {
        aiAssitantOptions.value = newOptions;
        nextTick(() => {
          isUpdated.value = true;
          resolve(true);
        });
      });
    };

    /**
     * 设置位置
     * @param x
     * @param y
     * @param width
     * @param height
     */
    const setPosition = (
      x?: number,
      y?: number,
      width?: number,
      height?: number,
    ) => {
      if (x !== undefined && y !== undefined) {
        aiBlueking.value?.updatePosition(x, y);
        aiAssitantOptions.value.defaultLeft = x;
        aiAssitantOptions.value.defaultTop = y;
      }

      if (width !== undefined && height !== undefined) {
        aiBlueking.value?.updateSize(width, height);
        aiAssitantOptions.value.defaultWidth = width;
        aiAssitantOptions.value.defaultHeight = height;
      }
    };

    /**
     * 自然语言转查询语句
     * @param args
     */
    const queryStringShowAiAssistant = (args: IQueryStringSendData) => {
      aiBlueking.value?.handleShow(undefined, { isTemporary: true }).then(() => {
        const shortcut = structuredClone(AI_BLUEKING_QUERY_STRING[0]);
        shortcut.components.forEach((comp) => {
          const value = args[comp.key];
          if (value) {
            comp.default = typeof value === 'object'
              ? JSON.stringify(value).replace(/<\/?mark>/gim, '')
              : value;
          }
        });

        try {
          aiBlueking.value?.handleShortcutClick?.({
            shortcut,
            source: 'popup',
          });
        } catch (error) {
          console.error(error);
        }
      });
    };

    expose({
      open: showAiAssistant,
      close: hiddenAiAssistant,
      sendMessage,
      setCiteText,
      show: () => aiBlueking.value?.handleShow(undefined, { isTemporary: true }),
      updateOptions,
      getOptions: () => aiAssitantOptions.value,
      isShown: () => isShow.value,
      setPosition,
      queryStringShowAiAssistant,
      isShow,
      aiBluekingInstance: aiBlueking,
    });

    return () => (
      <div class='bklog-ai-blueking-container'>
        {isUpdated.value && (
          <AIBlueking
            ref={aiBlueking}
            requestOptions={{
              beforeRequest: (data) => {
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
            onClose={handleClose}
            onShow={handleShow}
            defaultWidth={aiAssitantOptions.value.defaultWidth}
            defaultHeight={aiAssitantOptions.value.defaultHeight}
            defaultTop={aiAssitantOptions.value.defaultTop}
            defaultLeft={aiAssitantOptions.value.defaultLeft}
            draggable={aiAssitantOptions.value.draggable}
            title={aiAssitantOptions.value.title}
            maxWidth={aiAssitantOptions.value.maxWidth}
            defaultChatInputPosition={aiAssitantOptions.value.defaultChatInputPosition}
            showCompressionIcon={aiAssitantOptions.value.showCompressionIcon}
            showMoreIcon={aiAssitantOptions.value.showMoreIcon}
            showNewChatIcon={aiAssitantOptions.value.showNewChatIcon}
          />
        )}
      </div>
    );
  },
});
