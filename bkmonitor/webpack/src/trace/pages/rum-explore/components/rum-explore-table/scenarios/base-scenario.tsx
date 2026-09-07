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
 * AUTHORS OR COPYRIGHT HOLDERS LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
 * THE SOFTWARE.
 */

import type { MaybeRef } from 'vue';

import { get } from '@vueuse/core';

import FieldTypeIcon from '../../../../trace-explore/components/field-type-icon';

import type { BaseTableColumn } from '../../../../trace-explore/components/trace-explore-table/typing';
import type { IRumField } from '../../../typings';

/**
 * @abstract
 * @description RUM 检索表格场景渲染器抽象基类。
 * 职责边界：只负责「单元格怎么画、点了干什么」（renderType / getRenderValue / clickCallback / 表头..），
 *
 * 列配置解析采用「基线 + 场景增量」两层合并（模板方法 resolveColumnConfig）：
 *   - 基线 buildBaseline：子类按需基于字段元数据（fieldMap）推导本场景渲染语义，基类默认空实现；
 *   - 增量 columnOverrides：模式特有字段的取值映射 / renderType 覆盖 / 点击交互。
 * 列级 entry 做一层浅合并，增量只写自己知道的字段，其余继承基线。
 */
export abstract class BaseScenario {
  /**
   * @readonly 场景私有类名
   */
  abstract readonly privateClassName: string;

  /**
   * @readonly 场景表格行唯一键
   */
  abstract readonly rowKey: string;

  /**
   * @description 场景增量配置：仅模式特有字段的渲染差异，由子类声明（默认空）
   */
  protected columnOverrides: Record<string, BaseTableColumn> = {};

  constructor(
    protected readonly context: {
      /** 字段元数据映射 */
      fieldMap: MaybeRef<Map<string, IRumField>>;
      /** 点击列头的统计图标，触发字段分析 */
      onFieldAnalysis: (trigger: Element, field: IRumField) => void;
    }
  ) {}

  /**
   * @description 唯一出口（模板方法，子类不要覆盖）。合并基线推导与场景增量，产出声明式列配置。
   * @param {string} colKey 列键
   * @returns 声明式列配置（仅渲染/交互相关）
   */
  resolveColumnConfig(colKey: string): Partial<BaseTableColumn> {
    /** 列渲染机制（cellRenderer / renderType）互斥，override 优先于基线；同一列只应有一个渲染来源 */
    const override = this.columnOverrides[colKey];
    if (override) return override;
    return this.buildBaseline(colKey);
  }

  /**
   * @description 场景默认单元格取值：字段元数据声明了枚举值（option_values）时把原始值映射为别名，其余原样取值。
   *              对象/数组等结构化值统一 JSON 序列化后按纯文本展示（与 trace 检索表格默认取值一致）；
   *              空值统一返回空串，由表格渲染为空占位符。由表格以「默认取值逻辑」兜底执行，
   *              列自身配置了 getRenderValue 时以列配置为准。
   * @param {Record<string, unknown>} row 当前行数据
   * @param {BaseTableColumn} column 当前列配置
   * @returns {unknown} 单元格渲染值
   */
  getDefaultRenderValue(row: Record<string, unknown>, column: BaseTableColumn): unknown {
    const value = row?.[column.colKey];
    if (value === null || value === undefined || value === '') return '';
    /** 结构化值若原样返回会被 Vue 当作片段或 vnode 处理，渲染成无分隔文本或空白，故统一序列化 */
    if (typeof value === 'object') return JSON.stringify(value);
    return this.getFieldOptionAlias(column.colKey, value) ?? value;
  }

  /**
   * @description 取字段元数据声明的枚举别名（option_values），未声明枚举或无匹配项时返回 undefined，
   *              供本场景内需要「后台映射值优先」的列在自定义取值中复用。
   * @param {string} colKey 列键（字段名）
   * @param {unknown} value 原始值
   * @returns {string | undefined} 后台映射别名
   */
  protected getFieldOptionAlias(colKey: string, value: unknown): string | undefined {
    /** 枚举 value 声明为 string，行数据实际可能是 number / boolean，统一字符串化比较，避免类型差异导致别名静默失效 */
    const option = get(this.context.fieldMap)
      .get(colKey)
      ?.option_values?.find(item => `${item.value}` === `${value}`);
    return option?.alias;
  }

  /**
   * @description 场景私有钩子：由子类按需基于字段元数据（fieldMap）推导本场景的渲染语义，
   *              基类默认空实现（无公共推导）。读取 fieldMap 即满足「动态/响应式」：后台字段变更时随之变化。
   *              若某场景无需元数据推导，可直接复用默认实现。
   * @param {string} colKey 列键
   * @returns 声明式列配置（仅渲染/交互相关）
   */
  protected buildBaseline(_colKey: string): Partial<BaseTableColumn> {
    return {};
  }

  /**
   * @description 通用表头渲染：字段类型图标 + 标题 + 统计分析入口，各场景表头渲染一致，子类可按需覆盖。
   *              字段元数据缺失（本地列配置缓存了后端已下线的字段）时降级为空对象：标题回落为字段名，
   *              类型图标走 other 兜底，且不展示统计分析入口，避免整列表头渲染抛错。
   * @param {string} colKey 字段名（列键）
   * @returns {BaseTableColumn['title']} 表头渲染函数
   */
  renderHeader(colKey: string): BaseTableColumn['title'] {
    /** 字段元数据缺失（本地列配置缓存了后端已下线的字段）时降级为空对象，仅取用到的字段有兜底 */
    // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
    const field = get(this.context.fieldMap).get(colKey) ?? ({} as IRumField);
    return (() => (
      <div class='rum-table-header-cell'>
        <FieldTypeIcon
          class='field-type-icon'
          type={field.type}
        />
        <div
          class='header-title'
          v-overflow-tips={{
            placement: 'top',
            theme: 'dark text-wrap',
          }}
        >
          <span class='th-label'>{field.alias ?? colKey}</span>
        </div>
        {field.is_dimensions && (
          <i
            class='icon-monitor icon-Chart header-analysis-icon'
            onClick={event => {
              event.stopPropagation();
              this.context.onFieldAnalysis(event.currentTarget as Element, field);
            }}
          />
        )}
      </div>
    )) as unknown as BaseTableColumn['title'];
  }

  /**
   * @description 场景初始化（可选）
   */
  initialize?(): void;

  /**
   * @description 场景清理（可选）
   */
  cleanup?(): void;
}
