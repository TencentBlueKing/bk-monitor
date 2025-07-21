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

import { Message } from 'bk-magic-vue';
import dayjs from 'dayjs';
import isSameOrAfter from 'dayjs/plugin/isSameOrAfter';
import {
  Component,
  Emit,
  Model,
  Prop,
  Ref,
  Watch,
} from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import $http from '../../api';

import './authorization-dialog.scss';
import { AngleType, EditModel } from './authorization-list';

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

type AddType = 'alone' | 'batch';

@Component
export default class AuthorizationDialog extends tsc<IProps, IEvents> {
  @Model('change', { default: false, type: Boolean }) value: IProps['value'];
  @Prop({ required: true, type: [Number, String] }) spaceUid: number | string;
  @Prop({ required: true, type: String }) viewType: AngleType;
  @Prop({ required: true, type: String }) authorizer: string;
  @Prop({ default: null, required: false, type: Object })
  rowData: EditModel | null;
  @Prop({ default: [], required: true, type: Array }) actionList: {
    id: string;
    name: string;
  }[];
  @Ref() formRef: any;
  @Ref() actionFormRef: any;

  resourceList = [];
  /** 点开编辑时的被授权用户列表 */
  baseUserList = [];
  exportUser = '';
  actionCatchSelectObj = {};
  actionSelectListObj = {};
  authorizedUsersList = [];
  actionData = {
    actionShowList: [],
  };
  loading = false;
  addType: AddType = 'alone';

  formData: EditModel = {
    action_id: '',
    action_multiple: [],
    authorized_users: [],
    expire_time: '',
    resources: [],
  };

  rules = {
    action_id: [
      { message: $i18n.t('必填项'), required: true, trigger: 'blur' },
    ],
    action_multiple: [
      { message: $i18n.t('必填项'), required: true, trigger: 'blur' },
    ],
    authorized_users: [
      { message: $i18n.t('必填项'), required: true, trigger: 'blur' },
    ],
    expire_time: [
      { message: $i18n.t('必填项'), required: true, trigger: 'change' },
    ],
    resources: [
      { message: $i18n.t('必填项'), required: true, trigger: 'blur' },
    ],
  };

  actionRules = {
    select: [{ message: $i18n.t('必填项'), required: true, trigger: 'blur' }],
  };

  /** 编辑授权且为操作实例的弹窗 */
  get isResource() {
    return this.viewType === 'resource' && this.rowData;
  }

  get isAloneAddForm() {
    return this.addType === 'alone';
  }

  get authorizedFilterUsersList() {
    const userSet = new Set();
    return this.authorizedUsersList
      .map((item) => {
        if (!userSet.has(item.authorized_user)) {
          userSet.add(item.authorized_user);
          return {
            id: item.authorized_user,
            name: item.authorized_user,
          };
        }
      })
      .filter(Boolean);
  }

  get authorizedShowUsersList() {
    const userList = [
      {
        id: '__all__',
        name: window.mainComponent.$t('所有人'),
      },
    ];
    if (!this.formData.authorized_users.includes('__all__')) {
      userList.push(...this.authorizedFilterUsersList);
    }
    return userList;
  }

  @Watch('value')
  async handleValueChange(val: boolean) {
    if (val) {
      this.formRef.clearError();
      this.authorizedUsersList = await this.getAuthListData();
      if (this.rowData) {
        Object.keys(this.rowData ?? {}).forEach((key) => {
          if (Array.isArray(this.rowData[key])) {
            this.formData[key].splice(
              0,
              this.formData[key].length,
              ...this.rowData[key]
            ); // 清空数组
          } else {
            this.$set(this.formData, key, this.rowData[key]);
          }
        });

        this.$nextTick(() => {
          this.formData.resources.splice(
            0,
            this.formData.resources.length,
            ...(this.rowData.resources || [])
          );
        });
      } else {
        Object.assign(this.formData, {
          action_id: '',
          action_multiple: [],
          authorized_users: [],
          expire_time: '',
          resources: [],
        });
      }
    }
  }

  async handleActionChange(val: string) {
    if (!val || val === '-') return;
    this.formData.resources = [];
    this.resourceList = await this.getActionSelectList(val);
  }

