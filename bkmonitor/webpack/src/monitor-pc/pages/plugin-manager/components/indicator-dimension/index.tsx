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
import { Component, Prop, Provide, Ref, Watch } from 'vue-property-decorator';

import dayjs from 'dayjs';
import { retrieveCollectorPlugin } from 'monitor-api/modules/model';
import { getUnitList } from 'monitor-api/modules/strategies';
import { deepClone } from 'monitor-common/utils';

import MonitorImport from '../../../../components/monitor-import/monitor-import.vue';
import authorityMixinCreate from '../../../../mixins/authorityMixin';
import * as pluginManageAuth from '../../authority-map';
import FieldList from './field-list/index';
import GroupList from './group-list/index';
import {
  ALL_LABEL,
  type IBatchField,
  type IFlatField,
  type IGroupSubmitPayload,
  type IPluginGroup,
  type IPluginMeta,
  type ISelectedGroup,
  type IUnitItem,
} from './types';
import {
  applyBatchFieldChanges,
  applyGroupRules,
  deleteGroup,
  ensureDefaultGroup,
  flattenFields,
  getExportMetricJson,
  getMetricTypeList,
  moveCheckedFields,
  moveFieldToGroup,
  savePluginMetricJson,
} from './utils';

import './index.scss';

interface IProps {
  canEdit?: boolean;
  pluginId?: string;
}

@Component
export default class PluginIndicatorDimension extends authorityMixinCreate(pluginManageAuth) {
  @Prop({ default: '' }) pluginId: IProps['pluginId'];
  @Prop({ default: true }) canEdit: boolean;

  @Provide('authority') authority;
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;

  @Ref('groupListRef') readonly groupListRef!: InstanceType<typeof GroupList>;

  loading = false;
  isShowRightWindow = true;
  activeTab: 'dimension' | 'metric' = 'metric';
  selectedGroup: ISelectedGroup = { name: ALL_LABEL };
  groupList: IPluginGroup[] = [];
  unitList: IUnitItem[] = [];
  pluginMeta: IPluginMeta = {
    plugin_id: '',
    plugin_type: '',
    config_version: 1,
    info_version: 1,
    enable_field_blacklist: false,
    edit_allowed: true,
  };

  tabs = [
    { title: this.$t('指标'), id: 'metric' },
    { title: this.$t('维度'), id: 'dimension' },
  ];

  get fieldList(): IFlatField[] {
    return flattenFields(this.groupList);
  }

  get typeList() {
    return getMetricTypeList(this.pluginMeta.plugin_type);
  }

  get canManage() {
    return this.canEdit && this.authority.MANAGE_AUTH;
  }

  get currentPluginId() {
    return this.pluginId || (this.$route.params.pluginId as string);
  }

  @Watch('pluginId', { immediate: true })
  async handlePluginIdChange() {
    if (!this.currentPluginId) return;
    this.loading = true;
    try {
      await Promise.all([this.loadPlugin(), this.loadUnitList()]);
    } finally {
      this.loading = false;
    }
  }

  /** 与设置指标&维度页 getUnitListData 保持一致 */
  async loadUnitList() {
    const data = await getUnitList().catch(() => []);
    this.unitList = (data || []).map(item => ({
      ...item,
      children: item.formats,
      id: item.name,
    }));
  }

  async loadPlugin() {
    if (!this.currentPluginId) return;
    const detailData = await retrieveCollectorPlugin(this.currentPluginId).catch(() => ({}));
    this.pluginMeta = {
      plugin_id: detailData.plugin_id,
      plugin_type: detailData.plugin_type,
      config_version: detailData.config_version,
      info_version: detailData.info_version,
      enable_field_blacklist: detailData.enable_field_blacklist,
      edit_allowed: detailData.edit_allowed,
    };
    this.groupList = ensureDefaultGroup(detailData.metric_json || [], this.$tc('默认分组'));
  }

  async persist(nextGroups: IPluginGroup[], successMsg = true, silent = false) {
    if (!silent) {
      this.loading = true;
    }
    try {
      const data = await savePluginMetricJson(this.pluginMeta, nextGroups);
      if (data?.config_version != null) {
        this.pluginMeta.config_version = data.config_version;
      }
      if (data?.info_version != null) {
        this.pluginMeta.info_version = data.info_version;
      }
      if (successMsg) {
        this.$bkMessage({ theme: 'success', message: this.$t('变更成功') });
      }
      if (silent) {
        this.groupList = nextGroups;
      } else {
        await this.loadPlugin();
        this.$emit('refresh');
      }
      return true;
    } catch (err) {
      this.$bkMessage({ theme: 'error', message: err?.message || this.$t('更新失败'), ellipsisLine: 0 });
      return false;
    } finally {
      if (!silent) {
        this.loading = false;
      }
    }
  }

