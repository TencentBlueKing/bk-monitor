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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './skeleton-base.scss';

/** 骨架屏简易版配置 */
export interface ISkeletonSimpleOption {
  /** 行数 */
  row: number;
  /** 每行宽度 */
  width?: number | string;
  /** 每行高度 */
  height?: number | string;
  /** 行内分布方式 */
  justifyContent?: string;
}

/** 骨架屏每行配置 */
export interface ISkeletonOption {
  /** 每行几列，每列宽度 */
  widths?: number | string | (number | string)[];
  /** 每行高度 */
  height?: number | string;
  /** 行内分布方式 */
  justifyContent?: string;
}

export interface ISkeletonBaseProps {
  /** 标题配置 */
  title?: ISkeletonSimpleOption | ISkeletonOption[];
  /** 子级配置 */
  children?: ISkeletonSimpleOption | ISkeletonOption[];
  /** 是否需要分组 */
  hasGroup?: boolean;
  /** 分组数量 */
  groupNumber?: number;
}
@Component
export default class SkeletonBase extends tsc<ISkeletonBaseProps> {
  @Prop({ default: undefined }) readonly title: ISkeletonSimpleOption | ISkeletonOption[];
  @Prop({ default: () => ({ row: 4, width: '100%', height: '32px' }) }) readonly children:
    | ISkeletonSimpleOption
    | ISkeletonOption[];
  @Prop({ default: false }) readonly hasGroup: boolean;
  @Prop({ default: 3 }) readonly groupNumber: number;

  createSimpleSkeleton(option: ISkeletonSimpleOption) {
    if (!option) return;
    const { row, width = '100%', height, justifyContent } = option;
    const style = {
      width: typeof width === 'string' ? width : `${width}px`,
      height: typeof height === 'string' ? height : `${height || 24}px`
    };
    return new Array(row).fill('').map(() => (
      <div
        class='skeleton-row'
        style={{ justifyContent: justifyContent || 'space-between' }}
      >
        <div
          class='skeleton-element'
          style={style}
        ></div>
      </div>
    ));
  }

  createSkeleton(option: ISkeletonOption[]) {
    return option.map(item => {
      const { widths, height, justifyContent } = item;
      const cols = (Array.isArray(widths) ? widths : [widths]).map(width => {
        if (width) return typeof width === 'string' ? width : `${width}px`;
        return '100%';
      });
      const heightStyle = typeof height === 'string' ? height : `${height || 24}px`;
      return (
        <div
          class='skeleton-row'
          style={{ justifyContent: justifyContent || 'space-between' }}
        >
          {cols.map(width => (
            <div
              class='skeleton-element'
              style={{ width, height: heightStyle }}
            ></div>
          ))}
        </div>
      );
    });
  }

  render() {
    return (
      <div class='skeleton-base-comp'>
        {new Array(this.hasGroup ? this.groupNumber : 1).fill('').map(() => [
          <div
            class={{
              'skeleton-title-wrap': true,
              'show-title': Array.isArray(this.title) ? !!this.title.length : !!this.title
            }}
          >
            {Array.isArray(this.title) ? this.createSkeleton(this.title) : this.createSimpleSkeleton(this.title)}
          </div>,
          <div class='skeleton-body-wrap'>
            {Array.isArray(this.children)
              ? this.createSkeleton(this.children)
              : this.createSimpleSkeleton(this.children)}
          </div>
        ])}
      </div>
    );
  }
}
