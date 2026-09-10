/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { defineComponent } from 'vue';

import { navigateToLogTab, openLogClusteringPlaceholder } from '../navigate';
import AnalysisDetailContent from './analysis-detail-content';
import SuspiciousAnalysisGroup from './suspicious-analysis-group';

import type { IPatternBlock } from '../typing';

import './log-panel.scss';

const MOCK_LOG_CLUSTERS = [
  {
    logCount: 212,
    pattern: 'systemd: Started Session * of user root',
    demoLog: JSON.stringify({
      dtEventTimeStamp: 1713612122000,
      ip: '10.0.34.2',
      path: '/var/log/messages',
      log: 'systemd: Started Session 2334 of user root',
    }),
  },
  {
    logCount: 86,
    pattern: '* probe failed: dial tcp *: i/o timeout',
    demoLog: JSON.stringify({
      dtEventTimeStamp: 1713611921000,
      ip: '10.0.34.8',
      path: '/var/log/kubelet.log',
      log: 'Liveness probe failed: dial tcp 10.0.34.8:8080: i/o timeout',
    }),
  },
];

export default defineComponent({
  name: 'LogPanel',
  setup() {
    const handleBlockJump = (block: IPatternBlock & { jumpable?: boolean }, item: (typeof MOCK_LOG_CLUSTERS)[0]) => {
      let keyword = item.demoLog;
      try {
        const parsed = JSON.parse(item.demoLog);
        keyword = parsed?.log || item.demoLog;
      } catch {
        keyword = item.demoLog;
      }
      navigateToLogTab(keyword);
    };

    return {
      handleBlockJump,
    };
  },
  render() {
    return (
      <div class='suspicious-log-panel'>
        <div class='card-summary'>
          <div class='card-summary-title'>{this.$t('日志分析总结：')}</div>
          <div>
            {this.$t('对告警窗口内异常日志做了聚类，下面给出出现次数最高的 Pattern 和对应示例日志，便于对照排查。')}
          </div>
        </div>
        <div class='log-group-list'>
          {MOCK_LOG_CLUSTERS.map((item, index) => (
            <SuspiciousAnalysisGroup key={item.pattern}>
              {{
                title: () => (
                  <div class='group-title'>
                    <span class='group-name'>
                      {`${this.$t('聚类结果')} ${index + 1}`}
                      <i
                        class='icon-monitor icon-fenxiang jump-btn'
                        onClick={e => {
                          e.stopPropagation();
                          openLogClusteringPlaceholder(item.pattern);
                        }}
                      />
                      <i18n-t
                        class='group-count'
                        keypath='（共 {0} 条日志）'
                        tag='span'
                      >
                        <span class='count-strong'>{item.logCount}</span>
                      </i18n-t>
                    </span>
                  </div>
                ),
                default: () => (
                  <AnalysisDetailContent
                    blocks={[
                      { title: 'Pattern：', value: item.pattern, kind: 'text' },
                      {
                        title: this.$t('示例日志：') as string,
                        value: item.demoLog,
                        kind: 'json',
                        jumpable: true,
                      },
                    ]}
                    tableData={[]}
                    contentData={[]}
                    onBlockJump={block => this.handleBlockJump(block, item)}
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