  changeGroupFilterList(groupInfo: ISelectedGroup) {
    this.selectedGroup = groupInfo;
  }

  handleShowAddGroup() {
    this.groupListRef?.handleAddGroup();
  }

  async handleSubmitGroup(payload: IGroupSubmitPayload) {
    const next = deepClone(this.groupList) as IPluginGroup[];
    if (payload.isEdit) {
      const target = next.find(item => item.table_name === payload.oldName);
      if (!target) return;
      target.table_name = payload.table_name;
      target.table_desc = payload.table_desc;
      target.rule_list = payload.rule_list;
      target.fields = target.fields?.length ? target.fields : payload.fields || [];
    } else {
      next.push({
        table_name: payload.table_name,
        table_desc: payload.table_desc,
        rule_list: payload.rule_list,
        fields: payload.fields || [],
      });
    }
    // 编辑时保留当前分类已有指标，只按规则从默认分组吸入匹配项
    const applied = applyGroupRules(next, payload.table_name, !payload.isEdit);
    const ok = await this.persist(applied);
    if (!ok) return;
    this.groupListRef?.handleCancel();
    this.groupListRef?.changeSelectedLabelByName(payload.table_name);
    if (!payload.isEdit) {
      this.groupListRef?.scrollToGroup(payload.table_name);
    }
  }

  async handleDeleteGroup(name: string) {
    const next = deleteGroup(this.groupList, name);
    await this.persist(next);
    if (this.selectedGroup.name === name) {
      this.changeGroupFilterList({ name: ALL_LABEL });
      this.groupListRef?.changeSelectedLabelByName(ALL_LABEL);
    }
  }

  findField(uid: string) {
    return this.fieldList.find(item => item.uid === uid);
  }

  async handleEditField(uid: string, patch: Partial<IFlatField>) {
    const field = this.findField(uid);
    if (!field) return;
    const next = deepClone(this.groupList) as IPluginGroup[];
    const group = next.find(item => item.table_name === field.table_name);
    const target = group?.fields.find(item => item.name === field.name && item.monitor_type === field.monitor_type);
    if (!target) return;
    Object.assign(target, patch);
    if (patch.type !== undefined && target.monitor_type === 'metric') {
      target.is_diff_metric = patch.type === 'diff';
    }
    await this.persist(next, true, true);
  }

  async handleMoveField(uid: string, targetName: string) {
    const field = this.findField(uid);
    if (!field || field.table_name === targetName) return;
    const next = moveFieldToGroup(this.groupList, field, targetName);
    await this.persist(next, true, true);
  }

  async handleBatchMove(targetName: string, uids: string[]) {
    const next = deepClone(this.groupList) as IPluginGroup[];
    for (const group of next) {
      for (const item of group.fields) {
        const uid = `${group.table_name}::${item.monitor_type}::${item.name}`;
        item.selection = uids.includes(uid) && item.monitor_type === 'metric';
      }
    }
    const moved = moveCheckedFields(next, targetName);
    await this.persist(moved);
  }

  async handleSaveBatch(rows: IBatchField[], deletedUids: string[]) {
    const next = applyBatchFieldChanges(this.groupList, rows, deletedUids, this.activeTab);
    await this.persist(next);
  }

  handleExportMetric() {
    const downloadEl = document.createElement('a');
    const blob = new Blob([JSON.stringify(getExportMetricJson(this.groupList), null, 4)]);
    const fileUrl = URL.createObjectURL(blob);
    downloadEl.href = fileUrl;
    downloadEl.download = `${this.pluginMeta.plugin_id}-${dayjs.tz().format('YYYY-MM-DD HH-mm-ss')}.json`;
    downloadEl.style.display = 'none';
    document.body.appendChild(downloadEl);
    downloadEl.click();
    document.body.removeChild(downloadEl);
    URL.revokeObjectURL(fileUrl);
  }

