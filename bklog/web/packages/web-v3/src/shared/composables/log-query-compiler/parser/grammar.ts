/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

/** 预留 grammar 声明；当前实现以 Parser 代码为准 */
export const QUERY_GRAMMAR = {
  fieldValue: 'Identifier ":" Value',
  boolean: 'Clause (("AND"|"OR") Clause)*',
  firstColonOnly: true,
};
