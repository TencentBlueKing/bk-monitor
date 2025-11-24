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

/**
 * 角色内容项
 */
export interface RoleContent {
  id: number | null;
  role: string;
  content: string;
  extra: any | null;
}

/**
 * 角色信息
 */
export interface RoleInfo {
  role_id: number;
  role_name: string;
  role_variable: any[];
  role_content: RoleContent[];
  status: string;
  generate_type: string;
}

/**
 * 会话属性
 */
export interface SessionProperty {
  is_auto_clear: boolean;
  is_auto_clac_prompt: boolean;
}

/**
 * 会话数据
 */
export interface SessionData {
  created_by: string;
  updated_by: string;
  created_at: string;
  updated_at: string;
  session_code: string;
  session_name: string;
  model: string;
  role_info: RoleInfo;
  session_property: SessionProperty;
}

/**
 * 引用数据项
 */
export interface CiteDataItem {
  key: string;
  value: string;
}

/**
 * 引用信息
 */
export interface Cite {
  type: string;
  title: string;
  data: CiteDataItem[];
}

/**
 * 上下文项
 */
export interface ContextItem {
  [key: string]: string | number;
  context_type: string;
  __label: string;
  __key: string;
  __value: string | number;
}

/**
 * 额外信息
 */
export interface Extra {
  cite?: Cite;
  command: string;
  context: ContextItem[];
  anchor_path_resources?: Record<string, any>;
}

/**
 * 会话内容属性
 */
export interface SessionContentProperty {
  extra?: Extra;
}

/**
 * 创建会话内容请求参数
 */
export interface SessionContentParams {
  session_code: string;
  role: string;
  content: string;
  property: SessionContentProperty;
}

/**
 * 会话内容数据
 */
export interface SessionContentData {
  id: number;
  session_code: string;
  role: string;
  content: string;
  property: SessionContentProperty;
  created_at?: string;
  updated_at?: string;
}

export interface ChatCompletionParams {
  session_content_id: number;
  session_code: string;
  execute_kwargs: {
    stream: boolean;
  };
}

/**
 * 自然语言转查询语句响应
 */
export interface TextToQueryResponse {
  model: string;
  id: string;
  choices: {
    delta: {
      content: string;
      role: string;
    };
  }[];
}
