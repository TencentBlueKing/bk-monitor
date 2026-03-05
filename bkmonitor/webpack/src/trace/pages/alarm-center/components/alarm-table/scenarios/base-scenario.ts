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

import {
  type BaseTableColumn,
  ExploreTableColumnTypeEnum,
} from '../../../../trace-explore/components/trace-explore-table/typing';

import type { TableEmpty } from '../../../typings';
/**
 * @abstract
 * @description 场景表格特殊列渲染配置抽象基类
 */
export abstract class BaseScenario {
  /**
   * @readonly 场景标识
   */
  abstract readonly name: string;

  /**
   * @readonly 场景私有类名
   */
  abstract readonly privateClassName: string;

  /**
   * @description 场景清理（可选）
   */
  cleanup?(): void;

  /**
   * @description 获取当前场景的特殊列配置(只实现私有列配置，公共的可配置在基类 getCommonColumnsConfig 中)
   * @returns 列键到特殊配置的映射
   */
  abstract getColumnsConfig(): Record<string, BaseTableColumn>;

  /**
   * @description 公共列配置（所有场景共享）
   * @returns 公共列配置的映射
   */

  protected getCommonColumnsConfig(): Record<string, Partial<BaseTableColumn>> {
    return {
      create_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      begin_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      end_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      latest_time: {
        renderType: ExploreTableColumnTypeEnum.TIME,
      },
      // 其他通用列...
    };
  }

  /**
   * @description 获取当前场景的空数据配置
   * @returns 空数据展示配置
   */
  abstract getEmptyConfig(): TableEmpty;

  /**
   * @description 获取合并后的列配置（公共+私有）
   * @returns 公共+场景私有合并后的列配置（最终外部获取到的列配置）
   */
  public getMergedColumnsConfig(): Record<string, Partial<BaseTableColumn>> {
    return {
      ...this.getCommonColumnsConfig(),
      ...this.getColumnsConfig(),
    };
  }

  /**
   * @description 场景初始化（可选）
   */
  initialize?(): void;
}
