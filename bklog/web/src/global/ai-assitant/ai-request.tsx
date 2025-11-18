import { random } from '@/common/util';
import store from '@/store';
import { IQueryStringSendData } from '.';
import { ChatCompletionParams, FetchResponse, SessionContentData, SessionContentParams, SessionData, TextToQueryResponse } from './interface';


const baseURL = window.AJAX_URL_PREFIX || '/api/v1';
const xsrfCookieName = 'bklog_csrftoken';
const xsrfHeaderName = 'X-CSRFToken';

/**
 * 获取Cookie
 * @param {String} name
 */
const getCookie = (name: string): string | null => {
  const reg = new RegExp(`(^|)${name}=([^;]*)(;|$)`);
  const data = document.cookie.match(reg);
  if (data) {
    return unescape(data[2]);
  }
  return null;
};

/**
 * 构建请求配置（模拟 axios 拦截器逻辑）
 */
const buildRequestConfig = (url: string, params?: any, method: 'POST' | 'GET' = 'POST') => {
  // URL 处理（对应 axios 拦截器中的 URL 检查）
  // if (!/^(https|http)?:\/\//.test(url)) {
  //   const prefix = url.indexOf('?') === -1 ? '?' : '&';
  // }
  const fullUrl = `${baseURL}${url}`;

  // 构建 headers（对应 axios 配置）
  const headers: Record<string, string> = {
    'X-Requested-With': 'XMLHttpRequest',
    'Content-Type': 'application/json',
  };

  // CSRF Token（对应 axios xsrfCookieName 和 xsrfHeaderName）
  const csrfToken = getCookie(xsrfCookieName);
  if (csrfToken) {
    headers[xsrfHeaderName] = csrfToken;
  }

  // 外部版后端需要读取header里的 spaceUid（对应 axios 拦截器）
  if (window.IS_EXTERNAL && JSON.parse(window.IS_EXTERNAL as string) && store.state.spaceUid) {
    headers['X-Bk-Space-Uid'] = store.state.spaceUid;
  }

  // 监控上层并没有使用 OT 这里直接自己生成traceparent id（对应 axios 拦截器）
  const traceparent = `00-${random(32, 'abcdef0123456789')}-${random(16, 'abcdef0123456789')}-01`;
  headers.Traceparent = traceparent;

  // 构建 fetch 配置（对应 axios withCredentials: true）
  const fetchConfig: RequestInit = {
    method,
    headers,
    credentials: 'include', // 对应 axios withCredentials: true
    body: params ? JSON.stringify(params) : undefined,
  };

  return { url: fullUrl, config: fetchConfig };
};

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
  const segment4 = `${((Math.random() * 4) | 0 + 8).toString(16)}${generateHex(3)}`;
  const segment5 = generateHex(12);
  return `${segment1}-${segment2}-${segment3}-${segment4}-${segment5}`;
};

/**
 * @description 请求 API
 * @param url string
 * @param params any
 * @param method 'POST' | 'GET'
 * @returns {Promise<FetchResponse<T>>}
 */
const request = <T = any>(url: string, params?: any, method: 'POST' | 'GET' = 'POST'): Promise<FetchResponse<T>> => {
  const { url: fullUrl, config } = buildRequestConfig(url, params, method);
  return fetch(fullUrl, config)
    .then(response => response.json())
    .then(data => data as FetchResponse<T>);
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
  return request(url, params);
};

/**
 * @description 创建会话内容
 * @param {SessionContentParams} params
 * @returns {Promise<FetchResponse<SessionContentData>>}
 */
export const createSessionContent = (params: SessionContentParams): Promise<FetchResponse<SessionContentData>> => {
  const url = '/ai_assistant/session_content/';
  return request<SessionContentData>(url, params);
};

/**
 * @description 请求聊天完成
 * @param {ChatCompletionParams} params
 * @returns {Promise<FetchResponse<ChatCompletionData>>}
 */
export const requestChatCompletion = (params: ChatCompletionParams): Promise<FetchResponse<TextToQueryResponse>> => {
  const url = '/ai_assistant/chat_completion/';
  return request(url, params);
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
        context: [{
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
        }],
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
