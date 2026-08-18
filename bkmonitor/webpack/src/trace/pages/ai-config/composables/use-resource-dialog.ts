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
import { computed, shallowRef } from 'vue';

import { Module } from '@blueking/ai-ui-sdk/enums';

import { MODULE_CONFIG } from '../constants';

import type { AiResourceType, SourceAnalysisRuleDto } from '../typings';
import type { IAgent, IKnowledgebase, ISkill } from '@blueking/ai-ui-sdk/types';

/** 弹窗确认事件数据 */
export interface IResourceDialogConfirmData {
  /** 已选智能体列表 */
  agents: IAgent[];
  /** 已选知识库列表 */
  knowledgebases: IKnowledgebase[];
  /** 已选 Skill 列表 */
  skills: ISkill[];
}

export interface IUseResourceDialogOptions {
  addResource: <T extends AiResourceType>(resourceType: T, resourceValue: SourceAnalysisRuleDto[T]) => void;
}

/**
 * @description 资源选择弹窗状态管理
 * 封装 RenderResourceDialog 的显隐、模块切换、确认回写等逻辑，宿主只需提供确认回调即可。
 */
export const useResourceDialog = ({ addResource }: IUseResourceDialogOptions) => {
  /** 弹窗是否可见 */
  const dialogIsShow = shallowRef(false);
  /** 当前资源模块 */
  const dialogModule = shallowRef<Module>(Module.Agent);
  /** 是否多选，智能体单选（agent_id 为单值），Skill / 知识库多选。 */
  const dialogMultiple = computed(() => dialogModule.value !== Module.Agent);

  /**
   * @description 打开对应模块的资源选择弹窗
   * @param {Module} m 资源模块
   */
  const handleOpenResourceDialog = (m: Module) => {
    dialogModule.value = m;
    dialogIsShow.value = true;
  };

  /**
   * @description 关闭弹窗
   */
  const handleCloseResourceDialog = () => {
    dialogIsShow.value = false;
  };

  /**
   * @description 弹窗确认：按当前模块从确认数据中提取资源值，写回规则后关闭弹窗
   * @param {IResourceDialogConfirmData} data 弹窗回传的已选资源
   */
  const handleDialogConfirm = (data: IResourceDialogConfirmData) => {
    const config = MODULE_CONFIG[dialogModule.value];
    if (config) {
      const items = data[config.field];
      const value = config.single ? (items[0] ? String(items[0].id) : '') : items.map(item => String(item.id));
      addResource(config.resource, value as SourceAnalysisRuleDto[AiResourceType]);
    }
    handleCloseResourceDialog();
  };

  return {
    /** 弹窗是否可见 */
    dialogIsShow,
    /** 当前资源模块 */
    dialogModule,
    /** 是否多选 */
    dialogMultiple,
    /** 打开对应模块的资源选择弹窗 */
    handleOpenResourceDialog,
    /** 关闭弹窗 */
    handleCloseResourceDialog,
    /** 弹窗确认：提取资源值并写回规则 */
    handleDialogConfirm,
  };
};
