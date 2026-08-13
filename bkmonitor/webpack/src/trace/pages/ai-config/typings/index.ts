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
/** AI 设置页面的 Tab */
export enum EAiConfigTab {
  /** 异常检测 */
  anomalyDetection = 'anomaly-detection',
  /** 源码 AI 分析 */
  sourceCodeAnalysis = 'source-code-analysis',
}

/** 智能检测方案所属的算法类型 */
export enum EIntelligentAlgorithm {
  /** 单指标异常检测 */
  intelligentDetect = 'IntelligentDetect',
  /** 场景智能异常检测 */
  multivariateAnomalyDetection = 'MultivariateAnomalyDetection',
}

/** 场景智能异常检测支持的场景，当前后端仅支持主机 */
export type SceneType = 'host';

/** 场景智能异常检测的场景列表，渲染顺序与此一致 */
export const SCENE_TYPES: SceneType[] = ['host'];

/** 场景名称，值为 i18n key，需在使用处经 t() 转换 */
export const SCENE_NAME_MAP: Record<SceneType, string> = {
  host: '主机',
};

/** AI 设置接口数据结构 */
export interface IAiSetting {
  kpi_anomaly_detection: IAnomalyDetectionConfig;
  multivariate_anomaly_detection: Partial<Record<SceneType, IAnomalyDetectionConfig>>;
}

/** 单项检测配置，除默认方案外的字段（敏感度、检测对象等）当前不在表单中呈现，保存时原样透传 */
export interface IAnomalyDetectionConfig {
  [key: string]: unknown;
  default_plan_id: number;
}

/** 场景智能异常检测的表单项 */
export interface ISceneFormItem {
  planId: PlanIdValue;
  type: SceneType;
}

/** 智能检测方案 */
export interface ISchemeItem {
  description: string;
  id: number;
  name: string;
  ts_depend: string;
  ts_freq: number;
}

/** 方案 id 的表单取值，空串代表未选择 */
export type PlanIdValue = '' | number;

/** 查询蓝盾项目的请求参数 */
export type TBkciProjectsParams = {
  /** 搜索关键字 */
  keyword: string;
  /** 页码 */
  page: number;
  /** 每页数量 */
  page_size: number;
};
/** 查询蓝盾项目的返回结果 */
export type TBkciProjectsResult = {
  /** 蓝盾项目列表 */
  list: { id: string; name: string }[];
  /** 总数 */
  total: number;
};

/** 查询源码仓库的请求参数 */
export type TBkciRepositoriesParams = {
  /** 蓝盾项目 id */
  bkci_project_id: string;
  /** 搜索关键字 */
  keyword: string;
  /** 页码 */
  page: number;
  /** 每页数量 */
  page_size: number;
};

/** 查询源码仓库的返回结果 */
export type TBkciRepositoriesResult = {
  /** 源码仓库列表 */
  list: { default_branch: string; id: string; name: string; scm_type: string }[];
  /** 总数 */
  total: number;
};

/** 查询源码分析配置的返回结果 */
export type TGetSourceAnalysisConfigResult = {
  /** 业务 id */
  bk_biz_id: number;
  /** 蓝盾项目 id，未配置时为空 */
  bkci_project_id: null | string;
  /** 源码仓库别名，未配置时为空 */
  repository_alias: null | string;
  /** 更新时间戳，未配置时为空 */
  updated_at: null | number;
  /** 更新人，未配置时为空 */
  updated_by: null | string;
};

export type TSaveSourceAnalysisConfigParams = {
  bkci_project_id: string;
  repository_alias: string;
};

/** 源码分析规则匹配条件 */
export type TSourceAnalysisCondition = {
  /** 条件连接符，如 and / or */
  condition: string;
  /** 匹配字段 */
  field: string;
  /** 匹配方法，如 eq / contains */
  method: string;
  /** 匹配值列表 */
  value: string[];
};

/** 源码分析规则 */
export type TSourceAnalysisRule = {
  /** 智能体 id */
  agent_id: string;
  /** 业务 id */
  bk_biz_id: number;
  /** 蓝盾项目 id */
  bkci_project_id: string;
  /** 匹配条件列表 */
  conditions: TSourceAnalysisCondition[];
  /** 创建时间戳 */
  created_at: number;
  /** 创建人 */
  created_by: string;
  /** 规则 id */
  id: number;
  /** 是否为默认规则 */
  is_default: boolean;
  /** 是否启用 */
  is_enabled: boolean;
  /** 关联知识库 id 列表 */
  knowledge_base_ids: string[];
  /** 优先级 */
  priority: number;
  /** 源码仓库别名 */
  repository_alias: string;
  /** 关联 skill id 列表 */
  skill_ids: string[];
  /** 更新时间戳 */
  updated_at: number;
  /** 更新人 */
  updated_by: string;
};
