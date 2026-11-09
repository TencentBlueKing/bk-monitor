/* Copyright (C) 2021 THL A29 Limited, a Tencent company.
 * 蓝鲸智云PaaS平台 (BlueKing PaaS), MIT License. */
// 项目组件使用 tdesign-vue-next。这里不再声明 bk-* 组件、指令或消息函数。
declare module 'bk-magic-vue' {
  export type Form = import('@/shared/types/legacy-form').LegacyFormInstance;
  export type From = Form;
  export interface Popover {
    show(delay?: number): void;
    hide(delay?: number): void;
    destroy(): void;
    setContent(content: string | Element): void;
  }
}
