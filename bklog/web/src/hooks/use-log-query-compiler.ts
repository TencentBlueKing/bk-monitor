/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 */

import {
  compile,
  compileFieldValue,
  compileFieldValueToQueryString,
  compileToQueryString,
  resolveAddToSearch,
  type AddToSearchPayload,
  type CompileResult,
  type CompilerOutputMode,
  type QueryCompilerOptions,
  type SelectionContext,
} from './log-query-compiler';

/**
 * 公共 Hook：全产品 Query Compiler 唯一入口封装。
 * 划词 / 点击 / 右键 / AI / Tag / URL 均应走 resolveAddToSearch 或 compile。
 */
export default function useLogQueryCompiler() {
  return {
    compile: (
      ctx: SelectionContext,
      outputMode?: CompilerOutputMode,
      options?: Partial<QueryCompilerOptions>,
    ): CompileResult => compile(ctx, outputMode, options),
    compileToQueryString,
    compileFieldValue,
    compileFieldValueToQueryString,
    resolveAddToSearch: (...args: Parameters<typeof resolveAddToSearch>): AddToSearchPayload =>
      resolveAddToSearch(...args),
  };
}
