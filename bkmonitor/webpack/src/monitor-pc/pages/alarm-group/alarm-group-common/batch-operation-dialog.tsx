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

import MemberSelector from '../alarm-group-add/member-selector.vue';
import { type OperationType, OperationTypeMap } from './utils';

import './batch-operation-dialog.scss';

interface BatchOperationDialogProps {
  show: boolean;
  operationType: string;
  groupIds: number[];
}

interface BatchOperationDialogEvents {
  onCloseDialog: () => void;
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
    },
  };
  btnType: 'append' | 'confirm' = 'confirm';

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
        const users = this.formModel.noticeUser.users;
        if (this.btnType === 'append') {
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

  handleClick(type: 'append' | 'confirm' = 'confirm') {
    this.btnType = type;
    this.handleConfirm();
  }

  handleConfirm() {
    this.formRef.validate(valid => {
      if (!valid) return;
      this.loading = true;
      const params = this.generateParams();
      bulkUpdateUserGroup(params)
        .then(() => {
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
        return (
          <bk-form-item
            error-display-type='normal'
            label={this.$t('通知对象')}
            label-width={100}
            property='users'
            required={true}
          >
            <MemberSelector
              class='user-selector'
              v-model={this.formModel.noticeUser.users}
              group-list={this.defaultGroupList}
            />
          </bk-form-item>
        );
    }
  }

  getFooterComponent() {
    switch (this.operationType) {
      case 'noticeUser':
        return [
          <bk-button
            key='append'
            loading={this.loading}
            theme='primary'
            onClick={() => this.handleClick('append')}
          >
            {this.$t('批量追加')}
          </bk-button>,
          <bk-button
            key='replace'
            loading={this.loading}
            theme='primary'
            onClick={() => this.handleClick('confirm')}
          >
            {this.$t('批量替换')}
          </bk-button>,
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
          {this.getFooterComponent()}
          <bk-button onClick={() => this.handleCancel(false)}> {this.$t('取消')} </bk-button>
        </div>
      </bk-dialog>
    );
  }
}
