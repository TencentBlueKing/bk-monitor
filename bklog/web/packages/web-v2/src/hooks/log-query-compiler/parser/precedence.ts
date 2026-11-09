/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

/** 预留：布尔优先级 AND > OR；当前 Parser 使用扁平 Boolean 节点 */
export const OPERATOR_PRECEDENCE: Record<string, number> = {
  NOT: 3,
  AND: 2,
  OR: 1,
};
