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
import { computed, defineComponent, ref } from 'vue';

import AIBlueking, { ChatHelper, MessageStatus, RoleType } from '@blueking/ai-blueking/vue2';

import { random } from '../common/util';

import './ai-assistant.scss';
import '@blueking/ai-blueking/dist/vue2/style.css';

interface ISendData {
  content: string; // 用户输入的内容
  cite?: string; // 引用的内容
  prompt?: string; // 使用的 prompt 模板
}

interface IRowSendData {
  space_uid: string;
  index_set_id: string;
  log_data: unknown;
  query: string;
  index: number;
  type: string;
  chat_context: unknown;
  'chat_context.role': RoleType;
  'chat_context.content': string;
}
export default defineComponent({
  setup(props, { expose, emit }) {
    const loading = ref(false);
    const messages = ref([]);
    const storeMsg = ref([]);

    const prompts = ref([]);
    let chatid = random(10);

    const top = 2;
    const left = window.innerWidth - 900;

    const startPosition = ref({ top, bottom: 4, left: left > 0 ? left : 100, right: 4 });
    const isShow = ref(false);
    const aiFixedLinkArgs = { index: null, id: null };
    const cachedArgs: Partial<IRowSendData> = {};

    const concatMsg = computed(() => [...storeMsg.value, ...messages.value]);

    const handleStart = () => {
      loading.value = true;
      const msg = {
        role: RoleType.Assistant,
        content: '正在分析...',
        status: MessageStatus.Loading,
      };
      messages.value.push(msg);
    };

    // 接收消息
    const handleReceiveMessage = (message: string, id: number | string) => {
      if (id !== chatid) {
        chatHelper.stop(id);
        return;
      }

      const currentMessage = messages.value.at(-1);
      if (currentMessage.status === MessageStatus.Loading) {
        // 如果是loading状态，直接覆盖
        currentMessage.content = message;
        currentMessage.status = MessageStatus.Success;
      } else if (currentMessage.status === MessageStatus.Success) {
        // 如果是后续消息，就追加消息
        currentMessage.content += message;
      }
    };

    // 聊天结束
    const handleEnd = (id: number | string, message?: string) => {
      if (id !== chatid) {
        return;
      }

      loading.value = false;
      const currentMessage = messages.value.at(-1);
      if (message) {
        // done 的情况下，返回 message，直接覆盖
        currentMessage.content = message;
        currentMessage.status = MessageStatus.Success;
      } else if (currentMessage.status === MessageStatus.Loading) {
        // loading 情况下终止
        currentMessage.content = '聊天内容已中断...';
        currentMessage.status = MessageStatus.Error;
      }
    };

    // 错误处理
    const handleError = (message: string, code: number | string, id: number | string) => {
      if (id !== chatid) {
        return;
      }

      if (message.includes('user authentication failed')) {
        // 未登录，跳转登录
        const loginUrl = new URL(process.env.BK_LOGIN_URL);
        loginUrl.searchParams.append('c_url', location.origin);
        window.location.href = loginUrl.href;
      } else {
        // 处理错误消息
        const currentMessage = messages.value.at(-1);
        currentMessage.status = MessageStatus.Error;
        currentMessage.content = message;
        loading.value = false;
      }
    };

    const prefix = window.AJAX_URL_PREFIX || '/api/v1';
    const chatHelper = new ChatHelper(
      `${prefix}ai_assistant/chat/`,
      handleStart,
      handleReceiveMessage,
      handleEnd,
      handleError,
    );

    const handleChoosePrompt = () => {};

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

    // 清空消息
    const handleClear = () => {
      storeMsg.value = [];
      const lastMesg = messages.value.at(-1);
      messages.value = [];
      if (lastMesg.status === MessageStatus.Loading) {
        messages.value.push(lastMesg);
      }

      messages.value.unshift({
        role: RoleType.User,
        content: getFixedRow(),
        status: MessageStatus.Success,
        isFixedMsg: true,
      });

      if (messages.value.length % 2 === 1) {
        messages.value.push({
          role: RoleType.Assistant,
          content: '您已清空历史会话，系统将继续按照上方初始日志响应问答...',
          status: MessageStatus.Success,
        });
      }
    };

    // 发送消息
    const handleSend = (args: ISendData) => {
      // 记录当前消息记录
      const chatHistory = [...messages.value];
      // 添加一条消息
      messages.value.push({
        role: 'user',
        content: args.content,
        cite: args.cite,
      });

      // 根据参数构造输入内容
      const input = args.prompt
        ? args.prompt // 如果有 prompt，直接使用
        : args.cite
          ? `${args.content}: ${args.cite}` // 如果有 cite，拼接 content 和 cite
          : args.content; // 否则只使用 content

      const { space_uid, index_set_id, log_data, type } = cachedArgs;
      const streamArgs = {
        query: input,
        chat_context: chatHistory,
        space_uid,
        index_set_id,
        log_data,
        type,
        'chat_context.role': RoleType.User,
      };

      // ai 消息，id是唯一标识当前流，调用 chatHelper.stop 的时候需要传入
      chatHelper.stream(streamArgs, chatid, { 'X-Requested-With': 'XMLHttpRequest' });
    };

    // 外部调用启动首次聊天
    // args：Partial<IRowSendData>
    const handleSendRowAi = (args: Partial<IRowSendData>) => {
      const lastMesg = messages.value.at(-1);
      if (lastMesg?.isFixedMsg) {
        messages.value.pop();
      }

      // 记录当前消息记录
      args['chat_context.role'] = RoleType.User;
      args.query = '帮我分析这条日志';

      messages.value.push({
        role: RoleType.User,
        content: getFixedRow(),
        status: MessageStatus.Loading,
        isFixedMsg: true,
      });

      // ai 消息，id是唯一标识当前流，调用 chatHelper.stop 的时候需要传入
      chatHelper.stream(args, chatid, { 'X-Requested-With': 'XMLHttpRequest' });
    };

    // 暂停聊天
    const handleStop = () => {
      chatHelper.stop(chatid);
    };

    const handleClose = () => {
      handleStop();
      isShow.value = false;
      storeMsg.value.push(...messages.value);
      messages.value = [];
      chatid = null;
      emit('close');
    };

    const setAiStart = (sendMsg = false, args: IRowSendData) => {
      chatid = random(10);
      isShow.value = true;
      if (sendMsg) {
        args.type = 'log_interpretation';
        Object.assign(cachedArgs, args);
        Object.assign(aiFixedLinkArgs, { index: args.index, id: chatid });
        handleSendRowAi(args);
      }
    };

    const handleScroll = () => {};
    const showAiAssistant = (sendMsg = false, args: IRowSendData) => {
      if (isShow.value && chatid) {
        handleStop();
        storeMsg.value.push(...messages.value);
        messages.value = [];
        setTimeout(() => {
          setAiStart(sendMsg, args);
        });
        return;
      }

      setAiStart(sendMsg, args);
    };

    const hiddenAiAssistant = () => {
      isShow.value = false;
    };

    const handleAiClick = args => {
      console.log('handleAiClick', args);
    };

    expose({
      open: showAiAssistant,
      close: hiddenAiAssistant,
    });

    return () => (
      <AIBlueking
        background='#f5f7fa'
        enable-popup={false}
        head-background='linear-gradient(267deg, #2dd1f4 0%, #1482ff 95%)'
        is-show={isShow.value}
        loading={loading.value}
        messages={concatMsg.value}
        prompts={prompts.value}
        startPosition={startPosition.value}
        on-ai-click={handleAiClick}
        on-choose-prompt={handleChoosePrompt}
        on-clear={handleClear}
        on-close={handleClose}
        on-scroll={handleScroll}
        on-send={handleSend}
        on-stop={handleStop}
      />
    );
  },
});
