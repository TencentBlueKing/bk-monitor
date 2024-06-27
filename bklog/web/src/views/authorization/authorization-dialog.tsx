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

import { Component, Emit, Model, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Message } from 'bk-magic-vue';
import dayjs from 'dayjs';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';

import $http from '../../api';
import { deepClone } from '../../common/util';
import { AngleType, EditModel } from './authorization-list';

import './authorization-dialog.scss';

const { $i18n } = window.mainComponent;

interface IProps {
  value?: boolean;
  rowData?: EditModel | null;
  spaceUid: number | string;
  viewType: AngleType;
  authorizer: string;
}

interface IEvents {
  onSuccess: boolean;
}

@Component
export default class AuthorizationDialog extends tsc<IProps, IEvents> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ required: true, type: [Number, String] }) spaceUid: number | string;
  @Prop({ required: true, type: String }) viewType: AngleType;
  @Prop({ required: true, type: String }) authorizer: string;
  @Prop({ required: false, type: Object, default: null }) rowData: EditModel | null;
  @Prop({ required: true, type: Array, default: [] }) actionList: { id: string; name: string }[];
  @Ref() formRef: any;

  resourceList = [];
  /** 点开编辑时的被授权用户列表 */
  baseUserList = [];
  loading = false;

  formData: EditModel = {
    action_id: '',
    authorized_users: [],
    resources: [],
    expire_time: '',
  };

  rules = {
    authorized_users: [{ required: true, message: $i18n.t('必填项'), trigger: 'blur' }],
    action_id: [{ required: true, message: $i18n.t('必填项'), trigger: 'blur' }],
    expire_time: [{ required: true, message: $i18n.t('必填项'), trigger: 'change' }],
  };

  /** 编辑授权且为操作实例的弹窗 */
  get isResource() {
    return this.viewType === 'resource' && this.rowData;
  }

  @Watch('value')
  handleValueChange(val: boolean) {
    if (val) {
      this.formRef.clearError();
      if (this.rowData) {
        this.formData = deepClone(this.rowData);
      } else {
        this.formData = {
          action_id: '',
          authorized_users: [],
          resources: [],
          expire_time: '',
        };
      }
    }
  }

  async handleActionChange(val) {
    if (!val) return;
    const res = await $http.request('authorization/getByAction', {
      query: {
        space_uid: this.spaceUid,
        action_id: val,
      },
    });
    this.resourceList = res?.data || [];
  }

  disabledDate(val) {
    const startDate = new Date(); // 当天
    const endDate = dayjs(startDate).add(1, 'year'); // 一年
    dayjs.extend(isSameOrAfter);
    // 小于当天或者大于一年的禁用
    return dayjs(val).isBefore(startDate, 'day') || dayjs(val).isSameOrAfter(endDate, 'day');
  }

  handleDateChange(val) {
    this.formData.expire_time = dayjs(val).format('YYYY-MM-DD 23:59:59');
  }

  @Emit('change')
  handleCancel(val?: boolean) {
    this.loading = false;
    return val ?? !this.value;
  }

  async handleConfirm() {
    try {
      await this.formRef.validate(async valid => {
        if (valid) {
          this.loading = true;
          try {
            const { expire_time, ...rest } = this.formData;
            const res = await $http.request('authorization/createOrUpdateExternalPermission', {
              data: {
                space_uid: this.spaceUid,
                ...rest,
                authorized_users: rest.authorized_users.map(val => val.replace(/[\r\n]/g, '')),

                ...(expire_time ? { expire_time } : {}),
                authorizer: this.authorizer,
                operate_type: this.rowData ? 'update' : 'create',
                view_type: this.viewType === 'approval' ? 'user' : this.viewType,
              },
            });
            Message({
              message: res.need_approval ? this.$t('已提交审批') : this.$t('操作成功'),
              theme: 'primary',
            });
            this.handleCancel(false);
            this.$emit('success', res.need_approval);
          } catch {}
          this.loading = false;
        }
      });
    } catch (error) {
      console.info(error);
    }
  }

  handleUsersChange(val: Array<string>) {
    if (this.isResource) {
      // 若是编辑操作实例 不允许新增新的被授权人 只能删除
      this.formData.authorized_users = val.filter(item => this.baseUserList.includes(item));
    }
  }

  /** 操作实例点开编辑时初始化授权人 */
  initUsersVal(val) {
    this.baseUserList = val ? this.formData.authorized_users : [];
  }

  render() {
    return (
      <bk-dialog
        width={480}
        auto-close={false}
        draggable={false}
        header-position='left'
        loading={this.loading}
        title={this.$t(this.rowData ? '编辑授权' : '添加授权')}
        value={this.value}
        on-value-change={this.initUsersVal}
        onCancel={this.handleCancel}
      >
        <bk-form
          ref='formRef'
          form-type='vertical'
          {...{
            props: {
              model: this.formData,
              rules: this.rules,
            },
          }}
        >
          <bk-form-item
            error-display-type='normal'
            property='authorized_users'
          >
            <div class='custom-label'>
              <span class='label required'>{this.$t('被授权人')}</span>
              <span class='hint'>({this.$t('批量粘贴请使用;进行分隔')})</span>
            </div>
            <bk-tag-input
              v-model={this.formData.authorized_users}
              allow-create={true}
              disabled={!!this.rowData && this.viewType === 'user'}
              separator=';'
              free-paste
              has-delete-icon
              onChange={this.handleUsersChange}
            />
          </bk-form-item>
          <bk-form-item
            error-display-type='normal'
            property='action_id'
          >
            <div class='custom-label'>
              <span class='label required'>{this.$t('操作权限')}</span>
              <span class='hint'>
                ({this.$t('来源于授权人:')} {this.authorizer})
              </span>
            </div>
            <bk-select
              v-model={this.formData.action_id}
              clearable={false}
              disabled={!!this.rowData}
              onChange={this.handleActionChange}
            >
              {this.actionList.map(item => (
                <bk-option
                  id={item.id}
                  name={item.name}
                ></bk-option>
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            error-display-type='normal'
            property='resources'
          >
            <div class='custom-label'>
              <span class='label'>{this.$t('操作实例')}</span>
              <span class='hint'>
                ({this.$t('来源于授权人:')} {this.authorizer})
              </span>
            </div>
            <bk-select
              v-model={this.formData.resources}
              disabled={!!this.rowData && this.viewType === 'resource'}
              multiple
            >
              {this.resourceList.map(item => (
                <bk-option
                  id={item.uid}
                  key={item.uid}
                  name={item.text}
                ></bk-option>
              ))}
            </bk-select>
          </bk-form-item>
          {!this.isResource && (
            <bk-form-item
              error-display-type='normal'
              property='expire_time'
            >
              <div class='custom-label'>
                <span class='label required'>{this.$t('截止时间')}</span>
              </div>
              <bk-date-picker
                clearable={false}
                format='yyyy-MM-dd HH:mm:ss'
                options={{ disabledDate: this.disabledDate }}
                type='date'
                value={this.formData.expire_time}
                onChange={this.handleDateChange}
              ></bk-date-picker>
            </bk-form-item>
          )}
        </bk-form>

        <div slot='footer'>
          <bk-button
            style='margin-right: 8px'
            loading={this.loading}
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确认')}
          </bk-button>
          <bk-button
            theme='default'
            onClick={() => this.handleCancel(false)}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
