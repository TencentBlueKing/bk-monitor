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
import ThresholdIcon from 'monitor-pc/static/images/svg/threshold.svg';
import AdvancedIcon from 'monitor-pc/static/images/svg/year-round.svg';

import { ALGORITHM_RELATIONSHIP } from '../constant';
import {
  type AlgorithmItem,
  type AlgorithmItemUnion,
  type AlgorithmType,
  type FluctuateAlgorithm,
  type SelectAlgorithmConfig,
  AlgorithmEnum,
  YearRoundAndRingRatioAlgorithmEnum,
} from '../typing';
import Fluctuate from './fluctuate';
import Threshold from './threshold';

import './algorithm-rules.scss';

interface AlgorithmRulesEvents {
  onChange: (algorithms: AlgorithmItemUnion[]) => void;
  onConnectorChange: (val: string) => void;
}

interface AlgorithmRulesProps {
  algorithms: AlgorithmItemUnion[];
  algorithmsUnit?: string;
  connector?: string;
}

type LocalAlgorithm = FluctuateAlgorithm | { data: AlgorithmItem<'Threshold'>[]; id: string; type: 'Threshold' };

@Component
export default class AlgorithmRules extends tsc<AlgorithmRulesProps, AlgorithmRulesEvents> {
  @Prop({ default: () => [] }) algorithms: AlgorithmItemUnion[];
  @Prop({ default: '' }) algorithmsUnit: string;
  @Prop({ default: 'and' }) connector: string;

  /** 各种规则检测配置 */
  get algorithmCategoryConfig(): { [key in AlgorithmType]: SelectAlgorithmConfig } {
    return {
      [AlgorithmEnum.Threshold]: {
        id: AlgorithmEnum.Threshold,
        name: this.$t('静态阈值') as string,
        icon: ThresholdIcon,
        disabled: this.localAlgorithms.some(item => item.type === AlgorithmEnum.Threshold),
        disabledTips: this.$t('静态阈值算法只能添加一次') as string,
      },
      [AlgorithmEnum.YearRoundAndRingRatio]: {
        id: AlgorithmEnum.YearRoundAndRingRatio,
        name: this.$t('同环比') as string,
        icon: AdvancedIcon,
        disabled: this.localAlgorithms.filter(item => item.type === AlgorithmEnum.YearRoundAndRingRatio).length === 3,
        disabledTips: this.$t('同环比算法最多添加三个级别') as string,
      },
    };
  }

  get algorithmCategoryLevel() {
    return {};
  }

  /** 本地告警规则数据 */
  localAlgorithms: Array<LocalAlgorithm> = [];

  /** 展示选择 */
  isShowAlgorithmsSelect = false;

  @Emit('change')
  handleAlgorithmsChange(): AlgorithmItemUnion[] {
    return this.localAlgorithms.reduce((pre, cur) => {
      const algorithms = structuredClone(cur);
      delete algorithms.id;
      if (algorithms.type === AlgorithmEnum.Threshold) {
        pre.push(...algorithms.data);
      } else {
        pre.push(algorithms);
      }
      return pre;
    }, []);
  }

  @Emit('connectorChange')
  handleConnectorChange(val: string) {
    return val;
  }

  init() {
    this.localAlgorithms = [];
    this.isShowAlgorithmsSelect = this.algorithms.length === 0;
    for (const item of this.algorithms) {
      switch (item.type) {
        case AlgorithmEnum.Threshold: {
          const threshold = this.localAlgorithms.find(item => item.type === AlgorithmEnum.Threshold);
          if (!threshold) {
            this.localAlgorithms.push({
              id: random(8),
              type: AlgorithmEnum.Threshold,
              data: [item],
            });
          } else {
            threshold.data.push(item);
          }
          break;
        }
        case AlgorithmEnum.YearRoundAndRingRatio:
          this.localAlgorithms.push({
            ...item,
            id: random(8),
          });
          break;
        default:
          break;
      }
    }
  }

  /** 渲染检测规则 */
  renderAlgorithmRules(item: LocalAlgorithm, index: number) {
    switch (item.type) {
      case AlgorithmEnum.Threshold:
        return (
          <Threshold
            data={item.data}
            defaultUnit={this.algorithmsUnit}
            onChange={this.handleThresholdAlgorithmsChange}
          />
        );
      case AlgorithmEnum.YearRoundAndRingRatio:
        return (
          <Fluctuate
            algorithmList={this.localAlgorithms.filter(item => item.type === AlgorithmEnum.YearRoundAndRingRatio)}
            data={item}
            onChange={val => {
              this.handleYearRoundAndRingRatioAlgorithmsChange(val, index);
            }}
          />
        );
      default:
        return null;
    }
  }

