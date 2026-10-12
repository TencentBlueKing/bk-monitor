/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { Component, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { GROUP_DEFAULT_NAME, type IFlatField, type IPluginGroup, type IUnitItem } from '../types';

import './index.scss';

interface IEmits {
  onClose: () => void;
  onEditField: (uid: string, patch: Partial<IFlatField>) => void;
  onMoveField: (uid: string, targetName: string) => void;
}

interface IProps {
  canManage?: boolean;
  groupList: IPluginGroup[];
  metricData: IFlatField;
  typeList: { id: string; name: string }[];
  unitList: IUnitItem[];
}

@Component
export default class PluginMetricDetail extends tsc<IProps, IEmits> {
  @Prop({ default: () => ({}) }) metricData: IProps['metricData'];
  @Prop({ default: () => [] }) unitList: IProps['unitList'];
  @Prop({ default: () => [] }) typeList: IProps['typeList'];
  @Prop({ default: () => [] }) groupList: IProps['groupList'];
  @Prop({ default: true }) canManage: boolean;

  @Ref() readonly descriptionInput!: HTMLInputElement;
  @Ref() readonly unitSelectInput!: { getPopoverInstance?: () => { show?: () => void } };
  @Ref() readonly typeSelectInput!: { getPopoverInstance?: () => { show?: () => void } };

  canEditAlias = false;
  canEditUnit = false;
  canEditType = false;
  copyAlias = '';
  copyUnit = '';
  copyType = '';

  get groupSelectList() {
    return this.groupList.map(item => ({
      id: item.table_name,
      name: item.table_name === GROUP_DEFAULT_NAME ? (this.$t('默认分组') as string) : item.table_name,
    }));
  }

  @Watch('metricData.uid')
  handleMetricChange() {
    this.resetEditState();
  }

  resetEditState() {
    this.canEditAlias = false;
    this.canEditUnit = false;
    this.canEditType = false;
    this.copyAlias = '';
    this.copyUnit = '';
    this.copyType = '';
  }

  getUnitName(id: string) {
    if (!id || id === 'none' || id === '--') return '--';
    let name = id;
    for (const group of this.unitList) {
      const res = (group.formats || []).find(item => item.id === id);
      if (res) {
        name = res.name;
      }
    }
    return name;
  }

  handleShowEditAlias() {
    if (!this.canManage) return;
    this.canEditAlias = true;
    this.copyAlias = this.metricData.description || '';
    this.$nextTick(() => {
      this.descriptionInput?.focus?.();
    });
  }

  handleEditAlias() {
    this.canEditAlias = false;
    if (this.copyAlias === (this.metricData.description || '')) {
      this.copyAlias = '';
      return;
    }
    this.$emit('editField', this.metricData.uid, { description: this.copyAlias });
  }

  handleShowEditUnit() {
    if (!this.canManage) return;
    this.copyUnit = this.metricData.unit;
    this.canEditUnit = true;
    this.$nextTick(() => {
      this.unitSelectInput?.getPopoverInstance?.()?.show?.();
    });
  }

  handleEditUnit(isShow: boolean) {
    if (isShow) return;
    this.canEditUnit = false;
    if (this.copyUnit === this.metricData.unit) return;
    this.$emit('editField', this.metricData.uid, { unit: this.copyUnit });
  }

  handleShowEditType() {
    if (!this.canManage) return;
    this.copyType = this.metricData.type;
    this.canEditType = true;
    this.$nextTick(() => {
      this.typeSelectInput?.getPopoverInstance?.()?.show?.();
    });
  }

  handleEditType(isShow: boolean) {
    if (isShow) return;
    this.canEditType = false;
    if (this.copyType === this.metricData.type) return;
    this.$emit('editField', this.metricData.uid, { type: this.copyType });
  }

  handleGroupChange(targetName: string) {
    if (!this.canManage || targetName === this.metricData.table_name) return;
    this.$emit('moveField', this.metricData.uid, targetName);
  }

  handleEditActive(val: boolean) {
    if (!this.canManage) return;
    this.$emit('editField', this.metricData.uid, { is_active: val });
  }

  renderInfoItem(label: string, value?: number | string) {
    return (
      <div class='info-item'>
        <span class='info-label'>{label}：</span>
        <div
          class='info-content readonly'
          v-bk-overflow-tips
        >
          {value ?? '--'}
        </div>
      </div>
    );
  }

  render() {
    if (!this.metricData?.name) {
      return null;
    }

    return (
      <div class='plugin-metric-detail'>
        <div class='card-header'>
          <h2 class='card-title'>{this.$t('指标详情')}</h2>
          <i
            class='icon-monitor icon-mc-close'
            onClick={() => this.$emit('close')}
          />
        </div>
        <div class='card-body'>
          <div class='info-column'>
            {this.renderInfoItem(this.$t('名称') as string, this.metricData.name)}
            <div class='info-item'>
              <span class='info-label'>{this.$t('别名')}：</span>
              {!this.canEditAlias ? (
                <div
                  class='info-content info-text'
                  v-bk-overflow-tips
                  onClick={this.handleShowEditAlias}
                >
                  {this.metricData.description || '--'}
                </div>
              ) : (
                <bk-input
                  ref='descriptionInput'
                  v-model={this.copyAlias}
                  onBlur={this.handleEditAlias}
                  onEnter={() => this.descriptionInput?.blur?.()}
                />
              )}
            </div>
            <div class='info-item is-group-item'>
              <span class='info-label'>{this.$t('分组')}：</span>
              <div class='info-content'>
                <div class='group-list'>
                  <bk-select
                    key={this.metricData.uid}
                    clearable={false}
                    disabled={!this.canManage}
                    searchable={true}
                    value={this.metricData.table_name}
                    onChange={this.handleGroupChange}
                  >
                    {this.groupSelectList.map(item => (
                      <bk-option
                        id={item.id}
                        key={item.id}
                        name={item.name}
                      />
                    ))}
                  </bk-select>
                </div>
              </div>
            </div>
            <div class='info-item'>
              <span class='info-label'>{this.$t('类型')}：</span>
              {!this.canEditType ? (
                <div
                  class='info-content'
                  onClick={this.handleShowEditType}
                >
                  {this.metricData.type || '--'}
                </div>
              ) : (
                <bk-select
                  ref='typeSelectInput'
                  ext-cls='unit-content unit-ext'
                  v-model={this.copyType}
                  clearable={false}
                  onToggle={this.handleEditType}
                >
                  {this.typeList.map(item => (
                    <bk-option
                      id={item.id}
                      key={item.id}
                      name={item.name}
                    />
                  ))}
                </bk-select>
              )}
            </div>
            <div class='info-item'>
              <span class='info-label'>{this.$t('单位')}：</span>
              {!this.canEditUnit ? (
                <div
                  class='info-content'
                  onClick={this.handleShowEditUnit}
                >
                  {this.getUnitName(this.metricData.unit)}
                </div>
              ) : (
                <bk-select
                  ref='unitSelectInput'
                  ext-cls='unit-content unit-ext'
                  v-model={this.copyUnit}
                  clearable={false}
                  searchable={true}
                  onToggle={this.handleEditUnit}
                >
                  {this.unitList.map(group => (
                    <bk-option-group
                      key={group.id || group.name}
                      name={group.name}
                    >
                      {(group.formats || []).map(option => (
                        <bk-option
                          id={option.id}
                          key={option.id}
                          name={option.name}
                        />
                      ))}
                    </bk-option-group>
                  ))}
                </bk-select>
              )}
            </div>
            <div class='info-item'>
              <span class='info-label'>{this.$t('启/停')}：</span>
              <bk-switcher
                class='switcher-btn'
                disabled={!this.canManage}
                size='small'
                theme='primary'
                value={this.metricData.is_active}
                onChange={this.handleEditActive}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }
}
