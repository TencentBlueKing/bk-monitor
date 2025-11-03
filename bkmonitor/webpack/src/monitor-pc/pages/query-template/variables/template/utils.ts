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

export const escapeRegex = (value: string): string => {
  return value.replace(/[\\^$*+?.()|[\]{}/]/g, '\\$&');
};

/*
 * This regex matches 3 types of variable reference with an optional format specifier
 * There are 6 capture groups that replace will return
 * \$([\w\u4e00-\u9fa5]+)                                    $var1 or $变量1
 * \[\[([\w\u4e00-\u9fa5]+?)(?::([\w\u4e00-\u9fa5]+))?\]\]                  [[var2]] or [[变量2]] or [[var2:fmt2]] or [[变量2:格式2]]
 * \${([\w\u4e00-\u9fa5]+)(?:\.([^:^}]+))?(?::([^}]+))?}   ${var3} or ${变量3} or ${var3.fieldPath} or ${var3:fmt3} (or ${var3.fieldPath:fmt3} but that is not a separate capture group)
 */
export const variableRegex =
  /\$([\w\u4e00-\u9fa5]+)|\[\[([\w\u4e00-\u9fa5]+?)(?::([\w\u4e00-\u9fa5]+))?\]\]|\${([\w\u4e00-\u9fa5]+)(?:\.([^:^}]+))?(?::([^}]+))?}/g;

export const getVariableNameInput = (val: string) => {
  const matches = val.matchAll(/\$\{([^}]+)\}/g);
  let str = '';
  for (const match of matches) {
    str = match[1];
    break;
  }
  return str;
};

export const isVariableName = (val: string) => {
  // return !!val && /^\$\{([\w\u4e00-\u9fa5]+)(?:\.([^:^}]+))?(?::([^}]+))?}$/.test(val);
  return !!val && /^\$\{([\w.]{1,50})}$/.test(val);
};

export const validateVariableNameInput = (str: string): string => {
  if (!str) {
    return window.i18n.t('变量名不能为空') as string;
  }
  if (!/^[\w.]{1,50}$/.test(str)) {
    return window.i18n.t('变量名仅支持大小写字符、数字、下划线、点（.），50个字符以内') as string;
  }
  return '';
};

/**
 * 判断字符串是否包含变量
 * @param target 目标字符串
 * @returns 是否包含变量
 */
export const hasVariable = (target: string) => {
  return target.match(variableRegex)?.length > 0;
};
