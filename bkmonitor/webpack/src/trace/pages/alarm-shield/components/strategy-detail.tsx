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
import { type PropType, defineComponent } from 'vue';

import { useI18n } from 'vue-i18n';

import { methodMap } from '../typing';

import './strategy-detail.scss';

export default defineComponent({
  name: 'StrategyDetail',
  props: {
    strategyData: {
      type: Object as PropType<any>,
      default: () => null,
    },
    detects: {
      type: Object as PropType<any>,
      default: () => null,
    },
    simple: {
      type: Boolean,
      default: false,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const levelMap = ['', t('致命'), t('提醒'), t('预警')];
    // 事件
    function getEventContent(queryConfig) {
      return (
        <div class='item-content'>
          <div class='column-item'>
            <div class='column-label'> {t('事件名称')} : </div>
            <div class='column-content item-font'>{props.strategyData.name}</div>
          </div>
          <div class='column-item'>
            <div class='column-label'> {t('告警级别')} : </div>
            <div class='column-content item-font'>{levelMap[props.strategyData.detects?.[0].level || 0]}</div>
          </div>
          {queryConfig.data_type_label === 'event' && queryConfig.data_source_label === 'custom' ? (
            <div class='column-item column-item-agg-condition'>
              <div class='column-label column-target'> {t('监控条件')} : </div>
              <div class='column-agg-condition'>
                {queryConfig.agg_condition.map((item, index) => [
                  index > 0 && <div class='column-agg-dimension mb-2'>{item.condition}</div>,
                  <div
                    key={index}
                    class='column-agg-dimension mb-2'
                  >{`${item.key} ${methodMap[item.method]} ${item.value.join(',')}`}</div>,
                ])}
              </div>
            </div>
          ) : undefined}
        </div>
      );
    }
    // 监控采集
    function getTimeSeriesContent(queryConfig) {
      return (
        <div class='item-content'>
          {[
            queryConfig.data_type_label === 'log'
              ? [
                  <div class='column-item'>
                    <div class='column-label'> {t('索引集')} : </div>
                    <div class='column-center'>{queryConfig.metric_field}</div>
                  </div>,
                  <div class='column-item'>
                    <div class='column-label'> {t('检索语句')} : </div>
                    <div class='column-center'>{queryConfig.keywords_query_string}</div>
                  </div>,
                ]
              : undefined,
            [
              <div class='column-item'>
                <div class='column-label'> {t('指标名称')} : </div>
                <div class='column-content'>
                  <div class='item-center'>{queryConfig.metric_field}</div>
                  <div class='item-source'>{queryConfig.metric_description}</div>
                </div>
              </div>,
              <div class='column-item'>
                <div class='column-label'> {t('计算公式')} : </div>
                <div class='column-content item-font'>
                  {queryConfig.agg_method === 'REAL_TIME' ? (
                    <div class='item-font'> {t('实时')} </div>
                  ) : (
                    <div class='item-font'>{queryConfig.agg_method}</div>
                  )}
                </div>
              </div>,
            ],
            queryConfig.agg_method !== 'REAL_TIME' ? (
              <div class='column-item'>
                <div class='column-label'> {t('汇聚周期')} : </div>
                <div class='column-content'>
                  {queryConfig.agg_interval / 60} {t('分钟')}{' '}
                </div>
              </div>
            ) : undefined,
            queryConfig.agg_method !== 'REAL_TIME' ? (
              <div class='column-item column-item-agg-condition'>
                <div class='column-label column-target'> {t('维度')} : </div>
                <div class='column-agg-condition'>
                  {queryConfig.agg_dimension?.map((item, index) => (
                    <div
                      key={index}
                      class='column-agg-dimension mb-2'
                    >
                      {item}
                    </div>
                  ))}
                </div>
              </div>
            ) : undefined,
            <div class='column-item column-item-agg-condition'>
              <div class='column-label column-target'> {t('监控条件')} : </div>
              <div class='column-agg-condition'>
                {queryConfig?.agg_condition?.map((item, index) => [
                  index > 0 && <div class='column-agg-dimension mb-2'>{item.condition}</div>,
                  <div
                    key={index}
                    class='column-agg-dimension mb-2'
                  >{`${item.key} ${methodMap[item.method]} ${item.value.join(',')}`}</div>,
                ])}
              </div>
            </div>,
          ]}
        </div>
      );
    }
    // 告警
    function getAlertContent(queryConfig) {
      return (
        <div class='item-content'>
          <div class='column-item'>
            <div class='column-label'> {t('告警名称')} : </div>
            <div class='column-content item-font'>{props.strategyData.name}</div>
          </div>
          {props.strategyData?.detects?.length && (
            <div class='column-item'>
              <div class='column-label'> {t('告警级别')} : </div>
              <div class='column-content item-font'>{levelMap[props.strategyData.detects[0].level]}</div>
            </div>
          )}
          <div class='column-item column-item-agg-condition'>
            <div class='column-label column-target'> {t('监控条件')} : </div>
            <div class='column-agg-condition'>
              {queryConfig.agg_condition.map((item, index) => [
                index > 0 && <div class='column-agg-dimension mb-2'>{item.condition}</div>,
                <div
                  key={index}
                  class='column-agg-dimension mb-2'
                >{`${item.key} ${methodMap[item.method]} ${item.value.join(',')}`}</div>,
              ])}
            </div>
          </div>
        </div>
      );
    }
    return () => (
      <div class={['alarm-shield-stratrgy-detail', { simple: props.simple }]}>
        {!props.simple && <div class='detail-header'>{t('策略内容')}</div>}
        {props.strategyData?.items?.[0].query_configs.map(item => (
          <div class='stratrgy-detail'>
            {(() => {
              if (item.data_type_label === 'event') {
                return getEventContent(item);
              }
              if (item.data_type_label === 'alert') {
                return getAlertContent(item);
              }
              if (item?.data_source_label === 'prometheus') {
                return (
                  <div class='item-content'>
                    <div class='column-item'>
                      <div class='column-label'> {t('告警名称')} : </div>
                      <div class='column-content item-font'>{props.strategyData.name}</div>
                    </div>
                    <div class='column-item'>
                      <div class='column-label'> {t('告警级别')} : </div>
                      <div class='column-content item-font'>{levelMap[props.strategyData.detects[0].level]}</div>
                    </div>
                    <div class='column-item'>
                      <div class='column-label'> {t('监控项')} : </div>
                      <div class='column-content item-font'>{item.promql}</div>
                    </div>
                  </div>
                );
              }
              return getTimeSeriesContent(item);
            })()}
          </div>
        ))}
      </div>
    );
  },
});
