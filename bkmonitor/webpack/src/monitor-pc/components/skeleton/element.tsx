/*
 * @Author: liangling0628 lingliang1100@gmail.com
 * @Date: 2024-03-06 16:26:54
 * @LastEditors: liangling0628 lingliang1100@gmail.com
 * @LastEditTime: 2024-03-08 15:43:59
 * @FilePath: /webpack/src/monitor-pc/components/skeleton/element.tsx
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%AE
 */
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
import { ofType } from 'vue-tsx-support';

import './skeleton';

import './skeleton.scss';

export interface ISkeletonElementProps {
  shape?: 'circle' | 'default'; // default 为默认形状
  active?: Boolean; // 是否显示loading
  width?: string | number;
  height?: string | number;
}
const SkeletonElement = {
  name: 'SkeletonElement',
  functional: true,
  inheritAttrs: true,
  props: {
    width: {
      type: [Number, String],
      default: '100%'
    },
    height: {
      type: [Number, String],
      default: '32px'
    },
    shape: {
      type: String,
      default: 'default'
    },
    active: {
      type: Boolean,
      default: true
    }
  },
  render(
    _,
    {
      props,
      data
    }: {
      props: ISkeletonElementProps;
      data: { [key: string]: any };
    }
  ) {
    return (
      <span
        class='skeleton-element'
        style={{
          // width: props.width,
          // height: props.height,
          borderRadius: props.shape === 'circle' ? '50%' : '2px'
        }}
        {...data}
      ></span>
    );
  }
};

export default ofType<ISkeletonElementProps>().convert(SkeletonElement as any);
