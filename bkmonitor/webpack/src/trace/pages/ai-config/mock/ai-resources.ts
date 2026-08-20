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
import {
  AgentType,
  EnumCharacter,
  KnowledgebaseType,
  KnowledgePathType,
  KnowledgeType,
  ResourceStatus,
} from '@blueking/ai-ui-sdk/enums';

import type { IAgent, IKnowledgebase, ISkill } from '@blueking/ai-ui-sdk/types';

export const mockAgentList: IAgent[] = [
  {
    id: 1,
    agentCode: 'ai-dev-assistant',
    agentName: 'AI 开发助手',
    description: 'AI 开发助手，提供代码分析和问题排查能力',
    icon: '',
    agentType: AgentType.Single,
    userGuide: '',
    isBindBkSaas: false,
    tagNames: [],
    generateType: EnumCharacter.User,
    isPublic: false,
    status: ResourceStatus.Ready,
    createdBy: 'admin',
    createdAt: '2026-08-01T00:00:00Z',
    updatedBy: 'admin',
    updatedAt: '2026-08-01T00:00:00Z',
    permission: {},
    version: '1.0.0',
    latestVersion: '1.0.0',
    agentUrl: '',
    downloadUrl: '',
    tenantId: 'default',
    fromPaas: false,
  },
  {
    id: 2,
    agentCode: 'ai-test-assistant',
    agentName: 'AI 测试助手',
    description: 'AI 测试助手，提供测试用例生成和执行能力',
    icon: '',
    agentType: AgentType.Single,
    userGuide: '',
    isBindBkSaas: false,
    tagNames: [],
    generateType: EnumCharacter.User,
    isPublic: false,
    status: ResourceStatus.Ready,
    spaceId: '',
    createdBy: 'admin',
    createdAt: '2026-08-01T00:00:00Z',
    updatedBy: 'admin',
    updatedAt: '2026-08-01T00:00:00Z',
    permission: {},
    version: '1.0.0',
    latestVersion: '1.0.0',
    agentUrl: '',
    downloadUrl: '',
    tenantId: 'default',
    fromPaas: false,
  },
];

export const mockSkillList: ISkill[] = [
  {
    id: 1,
    skillName: '日志分析 Skill',
    skillCode: 'log-analysis-skill',
    description: '日志分析 Skill，提供日志检索和异常定位能力',
    icon: '',
    url: '',
    fileName: 'log-analysis-skill.zip',
    fileSize: 1024,
    fileType: 'zip',
    tagNames: [],
    generateType: EnumCharacter.User,
    isPublic: false,
    createdBy: 'admin',
    createdAt: '2026-08-01T00:00:00Z',
    updatedBy: 'admin',
    updatedAt: '2026-08-01T00:00:00Z',
    permission: {},
    envs: [
      {
        key: 'BKM_URL',
        description: '监控地址',
        required: false,
        default: '',
        secret: false,
        value: '111',
      },
      {
        key: 'USERNAME',
        description: '请求用户身份',
        required: true,
        default: '',
        secret: true,
        value: '********',
      },
    ],
  },
  {
    id: 2,
    skillName: '指标分析 Skill',
    skillCode: 'metric-analysis-skill',
    description: '指标分析 Skill，提供指标查询和趋势分析能力',
    icon: '',
    url: '',
    fileName: 'metric-analysis-skill.zip',
    fileSize: 2048,
    fileType: 'zip',
    tagNames: [],
    generateType: EnumCharacter.User,
    isPublic: false,
    createdBy: 'admin',
    createdAt: '2026-08-01T00:00:00Z',
    updatedBy: 'admin',
    updatedAt: '2026-08-01T00:00:00Z',
    permission: {},
  },
  {
    id: 3,
    skillName: '数据查询 Skill',
    skillCode: 'data-query-skill',
    description: '数据查询 Skill，提供蓝鲸数据平台数据获取能力',
    icon: '',
    url: '',
    fileName: 'data-query-skill.zip',
    fileSize: 3072,
    fileType: 'zip',
    tagNames: [],
    generateType: EnumCharacter.User,
    isPublic: false,
    createdBy: 'admin',
    createdAt: '2026-08-01T00:00:00Z',
    updatedBy: 'admin',
    updatedAt: '2026-08-01T00:00:00Z',
    permission: {},
    envs: [
      {
        key: 'BKM_URL',
        description: '蓝鲸监控地址',
        required: false,
        default: '',
        secret: false,
        value: '111',
      },
      {
        key: 'USERNAME',
        description: '请求用户身份',
        required: true,
        default: '',
        secret: true,
        value: '********',
      },
    ],
  },
];

