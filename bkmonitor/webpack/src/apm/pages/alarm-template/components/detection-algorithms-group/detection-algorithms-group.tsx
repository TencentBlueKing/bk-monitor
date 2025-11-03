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

import { LEVEL_LIST } from '../template-form/constant';
import { type AlgorithmItemUnion, AlgorithmEnum } from '../template-form/typing';
import DetectionAlgorithm from './detection-algorithms';

import './detection-algorithms-group.scss';

interface DetectionAlgorithmsGroupProps {
  /** 检测算法数据数组 */
  algorithms: AlgorithmItemUnion[];
  connector?: string;
  /** 传入为空数组时显示的占位符，默认为 -- */
  placeholder?: string;
}

@Component
export default class DetectionAlgorithmsGroup extends tsc<DetectionAlgorithmsGroupProps> {
  /** 检测算法数据数组 */
  @Prop({ type: Array, default: () => [] }) algorithms!: AlgorithmItemUnion[];
  @Prop({ type: String, default: 'and' }) connector: string;

  /** 传入为空数组时显示的占位符，默认为 -- */
  @Prop({ type: String, default: '--' }) placeholder: string;

  /** 算法排序，从低往高 */
  algorithmsTypeSort = {
    [AlgorithmEnum.Threshold]: 0,
    [AlgorithmEnum.YearRoundAndRingRatio]: 1,
  };

  /**
   * 根据检测算法的级别分类展示
   * 判断一个告警级别是否配置了多个检测算法
   * 配置了多个检测算法需要展示组合样式， 否则展示对应的算法即可
   */
  get rulesLevelDisplayList() {
    return LEVEL_LIST.map(level => {
      const currentLevelAlgorithms = this.algorithms.filter(algorithm => algorithm.level === level.id);
      return {
        id: level.id,
        name: level.name,
        icon: level.icon,
        algorithms: currentLevelAlgorithms.sort(
          (a, b) => this.algorithmsTypeSort[a.type] - this.algorithmsTypeSort[b.type]
        ),
      };
    }).filter(item => item.algorithms.length > 0);
  }

  render() {
    return (
      <div class='detection-algorithms-group'>
        {this.rulesLevelDisplayList?.length
          ? this.rulesLevelDisplayList.map(rulesLevel => (
              <DetectionAlgorithm
                key={rulesLevel.id}
                algorithm={rulesLevel.algorithms}
                connector={this.connector}
              />
            ))
          : this.placeholder}
      </div>
    );
  }
}
