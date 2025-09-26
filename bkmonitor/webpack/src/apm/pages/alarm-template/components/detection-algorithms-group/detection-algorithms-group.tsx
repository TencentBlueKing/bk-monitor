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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import DetectionAlgorithm from './detection-algorithms';

import type { AlarmAlgorithmItem } from '../../typing';

import './detection-algorithms-group.scss';

interface DetectionAlgorithmsGroupProps {
  /** 检测算法数据数组 */
  algorithms: AlarmAlgorithmItem[];
  /** 传入为空数组时显示的占位符，默认为 -- */
  placeholder?: string;
}

@Component
export default class DetectionAlgorithmsGroup extends tsc<DetectionAlgorithmsGroupProps> {
  /** 检测算法数据数组 */
  @Prop({ type: Array, default: () => [] }) algorithms!: AlarmAlgorithmItem[];
  /** 传入为空数组时显示的占位符，默认为 -- */
  @Prop({ type: String, default: '--' }) placeholder: string;
  render() {
    return (
      <div class='detection-algorithms-group'>
        {this.algorithms?.length
          ? this.algorithms.map((algorithm, index) => (
              <DetectionAlgorithm
                key={`${algorithm?.level}-${index}`}
                algorithm={algorithm}
              />
            ))
          : this.placeholder}
      </div>
    );
  }
}
