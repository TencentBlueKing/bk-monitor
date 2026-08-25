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

// 字符白名单与后端 config/default.py 的 EXTRACT_FILE_PATTERN_CHARACTERS 保持一致
const ALLOWED_CHARACTERS = /^[():@[\]a-zA-Z0-9._/*~-]+$/;

/**
 * 校验日志提取路径，规则与后端 apps/log_extract/serializers.py::check_file_path_legal 对齐。
 * @returns 合法时返回空字符串，否则返回未经 i18n 的错误文案
 */
export const validateFilePath = (path: string, availablePaths: string[] = []): string => {
  const value = String(path ?? '').trim();

  if (!value) {
    return '请输入日志文件路径';
  }
  if (!value.startsWith('/')) {
    return '路径需以 / 开头';
  }
  if (/\/\/+/.test(value)) {
    return '路径不能包含连续的 /';
  }

  const segments = value.split('/');
  if (segments.some(segment => segment === '.' || segment === '..')) {
    return "路径不支持 '.' 与 '..' 相对路径";
  }
  if (segments.some(segment => segment.startsWith('.'))) {
    return "不支持以 '.' 开头的目录或文件";
  }
  if (!ALLOWED_CHARACTERS.test(value)) {
    return '路径包含不支持的字符';
  }
  if (availablePaths.length && !availablePaths.some(item => value.startsWith(item))) {
    return '路径不在可提取的目录范围内';
  }

  return '';
};
