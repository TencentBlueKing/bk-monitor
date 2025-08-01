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

import { Component, Emit, Prop, Ref, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { bulkUpdateUserGroup } from 'monitor-api/modules/model';
import { getReceiver } from 'monitor-api/modules/notice_group';

import { getDefaultUserGroupListSync } from '../../../components/user-selector/user-group';
import UserSelector from '../../../components/user-selector/user-selector';
import { type OperationType, OperationTypeMap } from './utils';

import './batch-operation-dialog.scss';

interface BatchOperationDialogEvents {
  onCloseDialog: () => void;
}

interface BatchOperationDialogProps {
  groupIds: number[];
  operationType: string;
  show: boolean;
}

@Component({
  name: 'BatchOperationDialog',
})
export default class BatchOperationDialog extends tsc<BatchOperationDialogProps, BatchOperationDialogEvents> {
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: String, default: '' }) operationType: OperationType;
  @Prop({ type: Array, default: () => [] }) groupIds: number[];

  @Ref('formRef') formRef: any;

  cacheInitData = null;

  loading = false;

  allReceiverData = [];
  // 用户组数据
  defaultGroupList = [];

  formModel = {
    noticeUser: {
      users: [],
      addMethod: 'append',
    },
  };

  get defaultUserGroupList() {
    return getDefaultUserGroupListSync(this.defaultGroupList[0]?.children || []);
  }

  get formData() {
    return this.formModel[this.operationType] || {};
  }

  get currentOperation() {
    return OperationTypeMap[this.operationType] || { width: 400, title: '' };
  }

  get formRules() {
    switch (this.operationType) {
      case 'noticeUser':
        return {
          users: [
            {
              required: true,
              message: this.$t('通知对象不能为空'),
              trigger: 'change',
            },
          ],
          addMethod: [
            {
              required: true,
              message: this.$t('添加方式必填'),
              trigger: 'change',
            },
          ],
        };
      default:
        return {};
    }
  }

  async getReceiverGroup() {
    await getReceiver().then(data => {
      this.allReceiverData = data;
      const groupData = data.find(item => item.id === 'group');
      groupData.type = 'group';
      groupData.children.map(item => (item.username = item.id));
      this.defaultGroupList.push(groupData);
    });
  }

  /**
   * @description: 处理接收人参数
   * @param {*}
   * @return {*}
   */
  handleNoticeReceiver() {
    const result = [];
    const groupMap = new Map();
    this.allReceiverData.forEach(item => {
      const isGroup = item.type === 'group';
      isGroup &&
        item.children.forEach(chil => {
          groupMap.set(chil.id, chil);
        });
    });
    this.formModel.noticeUser.users.forEach(id => {
      const isGroup = groupMap.has(id);
      result.push({
        display_name: isGroup ? groupMap.get(id)?.display_name : id,
        logo: '',
        id,
        type: isGroup ? 'group' : 'user',
        members: isGroup ? groupMap.get(id)?.members : undefined,
      });
    });
    return result;
  }

  @Watch('show')
  watchShowChange(val: boolean) {
    if (val) {
      this.cacheInitData = JSON.parse(JSON.stringify(this.formModel));
      this.getReceiverGroup();
    } else {
      this.formModel = JSON.parse(JSON.stringify(this.cacheInitData));
      this.formRef?.clearError();
    }
  }

  generateParams() {
    switch (this.operationType) {
      case 'noticeUser': {
        const { users, addMethod } = this.formModel.noticeUser;
        if (addMethod === 'append') {
          return {
            ids: this.groupIds,
            edit_data: {
              users,
              append_keys: ['users'],
            },
          };
        }
        return {
          ids: this.groupIds,
          edit_data: {
            users,
          },
        };
      }
    }
  }

  handleConfirm() {
    this.formRef.validate(valid => {
      if (!valid) return;
      this.loading = true;
      const params = this.generateParams();
      bulkUpdateUserGroup(params)
        .then(() => {
          this.$bkMessage({
            message: this.$t('批量编辑成功'),
            theme: 'success',
          });
          this.handleCancel(true);
        })
        .finally(() => {
          this.loading = false;
        });
    });
  }

  getCurrentOperationContent() {
    switch (this.operationType) {
      case 'noticeUser':
        return [
          <bk-form-item
            key='users'
            label={this.$t('通知对象')}
            property='users'
            required={true}
          >
            <UserSelector
              class='user-selector'
              userGroupList={this.defaultUserGroupList}
              userIds={this.formModel.noticeUser.users}
              onChange={users => (this.formModel.noticeUser.users = users)}
            />
          </bk-form-item>,
          <bk-form-item
            key='addMethod'
            label={this.$t('添加方式')}
            property='addMethod'
            required={true}
          >
            <bk-radio-group
              class='add-method-radio-group'
              v-model={this.formModel.noticeUser.addMethod}
            >
              <bk-radio value='append'>{this.$t('批量追加')}</bk-radio>
              <bk-radio value='replace'>{this.$t('批量替换')}</bk-radio>
            </bk-radio-group>
          </bk-form-item>,
        ];
    }
  }

  @Emit('closeDialog')
  handleCancel(resetRequest = false) {
    return resetRequest;
  }

  render() {
    return (
      <bk-dialog
        width={this.currentOperation.width}
        class='alarm-group-batch-operation-dialog'
        escClose={false}
        headerPosition={'left'}
        maskClose={false}
        render-directive='if'
        title={this.currentOperation.title}
        value={this.show}
        onCancel={() => this.handleCancel(false)}
      >
        <div class='alarm-group-batch-operation-wrap'>
          <bk-form
            ref='formRef'
            form-type='vertical'
            {...{
              props: {
                model: this.formData,
                rules: this.formRules,
              },
            }}
          >
            {this.getCurrentOperationContent()}
          </bk-form>
        </div>
        <div slot='footer'>
          <bk-button
            class='confirm-btn'
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button
            class='cancel-btn'
            onClick={() => this.handleCancel(false)}
          >
            {' '}
            {this.$t('取消')}{' '}
          </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
