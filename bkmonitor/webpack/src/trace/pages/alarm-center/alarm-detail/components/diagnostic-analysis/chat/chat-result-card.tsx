/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 */
import { type PropType, defineComponent, shallowRef } from 'vue';
import { useI18n } from 'vue-i18n';

import { DiagnosticTypeEnum, DiagnosticTypeMap } from '../constant';
import ChatResultChart from './chat-result-chart';
import { ChatResultKind } from './chat-result-typing';

import type {
  IChatAlertListResult,
  IChatEventListResult,
  IChatLogClusterResult,
  IChatMetricResult,
  IChatResult,
} from './chat-result-typing';

import './chat-result-card.scss';

/** 列表类结果每次展开的条数 */
const PAGE_SIZE = 5;

/** 告警级别展示 */
const SEVERITY_MAP: Record<number, { text: string; theme: string }> = {
  1: { text: window.i18n.t('致命') as string, theme: 'fatal' },
  2: { text: window.i18n.t('预警') as string, theme: 'warning' },
  3: { text: window.i18n.t('提醒') as string, theme: 'remind' },
};

export default defineComponent({
  name: 'ChatResultCard',
  props: {
    result: {
      type: Object as PropType<IChatResult>,
      required: true,
    },
  },
  setup() {
    const { t } = useI18n();
    /** 列表类结果先露出一批，其余点「展开更多」逐批追加 */
    const visibleCount = shallowRef(PAGE_SIZE);

    const handleExpandMore = () => {
      visibleCount.value += PAGE_SIZE;
    };

    return { t, visibleCount, handleExpandMore };
  },
  render() {
    /** 超出当前可见条数时给出展开入口 */
    const renderExpandMore = (total: number) =>
      total > this.visibleCount ? (
        <div
          class='chat-result-expand'
          data-hover-menu-avoid=''
          onClick={this.handleExpandMore}
        >
          {this.t('展开更多')}
          <i class='icon-monitor icon-arrow-down' />
        </div>
      ) : undefined;

    const renderMetric = (result: IChatMetricResult) => (
      <div class='chat-result-card is-metric'>
        <div class='chat-result-card-title'>{result.title}</div>
        {result.conditions.length ? (
          <div class='chat-result-conditions'>
            {result.conditions.map(item => (
              <span
                key={`${item.name}-${item.value}`}
                class='condition-tag'
                data-chat-category={DiagnosticTypeMap[DiagnosticTypeEnum.DIMENSION]}
                data-chat-label={item.name}
                data-chat-text={item.value}
              >
                {`${item.name} = ${item.value}`}
              </span>
            ))}
          </div>
        ) : undefined}
        <ChatResultChart series={result.series} />
      </div>
    );

    const renderAlertList = (result: IChatAlertListResult) => (
      <div class='chat-result-card is-alert-list'>
        <div class='chat-result-card-title'>
          <i18n-t keypath='共 {0} 个告警'>
            <span class='count-strong'>{result.total}</span>
          </i18n-t>
        </div>
        <div class='chat-result-list'>
          {result.alerts.slice(0, this.visibleCount).map(item => (
            <div
              key={item.id}
              class='chat-result-list-item'
            >
              <div class='item-head'>
                <span class={['severity-tag', SEVERITY_MAP[item.severity]?.theme]}>
                  {SEVERITY_MAP[item.severity]?.text}
                </span>
                <span
                  class='item-name'
                  data-chat-category={DiagnosticTypeMap[DiagnosticTypeEnum.DIMENSION]}
                  data-chat-label={this.t('告警名称')}
                  data-chat-text={item.name}
                >
                  {item.name}
                </span>
              </div>
              <div class='item-meta'>
                <span class='meta-cell'>{item.strategyName}</span>
                <span class='meta-cell'>{item.beginTime}</span>
                <span class='meta-cell'>{item.status}</span>
              </div>
            </div>
          ))}
        </div>
        {renderExpandMore(result.alerts.length)}
      </div>
    );

    const renderLogCluster = (result: IChatLogClusterResult) => (
      <div class='chat-result-card is-log-cluster'>
        <div class='chat-result-card-title'>
          <i18n-t keypath='该 Pattern 共匹配到 {0} 条日志'>
            <span class='count-strong'>{result.logCount}</span>
          </i18n-t>
        </div>
        <div class='chat-result-block'>
          <div class='block-title'>Pattern：</div>
          <div
            class='block-value'
            data-chat-category={DiagnosticTypeMap[DiagnosticTypeEnum.LOG]}
            data-chat-label='Pattern'
            data-chat-text={result.pattern}
          >
            {result.pattern}
          </div>
        </div>
        <ChatResultChart series={result.trend} />
        <div class='chat-result-block'>
          <div class='block-title'>{this.t('示例日志：')}</div>
          {result.demoLogs.slice(0, this.visibleCount).map((log, index) => (
            <div
              key={index}
              class='block-value is-json'
              data-chat-category={DiagnosticTypeMap[DiagnosticTypeEnum.LOG]}
              data-chat-label={this.t('示例日志')}
              data-chat-text={log}
            >
              {log}
            </div>
          ))}
          {renderExpandMore(result.demoLogs.length)}
        </div>
      </div>
    );

    const renderEventList = (result: IChatEventListResult) => (
      <div class='chat-result-card is-event-list'>
        <div class='chat-result-card-title'>
          <i18n-t keypath='共 {0} 个{1}'>
            <span class='count-strong'>{result.total}</span>
            <span>{result.unit}</span>
          </i18n-t>
        </div>
        <div class='chat-result-list'>
          {result.events.slice(0, this.visibleCount).map((item, index) => (
            <div
              key={`${item.name}-${index}`}
              class='chat-result-list-item'
            >
              <div class='item-head'>
                <span class='source-tag'>{item.source}</span>
                <span
                  class='item-name'
                  data-chat-category={DiagnosticTypeMap[DiagnosticTypeEnum.EVENT]}
                  data-chat-label={this.t('事件名')}
                  data-chat-text={item.name}
                >
                  {item.name}
                </span>
              </div>
              <div
                class='item-content'
                data-chat-category={DiagnosticTypeMap[DiagnosticTypeEnum.EVENT]}
                data-chat-label={this.t('事件内容')}
                data-chat-text={item.content}
              >
                {item.content}
              </div>
              <div class='item-meta'>
                <span class='meta-cell'>{item.time}</span>
              </div>
            </div>
          ))}
        </div>
        {renderExpandMore(result.events.length)}
      </div>
    );

    switch (this.result.kind) {
      case ChatResultKind.METRIC:
        return renderMetric(this.result);
      case ChatResultKind.ALERT_LIST:
        return renderAlertList(this.result);
      case ChatResultKind.LOG_CLUSTER:
        return renderLogCluster(this.result);
      case ChatResultKind.EVENT_LIST:
        return renderEventList(this.result);
      default:
        return null;
    }
  },
});
