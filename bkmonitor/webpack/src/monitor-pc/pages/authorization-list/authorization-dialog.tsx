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
import dayjs from 'dayjs';
import { createOrUpdateExternalPermission, getByAction } from 'monitor-api/modules/iam';
import { deepClone } from 'monitor-common/utils';

import { ACTION_MAP, AngleType, EditModel } from './authorization-list';

import './authorization-dialog.scss';

interface IProps {
  value?: boolean;
  rowData?: null | EditModel;
  bizId: number | string;
  viewType: AngleType;
  authorizer: string;
}

interface IEvents {
  onSuccess: boolean;
}

@Component
export default class AuthorizationDialog extends tsc<IProps, IEvents> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ required: true, type: [Number, String] }) bizId: number | string;
  @Prop({ required: true, type: String }) viewType: AngleType;
  @Prop({ required: true, type: String }) authorizer: string;
  @Prop({ required: false, type: Object, default: null }) rowData: null | EditModel;
  @Ref() formRef: any;

  resourceList = [];
  loading = false;

  formData: EditModel = {
    action_id: '',
    authorized_users: [],
    resources: [],
    expire_time: ''
  };

  rules = {
    authorized_users: [{ required: true, message: this.$t('必填项'), trigger: 'blur' }],
    action_id: [{ required: true, message: this.$t('必填项'), trigger: 'blur' }],
    expire_time: [{ required: true, message: this.$t('必填项'), trigger: 'change' }]
  };

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
          expire_time: ''
        };
      }
    }
  }

  async handleActionChange(val) {
    if (!val) return;
    const res = await getByAction({ bk_biz_id: this.bizId, action_id: val });
    this.resourceList = res;
  }

  disabledDate(val) {
    const startDate = new Date(); // 当天
    const endDate = dayjs.tz(startDate).add(1, 'year'); // 一年
    // 小于当天或者大于一年的禁用
    return (
      dayjs.tz(val).isBefore(startDate, 'day') ||
      (dayjs.tz(val).isSame(endDate, 'day') && dayjs.tz(val).isAfter(endDate, 'day'))
    );
  }

  handleDateChange(val) {
    this.formData.expire_time = dayjs.tz(val).format('YYYY-MM-DD 23:59:59');
  }

  @Emit('change')
  handleCancel(val?: boolean) {
    this.loading = false;
    return val ?? !this.value;
  }

  handleConfirm() {
    this.formRef.validate(async valid => {
      if (valid) {
        this.loading = true;
        try {
          const { authorized_users, ...params } = this.formData;
          const res = await createOrUpdateExternalPermission({
            bk_biz_id: this.bizId,
            ...params,
            authorized_users: authorized_users.map(item => item.replace(/\s/g, '')),
            authorizer: this.authorizer,
            operate_type: this.rowData ? 'update' : 'create',
            view_type: this.viewType === 'approval' ? 'user' : this.viewType
          });
          this.$bkMessage({
            message: res.need_approval ? this.$t('已提交审批') : this.$t('操作成功'),
            theme: 'primary'
          });
          this.handleCancel(false);
          this.$emit('success', res.need_approval);
        } catch {}
        this.loading = false;
      }
    });
  }

  render() {
    return (
      <bk-dialog
        value={this.value}
        title={this.$t(this.rowData ? '编辑授权' : '添加授权')}
        header-position='left'
        width={480}
        onCancel={this.handleCancel}
        auto-close={false}
        loading={this.loading}
        draggable={false}
      >
        <bk-form
          ref='formRef'
          form-type='vertical'
          {...{
            props: {
              model: this.formData,
              rules: this.rules
            }
          }}
        >
          <bk-form-item
            property='authorized_users'
            error-display-type='normal'
          >
            <div class='custom-label'>
              <span class='label required'>{this.$t('被授权人')}</span>
              <span class='hint'>({this.$t('批量粘贴请使用;进行分隔')})</span>
            </div>
            <bk-tag-input
              v-model={this.formData.authorized_users}
              allow-create={true}
              free-paste
              separator=';'
              disabled={!!this.rowData && this.viewType === 'user'}
              has-delete-icon
            />
          </bk-form-item>
          <bk-form-item
            property='action_id'
            error-display-type='normal'
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
              {Object.entries(ACTION_MAP).map(item => (
                <bk-option
                  id={item[0]}
                  name={item[1]}
                ></bk-option>
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            property='resources'
            error-display-type='normal'
          >
            <div class='custom-label'>
              <span class='label'>{this.$t('操作实例')}</span>
              <span class='hint'>
                ({this.$t('来源于授权人:')} {this.authorizer})
              </span>
            </div>
            <bk-select
              v-model={this.formData.resources}
              multiple
              disabled={!!this.rowData && this.viewType === 'resource'}
            >
              {this.resourceList.map(item => (
                <bk-option
                  id={item.uid}
                  name={item.text}
                  key={item.uid}
                ></bk-option>
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item
            property='expire_time'
            error-display-type='normal'
          >
            <div class='custom-label'>
              <span class='label required'>{this.$t('截止时间')}</span>
            </div>
            <bk-date-picker
              value={this.formData.expire_time}
              type='date'
              clearable={false}
              format='yyyy-MM-dd HH:mm:ss'
              options={{ disabledDate: this.disabledDate }}
              onChange={this.handleDateChange}
            ></bk-date-picker>
          </bk-form-item>
        </bk-form>

        <div slot='footer'>
          <bk-button
            theme='primary'
            style='margin-right: 8px'
            onClick={this.handleConfirm}
            loading={this.loading}
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
