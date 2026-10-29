/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
import 'tiny-pinyin';
declare module 'tiny-pinyin' {
  export function genToken(character: string): { source: string; target: string; type: 1 | 2 | 3 };
  // 1.3.2 intentionally accepts a boolean separator (and coerces it in join).
  export function convertToPinyin(text: string, separator: boolean, lowerCase?: boolean): string;
}
