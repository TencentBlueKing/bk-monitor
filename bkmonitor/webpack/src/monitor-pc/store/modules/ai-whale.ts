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
import { ChatHelper, type IMessage, type ISendData, MessageStatus, RoleType } from '@blueking/ai-blueking/vue2';
import { getCookie, random } from 'monitor-common/utils';
import { Action, Module, Mutation, VuexModule, getModule } from 'vuex-module-decorators';

import GlobalConfigMixin from '../../mixins/globalConfig';
import store from '../store';
const AI_USER_LIST = 'AI_USER_LIST';

// 定义模块
@Module({ name: 'ai-whale', dynamic: true, namespaced: true, store })
class AiWhaleStore extends VuexModule {
  chartId = random(10); // 初始化 chartId，随机生成一个10位数
  chatHelper = null; // chatHelper 实例
  enableAiAssistant = false; // 初始化 enableAiAssistant 状态
  loading = false; // 加载状态

  messages: IMessage[] = []; // 消息列表

  showAIBlueking = false; // AI小鲸聊天框

  // Mutation: 添加消息到 messages 列表
  @Mutation
  addMessage(message: IMessage) {
    this.messages.push(message);
  }

  // Mutation: 处理发送消息
  @Mutation
  handleAiBluekingSend(message: ISendData) {
    // 记录当前消息记录
    // const chatHistory = [...this.messages];
    // 添加一条消息
    this.messages.push({
      role: RoleType.User,
      content: message.content,
      cite: message.cite,
    });

    // 根据参数构造输入内容
    const input = message.prompt
      ? message.prompt // 如果有 prompt，直接使用
      : message.cite
        ? `${message.content}: ${message.cite}` // 如果有 cite，拼接 content 和 cite
        : message.content;

    // ai 消息，id是唯一标识当前流，调用 chatHelper.stop 的时候需要传入
    this.chatHelper.stream(
      {
        query: input,
        type: 'nature',
        polish: true,
        stream: true,
        bk_biz_id: window.bk_biz_id,
      },
      this.chartId,
      {
        'X-CSRFToken': window.csrf_token || getCookie(window.csrf_cookie_name),
        'X-Requested-With': 'XMLHttpRequest',
        'Source-App': window.source_app,
      }
    );
  }

  // Action: 初始化 Stream Chat Helper
  @Action
  initStreamChatHelper() {
    // 聊天开始
    const handleStart = () => {
      this.context.commit('setLoading', true);
      this.context.commit('addMessage', {
        role: RoleType.Assistant,
        content: window.i18n.tc('内容正在生成中...'),
        status: MessageStatus.Loading,
      });
    };

    // 接收消息
    const handleReceiveMessage = (message: string) => {
      const currentMessage = this.messages.at(-1);
      if (currentMessage.content === window.i18n.tc('内容正在生成中...')) {
        // 如果是 loading 状态，直接覆盖
        this.context.commit('updateLastMessage', { content: message, status: MessageStatus.Loading });
      } else if (currentMessage.status === 'loading') {
        // 如果是后续消息，就追加消息
        this.context.commit('updateLastMessage', {
          content: currentMessage.content + message,
          status: MessageStatus.Loading,
        });
      }
    };

    // 聊天结束
    const handleEnd = () => {
      const currentMessage = this.messages.at(-1);
      if (currentMessage.content === window.i18n.tc('内容正在生成中...')) {
        this.context.commit('updateLastMessage', { content: '聊天内容已中断', status: MessageStatus.Error });
      } else {
        this.context.commit('updateLastMessage', { content: currentMessage.content, status: MessageStatus.Success });
      }
      this.context.commit('setLoading', false);
    };

    // 错误处理
    const handleError = (message: string) => {
      if (message.includes('user authentication failed')) {
        // 未登录，跳转登录
        const loginUrl = new URL(process.env.BK_LOGIN_URL);
        loginUrl.searchParams.append('c_url', location.origin);
        window.location.href = loginUrl.href;
      } else {
        this.context.commit('updateLastMessage', { content: message, status: MessageStatus.Error });
        this.context.commit('setLoading', false);
      }
    };

    // 初始化 chatHelper 实例
    const chatHelper = new ChatHelper(
      `${window.site_url}rest/v2/ai_assistant/chat/chat_v2/`,
      handleStart,
      handleReceiveMessage,
      handleEnd,
      handleError
    );

    this.context.commit('setChatHelper', chatHelper);
  }

  // Mutation: 设置 chatHelper 实例
  @Mutation
  setChatHelper(chatHelper: any) {
    this.chatHelper = chatHelper;
  }

  // Mutation: 设置默认消息
  @Mutation
  setDefaultMessage() {
    this.messages = [
      {
        content: `${window.i18n.tc('你好，我是AI小鲸，你可以向我提问蓝鲸监控产品使用相关的问题。')}<br/>${window.i18n.tc('例如')}：<a href="javascript:;" data-ai='${JSON.stringify({ type: 'send', content: window.i18n.tc('监控策略如何使用？') })}' class="ai-clickable">${window.i18n.tc('监控策略如何使用？')}</a>`,
        role: RoleType.Assistant,
      },
    ];
  }

  // Mutation: 设置 enableAiAssistant 的值
  @Mutation
  setEnableAiAssistant(value: boolean) {
    this.enableAiAssistant = value;
  }

  // Action: 异步设置 enableAiAssistant
  @Action
  async setEnableAiAssistantAction() {
    if (!window.enable_ai_assistant) {
      this.context.commit('setEnableAiAssistant', false);
      return;
    }

    // 获取全局配置中的 AI 用户列表
    const globalConfigModal = new GlobalConfigMixin();

    const list: string[] = await globalConfigModal.handleGetGlobalConfig<string[]>(AI_USER_LIST);

    // 检查当前用户是否在 AI 用户列表中
    const isEnabled = list.includes(window.username);

    // 通过 Mutation 设置 enableAiAssistant 的值
    this.context.commit('setEnableAiAssistant', isEnabled);
  }

  // Mutation: 设置加载状态
  @Mutation
  setLoading(loading: boolean) {
    this.loading = loading;
  }

  @Mutation
  setShowAIBlueking(value: boolean) {
    this.showAIBlueking = value;
  }

  // Mutation: 更新最后一条消息的内容和状态
  @Mutation
  updateLastMessage({ content, status }: { content: string; status: MessageStatus }) {
    const currentMessage = this.messages.at(-1);
    currentMessage.content = content;
    currentMessage.status = status;
  }
}

export default getModule(AiWhaleStore);
