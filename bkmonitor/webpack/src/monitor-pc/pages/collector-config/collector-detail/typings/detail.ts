/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
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

import type CollectorDetail from '../collector-detail';

/**
 * @enum {('configuration' | 'DataLink' | 'fieldDetails' | 'StorageState' | 'targetDetail')} 采集详情tab枚举类型
 */
export enum TabEnum {
  /**
   * @description 配置信息tab
   */
  Configuration = 'configuration',
  /**
   * @description 链路状态tab
   */
  DataLink = 'DataLink',
  /**
   * @description 指标/维度tab
   */
  FieldDetails = 'fieldDetails',
  /**
   * @description 存储状态tab
   */
  StorageState = 'StorageState',
  /**
   * @description 采集状态tab
   */
  TargetDetail = 'targetDetail',
}

export enum TCollectorAlertStage {
  collecting = 'collecting',
  storage = 'storage',
  transfer = 'transfer',
}

export type ChangeConfig<T extends TabEnum, K extends TabProperty<T>> = {
  data: TabValue<T, K>;
  property: K;
  tab: T;
};

export interface DetailData {
  basic_info: Record<string, any>;
  extend_info: Record<string, any>;
  metric_list: Record<string, any>[];
  runtime_params: Record<string, any>[];
  subscription_id: number;
}
export type TabData<T extends TabEnum> = CollectorDetail['allData'][T];
export type TabProperty<T extends TabEnum> = keyof TabData<T>;

export type TabValue<T extends TabEnum, K extends TabProperty<T>> = TabData<T>[K];
