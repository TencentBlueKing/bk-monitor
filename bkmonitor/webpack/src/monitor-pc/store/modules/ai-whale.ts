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

import { Action, getModule, Module, Mutation, VuexModule } from 'vuex-module-decorators';

import GlobalConfigMixin from '../../mixins/globalConfig';
import store from '../store';

import type { AIBluekingShortcut } from '@/components/ai-whale/types';

const AI_USER_LIST = 'AI_USER_LIST';
const AI_BIZ_LIST = 'AI_BIZ_LIST';

// 定义模块
@Module({ name: 'aiWhale', dynamic: true, namespaced: true, store })
class AiWhaleStore extends VuexModule {
  aiBizList: string[] = null; // AI业务列表
  aiUserList: string[] = null; // AI用户列表
  customFallbackShortcut: Partial<AIBluekingShortcut> = {}; // 自定义快捷方式
  enableAiAssistant = false; // 初始化 enableAiAssistant 状态
  message = ''; // 会话内容
  showAIBlueking = false; // AI小鲸聊天框

  // Mutation: 处理发送消息
  @Mutation
  sendMessage(message: string) {
    this.message = message;
    this.showAIBlueking = true;
  }

  @Mutation
  setAiBizList(value: string[]) {
    this.aiBizList = value;
  }

  @Mutation
  setAiUserList(value: string[]) {
    this.aiUserList = value;
  }

  @Mutation
  setCustomFallbackShortcut(shortcut: Partial<AIBluekingShortcut>) {
    this.customFallbackShortcut = shortcut;
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
    const list = this.aiBizList ? this.aiBizList : await globalConfigModal.handleGetGlobalConfig<string[]>(AI_BIZ_LIST);
    !this.aiBizList && this.context.commit('setAiBizList', list);
    let userList = [];
    // 检查当前用户是否在 AI 用户列表中
    let isEnabled = this.context.rootGetters.bizId && list.some(item => +item === +this.context.rootGetters.bizId);
    if (!isEnabled) {
      userList = this.aiUserList
        ? this.aiUserList
        : await globalConfigModal.handleGetGlobalConfig<string[]>(AI_USER_LIST);
      isEnabled = userList.some(user => user === window.username || user === window.user_name);
      !this.aiUserList && this.context.commit('setAiUserList', userList);
    }
    // 如果 务列表和用户列表都为空，则默认开启
    if (!isEnabled && this.aiBizList?.length < 1 && this.aiUserList?.length < 1) {
      isEnabled = true;
    }
    // 通过 Mutation 设置 enableAiAssistant 的值
    this.context.commit('setEnableAiAssistant', isEnabled);
  }

  @Mutation
  setShowAIBlueking(value: boolean) {
    this.showAIBlueking = value;
  }
}

export default getModule(AiWhaleStore);
