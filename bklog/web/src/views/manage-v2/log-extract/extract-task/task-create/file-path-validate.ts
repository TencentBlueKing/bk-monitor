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

// 已选列表上限，与后端 CSTONE_DOWNLOAD_FILES_LIMIT 默认值保持一致，避免提交时才被拒
export const MAX_SELECTED_FILES = 10;

/** extract/getAvailableExplorerPath 返回的单条可提取策略 */
export interface ExtractStrategy {
  file_path: string;
  file_type?: string[];
}

/** 校验结果，message 为空表示合法；message 是待 i18n 的文案，params 供占位符替换 */
export interface PathValidateResult {
  message: string;
  params?: Record<string, string>;
}

const VALID: PathValidateResult = { message: '' };

// 与后端 config/default.py 的 EXTRACT_FILE_PATTERN_CHARACTERS 逐字符保持一致。
// 结尾的 '*-~' 在字符组里是 0x2A~0x7E 的区间而非三个字面量，改动写法会让前后端松紧不一致。
const CHARACTER_CLASS = '():@\\[\\]a-zA-Z0-9._/*-~';
const ALLOWED_CHARACTERS = new RegExp(`^[${CHARACTER_CLASS}]+$`);

// 与后端 apps/log_extract/serializers.py::check_file_path_legal 对齐
const checkPathFormat = (value: string): PathValidateResult => {
  if (!value) {
    return { message: '请输入日志文件路径' };
  }
  if (!value.startsWith('/')) {
    return { message: '路径需以 / 开头' };
  }
  if (/\/\/+/.test(value)) {
    return { message: '路径不能包含连续的 /' };
  }

  const segments = value.split('/');
  if (segments.some(segment => segment === '.' || segment === '..')) {
    return { message: "路径不支持 '.' 与 '..' 相对路径" };
  }
  if (segments.some(segment => segment.startsWith('.'))) {
    return { message: "不支持以 '.' 开头的目录或文件" };
  }
  if (!ALLOWED_CHARACTERS.test(value)) {
    return { message: '路径包含不支持的字符' };
  }

  return VALID;
};

/**
 * 校验浏览目录，对应后端 ExplorerHandler.filter_server_access_file 的非 fname 分支：
 * 只做策略目录的前缀匹配，不校验文件类型。
 */
export const validateDirectoryPath = (path: string, strategies: ExtractStrategy[] = []): PathValidateResult => {
  const value = String(path ?? '').trim();
  const formatResult = checkPathFormat(value);
  if (formatResult.message) {
    return formatResult;
  }
  if (strategies.length && !strategies.some(item => value.startsWith(item.file_path))) {
    return { message: '路径不在可提取的目录范围内' };
  }
  return VALID;
};

// 复刻后端按策略 file_type 拼接的文件名正则，例如 ['.log', '.gz'] -> /^[字符集]+((\.log)$|(\.gz)$)/
// file_type 为空时拼出 /^[字符集]+()/，与后端一致地放通该目录下的所有文件
const buildFileNamePattern = (fileTypes: string[]): RegExp => {
  const alternatives = fileTypes.map(fileType => {
    // 以 * 结尾表示前缀匹配，不锚定行尾
    const anchor = fileType.endsWith('*') ? '' : '$';
    return fileType.startsWith('.') ? `(\\${fileType})${anchor}` : `${fileType}${anchor}`;
  });
  return new RegExp(`^[${CHARACTER_CLASS}]+(${alternatives.join('|')})`);
};

/**
 * 校验待提取的日志文件路径，对应后端 ExplorerHandler.filter_server_access_file 的 fname 分支：
 * 先命中某条策略的目录前缀，再用该策略的文件类型白名单校验剩余文件名。
 * 手动输入绕过了文件列表的类型过滤，因此这层校验必须做，否则会在创建任务时才被后端拒绝。
 */
export const validateFilePath = (path: string, strategies: ExtractStrategy[] = []): PathValidateResult => {
  const value = String(path ?? '').trim();
  const formatResult = checkPathFormat(value);
  if (formatResult.message) {
    return formatResult;
  }
  if (!strategies.length) {
    return { message: '请先选择文件来源主机' };
  }

  const matchedStrategies = strategies.filter(item => value.startsWith(item.file_path));
  if (!matchedStrategies.length) {
    return { message: '路径不在可提取的目录范围内' };
  }

  const isTypeAllowed = matchedStrategies.some(item =>
    buildFileNamePattern(item.file_type ?? []).test(value.slice(item.file_path.length)),
  );
  if (!isTypeAllowed) {
    const allowedTypes = Array.from(new Set(matchedStrategies.flatMap(item => item.file_type ?? [])));
    return { message: '仅支持提取以下类型的文件：{0}', params: { 0: allowedTypes.join('、') } };
  }

  return VALID;
};
