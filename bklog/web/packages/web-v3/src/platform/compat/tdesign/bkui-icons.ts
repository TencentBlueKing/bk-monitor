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

import { defineComponent, h } from 'vue';

function icon(name: string, path: string) {
  return defineComponent({
    name,
    inheritAttrs: true,
    setup(_, { attrs }) {
      return () =>
        h(
          'svg',
          {
            ...attrs,
            viewBox: '0 0 16 16',
            width: '1em',
            height: '1em',
            fill: 'none',
            stroke: 'currentColor',
            'aria-hidden': 'true',
          },
          [h('path', { d: path, 'stroke-width': '1.5', 'stroke-linecap': 'round', 'stroke-linejoin': 'round' })],
        );
    },
  });
}

export const AngleLeft = icon('AngleLeft', 'M10 3 L5 8 L10 13');
export const AngleRight = icon('AngleRight', 'M6 3 L11 8 L6 13');
export const AngleDown = icon('AngleDown', 'M3 6 L8 11 L13 6');
export const AngleDoubleLeft = icon('AngleDoubleLeft', 'M8 3 L3 8 L8 13 M13 3 L8 8 L13 13');
export const AngleDoubleRight = icon('AngleDoubleRight', 'M3 3 L8 8 L3 13 M8 3 L13 8 L8 13');
export const Close = icon('Close', 'M4 4 L12 12 M12 4 L4 12');
export const Del = Close;
export const Done = icon('Done', 'M3 8 L7 12 L13 4');
export const Error = icon('Error', 'M8 3 L13 12 L3 12 Z M8 6 L8 9 M8 11 L8 11.5');
export const Search = icon('Search', 'M7 3 A4 4 0 1 1 7 11 A4 4 0 1 1 7 3 M10.5 10.5 L13 13');
export const EditLine = icon('EditLine', 'M3 13 L6 12 L12 6 L9 3 L3 9 Z');
export const Transfer = icon('Transfer', 'M3 5 L13 5 M10 2 L13 5 L10 8 M13 11 L3 11 M6 8 L3 11 L6 14');
export const UpShape = icon('UpShape', 'M8 3 L13 11 L3 11 Z');
