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

import { Component } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import ExploreCollapseWrapper from 'monitor-ui/chart-plugins/plugins/explore-custom-graph/components/explore-collapse-wrapper';

import QueryConfigDetail from '../../components/query-config/query-config-detail';
import { TVariableType } from '../../components/type/query-config';

import './config-panel.scss';

@Component
export default class ConfigPanel extends tsc<object> {
  render() {
    return (
      <div class='config-panel'>
        <div class='base-info'>
          <div class='info-header'>
            <span class='header-title'>{this.$t('基本信息')}</span>
          </div>
          <div class='info-main'>
            <div class='info-item'>
              <span class='info-item-label'>{`${this.$t('模板名称')}:`}</span>
              <span class='info-item-value'>我是模板名称占位A</span>
            </div>
            <div class='info-item'>
              <span class='info-item-label'>{`${this.$t('模板说明')}:`}</span>
              <span class='info-item-value'>
                那些更棒的点子来自于个体依然用过去习惯的方式思考创意时——坐在办公桌前时，在咖啡店等咖啡时，洗澡时。这些由人们独自想出的点子更胜一筹。当讨论会的狂热劲头散去，头脑风暴产生的点子其实并没有那么特别
              </span>
            </div>
          </div>
        </div>
        <ExploreCollapseWrapper
          class='collapse-panel'
          collapseShowHeight={24}
          defaultHeight={0}
          hasResize={false}
          title={this.$t('模板配置') as string}
        >
          <QueryConfigDetail
            queryConfig={{
              alias: 'a',
              metric_id: 'bk_monitor.system.io.util',
              functions: [
                {
                  id: 'irate',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
                {
                  id: 'increase',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
                {
                  id: 'deriv',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
              ],
              agg_method: 'AVG',
              agg_interval: 60,
              agg_dimension: ['hostname', '${dimension}'],
              agg_condition: [
                {
                  key: 'hostname',
                  value: ['xxxxxx1', 'test22'],
                  method: 'eq',
                  condition: 'and',
                  dimension_name: '主机名',
                },
                {
                  key: 'ip',
                  value: ['ipipipipipip'],
                  method: 'neq',
                  condition: 'and',
                  dimension_name: '目标ID',
                },
              ],
              metric_field: 'util',
              unit: '',
            }}
            variables={[
              {
                name: 'dimension',
                value: ['bk_agent_id', 'device_name'],
                type: TVariableType.DIMENSION,
              },
            ]}
          />
          <QueryConfigDetail
            queryConfig={{
              alias: 'a',
              metric_id: 'bk_monitor.system.io.util',
              functions: [
                {
                  id: 'irate',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
                {
                  id: 'increase',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
                {
                  id: 'deriv',
                  params: [
                    {
                      id: 'window',
                      value: '2m',
                    },
                  ],
                },
              ],
              agg_method: '${method_var}',
              agg_interval: 47,
              agg_dimension: ['hostname', 'ip'],
              agg_condition: [
                {
                  key: 'hostname',
                  value: ['xxxxxx1', 'test22'],
                  method: 'eq',
                  condition: 'and',
                  dimension_name: '主机名',
                },
                {
                  key: 'ip',
                  value: ['ipipipipipip'],
                  method: 'neq',
                  condition: 'and',
                  dimension_name: '目标ID',
                },
              ],
            }}
            variables={[
              {
                name: 'method_var',
                value: 'SUM',
                type: TVariableType.METHOD,
              },
            ]}
          />
          {new Array(Math.floor(Math.random() * 10)).fill(1).map((_, index) => (
            <div
              key={index}
              style={{
                height: '209px',
                background: '#F5F7FA',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
              }}
            >
              模板配置卡片{index}
            </div>
          ))}
        </ExploreCollapseWrapper>
        <ExploreCollapseWrapper
          class='collapse-panel'
          collapseShowHeight={24}
          defaultHeight={0}
          hasResize={false}
          title={this.$t('变量列表') as string}
        >
          {new Array(Math.floor(Math.random() * 10)).fill(1).map((_, index) => (
            <div
              key={index}
              style={{
                height: '152px',
                background: '#FFFFFF',
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                border: '1px solid #DCDEE5',
              }}
            >
              变量卡片{index}
            </div>
          ))}
        </ExploreCollapseWrapper>
      </div>
    );
  }
}
