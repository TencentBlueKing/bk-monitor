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
import { Component, Emit, Inject, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { deepClone } from '../../../../../monitor-common/utils/utils';
import AlarmGroupDetail, { IAlarmGroupDeatail } from '../../../alarm-group/alarm-group-detail/alarm-group-detail';
import * as ruleAuth from '../../../strategy-config/authority-map';

import './alarm-group.scss';

export interface IAlarmGroupList {
  id: number | string;
  name: string;
  receiver: string[];
}

interface IAlarmList {
  value?: number[];
  list: any[];
  disabledList?: number[];
  disabled?: boolean;
  readonly?: boolean;
  strategyId?: number | string;
  showAddTip?: boolean;
  isSimple?: boolean; // 简洁模式（无预览，无回填）
  isOpenNewPage?: boolean; // 点击创建按钮新开页
  tagClick?: (id: number, e: Event) => void;
  isRefresh?: boolean;
  loading?: boolean;
}
interface IEvent {
  onChange?: number[];
  onAddGroup?: void;
  onToggle?: (v: boolean) => void;
  onRefresh?: () => void;
}
@Component({ name: 'AlarmGroup' })
export default class AlarmGroup extends tsc<IAlarmList, IEvent> {
  // 外部值
  @Model('emitValueChange', { type: Array }) readonly value: number[];
  @Prop({ default: () => [], type: Array }) readonly list: IAlarmGroupList[];
  @Prop({ default: false, type: Boolean }) readonly readonly: boolean;
  @Prop({ default: false, type: Boolean }) readonly isRefresh: boolean;
  @Prop({ default: false, type: Boolean }) readonly loading: boolean;
  @Prop({ default: true, type: Boolean }) showAddTip: Boolean;
  @Prop({ default: false, type: Boolean }) isSimple: boolean; // 简洁模式（无预览，无回填）
  @Prop({ default: null, type: Function }) tagClick: (id: number, e: Event) => void;
  @Prop({ default: false, type: Boolean }) isOpenNewPage: boolean; // 点击创建按钮新开页

  @Ref('alarmGroupSelect') readonly alarmGroupSelectRef: any;
  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;

  localValue: number[] = [];

  detail: IAlarmGroupDeatail = {
    id: 0,
    show: false
  };

  @Watch('value', { immediate: true, deep: true })
  valueChange(v) {
    this.localValue = deepClone(v || []);
  }

  @Emit('change')
  @Emit('emitValueChange')
  handleValueEmit(v?: any) {
    return v || this.localValue;
  }

  @Emit('addGroup')
  emitAddGroup() {}

  /**
   * 处理名称
   */
  handleTagName(id: number) {
    const res = this.list.find(item => item.id === id);
    return res ? res.name : '';
  }

  /**
   * 选中告警组
   */
  handleSelectTag(id: number, e: Event) {
    e.stopPropagation();
    // if (this.readonly) return
    if (this.isSimple) return;
    this.detail.id = id;
    this.detail.show = true;
  }

  /**
   * 删除告警组
   */
  handleDelete(index: number, e: Event) {
    e.stopPropagation();
    if (this.readonly) return;
    this.localValue.splice(index, 1);
    // this.handleValueEmit()
  }

  /**
   * 展示下拉
   */
  handleShowSelect() {
    if (this.readonly) return;
    this.alarmGroupSelectRef.show();
  }
  /**
   * 隐藏下拉
   */
  hiddenSelect() {
    if (this.readonly) return;
    this.alarmGroupSelectRef.close();
  }

  // 详情页关闭
  handleDetailClose() {
    this.detail.id = 0;
    this.detail.show = false;
  }

  /**
   * 选择告警组
   */
  handleSelectChange() {
    this.handleValueEmit();
  }

  /**
   * 跳转编辑告警组
   */
  handleEditAlarmGroup(id) {
    this.detail.show = false;
    this.$router.push({
      name: 'alarm-group-edit',
      params: {
        id
      }
    });
  }

  /**
   * 新增告警组
   */
  handleCreateAlarmGroup() {
    if (this.isOpenNewPage) {
      const url = `${location.origin}${location.pathname}?bizId=${this.$store.getters.bizId}#/alarm-group/add`;
      window.open(url);
      return;
    }
    this.emitAddGroup();
    this.hiddenSelect();
    this.$router.push({
      name: 'alarm-group-add'
    });
  }

  handleToggle(v: boolean) {
    this.$emit('toggle', v);
  }

  handleRefresh(e: Event) {
    e.stopPropagation();
    if (this.loading) {
      return;
    }
    this.$emit('refresh');
  }

  render() {
    return (
      <div class={['alarm-group-wrap', { 'is-readonly': this.readonly }]}>
        <div class='alarm-group-tag-list'>
          {this.localValue.map((item, index) => (
            <span
              class={['alarm-group-tag', { 'tag-active': this.detail.id === item }]}
              key={index}
              onClick={e => (this.tagClick ? this.tagClick(item, e) : this.handleSelectTag(item, e))}
            >
              <span
                class='tag-text'
                v-bk-overflow-tips
              >
                {this.handleTagName(item)}
              </span>
              {this.readonly ? undefined : (
                <span
                  class='icon-monitor icon-mc-close'
                  onClick={e => this.handleDelete(index, e)}
                ></span>
              )}
            </span>
          ))}
          {this.readonly ? undefined : (
            <span class='add-btn'>
              <bk-select
                ext-popover-cls='alarm-group-popover'
                class='alarm-group-select'
                ref='alarmGroupSelect'
                popover-width={380}
                popover-options={{
                  boundary: 'window',
                  flipOnUpdate: true
                }}
                searchable
                multiple
                v-model={this.localValue}
                onChange={this.handleSelectChange}
                onToggle={this.handleToggle}
                zIndex={5000}
              >
                {this.list.map(option => (
                  <bk-option
                    key={option.id}
                    id={option.id}
                    name={option.name}
                  >
                    <div class='alarm-group-option'>
                      <div class='group-content'>
                        <div
                          class='item-name'
                          v-bk-overflow-tips
                        >
                          {option.name}
                        </div>
                        <div class='item-person'>
                          <span class='item-person-title'>{`${
                            option.needDuty ? `${window.i18n.t('当前轮值')}：` : ''
                          }`}</span>
                          {option.receiver.join(',') || `(${window.i18n.t('空')})`}
                        </div>
                      </div>
                      {this.localValue.includes(option.id) ? <i class='bk-icon icon-check-1 check-icon' /> : undefined}
                    </div>
                  </bk-option>
                ))}
                <div
                  slot='extension'
                  class='item-input-create'
                  v-authority={{ active: !this.authority?.ALARM_GROUP_MANAGE_AUTH }}
                  onClick={() =>
                    this.authority?.ALARM_GROUP_MANAGE_AUTH
                      ? this.handleCreateAlarmGroup()
                      : this?.handleShowAuthorityDetail(ruleAuth?.ALARM_GROUP_MANAGE_AUTH)
                  }
                >
                  <div class='add-container'>
                    <i class='bk-icon icon-plus-circle'></i>
                    <span class='add-text'>{this.$t('新增告警组')}</span>
                  </div>
                  {this.isRefresh && (
                    <div
                      class='loading-wrap'
                      onClick={this.handleRefresh}
                    >
                      {this.loading ? (
                        <img
                          // eslint-disable-next-line @typescript-eslint/no-require-imports
                          src={require('../../../../static/images/svg/spinner.svg')}
                          class='status-loading'
                        ></img>
                      ) : (
                        <span class='icon-monitor icon-zhongzhi1'></span>
                      )}
                    </div>
                  )}
                </div>
              </bk-select>
              <span
                class={['add-tag']}
                onClick={this.handleShowSelect}
              >
                <span class='icon-monitor icon-mc-add'></span>
              </span>
            </span>
          )}
        </div>
        {/* 详情页 组件 */}
        <AlarmGroupDetail
          id={this.detail.id}
          v-model={this.detail.show}
          customEdit
          onEditGroup={this.handleEditAlarmGroup}
          onShowChange={val => !val && (this.detail.id = 0)}
        ></AlarmGroupDetail>
      </div>
    );
  }
}
