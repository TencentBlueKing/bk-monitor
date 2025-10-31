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

import { ConditionMethodAliasMap } from 'monitor-pc/pages/query-template/constants';

import {
  ALGORITHM_RELATIONSHIP_MAP,
  ALGORITHM_TYPE_MAP,
  LEVEL_LIST,
  YEAR_ROUND_AND_RING_RATION_ALGORITHM_MAP,
} from '../template-form/constant';
import { type AlgorithmItemUnion, AlgorithmEnum } from '../template-form/typing';

import './detection-algorithms.scss';

interface DetectionAlgorithmProps {
  /** 检测算法数据 */
  algorithm: AlgorithmItemUnion[];
  connector?: string;
}

@Component
export default class DetectionAlgorithm extends tsc<DetectionAlgorithmProps> {
  /** 检测算法数据 */
  @Prop({ type: Array, default: () => [] }) algorithm!: AlgorithmItemUnion[];
  @Prop({ type: String, default: 'and' }) connector!: string;

  get algorithmDisplayConfig() {
    const level = LEVEL_LIST.find(item => item.id === this.algorithm[0]?.level);
    return {
      algorithmLabel: this.algorithm.length > 1 ? this.$t('组合') : ALGORITHM_TYPE_MAP[this.algorithm[0]?.type],
      levelIcon: level.icon,
      levelName: level.name,
    };
  }

  renderAlgorithmContent(algorithm: AlgorithmItemUnion, index: number) {
    switch (algorithm.type) {
      case AlgorithmEnum.Threshold:
        return (
          <div class='threshold-algorithm-content'>
            <span class='method'>{ConditionMethodAliasMap[algorithm.config?.method]}</span>
            <span class='bold'>
              {algorithm.config?.threshold}
              {algorithm.unit_prefix}
            </span>
          </div>
        );
      case AlgorithmEnum.YearRoundAndRingRatio:
        return (
          <div class='year-round-and-ring-ratio-algorithm-content'>
            {index > 0 && '('}
            <i18n path='{0}上升{1}%或下降{2}%'>
              <span>{YEAR_ROUND_AND_RING_RATION_ALGORITHM_MAP[algorithm.config.method]}</span>
              <span class='bold'>{algorithm.config.ceil}</span>
              <span class='bold'>{algorithm.config.floor}</span>
            </i18n>
            {index > 0 && ')'}
          </div>
        );
      default:
        return null;
    }
  }

  render() {
    return (
      <div class='detection-algorithms'>
        <div class='detection-algorithms-label'>{this.algorithmDisplayConfig.algorithmLabel},</div>
        <div class='detection-algorithms-content'>
          {this.algorithm.map((algorithm, index) => [
            index > 0 && (
              <span
                key='connector'
                class='connector'
              >
                {ALGORITHM_RELATIONSHIP_MAP[this.connector]}
              </span>
            ),
            this.renderAlgorithmContent(algorithm, index),
            <span key='comma'>,</span>,
          ])}
        </div>
        <div class='detection-algorithms-level'>
          <i class={['icon-monitor', this.algorithmDisplayConfig.levelIcon]} />
          <span class='level-text'>{this.algorithmDisplayConfig.levelName}</span>
        </div>
      </div>
    );
  }
}
