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

import { random } from '../../../monitor-common/utils/utils';

export interface ISkeleton {
  type?: string;
  x?: number;
  y?: number;
  width: number;
  height: number;
  rx?: number;
  ry?: number;
  skeletons?: ISkeleton[];
}
export interface ISkeletonProps {
  visible?: boolean;
  width?: number;
  height?: number;
  speed?: number;
  backgroundColor?: string;
  secondaryColor?: string;
  primaryOpacity?: number;
  secondaryOpacity?: number;
  animate?: boolean;
  skeletons?: ISkeleton[];
  options?: ISkeleton;
}
const SkeletonContanier = {
  name: 'SkeletonContanier',

  functional: true,

  props: {
    visible: Boolean,
    width: {
      type: Number,
      default: 1920
    },
    height: {
      type: Number,
      default: 1080
    },
    speed: {
      type: Number,
      default: 1.4
    },
    backgroundColor: {
      type: String,
      default: '#f2f2f2'
    },
    secondaryColor: {
      type: String,
      default: '#e6e6e6'
    },
    primaryOpacity: {
      type: Number,
      default: 1
    },
    secondaryOpacity: {
      type: Number,
      default: 1
    },
    animate: {
      type: Boolean,
      default: true
    },
    skeletons: {
      type: Array,
      default: () => []
    },
    options: Object
  },

  render(
    h,
    {
      props,
      data,
      children
    }: {
      props: ISkeletonProps;
      data: any;
      children: any;
    }
  ) {
    const idClip = random(4);
    const idGradient = random(4);
    const { options } = props;
    return (
      <svg
        style={{
          display: props.visible === false ? 'none' : 'block'
        }}
        {...data}
        viewBox={`0 0 ${options?.width || props.width} ${options?.height || props.height}`}
        version='1.1'
        xmlns='http://www.w3.org/2000/svg'
      >
        <rect
          style={{ fill: `url(#${idGradient})` }}
          clip-path={`url(#${idClip})`}
          x='0'
          y='0'
          width={options?.width || props.width}
          height={options?.height || props.height}
        />

        <defs>
          <clipPath id={idClip}>
            {children ||
              (options?.skeletons || props.skeletons).map(skeleton =>
                h(skeleton.type || 'rect', {
                  attrs: skeleton
                })
              )}
          </clipPath>

          <linearGradient id={idGradient}>
            <stop
              offset='0%'
              stop-color={props.backgroundColor}
              stop-opacity={props.primaryOpacity}
            >
              {props.animate ? (
                <animate
                  attributeName='offset'
                  values='-2; 1'
                  dur={`${props.speed}s`}
                  repeatCount='indefinite'
                />
              ) : null}
            </stop>
            <stop
              offset='50%'
              stop-color={props.secondaryColor}
              stop-opacity={props.secondaryOpacity}
            >
              {props.animate ? (
                <animate
                  attributeName='offset'
                  values='-1.5; 1.5'
                  dur={`${props.speed}s`}
                  repeatCount='indefinite'
                />
              ) : null}
            </stop>
            <stop
              offset='100%'
              stop-color={props.backgroundColor}
              stop-opacity={props.primaryOpacity}
            >
              {props.animate ? (
                <animate
                  attributeName='offset'
                  values='-1; 2'
                  dur={`${props.speed}s`}
                  repeatCount='indefinite'
                />
              ) : null}
            </stop>
          </linearGradient>
        </defs>
      </svg>
    );
  }
};

export default ofType<ISkeletonProps>().convert(SkeletonContanier as any);
