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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { createOrUpdateGroupingRule, previewGroupingRule } from 'monitor-api/modules/custom_report';

import { statusMap } from './metric-table';

import './dimension-tab-detail.scss';

@Component
export default class DimensionTabDetail extends tsc<any, any> {
  @Prop({ default: () => [] }) dimensionTable;
  allCheckValue = false;
  table = {};
  async created() {

  }

  updateCheckValue() { }
  handleCheckChange() { }
  showMetricDetail() { }
  getTableComponent() {
    // 状态点组件
    const statusPoint = (color1: string, color2: string) => (
      <div
        style={{ background: color2 }}
        class='status-point'
      >
        <div
          style={{ background: color1 }}
          class='point'
        />
      </div>
    );

    // 表格列配置
    const columnConfigs = [
      {
        id: 'name',
        width: 200,
        label: this.$t('名称'),
        prop: 'name',
        scopedSlots: {
          default: props => (
            <span
              class='name'
              onClick={() => this.showMetricDetail(props)}
            >
              {props.row.name || '--'}
            </span>
          ),
        },
      },
      {
        id: 'description',
        width: 300,
        label: this.$t('别名'),
        prop: 'description',
        scopedSlots: {
          default: props => props.row.description || '--',
        },
      },
      {
        id: 'disabled',
        width: 200,
        label: this.$t('状态'),
        scopedSlots: {
          default: props => (
            <span class='status-wrap'>
              {statusPoint(
                statusMap.get(Boolean(props.row?.disabled)).color1,
                statusMap.get(Boolean(props.row?.disabled)).color2
              )}
              <span>{statusMap.get(Boolean(props.row?.disabled)).name}</span>
            </span>
          ),
        },
      },
      {
        id: 'common',
        width: 75,
        label: this.$t('常用维度'),
        scopedSlots: {
          default: props => (
            <div class='switch-wrap'>
              <bk-switcher
                key={props.row.id}
                v-model={props.row.common}
                size='small'
                theme='primary'
              />
            </div>
          ),
        },
      },
    ];

    return (
      <bk-table
        ref='strategyTable'
        class='dimension-table'
        v-bkloading={{ isLoading: this.table?.loading }}
        empty-text={this.$t('无数据')}
        max-height={474}
        {...{ props: { data: this.dimensionTable } }}
      >
        <div slot='empty'>{/* 保持空状态 */}</div>

        {columnConfigs.map(config => {
          return (
            <bk-table-column
              key={config.id}
              {...{
                props: {
                  type: config.type,
                  label: config.label,
                  prop: config.prop,
                  width: config.width,
                  align: config.align,
                  ...config.props,
                },
              }}
              scopedSlots={config.scopedSlots}
            />
          );
        })}
      </bk-table>
    );
  }
  render() {
    return (
      <div class='dimension-table-content'>
        <div class='dimension-table-header'>
          <div class='dimension-btn'>
            <bk-button
              class='header-btn'
              // v-authority={{ active: !this.authority.MANAGE_AUTH }}
              theme='primary'
              onClick={() => { }}
            >
              {this.$t('编辑')}
            </bk-button>
          </div>
          <bk-input
            ext-cls='search-table'
            placeholder={this.$t('搜索')}
            right-icon='icon-monitor icon-mc-search'
          />
        </div>
        <div class='dimension-table'>{this.getTableComponent()}</div>
      </div>
    );
  }
}
