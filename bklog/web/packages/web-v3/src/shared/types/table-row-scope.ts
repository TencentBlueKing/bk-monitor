/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
/** The row comes from the containing table's actual data expression. */
export type TableRowScope<Rows> = {
  row: NonNullable<Rows> extends readonly (infer Row)[] ? Row : never;
  $index: number;
  index: number;
  rowIndex: number;
  column: Record<string, unknown>;
  [context: string]: unknown;
};
