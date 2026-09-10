/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { defineComponent } from 'vue';

import { navigateToTraceBySpan, navigateToTraceTab } from '../navigate';
import AnalysisDetailContent from './analysis-detail-content';
import SuspiciousAnalysisGroup from './suspicious-analysis-group';

import type { ITableItem } from '../typing';

import './link-panel.scss';

const MOCK_TRACE_RESULTS = [
  {
    logCount: 2,
    pattern: "TypeError: '<' not supported between instances of 'str' and 'int'",
    tableData: [
      { name: 'Span ID', value: 'a1b2c3d4e5f60718', link: true },
      { name: '所属 Trace', value: '7160731cd9fe607033c1ae7d7a5f449b', link: true },
      { name: '所属应用', value: 'bkmonitorv3', link: true },
      { name: '所属服务', value: 'unify-query', link: true },
      { name: '调用类型', value: 'SERVER', link: true },
      {
        name: '异常信息',
        value: "TypeError: '<' not supported between instances of 'str' and 'int' in IncidentHandlersResource",
      },
    ],
  },
];

export default defineComponent({
  name: 'LinkPanel',
  setup() {
    const handleValueClick = (item: ITableItem, tableData: ITableItem[]) => {
      navigateToTraceTab(item, tableData);
    };

    const handleSpanTitleClick = (tableData: ITableItem[]) => {
      navigateToTraceBySpan(tableData);
    };

    return {
      handleValueClick,
      handleSpanTitleClick,
    };
  },
  render() {
    return (
      <div class='suspicious-link-panel'>
        <div class='card-summary'>
          <div class='card-summary-title'>{this.$t('Trace 分析总结：')}</div>
          <div>
            {this.$t(
              '在关联调用链中定位到异常 Span，下面给出 Pattern 与示例 span 明细，点击字段可跳转到 Trace 检索。'
            )}
          </div>
        </div>
        <div class='link-group-list'>
          {MOCK_TRACE_RESULTS.map((item, index) => (
            <SuspiciousAnalysisGroup key={item.pattern}>
              {{
                title: () => (
                  <div class='group-title'>
                    <span class='group-name'>
                      {`${this.$t('分析结果')} ${index + 1}`}
                      <i18n-t
                        class='group-count'
                        keypath='（共 {0} 条异常信息）'
                        tag='span'
                      >
                        <span class='count-strong'>{item.logCount}</span>
                      </i18n-t>
                    </span>
                  </div>
                ),
                default: () => (
                  <AnalysisDetailContent
                    blocks={[{ title: 'Pattern：', value: item.pattern, kind: 'text' }]}
                    tableTitle={this.$t('示例 span：') as string}
                    tableTitleClickable
                    tableData={item.tableData}
                    contentData={[]}
                    onTableTitleClick={() => this.handleSpanTitleClick(item.tableData)}
                    onValueClick={row => this.handleValueClick(row, item.tableData)}
                  />
                ),
              }}
            </SuspiciousAnalysisGroup>
          ))}
        </div>
      </div>
    );
  },
});