  handleClickActionList(newVal: string[]) {
    this.actionData.actionShowList = newVal.map((item) => {
      const newObj = {
        id: item,
        list: this.actionSelectListObj[item] ?? [],
        name: this.actionList.find((aItem) => aItem.id === item).name,
        select: this.actionCatchSelectObj[item] ?? [],
      };
      return newObj;
    });
    this.actionList.forEach((item) => {
      if (!newVal.includes(item.id)) this.actionCatchSelectObj[item.id] = [];
      this.handleQuestAction(item.id);
    });
    this.formData.action_multiple = newVal;
  }

  async handleQuestAction(actionID) {
    const actionIndex = this.actionData.actionShowList.findIndex(
      (item) => item.id === actionID
    );
    if (!this.actionSelectListObj[actionID] && actionIndex >= 0) {
      this.actionData.actionShowList[actionIndex].list =
        await this.getActionSelectList(actionID);
      this.actionSelectListObj[actionID] =
        this.actionData.actionShowList[actionIndex].list;
    }
  }

  async handleSelectExportConfig(user) {
    const userAuthorized = this.authorizedUsersList.filter(
      (item) => item.authorized_user === user
    );
    this.formData.action_multiple = [];
    userAuthorized.forEach((item) => {
      this.actionCatchSelectObj[item.action_id] = item.resources;
    });
    this.handleClickActionList(userAuthorized.map((item) => item.action_id));
  }

  handleSelectAction(val: string, action) {
    this.actionCatchSelectObj[action.id] = val;
  }

  async getActionSelectList(val: string): Promise<any> {
    try {
      const res = await $http.request('authorization/getByAction', {
        query: {
          action_id: val,
          space_uid: this.spaceUid,
        },
      });
      return res?.data;
    } catch (err) {
      return [];
    }
  }

  disabledDate(val) {
    const startDate = new Date(); // 当天
    const endDate = dayjs(startDate).add(1, 'year'); // 一年
    dayjs.extend(isSameOrAfter);
    // 小于当天或者大于一年的禁用
    return (
      dayjs(val).isBefore(startDate, 'day') ||
      dayjs(val).isSameOrAfter(endDate, 'day')
    );
  }

  handleDateChange(val) {
    this.formData.expire_time = dayjs(val).format('YYYY-MM-DD 23:59:59');
  }

  @Emit('change')
  handleCancel(val?: boolean) {
    this.loading = false;
    setTimeout(() => {
      this.addType = 'alone';
      this.actionSelectListObj = {};
      this.actionCatchSelectObj = {};
      this.actionData.actionShowList = [];
      this.authorizedUsersList = [];
      this.exportUser = '';
    }, 300);
    return val ?? !this.value;
  }

