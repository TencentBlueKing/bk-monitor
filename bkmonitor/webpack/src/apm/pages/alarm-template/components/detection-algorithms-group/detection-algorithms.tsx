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

import { DetectionAlgorithmLevelMap } from '../../constant';

import type { AlarmAlgorithmItem } from '../../typing';

import './detection-algorithms.scss';

interface DetectionAlgorithmProps {
  /** 检测算法数据 */
  algorithm: AlarmAlgorithmItem;
}

@Component
export default class DetectionAlgorithm extends tsc<DetectionAlgorithmProps> {
  /** 检测算法数据 */
  @Prop({ type: Object, default: () => {} }) algorithm!: AlarmAlgorithmItem;
  render() {
    return (
      <div class='detection-algorithms'>
        <div class='detection-algorithms-label'>{this.$t('静态阈值')},</div>
        <div class='detection-algorithms-content'>
          <span class='method'>{ConditionMethodAliasMap[this.algorithm?.config?.method]}</span>
          <span class='threshold'>
            {this.algorithm?.config?.threshold}
            {this.algorithm?.unit_prefix}
          </span>
          <span>,</span>
        </div>
        <div class='detection-algorithms-lever'>
          <i class={['icon-monitor', DetectionAlgorithmLevelMap[this.algorithm?.level]?.icon]} />
          <span class='lever-text'>{DetectionAlgorithmLevelMap[this.algorithm?.level]?.name}</span>
        </div>
      </div>
    );
  }
}
