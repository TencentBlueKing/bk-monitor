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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { statusMap } from './metric-table';
import { fuzzyMatch } from './metric-table-slide';

import './dimension-tab-detail.scss';

// 维度详情接口
interface DimensionDetail {
  name: string;
  description: string;
  disabled: boolean;
  common: boolean;
  create_time?: number;
  update_time?: number;
}

@Component
export default class DimensionTabDetail extends tsc<any> {
  @Prop({ default: () => [], type: Array }) dimensionTable: DimensionDetail[];

  // 编辑相关状态
  canEditName = false;
  copyDescription = '';
  editingIndex = -1; // 当前编辑的行索引

  search = ''; // 搜索

  // 状态点样式生成函数
  statusPoint(color1: string, color2: string) {
    return (
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
  }

  get tableData() {
    return this.dimensionTable.filter(item => {
      return fuzzyMatch(item.name, this.search) || fuzzyMatch(item.description, this.search);
    });
  }

  @Emit('showDimensionSlider')
  showDimensionSlider() {
    return true;
  }

  // 处理点击别名
  handleDescFocus(props) {
    this.copyDescription = props.row.description;
    this.editingIndex = props.$index;
  }

  // 处理别名编辑
  handleEditDescription(row: DimensionDetail) {
    this.canEditName = false;
    if (this.copyDescription === row.description) return;
    this.updateDimensionField(row.name, 'description', this.copyDescription);
    row.description = this.copyDescription;
  }

  // 处理状态切换
  async handleClickDisabled(row: DimensionDetail) {
    const newStatus = !row.disabled;
    row.disabled = newStatus;
    await this.updateDimensionField(row.name, 'disabled', newStatus);
  }

  // 处理常用维度切换
  async handleCommonChange(row: DimensionDetail, val: boolean) {
    row.common = val;
    await this.updateDimensionField(row.name, 'common', val);
  }

  // 统一更新维度字段的API调用
  async updateDimensionField(dimensionName: string, field: string, value: any) {
    try {
      await this.$store.dispatch('custom-escalation/modifyCustomTsFields', {
        time_series_group_id: this.$route.params.id,
        update_fields: [
          {
            type: 'dimension',
            [field]: value,
            name: dimensionName,
          },
        ],
      });
    } catch (e) {
      console.error('Update dimension failed:', e);
      // this.$bkMessage({
      //   message: this.$t('更新失败'),
      //   theme: 'error',
      // });
    }
  }

  // 表格列配置
  get columnConfigs() {
    return [
      {
        id: 'name',
        width: 200,
        label: this.$t('名称'),
        scopedSlots: {
          default: (props: { row: DimensionDetail }) => <span class='name'>{props.row.name || '--'}</span>,
        },
      },
      {
        id: 'description',
        width: 300,
        label: this.$t('别名'),
        scopedSlots: {
          default: (props: { row: DimensionDetail; $index: number }) => (
            <div class='description-cell'>
              {this.editingIndex === props.$index ? (
                <bk-input
                  v-model={this.copyDescription}
                  onBlur={() => {
                    this.editingIndex = -1;
                    this.handleEditDescription(props.row);
                  }}
                />
              ) : (
                <span
                  class='editable-text'
                  onClick={() => this.handleDescFocus(props)}
                >
                  {props.row.description || '--'}
                </span>
              )}
            </div>
          ),
        },
      },
      {
        id: 'status',
        width: 200,
        label: this.$t('状态'),
        scopedSlots: {
          default: (props: { row: DimensionDetail }) => (
            <div
              class='status-wrap clickable'
              onClick={() => this.handleClickDisabled(props.row)}
            >
              {this.statusPoint(statusMap.get(props.row.disabled).color1, statusMap.get(props.row.disabled).color2)}
              <span>{statusMap.get(props.row.disabled).name}</span>
            </div>
          ),
        },
      },
      {
        id: 'common',
        width: 150,
        label: this.$t('常用维度'),
        scopedSlots: {
          default: (props: { row: DimensionDetail }) => (
            <bk-switcher
              v-model={props.row.common}
              size='small'
              theme='primary'
              onChange={(val: boolean) => this.handleCommonChange(props.row, val)}
            />
          ),
        },
      },
    ];
  }

  // 表格组件
  getTableComponent() {
    return (
      <bk-table
        // height='100%'
        class='dimension-table'
        data={this.tableData}
        row-hover='auto'
      >
        {this.columnConfigs.map(config => (
          <bk-table-column
            key={config.id}
            width={config.width}
            renderHeader={() => {
              return <div> {this.$t(config.label as string)} </div>;
            }}
            label={config.label}
            scopedSlots={config.scopedSlots}
          />
        ))}
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
              theme='primary'
              onClick={this.showDimensionSlider}
            >
              {this.$t('编辑')}
            </bk-button>
          </div>
          <bk-input
            ext-cls='search-table'
            v-model={this.search}
            placeholder={this.$t('搜索')}
            right-icon='icon-monitor icon-mc-search'
          />
        </div>
        <div class='table-container'>{this.getTableComponent()}</div>
      </div>
    );
  }
}