  /** 删除检测规则 */
  handleDelete(index: number) {
    this.localAlgorithms.splice(index, 1);
    this.handleAlgorithmsChange();
    this.isShowAlgorithmsSelect = this.localAlgorithms.length === 0;
  }

  /** 添加检测规则 */
  handleSelectAlgorithms(item: SelectAlgorithmConfig) {
    if (item.disabled) return;
    switch (item.id) {
      case AlgorithmEnum.Threshold: {
        this.localAlgorithms.push({
          id: random(8),
          type: item.id,
          data: [
            {
              type: item.id,
              unit_prefix: '',
              level: 1,
              config: {
                method: 'gte',
                threshold: 1,
              },
            },
          ],
        });
        break;
      }
      case AlgorithmEnum.YearRoundAndRingRatio: {
        const algorithms = this.localAlgorithms.filter(item => item.type === AlgorithmEnum.YearRoundAndRingRatio);
        const level = [1, 2, 3].find(item => !algorithms.some(algorithms => algorithms.level === item)) || 1;
        this.localAlgorithms.push({
          id: random(8),
          type: item.id,
          unit_prefix: '',
          level: level as 1 | 2 | 3,
          config: {
            ceil: 1,
            floor: 1,
            method: YearRoundAndRingRatioAlgorithmEnum.FiveMinuteRingRatio,
          },
        });
        break;
      }
    }
    this.handleAlgorithmsChange();
    setTimeout(() => {
      this.isShowAlgorithmsSelect = false;
    }, 16);
  }

  /** 静态阈值规则变更 */
  handleThresholdAlgorithmsChange(val: AlgorithmItem<'Threshold'>[]) {
    const item = this.localAlgorithms.find(item => item.type === AlgorithmEnum.Threshold);
    item.data = val;
    this.handleAlgorithmsChange();
  }

  handleYearRoundAndRingRatioAlgorithmsChange(val: FluctuateAlgorithm, index: number) {
    this.localAlgorithms[index] = val;
    this.handleAlgorithmsChange();
  }

  handleShowAlgorithmsSelect() {}

  mounted() {
    this.init();
  }

  render() {
    return (
      <div class='alarm-template-algorithm-rules'>
        <i18n
          class='algorithm-relation'
          path='同级别的各算法之间是{0}的关系'
        >
          <bk-select
            class='inline-select'
            behavior='simplicity'
            clearable={false}
            value={this.connector}
            onChange={this.handleConnectorChange}
          >
            {ALGORITHM_RELATIONSHIP.map(opt => (
              <bk-option
                id={opt.id}
                key={opt.id}
                name={opt.name}
              />
            ))}
          </bk-select>
        </i18n>
        {this.localAlgorithms.map((item, index) => (
          <div
            key={item.id}
            class='algorithm-rules-wrapper'
          >
            <div class='algorithm-rules-header'>
              <div class='title-wrap'>
                <img
                  class='type-icon'
                  alt=''
                  src={this.algorithmCategoryConfig[item.type].icon}
                />
                <span class='title'>{this.algorithmCategoryConfig[item.type].name}</span>
              </div>
              <span
                class='icon-monitor icon-mc-delete-line del-btn'
                onClick={() => this.handleDelete(index)}
              />
            </div>
            <div class='algorithm-rules-content'>{this.renderAlgorithmRules(item, index)}</div>
          </div>
        ))}
        <div class='add-algorithm-rules-wrapper'>
          {this.isShowAlgorithmsSelect ? (
            <div class='select-algorithms'>
              <div class='select-algorithms-title'>{this.$t('选择算法')}</div>
              <div class='algorithms-category-item'>
                <div class='category-title'>{this.$t('常规算法')}</div>
                <div class='category-child'>
                  {Object.values(this.algorithmCategoryConfig).map(item => (
                    <div
                      key={item.id}
                      class={['child-item', { disabled: item.disabled }]}
                      v-bk-tooltips={{
                        content: item.disabledTips,
                        disabled: !item.disabled,
                      }}
                      onClick={() => {
                        this.handleSelectAlgorithms(item);
                      }}
                    >
                      <img
                        class='type-icon'
                        alt=''
                        src={item.icon}
                      />
                      <span class='algorithms-name'>{item.name}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            <div
              class='add-btn'
              onClick={() => {
                this.isShowAlgorithmsSelect = true;
              }}
            >
              <i class='icon-monitor icon-plus-line' />
              <span class='btn-text'>{this.$t('检测规则')}</span>
            </div>
          )}
        </div>
      </div>
    );
  }
}
