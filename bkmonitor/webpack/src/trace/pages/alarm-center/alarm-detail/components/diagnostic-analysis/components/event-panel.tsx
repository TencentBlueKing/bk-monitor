/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { defineComponent } from 'vue';

import { ChatResultKind } from '../chat/chat-result-typing';
import { DiagnosticTypeEnum, DiagnosticTypeMap } from '../constant';
import AnalysisDetailContent from './analysis-detail-content';
import SuspiciousAnalysisGroup from './suspicious-analysis-group';
import { useAlarmCenterDetailStore } from '@/store/modules/alarm-center-detail';

import './event-panel.scss';

const MOCK_EVENT_GROUPS = [
  {
    title: 'K8s 事件',
    unit: '事件',
    total: 20,
    top: 'Top2',
    items: [
      {
        name: 'FailedMount',
        tableData: [
          { name: '发生时间', value: '2024-04-20 19:22:02' },
          { name: '事件名', value: 'FailedMount' },
          {
            name: '事件内容',
            value: 'MountVolume.SetUp failed for volume "kube-api-access-xxx": object "default"/"sa-token" not found',
          },
        ],
      },
      {
        name: 'Unhealthy',
        tableData: [
          { name: '发生时间', value: '2024-04-20 19:18:41' },
          { name: '事件名', value: 'Unhealthy' },
          {
            name: '事件内容',
            value: 'Liveness probe failed: Get "http://10.0.34.2:8080/healthz": context deadline exceeded (io timeout)',
          },
        ],
      },
    ],
  },
  {
    title: 'ITSM 系统事件',
    unit: '事件',
    total: 10,
    top: 'Top2',
    items: [
      {
        name: '变更单审批超时',
        tableData: [
          { name: '发生时间', value: '2024-04-20 18:05:11' },
          { name: '事件名', value: '变更单审批超时' },
          { name: '事件内容', value: 'ITSM ticket TICKET-20240420-118 超过 30 分钟未完成审批' },
        ],
      },
    ],
  },
];

export default defineComponent({
  name: 'EventPanel',
  setup() {
    const store = useAlarmCenterDetailStore();

    /** 点事件总数：在会话里回显这组事件的列表 */
    const handleTotalClick = (event: MouseEvent, group: (typeof MOCK_EVENT_GROUPS)[number]) => {
      event.stopPropagation();
      store.requestChatResult({
        kind: ChatResultKind.EVENT_LIST,
        question: window.i18n.t('{0} 这 {1} 个{2}分别是什么？', [group.title, group.total, group.unit]) as string,
        context: { eventGroup: group.title, eventTotal: group.total, eventUnit: group.unit },
      });
    };

    return {
      chatCategory: DiagnosticTypeMap[DiagnosticTypeEnum.EVENT] as string,
      handleTotalClick,
    };
  },
  render() {
    return (
      <div class='suspicious-event-panel'>
        <div class='card-summary'>
          <div class='card-summary-title'>{this.$t('事件分析总结：')}</div>
          <div>
            {this.$t('通过分析告警产生前 1 小时时间窗口事件，识别出与当前告警高度相关的 K8s 与变更事件，示例如下。')}
          </div>
        </div>
        <div class='event-group-list'>
          {MOCK_EVENT_GROUPS.map(group => (
            <SuspiciousAnalysisGroup
              key={group.title}
              tone='event'
            >
              {{
                title: () => (
                  <div class='group-title event-parent-title'>
                    <span class='event-icon'>
                      <i class='icon-monitor icon-shijianjiansuo' />
                    </span>
                    <span class='group-name'>{group.title}</span>
                    <span class='group-count'>
                      <i18n-t keypath='（共 {0} 个{1}，展示 {2} 如下）'>
                        <span
                          class='count-strong is-clickable'
                          v-bk-tooltips={{ content: this.$t('查看详情') }}
                          onClick={e => this.handleTotalClick(e, group)}
                        >
                          {group.total}
                        </span>
                        <span>{group.unit}</span>
                        <span class='count-strong'>{group.top}</span>
                      </i18n-t>
                    </span>
                  </div>
                ),
                default: () =>
                  group.items.map(item => (
                    <SuspiciousAnalysisGroup
                      key={item.name}
                      tone='inner'
                    >
                      {{
                        title: () => (
                          <div class='group-title'>
                            <span
                              class='group-name'
                              data-chat-category={this.chatCategory}
                              data-chat-label={this.$t('事件名')}
                              data-chat-text={item.name}
                            >
                              {item.name}
                            </span>
                          </div>
                        ),
                        default: () => (
                          <AnalysisDetailContent
                            chatCategory={this.chatCategory}
                            tableData={item.tableData}
                            contentData={[]}
                          />
                        ),
                      }}
                    </SuspiciousAnalysisGroup>
                  )),
              }}
            </SuspiciousAnalysisGroup>
          ))}
        </div>
      </div>
    );
  },
});
