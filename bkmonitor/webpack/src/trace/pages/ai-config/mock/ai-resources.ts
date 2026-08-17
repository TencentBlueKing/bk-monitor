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
    fileName: '监控运维知识库',
    fileType: 'folder',
    pipelineCodes: {},
    updateFrequency: 7,
    name: '监控运维知识库',
    type: KnowledgebaseType.Default,
    status: ResourceStatus.Ready,
    approvers: ['admin'],
    ticketUrl: '',
    generateType: EnumCharacter.User,
    isPublic: false,
    pathType: KnowledgePathType.Folder,
    createdType: KnowledgeType.Manual,
    number: 0,
    description: '监控平台运维操作手册',
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
