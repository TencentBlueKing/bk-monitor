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

import { Component, Emit, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { validateCustomTsGroupLabel } from 'monitor-api/modules/custom_report';
import { Debounce, deepClone } from 'monitor-common/utils';

import { fuzzyMatch } from './metric-table-slide';

import './dimension-table-slide.scss';

interface IDimensionItem {
  name: string;
  description?: string;
  disabled?: boolean;
  isNew?: boolean;
  error?: string;
  common?: boolean;
  type?: string;
}

@Component
export default class DimensionTableSlide extends tsc<any> {
  @Prop({ type: Boolean, default: false }) isShow: boolean;
  @Prop({ default: () => [] }) dimensionTable: any[];

  /** 表格配置 */
  filedSettings = {
    name: { label: '名称', width: 280, renderFn: props => this.renderNameColumn(props) },
    description: { label: '别名', width: 280, renderFn: (props, key) => this.renderInputColumn(props, key) },
    // disabled: { label: '启/停', width: 120, renderFn: (props, key) => this.renderSwitch(props.row, key) },
    common: { label: '常用维度', width: 140, renderFn: (props, key) => this.renderCheckbox(props.row, key) },
    hidden: { label: '显示', width: 120, renderFn: (props, key) => this.renderSwitch(props.row, key, true) },
    operate: { label: '操作', width: 80, renderFn: props => this.renderOperations(props) },
  };
  /** 维度搜索 */
  search = '';
  /** 表格宽度 */
  width = 1400;
  /** 表格数据 */
  localTable: IDimensionItem[] = [];
  /** 删除的维度名称列表 */
  delArray: IDimensionItem[] = [];

  // 响应式处理
  @Watch('dimensionTable', { immediate: true })
  handleDimensionTableChange(newVal: IDimensionItem[]) {
    this.localTable = deepClone(newVal);
  }

  render() {
    return (
      <bk-sideslider
        {...{ on: { 'update:isShow': this.handleCancel } }}
        width={this.width}
        ext-cls='dimension-slider-box'
        isShow={this.isShow}
        quickClose
        onHidden={this.handleCancel}
      >
        <div
          class='sideslider-title'
          slot='header'
        >
          {this.$t('批量编辑维度')}
        </div>
        <div
          class='dimension-slider-content'
          slot='content'
        >
          <div class='slider-search'>
            <bk-input
              v-model={this.search}
              placeholder={this.$t('搜索维度')}
              right-icon='bk-icon icon-search'
              on-change={this.handleSearchChange}
            />
          </div>
          {/* 头部和搜索 */}
          <bk-table
            class='slider-table'
            data={this.localTable}
            colBorder
          >
            <div slot='empty'>
              <div class='empty-slider-table'>
                <div class='empty-img'>
                  <bk-exception
                    class='exception-wrap-item exception-part'
                    scene='part'
                    type='empty'
                  >
                    <span class='empty-text'>{this.$t('暂无数据')}</span>
                  </bk-exception>
                </div>
                {this.search ? (
                  <div
                    class='add-row'
                    onClick={this.handleClearSearch}
                  >
                    {this.$t('清空检索')}
                  </div>
                ) : (
                  <div
                    class='add-row'
                    onClick={() => this.handleAddRow(-1)}
                  >
                    {this.$t('新增维度')}
                  </div>
                )}
              </div>
            </div>
            {Object.entries(this.filedSettings).map(([key, config]) => (
              <bk-table-column
                key={key}
                scopedSlots={{
                  default: props => {
                    /** 自定义 */
                    if (config?.renderFn) {
                      return config?.renderFn(props, key);
                    }
                    return props.row[key] || '--';
                  },
                }}
                label={this.$t(config.label)}
                minWidth={config.width}
                prop={key}
              />
            ))}
          </bk-table>
          <div class='slider-footer'>
            <bk-button
              // disabled={!this.localTable.length}
              theme='primary'
              onClick={this.handleSave}
            >
              {this.$t('保存')}
            </bk-button>
            <bk-button onClick={this.handleCancel}>{this.$t('取消')}</bk-button>
          </div>
        </div>
      </bk-sideslider>
    );
  }

  @Emit('hidden')
  handleCancel() {
    this.delArray = [];
    this.localTable = deepClone(this.dimensionTable);
    this.search = '';
    return false;
  }

  /**
   * @description: 搜索
   * @param {*}
   * @return {*}
   */
  @Debounce(300)
  handleSearchChange() {
    this.localTable = this.dimensionTable.filter(item => {
      return fuzzyMatch(item.name, this.search) || fuzzyMatch(item.description, this.search);
    });
  }

  handleClearSearch() {
    this.search = '';
  }

  changeSwitch(row, field, v) {
    row[field] = v;
  }

  // 保存逻辑
  async handleSave() {
    const newRows = this.localTable.filter(row => row.isNew);

    // 并行执行所有验证
    const validationResults = await Promise.all(
      newRows.map(async row => {
        const isValid = await this.validateName(row);
        if (!isValid) {
          // TODO: 错误反馈
          // this.$bkMessage({ message: row.error, theme: 'error' });
        }
        return isValid;
      })
    );

    // 检查全局有效性
    const allValid = validationResults.every(valid => valid);
    if (!allValid) return;

    // 清除临时状态
    for (const row of newRows) {
      row.isNew = undefined;
      row.error = undefined;
    }
    // 提交
    this.$emit('saveInfo', this.localTable, this.delArray);
  }

  // 渲染输入列
  private renderInputColumn(props: { row: IDimensionItem; $index: number }, field: string) {
    return (
      <bk-input
        class='slider-input'
        v-model={props.row[field]}
      />
    );
  }

  private renderNameColumn(props: { row: IDimensionItem }) {
    if (props.row.isNew) {
      return (
        <div
          class='name-editor'
          v-bk-tooltips={{
            content: props.row.error,
            disabled: !props.row.error,
          }}
        >
          <bk-input
            class={{ 'is-error': props.row.error, 'slider-input': true }}
            v-model={props.row.name}
            onBlur={() => this.validateName(props.row)}
            onInput={() => this.clearError(props.row)}
          />
        </div>
      );
    }
    return <span class='name'>{props.row.name || '--'}</span>;
  }

  // 渲染开关
  private renderSwitch(row: IDimensionItem, field: 'disabled' | 'hidden', isNegation = false) {
    return (
      <bk-switcher
        size='small'
        theme='primary'
        value={isNegation ? !row[field] : row[field]}
        onChange={v => this.changeSwitch(row, field, isNegation ? !v : v)}
      />
    );
  }
  // 渲染checkbox
  private renderCheckbox(row: IDimensionItem, field: 'common') {
    return (
      <bk-checkbox
        v-model={row[field]}
        false-value={false}
        true-value={true}
      />
    );
  }

  // 操作列
  private renderOperations(props: { $index: number }) {
    return (
      <div class='operations'>
        <i
          class='bk-icon icon-plus-circle-shape'
          onClick={() => this.handleAddRow(props.$index)}
        />
        <i
          class='bk-icon icon-minus-circle-shape'
          onClick={() => this.handleRemoveRow(props.$index)}
        />
      </div>
    );
  }

  private async validateName(row): Promise<boolean> {
    // 同步验证
    const syncError = this.validateSync(row);
    if (syncError) {
      this.$set(row, 'error', syncError);
      return false;
    }
    // 异步验证
    const asyncError = await this.validateAsync(row);
    if (asyncError) {
      this.$set(row, 'error', asyncError);
      return false;
    }

    row.error = '';
    return true;
  }

  // 同步验证逻辑
  private validateSync(row): string {
    if (!row.name?.trim()) {
      return this.$t('名称不能为空') as string;
    }
    if (this.localTable.some(item => item !== row && item.name === row.name)) {
      return this.$t('名称已存在') as string;
    }
    if (/[\u4e00-\u9fa5]/.test(row.name.trim())) {
      return this.$t('输入非中文符号') as string;
    }
    return '';
  }

  // 异步验证逻辑
  private async validateAsync(row): Promise<string> {
    try {
      const isValid = await validateCustomTsGroupLabel({ data_label: row.name });
      return isValid ? '' : (this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string);
    } catch {
      return this.$t('仅允许包含字母、数字、下划线，且必须以字母开头') as string;
    }
  }

  private clearError(row) {
    if (row.error) row.error = '';
  }

  // 添加/删除行逻辑
  private handleAddRow(index: number) {
    this.localTable.splice(index + 1, 0, {
      name: '',
      description: '',
      disabled: false,
      common: false,
      isNew: true,
    });
  }

  private handleRemoveRow(index: number) {
    const item = this.localTable[index];
    if (!item.isNew) {
      this.delArray.push({
        type: 'dimension',
        name: item.name,
      });
    }
    this.localTable.splice(index, 1);
  }
}
