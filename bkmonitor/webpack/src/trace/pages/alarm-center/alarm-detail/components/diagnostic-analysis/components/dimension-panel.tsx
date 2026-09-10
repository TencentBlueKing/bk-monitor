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
import { computed, defineComponent } from 'vue';

import { storeToRefs } from 'pinia';

import { isHostNavigableDimension, navigateToHostTab, navigateToViewDimensions, openStrategyDetail } from '../navigate';
import AnalysisDetailContent from './analysis-detail-content';
import SuspiciousAnalysisGroup from './suspicious-analysis-group';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import type { ITableItem } from '../typing';

import './dimension-panel.scss';

interface IDimensionStrategy {
  strategy_id: number;
  strategy_name: string;
}

interface IDimensionGroup {
  alertCount: number;
  /** 该维度组合下关联告警所属的策略；多策略时「包含 x 个告警」跳转首个策略详情 */
  strategies: IDimensionStrategy[];
  score: string;
  tableData: ITableItem[];
}

/** 【临时联调 mock】维度下钻结果，联调就绪后替换为接口数据 */
const MOCK_DIMENSION_GROUPS: IDimensionGroup[] = [
  {
    score: '90%',
    alertCount: 3,
    strategies: [
      { strategy_id: 1001, strategy_name: '日志平台 - es 磁盘容量告警' },
      { strategy_id: 1002, strategy_name: '蓝鲸 - es 磁盘容量告警' },
    ],
    tableData: [
      { name: '主机名', value: 'VM-156-110-centos', link: true },
      { name: '目标 IP', value: '11.185.157.110', link: true },
      { name: '管控区域', value: '0' },
      { name: 'Key 占位', value: 'Value 占位' },
    ],
  },
  {
    score: '80%',
    alertCount: 2,
    strategies: [{ strategy_id: 1001, strategy_name: '日志平台 - es 磁盘容量告警' }],
    tableData: [
      { name: '主机名', value: 'VM-156-110-centos', link: true },
      { name: '目标 IP', value: '11.185.157.111', link: true },
      { name: '管控区域', value: '0' },
      { name: 'Key 占位', value: 'Value 占位' },
    ],
  },
  {
    score: '80%',
    alertCount: 1,
    strategies: [{ strategy_id: 1002, strategy_name: '蓝鲸 - es 磁盘容量告警' }],
    tableData: [
      { name: '主机名', value: 'VM-156-110-centos', link: true },
      { name: '目标 IP', value: '11.185.157.112', link: true },
      { name: '管控区域', value: '0' },
      { name: 'Key 占位', value: 'Value 占位' },
    ],
  },
];

/** mock 里的占位维度，用告警真实可下钻维度替换，跳转维度分析时才有维度可选中 */
const PLACEHOLDER_DIMENSION_NAME = 'Key 占位';

export default defineComponent({
  name: 'DimensionPanel',
  setup() {
    const { viewDimensionList } = storeToRefs(useAlarmCenterDetailStore());

    /** 【临时联调 mock】把占位维度替换成该告警真实维度，每组各取一个便于区分选中效果 */
    const dimensionGroups = computed<IDimensionGroup[]>(() => {
      const realDimensions = viewDimensionList.value;
      if (!realDimensions.length) return MOCK_DIMENSION_GROUPS;
      return MOCK_DIMENSION_GROUPS.map((group, index) => ({
        ...group,
        tableData: group.tableData.map(item =>
          item.name === PLACEHOLDER_DIMENSION_NAME
            ? { ...item, name: realDimensions[index % realDimensions.length].name }
            : item
        ),
      }));
    });

    const handleDimensionValueClick = (item: ITableItem) => {
      if (!isHostNavigableDimension(item.name)) return;
      navigateToHostTab(item);
    };

    const handleJumpDimensionAnalysis = (event: MouseEvent, tableData: ITableItem[]) => {
      event.stopPropagation();
      navigateToViewDimensions(tableData);
    };

    /** 包含 x 个告警：跳转该组关联策略详情（多策略时取首个） */
    const handleAlertCountClick = (event: MouseEvent, group: IDimensionGroup) => {
      event.stopPropagation();
      const strategyId = group.strategies[0]?.strategy_id;
      if (strategyId === undefined) return;
      openStrategyDetail(strategyId);
    };

    const handleStrategyClick = (event: MouseEvent, strategy: IDimensionStrategy) => {
      event.stopPropagation();
      openStrategyDetail(strategy.strategy_id);
    };

    return {
      dimensionGroups,
      handleDimensionValueClick,
      handleJumpDimensionAnalysis,
      handleAlertCountClick,
      handleStrategyClick,
    };
  },
  render() {
    return (
      <div class='suspicious-dimension-panel'>
        <div class='panel-header'>
          <span class='tips'>{this.$t('故障关联的告警，统计出最异常的维度（组合）：')}</span>
          <span class='link-text view-all'>
            {this.$t('查看全部')}
            <i class='icon-monitor icon-fenxiang' />
          </span>
        </div>
        <div class='dimension-group-list'>
          {this.dimensionGroups.map((group, index) => (
            <SuspiciousAnalysisGroup
              key={group.strategies.map(item => item.strategy_id).join('-')}
              defaultExpand={index === 0}
              tone='inner'
            >
              {{
                title: () => (
                  <div class='group-title'>
                    <span class='group-name'>
                      {`${this.$t('异常维度（组合）')} ${index + 1}`}
                      <i
                        class='icon-monitor icon-fenxiang jump-btn'
                        onClick={e => this.handleJumpDimensionAnalysis(e, group.tableData)}
                      />
                    </span>
                    <i18n-t
                      class='abnormality-score'
                      keypath='异常程度 {0}'
                      tag='span'
                    >
                      <span class='score-value'>{group.score}</span>
                    </i18n-t>
                  </div>
                ),
                default: () => (
                  <AnalysisDetailContent
                    tableData={group.tableData}
                    contentData={[]}
                    onValueClick={this.handleDimensionValueClick}
                  />
                ),
                footer: () => (
                  <div class='footer-content'>
                    <i18n-t
                      class='footer-item'
                      keypath='包含 {0} 个告警，来源于以下 {1} 个策略：'
                      tag='span'
                    >
                      <b
                        class='link-text'
                        onClick={e => this.handleAlertCountClick(e, group)}
                      >
                        {group.alertCount}
                      </b>
                      <b class='count-strong'>{group.strategies.length}</b>
                    </i18n-t>
                    {group.strategies.map(strategy => (
                      <span
                        key={strategy.strategy_id}
                        class='footer-item'
                      >
                        <span
                          class='link-text'
                          onClick={e => this.handleStrategyClick(e, strategy)}
                        >
                          {strategy.strategy_name}
                        </span>
                      </span>
                    ))}
                  </div>
                ),
              }}
            </SuspiciousAnalysisGroup>
          ))}
        </div>
      </div>
    );
  },
});