  async handleConfirm() {
    let checkActionMultiple = true;
    if (!this.isAloneAddForm && !!this.actionData.actionShowList.length) {
      try {
        await this.actionFormRef?.validate();
      } catch (error) {
        checkActionMultiple = false;
      }
    }
    try {
      if (this.isAloneAddForm) {
        this.formData.action_multiple = ['-'];
      } else {
        this.formData.resources = [0];
        this.formData.action_id = '-';
      }
      await this.formRef.validate(async (valid) => {
        if (!checkActionMultiple) return;
        if (valid) {
          this.loading = true;
          let res = null;
          try {
            if (this.isAloneAddForm) {
              res = await this.authorizedRequest(this.formData);
            } else {
              const { action_multiple: actionMultiple, ...reset } =
                this.formData;
              const requestData = actionMultiple.map((item) => ({
                ...reset,
                action_id: item,
                resources:
                  this.actionData.actionShowList.find(
                    (aItem) => aItem.id === item
                  )?.select || [],
              }));
              const resList = await Promise.all(
                requestData.map((item) => this.authorizedRequest(item))
              );
              res = resList[0];
            }
            Message({
              message: res.need_approval
                ? this.$t('已提交审批')
                : this.$t('操作成功'),
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

  async authorizedRequest(formData) {
    const { expire_time, ...rest } = formData;
    return await $http.request(
      'authorization/createOrUpdateExternalPermission',
      {
        data: {
          space_uid: this.spaceUid,
          ...rest,
          authorized_users: rest.authorized_users.map((val) =>
            val.replace(/[\r\n]/g, '').trim()
          ),

          ...(expire_time ? { expire_time } : {}),
          authorizer: this.authorizer,
          operate_type: this.rowData ? 'update' : 'create',
          view_type: this.viewType === 'approval' ? 'user' : this.viewType,
        },
      }
    );
  }

  handleUsersChange(val: Array<string>) {
    const lastCheck = val[val.length - 1];
    if (lastCheck === '__all__') {
      this.formData.authorized_users.splice(0, val.length, '__all__');
    } else if (val.includes('__all__')) {
      this.formData.authorized_users = val.filter((item) => item !== '__all__');
    }
    // if (this.isResource) {
    //   // 若是编辑操作实例 不允许新增新的被授权人 只能删除
    //   this.formData.authorized_users = val.filter(item => this.baseUserList.includes(item));
    // }
  }

  /** 操作实例点开编辑时初始化授权人 */
  initUsersVal(val) {
    this.baseUserList = val ? this.formData.authorized_users : [];
  }

  handleSelectAloneType(authorizeType: AddType) {
    this.addType = authorizeType;
    this.formRef.clearError();
    if (!this.isAloneAddForm) {
      this.formData.action_multiple = [];
      this.actionCatchSelectObj = {};
      this.actionData.actionShowList = [];
    } else {
      this.formData.action_id = '';
      this.formData.resources = [];
    }
  }

  // 获取被授权人，操作实例tab栏的列表数据
  async getAuthListData(): Promise<any> {
    try {
      const res = await $http.request(
        'authorization/getExternalPermissionList',
        {
          query: {
            space_uid: this.spaceUid,
            view_type: 'user',
          },
        }
      );
      return res?.data ?? [];
    } catch (error) {
      return [];
    }
  }

  render() {
    const aloneAuthorizeSlot = () => {
      return (
        <div>
          <bk-form-item
            error-display-type="normal"
            property="authorized_users"
            v-show={this.isAloneAddForm}
          >
            <div class="custom-label">
              <span class="label required">{this.$t('被授权人')}</span>
              <span class="hint">({this.$t('批量粘贴请使用;进行分隔')})</span>
            </div>
            <bk-tag-input
              allow-create={true}
              disabled={!!this.rowData && this.viewType === 'user'}
              free-paste
              has-delete-icon
              list={this.authorizedShowUsersList}
              onChange={this.handleUsersChange}
              separator=";"
              trigger="focus"
              v-model={this.formData.authorized_users}
            />
          </bk-form-item>

          <bk-form-item
            error-display-type="normal"
            property="action_id"
            v-show={this.isAloneAddForm}
          >
            <div class="custom-label">
              <span class="label required">{this.$t('操作权限')}</span>
              <span class="hint">
                ({this.$t('来源于授权人:')} {this.authorizer})
              </span>
            </div>
            <bk-select
              clearable={false}
              disabled={!!this.rowData}
              onChange={this.handleActionChange}
              v-model={this.formData.action_id}
            >
              {this.actionList.map((item) => (
                <bk-option id={item.id} name={item.name}></bk-option>
              ))}
            </bk-select>
          </bk-form-item>

          <bk-form-item
            error-display-type="normal"
            property="resources"
            v-show={this.isAloneAddForm}
          >
            <div class="custom-label">
              <span class="label required">{this.$t('操作实例')}</span>
              <span class="hint">
                ({this.$t('来源于授权人:')} {this.authorizer})
              </span>
            </div>
            <bk-select
              disabled={!!this.rowData && this.viewType === 'resource'}
              multiple
              searchable
              v-model={this.formData.resources}
            >
              {this.resourceList.map((item) => (
                <bk-option
                  id={item.uid}
                  key={item.uid}
                  name={item.text}
                ></bk-option>
              ))}
            </bk-select>
          </bk-form-item>
        </div>
      );
    };

    const batchAuthorizeSlot = () => {
      return (
        <div style="margin-bottom: 8px;">
          <i18n
            class="import-user-content"
            path="导入{0}的权限配置"
            v-show={!this.isAloneAddForm && !this.rowData}
          >
            <bk-select
              behavior="simplicity"
              onSelected={this.handleSelectExportConfig}
              popover-min-width={200}
              searchable
              style="min-width: 120px; display: inline-block;"
              v-model={this.exportUser}
            >
              {this.authorizedFilterUsersList.map((item) => (
                <bk-option
                  id={item.id}
                  key={item.id}
                  name={item.name}
                ></bk-option>
              ))}
            </bk-select>
          </i18n>

          <bk-form-item
            error-display-type="normal"
            property="authorized_users"
            v-show={!this.isAloneAddForm}
          >
            <div class="custom-label">
              <span class="label required">{this.$t('被授权人')}</span>
              <span class="hint">({this.$t('批量粘贴请使用;进行分隔')})</span>
            </div>
            <bk-tag-input
              allow-create={true}
              disabled={!!this.rowData && this.viewType === 'user'}
              free-paste
              has-delete-icon
              list={this.authorizedShowUsersList}
              onChange={this.handleUsersChange}
              separator=";"
              trigger="focus"
              v-model={this.formData.authorized_users}
            />
          </bk-form-item>

          <bk-form-item
            error-display-type="normal"
            property="action_multiple"
            v-show={!this.isAloneAddForm && !this.rowData}
          >
            <div class="custom-label">
              <span class="label required">{this.$t('操作权限')}</span>
              <span class="hint">({this.$t('至少选择一个操作权限')})</span>
            </div>
            <bk-checkbox-group
              onChange={this.handleClickActionList}
              v-model={this.formData.action_multiple}
            >
              {this.actionList.map((item) => (
                <bk-checkbox value={item.id}>{item.name}</bk-checkbox>
              ))}
            </bk-checkbox-group>
          </bk-form-item>

          <bk-form
            form-type="vertical"
            ref="actionFormRef"
            {...{
              props: {
                model: this.actionData,
              },
            }}
          >
            {this.actionData.actionShowList.map((action, index) => (
              <bk-form-item
                error-display-type="normal"
                property={`actionShowList.${index}.select`}
                rules={this.actionRules.select}
                v-show={!this.isAloneAddForm && !this.rowData}
              >
                <div class="custom-label">
                  <span class="label required">{action.name}</span>
                </div>
                <bk-select
                  disabled={!!this.rowData && this.viewType === 'resource'}
                  multiple
                  onSelected={(v) => this.handleSelectAction(v, action)}
                  searchable
                  v-model={action.select}
                >
                  {action.list.map((item) => (
                    <bk-option
                      id={item.uid}
                      key={item.uid}
                      name={item.text}
                    ></bk-option>
                  ))}
                </bk-select>
              </bk-form-item>
            ))}
          </bk-form>
        </div>
      );
    };

    return (
      <bk-dialog
        auto-close={false}
        draggable={false}
        header-position="left"
        loading={this.loading}
        mask-close={false}
        on-value-change={this.initUsersVal}
        onCancel={this.handleCancel}
        title={this.$t(this.rowData ? '编辑授权' : '添加授权')}
        value={this.value}
        width={480}
      >
        <bk-form
          form-type="vertical"
          ref="formRef"
          {...{
            props: {
              model: this.formData,
              rules: this.rules,
            },
          }}
        >
          {!this.rowData && (
            <div class="select-group bk-button-group">
              <bk-button
                class={{ 'is-selected': this.isAloneAddForm }}
                onClick={() => this.handleSelectAloneType('alone')}
              >
                {$i18n.t('单独授权')}
              </bk-button>
              <bk-button
                class={{ 'is-selected': !this.isAloneAddForm }}
                onClick={() => this.handleSelectAloneType('batch')}
              >
                {$i18n.t('批量授权')}
              </bk-button>
            </div>
          )}

          {aloneAuthorizeSlot()}
          {batchAuthorizeSlot()}

          {!this.isResource && (
            <bk-form-item error-display-type="normal" property="expire_time">
              <div class="custom-label">
                <span class="label required">{this.$t('截止时间')}</span>
              </div>
              <bk-date-picker
                clearable={false}
                format="yyyy-MM-dd HH:mm:ss"
                onChange={this.handleDateChange}
                options={{ disabledDate: this.disabledDate }}
                type="date"
                value={this.formData.expire_time}
              ></bk-date-picker>
            </bk-form-item>
          )}
        </bk-form>

        <div slot="footer">
          <bk-button
            loading={this.loading}
            onClick={this.handleConfirm}
            style="margin-right: 8px"
            theme="primary"
          >
            {this.$t('确认')}
          </bk-button>
          <bk-button onClick={() => this.handleCancel(false)} theme="default">
            {this.$t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
