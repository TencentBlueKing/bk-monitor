/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

/** 预留：ES mapping / schema 注入点，后续 AI / 手工输入复用 */
export interface FieldSchemaItem {
  field_name: string;
  field_type: string;
  is_analyzed?: boolean;
  tokenize_on_chars?: string;
}

export type FieldSchemaMap = Record<string, FieldSchemaItem>;

export const buildSchemaMap = (fields: FieldSchemaItem[] = []): FieldSchemaMap => {
  const map: FieldSchemaMap = {};
  fields.forEach((item) => {
    if (item?.field_name) {
      map[item.field_name] = item;
    }
  });
  return map;
};
