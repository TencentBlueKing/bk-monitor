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
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
 * rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import type {
  IAlertData,
  IContentList,
  IEventsAnalysis,
  IExtractedInfoList,
  IInteraction,
  ISummaryList,
  OverflowPopType,
} from '../../types';
import type { IOpenDrawerContext } from '../interaction-handler';

/** 各诊断模块渲染函数共享的上下文（原 createShootingModule 的 options 内联类型） */
export interface IShootingModuleContext {
  /** 各折叠面板的激活状态索引 */
  activeIndex: Record<string, number[] | Record<string, number[]>>;
  /** 业务ID列表 */
  bkzIds: string[];
  /** 内容数据列表 */
  contentList: IContentList;
  /** 各模块 display 层交互配置 */
  displayInteractionList: Record<string, IInteraction | undefined>;
  /** 事件分析数据 */
  eventsData: IEventsAnalysis[];
  /** 提取的信息，用来给Markdown渲染使用 */
  extractedInfoList: IExtractedInfoList;
  /** 故障详情数据 */
  incidentDetailData: Record<string, any>;
  /** 各模块的总结内容 */
  summaryList: ISummaryList;
  /** 链接跳转前校验事件或 Trace 数据可用性 */
  checkInteractionAvailability?: (
    interaction: IInteraction,
    availabilityRef?: IInteraction['detail_ref']
  ) => Promise<boolean>;
  /** 执行 interaction 前清理当前分析弹窗 */
  closeAnalysisPopovers?: () => void;
  /** 跳转到告警列表的回调函数 */
  goAlertList: (list: IAlertData[]) => void;
  /** 鼠标悬停事件处理函数 */
  handleMouseEnter: (e: MouseEvent, index: number, type: OverflowPopType) => void;
  /** Popover关闭事件处理函数 */
  handlePopoverClose: (item: { isShow: boolean }) => void;
  /** 打开后端 interaction 指定的详情侧滑 */
  onOpenDrawer?: (context: IOpenDrawerContext) => void;
  /** 查看全部子事件的回调函数，用于打开侧滑展示完整事件列表 */
  onViewAllEvents?: (item: IEventsAnalysis) => void;
  /** 查看完整 JSON 的回调函数，用于打开侧滑 */
  onViewFullJson?: (data: any, dataIndex: number) => void;
  /** Popover状态管理对象 */
  popoverState: {
    currentPopover: null | { index: number; type: OverflowPopType };
    overflowMap: Record<string, boolean>;
  };
}

/** 国际化翻译函数 */
export type TranslateFn = (key: string) => string;
