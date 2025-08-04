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

import { random } from 'monitor-common/utils';
import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import GlobalConfigMixin from '../../mixins/globalConfig';
import store from '../store';

import type { AIQuickActionData } from '../../components/ai-whale/ai-whale';
const AI_USER_LIST = 'AI_USER_LIST';

// 定义模块
@Module({ name: 'aiWhale', dynamic: true, namespaced: true, store })
class AiWhaleStore extends VuexModule {
  aiQuickActionData: Partial<AIQuickActionData> = {}; // 储用于调用 AI 小鲸quickActions()的参数
  chartId = random(10); // 初始化 chartId，随机生成一个10位数
  enableAiAssistant = false; // 初始化 enableAiAssistant 状态
  loading = false; // 加载状态
  message = ''; // 会话内容
  showAIBlueking = false; // AI小鲸聊天框

  // Mutation: 处理发送消息
  @Mutation
  sendMessage(message: string) {
    this.message = message;
    this.showAIBlueking = true;
  }

  // Mutation: 设置默认消息
  @Mutation
  setDefaultMessage() {
    // this.messages = [
    //   {
    //     content: `${window.i18n.tc('你好，我是AI小鲸，你可以向我提问蓝鲸监控产品使用相关的问题。')}<br/>${window.i18n.tc('例如')}：<a href="javascript:;" data-ai='${JSON.stringify({ type: 'send', content: window.i18n.tc('监控策略如何使用？') })}' class="ai-clickable">${window.i18n.tc('监控策略如何使用？')}</a>`,
    //     role: RoleType.Assistant,
    //   },
    // ];
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
    const isEnabled = list.includes(window.username || window.user_name);
    // 通过 Mutation 设置 enableAiAssistant 的值
    this.context.commit('setEnableAiAssistant', isEnabled);
  }

  @Mutation
  setShowAIBlueking(value: boolean) {
    this.showAIBlueking = value;
  }
}

export default getModule(AiWhaleStore);