  async handleImportMetric(data: string) {
    if (!this.canManage) {
      this.handleShowAuthorityDetail();
      return;
    }
    let dataJson = null;
    try {
      dataJson = JSON.parse(data);
    } catch (error) {
      console.log(error);
    }
    if (!Array.isArray(dataJson) || !dataJson.length) {
      this.$bkMessage({
        theme: 'error',
        message: this.$t('未检测到需要导入的指标和维度'),
      });
      return;
    }
    const errorList = [];
    const list: IPluginGroup[] = [];
    const allMetricFieldList = [];
    dataJson.forEach((item, index) => {
      if (!item.table_name) {
        errorList.push(this.$t('第{index}个分组未填写字段table_name', { index: index + 1 }));
        return;
      }
      const tableItem: IPluginGroup = {
        table_name: item.table_name,
        table_desc: item.table_desc || item.table_name,
        rule_list: item.rule_list || [],
        fields: [],
      };
      const fieldList = [];
      (item.fields || []).forEach((field, childIndex) => {
        if (!field.name) {
          errorList.push(
            this.$t('分组：{tableName} 第{index}个字段未填写名称', {
              tableName: item.table_name,
              index: childIndex + 1,
            })
          );
          return;
        }
        if (fieldList.some(set => set.description !== '' && set.description === field.description)) {
          errorList.push(
            this.$t('分组：{tableName} 别名：{fieldName}重复', {
              tableName: item.table_name,
              fieldName: field.description,
            })
          );
        }
        if (field.monitor_type === 'metric') {
          if (allMetricFieldList.some(set => set.name === field.name)) {
            errorList.push(
              this.$t('分组：{tableName} 指标名：{fieldName}重复', {
                tableName: item.table_name,
                fieldName: field.name,
              })
            );
          }
          fieldList.push({
            ...field,
            monitor_type: 'metric',
            is_active: field.is_active !== false,
            type: field.type || 'double',
            unit: field.unit || 'none',
          });
          allMetricFieldList.push(field);
        } else if (field.monitor_type === 'dimension') {
          fieldList.push({
            ...field,
            monitor_type: 'dimension',
            is_active: field.is_active !== false,
            type: field.type || 'string',
            unit: field.unit || 'none',
          });
        } else {
          errorList.push(
            this.$t('分组：{tableName} 字段：{fieldName}填写字段分类错误', {
              tableName: item.table_name,
              fieldName: field.name,
            })
          );
        }
      });
      tableItem.fields = fieldList;
      list.push(tableItem);
    });
    if (errorList.length) {
      this.$bkMessage({
        theme: 'error',
        message: this.$createElement(
          'ul',
          {},
          errorList.map(message => this.$createElement('li', {}, message))
        ),
        delay: 10000,
        ellipsisLine: 0,
      });
      return;
    }
    const next = ensureDefaultGroup(list, this.$tc('默认分组'));
    await this.persist(next);
  }

  render() {
    return (
      <div
        class='plugin-indicator-dimension'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class={{ left: true, active: this.isShowRightWindow }}>
          <div
            class='right-button'
            onClick={() => {
              this.isShowRightWindow = !this.isShowRightWindow;
            }}
          >
            {this.isShowRightWindow ? (
              <i class='icon-monitor icon-arrow-left icon' />
            ) : (
              <i class='icon-monitor icon-arrow-right icon' />
            )}
          </div>
          <GroupList
            ref='groupListRef'
            canManage={this.canManage}
            confirmLoading={this.loading}
            groupList={this.groupList}
            onChangeGroup={this.changeGroupFilterList}
            onDeleteGroup={this.handleDeleteGroup}
            onSubmitGroup={this.handleSubmitGroup}
          />
        </div>
        <div class='plugin-indicator-dimension-content'>
          <div class='list-header'>
            <div class='head'>
              <div class='tabs'>
                {this.tabs.map(({ title, id }) => (
                  <span
                    key={id}
                    class={['tab', id === this.activeTab ? 'active' : '']}
                    onClick={() => {
                      this.activeTab = id as 'dimension' | 'metric';
                    }}
                  >
                    {title}
                  </span>
                ))}
              </div>
              <div class='tools'>
                <MonitorImport
                  class='tool'
                  return-text={true}
                  onChange={this.handleImportMetric}
                >
                  <i class='icon-monitor icon-xiazai2' /> {this.$t('导入')}
                </MonitorImport>
                <span
                  class='tool'
                  onClick={() => this.handleExportMetric()}
                >
                  <i class='icon-monitor icon-shangchuan' />
                  {this.$t('导出')}
                </span>
              </div>
            </div>
          </div>
          <FieldList
            key={this.activeTab}
            canManage={this.canManage}
            fieldList={this.fieldList}
            groupList={this.groupList}
            mode={this.activeTab}
            selectedGroup={this.selectedGroup}
            typeList={this.typeList}
            unitList={this.unitList}
            onBatchMove={this.handleBatchMove}
            onEditField={this.handleEditField}
            onMoveField={this.handleMoveField}
            onSaveBatch={this.handleSaveBatch}
            onShowAddGroup={this.handleShowAddGroup}
          />
        </div>
      </div>
    );
  }
}
