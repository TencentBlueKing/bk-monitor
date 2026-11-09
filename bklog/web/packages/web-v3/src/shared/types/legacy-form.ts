/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
/** Imperative form API exposed by the retained form adapter. */
export interface LegacyFormInstance {
  validate(callback?: (valid: boolean) => unknown): Promise<unknown>;
  clearError(): void;
  formItems?: { property: string; $children?: { focus?: () => void }[] }[];
}
