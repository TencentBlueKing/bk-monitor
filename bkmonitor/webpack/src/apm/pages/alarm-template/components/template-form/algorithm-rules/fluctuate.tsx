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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { random } from 'monitor-common/utils';

import { LEVEL_LIST, YEAR_ROUND_AND_RING_RATION_ALGORITHM } from '../constant';
import {
  type FluctuateAlgorithm,
  type YearRoundAndRingRatioAlgorithmType,
  AlgorithmEnum,
  YearRoundAndRingRatioAlgorithmEnum,
} from '../typing';

import './fluctuate.scss';

interface FluctuateEvents {
  onChange: (val: FluctuateAlgorithm) => void;
}

interface FluctuateProps {
  algorithmList: FluctuateAlgorithm[];
  data: FluctuateAlgorithm;
}

@Component
export default class Fluctuate extends tsc<FluctuateProps, FluctuateEvents> {
  @Prop({ default: null }) data: FluctuateAlgorithm;
  @Prop({ default: () => [] }) algorithmList: FluctuateAlgorithm[];

  localData: FluctuateAlgorithm = {
    id: random(8),
    level: 1,
    type: AlgorithmEnum.YearRoundAndRingRatio,
    unit_prefix: '',
    config: {
      method: YearRoundAndRingRatioAlgorithmEnum.FiveMinuteRingRatio,
      ceil: 100,
      floor: 100,
    },
  };

  /** 已选择的告警级别 */
  get levelList() {
    const otherAlgorithmList = this.algorithmList.filter(algorithm => algorithm !== this.data);
    return LEVEL_LIST.map(level => {
      return {
        ...level,
        disabled: otherAlgorithmList.some(algorithm => algorithm.level === level.id),
      };
    });
  }

  get categoryList() {
    return YEAR_ROUND_AND_RING_RATION_ALGORITHM.map(item => {
      return {
        ...item,
        disabled: false,
      };
    });
  }

  handleLevelChange(level: 1 | 2 | 3) {
    this.localData.level = level;
    this.handleChange();
  }

  handleCategoryChange(method: YearRoundAndRingRatioAlgorithmType) {
    this.localData.config.method = method;
    this.handleChange();
  }

  handleValueChange(type: 'ceil' | 'floor', value: number) {
    this.localData.config[type] = value;
    this.handleChange();
  }

  @Emit('change')
  handleChange() {
    return this.localData;
  }

  mounted() {
    if (this.data) {
      this.localData = this.data;
    }
  }

  render() {
    return (
      <div class='alarm-template-fluctuate-detect'>
        <div class='alarm-level form-item'>
          <div class='form-item-title'>{this.$t('告警级别')}</div>
          <div class='form-item-content'>
            <bk-select
              ext-cls='level-select'
              behavior='simplicity'
              clearable={false}
              ext-popover-cls='algorithm-rules-level-select-popover'
              prefix-icon={`icon-monitor ${this.levelList[this.localData.level - 1].icon}`}
              value={this.localData.level}
              onChange={this.handleLevelChange}
            >
              {this.levelList.map(level => (
                <bk-option
                  id={level.id}
                  key={level.id}
                  v-bk-tooltips={{
                    content: this.$t('已有相同算法,设置为{name}级别', { name: level.name }),
                    disabled: !level.disabled,
                    allowHTML: false,
                  }}
                  disabled={level.disabled}
                  name={level.name}
                >
                  <i class={`icon-monitor ${level.icon}`} />
                  <span class='name'>{level.name}</span>
                </bk-option>
              ))}
            </bk-select>
          </div>
        </div>
        <div class='alarm-condition form-item'>
          <div class='form-item-title'>{this.$t('告警条件')}</div>
          <div class='form-item-content'>
            <i18n
              class='algorithm-category flex'
              path='较{0}对比'
              tag='div'
            >
              <bk-select
                class='inline-select'
                behavior='simplicity'
                clearable={false}
                value={this.localData.config.method}
                onChange={this.handleCategoryChange}
              >
                {this.categoryList.map(opt => (
                  <bk-option
                    id={opt.id}
                    key={opt.id}
                    name={opt.name}
                  />
                ))}
              </bk-select>
            </i18n>
            ，
            <div class='algorithm-value'>
              <i18n
                class='flex'
                path='上升{0}%时触发告警'
                tag='div'
              >
                <bk-input
                  class='w80'
                  behavior='simplicity'
                  clearable={false}
                  max={100}
                  min={1}
                  show-controls={false}
                  type='number'
                  value={this.localData.config.ceil}
                  onBlur={value => {
                    this.handleValueChange('ceil', value);
                  }}
                  onEnter={value => {
                    this.handleValueChange('ceil', value);
                  }}
                />
              </i18n>
              <i18n
                class='flex'
                path='下降{0}%时触发告警'
                tag='div'
              >
                <bk-input
                  class='w80'
                  behavior='simplicity'
                  clearable={false}
                  max={100}
                  min={1}
                  show-controls={false}
                  type='number'
                  value={this.localData.config.floor}
                  onBlur={value => {
                    this.handleValueChange('floor', value);
                  }}
                  onEnter={value => {
                    this.handleValueChange('floor', value);
                  }}
                />
              </i18n>
            </div>
          </div>
        </div>
      </div>
    );
  }
}
