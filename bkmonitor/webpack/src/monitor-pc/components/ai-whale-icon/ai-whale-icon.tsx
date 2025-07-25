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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import aiWhaleStore from '../../store/modules/ai-whale';

import './ai-whale-icon.scss';

interface AIWhaleIconProps {
  content: string;
  tip?: string;
  type: 'description' | 'explanation' | 'guideline';
}

@Component
export default class AIWhaleIcon extends tsc<AIWhaleIconProps> {
  @Prop({ required: true }) type!: AIWhaleIconProps['type']; // 功能
  @Prop({ required: true }) content!: string; // 内容
  @Prop({ default: '' }) tip?: string; // 提示信息
  // 是否显示AI智能助手
  get enableAiAssistant() {
    // return false; // 暂时不上线 等ai小鲸新模型调试好后
    return aiWhaleStore.enableAiAssistant;
  }
  /* 图标点击事件 */
  handleClick() {
    if (!this.enableAiAssistant) return;
    aiWhaleStore.setShowAIBlueking(true);
    if (this.type === 'guideline') {
      // 操作指引
      aiWhaleStore.sendMessage(`操作指引文案：“${this.content}”
当前场景：“策略配置”
请问为什么会触发当前的操作指引文案，后续可能出现什么情况，分别应该做什么操作`);
      return;
    }
    if (this.type === 'explanation') {
      // 名词解释
      aiWhaleStore.sendMessage(`名称解释文案：“${this.content}”
当前场景：“策略配置”
请提供该名词在当前场景下的详细解释，如果需要可参考知识库内容`);
      return;
    }
    if (this.type === 'description') {
      // 功能说明
      aiWhaleStore.sendMessage(`功能说明文案：“${this.content}”
当前场景：“策略配置”
请结合知识库内容和当前场景，详细介绍功能说明文案中的内容`);
      return;
    }
  }

  render() {
    const tips = this.enableAiAssistant && !this.tip ? this.$t('点击问AI小鲸') : this.tip;
    return (
      <i
        class={`icon-monitor ${this.enableAiAssistant ? 'icon-AI' : 'icon-tishi'} ai-whale-icon`}
        v-bk-tooltips={{
          content: tips,
          placement: 'top-start',
          maxWidth: '200',
          allowHTML: false,
          disabled: !tips,
        }}
        onClick={this.handleClick}
      />
    );
  }
}
