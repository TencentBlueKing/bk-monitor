/**
 * UI → 语句模式切换：转换决策（与 generateQueryString 响应对齐）
 */

export type GenerateQueryStringResponse = {
  result?: boolean;
  data?: {
    querystring?: string;
  };
};

export type UiToSqlConvertOutcome =
  | { ok: true; keyword: string; autoQuery: false }
  | { ok: false; autoQuery: false; warn: true };

/**
 * 是否需要在模式切换时调用 UI→SQL 转换
 */
export function shouldConvertUiToSqlOnModeSwitch(fromIndex: number, toIndex: number, additionLength: number): boolean {
  return fromIndex === 0 && toIndex === 1 && additionLength > 0;
}

/**
 * 解析 generateQueryString 响应为模式切换填充结果
 * - 成功：覆盖 keyword，不自动查询
 * - 失败：仍允许切换，需 warning，不自动查询
 */
export function resolveUiToSqlConvertOutcome(
  res: GenerateQueryStringResponse | null | undefined,
): UiToSqlConvertOutcome {
  if (res?.result) {
    return {
      ok: true,
      keyword: res.data?.querystring || '',
      autoQuery: false,
    };
  }

  return {
    ok: false,
    autoQuery: false,
    warn: true,
  };
}
