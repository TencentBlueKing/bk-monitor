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

import { requestJson } from '@/request';
import { IQueryStringSendData } from '.';
import {
  ChatCompletionParams,
  SessionContentData,
  SessionContentParams,
  SessionData,
  TextToQueryResponse,
} from './interface';
import { FetchResponse } from '@/request/types';

/**
 * @description 生成会话代码
 * @returns {string}
 */
const getSessionCode = () => {
  // 生成一个随机的 session_code，格式为：'xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx'
  const generateHex = (length) => {
    let result = '';
    for (let i = 0; i < length; i++) {
      result += ((Math.random() * 16) | 0).toString(16);
    }
    return result;
  };
  const segment1 = generateHex(8);
  const segment2 = generateHex(4);
  const segment3 = generateHex(4);
  const segment4 = `${((Math.random() * 4) | (0 + 8)).toString(16)}${generateHex(3)}`;
  const segment5 = generateHex(12);
  return `${segment1}-${segment2}-${segment3}-${segment4}-${segment5}`;
};

/**
 * @description 解析响应数据
 * @param resp {FetchResponse<T>}
 * @returns {T}
 */
const resolveResponse = <T = any>(resp: FetchResponse<T>) => {
  if (typeof resp.result === 'boolean' && resp.result) {
    return resp.data;
  }

  if (resp.result === undefined) {
    return resp as T;
  }

  throw new Error(resp.message);
};

/**
 * @description 创建新会话
 */
export const createSession = (): Promise<FetchResponse<SessionData>> => {
  const url = '/ai_assistant/session/';
  const params = {
    created_at: new Date().toISOString(),
    is_temporary: true,
    session_code: getSessionCode(),
    session_name: '新会话',
    session_property: {},
    updated_at: new Date().toISOString(),
  };
  return requestJson({ url, params });
};

/**
 * @description 创建会话内容
 * @param {SessionContentParams} params
 * @returns {Promise<FetchResponse<SessionContentData>>}
 */
export const createSessionContent = (params: SessionContentParams): Promise<FetchResponse<SessionContentData>> => {
  const url = '/ai_assistant/session_content/';
  return requestJson({ url, params });
};

/**
 * @description 请求聊天完成
 * @param {ChatCompletionParams} params
 * @returns {Promise<FetchResponse<ChatCompletionData>>}
 */
export const requestChatCompletion = (params: ChatCompletionParams): Promise<FetchResponse<TextToQueryResponse>> => {
  const url = '/ai_assistant/chat_completion/';
  return requestJson({ url, params });
};

/**
 * @description 获取会话上下文参数
 * @param args {IQueryStringSendData & { keyword: string }}
 * @param sessionCode string
 * @returns {SessionContentParams}
 */
const getSessionContextParams = (args: IQueryStringSendData & { keyword: string }, sessionCode: string) => {
  return {
    session_code: sessionCode,
    role: 'user',
    content: args.description,
    property: {
      extra: {
        context: [
          {
            index_set_id: args.index_set_id,
            context_type: 'textarea',
            __label: 'index_set_id',
            __key: 'index_set_id',
            __value: args.index_set_id,
          },
          {
            description: args.keyword,
            context_type: 'textarea',
            __label: '检索需求',
            __key: 'description',
            __value: args.keyword,
          },
          {
            domain: args.domain,
            context_type: 'textarea',
            __label: 'domain',
            __key: 'domain',
            __value: args.domain,
          },
          {
            fields: args.fields,
            context_type: 'textarea',
            __label: 'fields',
            __key: 'fields',
            __value: args.fields,
          },
        ],
        cite: {
          title: '自然语言转查询语句',
          type: 'structured',
          data: [
            {
              key: '检索需求',
              value: args.keyword,
            },
          ],
        },
        command: 'querystring_generate_json',
      },
    },
  };
};

/**
 * @description 请求 AI 结果
 * @param args {IQueryStringSendData & { keyword: string }}
 * @returns {Promise<TextToQueryResponse>}
 */
export const requestAIResult = (args: IQueryStringSendData & { keyword: string }): Promise<TextToQueryResponse> => {
  return createSession().then((resp) => {
    const sessionData = resolveResponse(resp);
    return createSessionContent(getSessionContextParams(args, sessionData.session_code)).then((resp) => {
      const sessionContentData = resolveResponse(resp);
      return requestChatCompletion({
        session_content_id: sessionContentData.id,
        session_code: sessionData.session_code,
        execute_kwargs: {
          stream: false,
        },
      }).then((resp) => {
        return resolveResponse(resp);
      });
    });
  });
};