export const mockKnowledgebaseList: IKnowledgebase[] = [
  {
    id: 1,
    knowledgebaseId: 1,
    knowledgebaseCode: 'troubleshooting-kb',
    spaceId: 'default',
    anchorPath: '/troubleshooting-kb',
    parentAnchorPath: '/',
    filePath: '/troubleshooting-kb',
    fileName: '故障排查知识库',
    fileType: 'folder',
    pipelineCodes: {},
    updateFrequency: 7,
    name: '故障排查知识库',
    type: KnowledgebaseType.Default,
    status: ResourceStatus.Ready,
    approvers: ['admin'],
    ticketUrl: '',
    generateType: EnumCharacter.User,
    isPublic: false,
    pathType: KnowledgePathType.Folder,
    createdType: KnowledgeType.Manual,
    number: 0,
    description: '常见故障场景与排查指引',
    folderNumber: 0,
    url: '',
    updatedBy: 'admin',
    updatedAt: '2026-08-01T00:00:00Z',
    indexConfig: {
      vector_indexes: [],
      scalar_indexes: [],
      full_text_indexes: [],
    },
    permission: {},
    children: [],
  },
  {
    id: 2,
    knowledgebaseId: 2,
    knowledgebaseCode: 'monitor-ops-kb',
    spaceId: 'default',
    anchorPath: '/monitor-ops-kb',
    parentAnchorPath: '/',
    filePath: '/monitor-ops-kb',
    fileName: '运维知识库',
    fileType: 'folder',
    pipelineCodes: {},
    updateFrequency: 7,
    name: '运维知识库',
    type: KnowledgebaseType.Default,
    status: ResourceStatus.Ready,
    approvers: ['admin'],
    ticketUrl: '',
    generateType: EnumCharacter.User,
    isPublic: false,
    pathType: KnowledgePathType.Folder,
    createdType: KnowledgeType.Manual,
    number: 0,
    description: '运维操作手册',
    folderNumber: 0,
    url: '',
    updatedBy: 'admin',
    updatedAt: '2026-08-01T00:00:00Z',
    indexConfig: {
      vector_indexes: [],
      scalar_indexes: [],
      full_text_indexes: [],
    },
    permission: {},
    children: [],
  },
];

/* ---------- 资源详情批量查询 mock 函数（与真实接口同签名，services 替换 import 来源即可切换） ---------- */

/** 模拟网络延迟（ms） */
const MOCK_LATENCY = 300;

/** mock 成功响应：延迟后 resolve */
const mockResolve = <T>(data: T): Promise<T> =>
  new Promise(resolve => {
    setTimeout(() => resolve(data), MOCK_LATENCY);
  });

/**
 * @description 批量查询智能体详情（mock）：按 id 过滤，未传 id 时返回全部
 * @description 真实接口：`POST {apiPrefix}/agent/v1/agent/batch/`
 * @param {number[]} [agentIds] 智能体 ID 列表
 * @returns {Promise<IAgent[]>} 智能体详情列表
 */
export const getAgentsByIds = (agentIds?: number[]): Promise<IAgent[]> =>
  mockResolve(agentIds ? mockAgentList.filter(item => agentIds.includes(item.id)) : [...mockAgentList]);

/**
 * @description 批量查询 Skill 详情（mock）：按 id 过滤，未传 id 时返回全部
 * @description 真实接口：`POST {apiPrefix}/skill/v1/skill/batch/`
 * @param {number[]} [skillIds] Skill ID 列表
 * @returns {Promise<ISkill[]>} Skill 详情列表
 */
export const getSkillsByIds = (skillIds?: number[]): Promise<ISkill[]> =>
  mockResolve(skillIds ? mockSkillList.filter(item => skillIds.includes(item.id)) : [...mockSkillList]);

/**
 * @description 批量查询知识库详情（mock）：按 id 过滤，未传 id 时返回全部
 * @description 真实接口：`POST {apiPrefix}/knowledgebase/v1/knowledgebase/batch/`
 * @param {number[]} [knowledgebaseIds] 知识库 ID 列表
 * @returns {Promise<IKnowledgebase[]>} 知识库详情列表
 */
export const getKnowledgebasesByIds = (knowledgebaseIds?: number[]): Promise<IKnowledgebase[]> =>
  mockResolve(
    knowledgebaseIds
      ? mockKnowledgebaseList.filter(item => knowledgebaseIds.includes(item.id))
      : [...mockKnowledgebaseList]
  );
