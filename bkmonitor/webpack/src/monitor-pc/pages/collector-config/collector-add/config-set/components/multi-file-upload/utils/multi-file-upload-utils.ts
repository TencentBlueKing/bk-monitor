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

/** 对当前完整文件集合做校验，返回整体校验结果 */
export type FileValidator = (files: IUploadedFile[]) => Promise<IValidateResult>;

/** 校验错误项，结构对齐后端 data.errors[] / data.files[].errors[] */
export interface IFileCheckError {
  code?: string;
  message: string;
  path?: string;
  related_uid?: string;
}
/** 多文件上传组件对外/对接口使用的文件结构 */
export interface IUploadedFile {
  content: string;
  filename: string;
  uid: string;
}

/** 单文件校验结果，结构对齐后端 data.files[] */
export interface IValidateFileResult {
  errors: IFileCheckError[];
  filename: string;
  preview?: null | { credential_source: string; qcloud_yaml: string };
  summary?: null | { products: string[]; region: string };
  uid: string;
  valid: boolean;
}

/** 整体校验结果，结构对齐后端 data */
export interface IValidateResult {
  errors: IFileCheckError[];
  files: IValidateFileResult[];
  valid: boolean;
}

/** 本地读取文件失败时的错误标识 */
export const FILE_ENCODING_INVALID = 'FILE_ENCODING_INVALID';
export const FILE_READ_FAILED = 'FILE_READ_FAILED';

/** 编辑所依据的源版本已变化（需刷新后重新编辑） */
export const CONFIG_VERSION_CHANGED = 'CONFIG_VERSION_CHANGED';
/** 历史配置无法无损转换 */
export const LEGACY_CONVERSION_FAILED = 'LEGACY_CONVERSION_FAILED';
/** 保存前复验失败的数值码 */
export const COLLECT_CONFIG_PARAMS_ERROR = 3311013;

/** 接口失败响应解析结果 */
export interface IParsedApiError {
  /** 顶层数值码 */
  code?: number;
  /** 失败时已持久化的目标部署版本（data.deployment_id） */
  deploymentId?: number;
  /** 配置级错误 data.errors */
  errors: IFileCheckError[];
  /** 逐文件错误 data.files */
  files: IValidateFileResult[];
  /** 是否拿到了服务端响应体（false 表示超时/断线/取消，结果未知） */
  hasResponse: boolean;
  /** 失败时已持久化的配置 ID（data.id） */
  id?: number;
  message: string;
}

/**
 * @description 解析接口失败对象。
 * 非 2xx 时 axios 拒绝为含 status 的响应对象（响应体在 data）；HTTP 200 但 result=false 时直接拒绝为响应体；
 * 超时、断线、取消没有响应体。
 * @param error 请求拒绝值
 */
export const parseApiError = (error: any): IParsedApiError => {
  const body = typeof error?.status === 'number' && error.data && typeof error.data === 'object' ? error.data : error;
  const hasResponse = !!body && typeof body === 'object' && ('result' in body || 'code' in body);
  const payload = hasResponse && body.data && typeof body.data === 'object' ? body.data : {};
  return {
    hasResponse,
    code: hasResponse ? Number(body.code) || undefined : undefined,
    message: (hasResponse && body.message) || error?.message || '',
    id: payload.id,
    deploymentId: payload.deployment_id,
    errors: Array.isArray(payload.errors) ? payload.errors : [],
    files: Array.isArray(payload.files) ? payload.files : [],
  };
};

/** 是否存在可回填的业务校验错误（集合级或文件级） */
export const hasBusinessErrors = (parsed: IParsedApiError): boolean =>
  parsed.errors.length > 0 || parsed.files.some(file => file.errors?.length);

/**
 * @description 判断文件扩展名是否在 accept 允许范围内（忽略大小写，仅识别 `.ext` 形式；accept 为空不限制）
 * @param filename 文件名
 * @param accept 形如 `.yaml,.yml` 的限制串
 */
export const hasAcceptedExtension = (filename: string, accept: string): boolean => {
  const exts = (accept || '')
    .split(',')
    .map(item => item.trim().toLowerCase())
    .filter(item => item.startsWith('.'));
  if (!exts.length) return true;
  const name = filename.toLowerCase();
  return exts.some(ext => name.endsWith(ext));
};

/**
 * @description 将 accept 限制串格式化为展示文案，如 `.yaml,.yml` -> `.yaml 或 .yml`
 * @param accept 形如 `.yaml,.yml` 的限制串
 * @param separator 扩展名之间的连接词（已翻译）
 */
export const formatAcceptText = (accept: string, separator: string): string =>
  (accept || '')
    .split(',')
    .map(item => item.trim())
    .filter(Boolean)
    .join(` ${separator} `);

/**
 * @description 以严格 UTF-8 读取文件文本；非法字节会拒绝，而不是静默替换为 U+FFFD
 * @param file 待读取文件
 * @returns 文件文本内容（自动去除 BOM）
 */
export const readFileAsUtf8 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      try {
        resolve(new TextDecoder('utf-8', { fatal: true }).decode(reader.result as ArrayBuffer));
      } catch {
        reject(new Error(FILE_ENCODING_INVALID));
      }
    };
    reader.onerror = () => reject(new Error(FILE_READ_FAILED));
    reader.readAsArrayBuffer(file);
  });

/**
 * @description 格式化文件大小展示
 * @param bytes 字节数
 */
export const formatFileSize = (bytes: number): string => {
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};
