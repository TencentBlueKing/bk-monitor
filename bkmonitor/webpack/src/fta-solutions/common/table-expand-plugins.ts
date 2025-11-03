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

/**
 * @description vue2版本 bk-table 功能拓展--表格定位色功能类（点击table行存储当前行索引变色）
 */
export class TableClickCurrentExpand {
  private rowCurrentIndex = -1;

  /**
   * @description 根据表格行索引判断设置行类名（bk-table-row--current）从而实现表格点击后定位色功能
   * @description 主要利用 bk-table 的 row-class-name 属性
   */
  getClassNameByCurrentIndex() {
    return (rowObject: { row: unknown; rowIndex: number }) => {
      const { rowIndex } = rowObject;
      return rowIndex === this.rowCurrentIndex ? 'bk-table-row--current' : '';
    };
  }

  /**
   * @description 获取当前缓存的表格行索引
   */
  getRowCurrentIndex() {
    return this.rowCurrentIndex;
  }

  /**
   * @description 重置当前缓存表格行索引
   */
  resetRowCurrentIndex() {
    this.rowCurrentIndex = -1;
  }

  /**
   * @description 设置当前表格行索引
   * @param { number } index 需要缓存的表格行索引
   */
  setRowCurrentIndex(index: number) {
    this.rowCurrentIndex = index;
  }

  /**
   * @description 表格点击行事件（点击后设置当前表格行索引）
   * @description 参数可看vue2 bk-table 文档 -- row-click 事件
   */
  tableRowClick() {
    return (row, event, column, rowIndex) => {
      this.setRowCurrentIndex(rowIndex);
    };
  }
}
