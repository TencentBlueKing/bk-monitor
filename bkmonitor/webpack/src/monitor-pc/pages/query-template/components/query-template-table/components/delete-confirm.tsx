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
import { emit, Component as tsc } from 'vue-tsx-support';

import './delete-confirm.scss';

interface DeleteConfirmEmit {
  onCancel: () => void;
  onConfirm: () => void;
}

interface DeleteConfirmProps {
  templateName: string;
}

@Component
export default class DeleteConfirm extends tsc<DeleteConfirmProps, DeleteConfirmEmit> {
  @Prop({ type: String }) templateName: string;

  @Emit('confirm')
  confirm() {
    return;
  }
  @Emit('cancel')
  cancel() {
    return;
  }

  render() {
    return (
      <div class='delete-confirm-tip'>
        <div class='tip-title'>
          <span>{this.$t('确认删除该查询模板？')}</span>
        </div>
        <div class='tip-confirm-info'>
          <div class='tip-confirm-info-item'>
            <span class='info-item-label'>{this.$t('模板名称:')}</span>
            <span class='info-item-value'>{this.templateName}</span>
          </div>
        </div>
        <div class='tip-description'>
          <span>{this.$t('删除后不可恢复，请谨慎操作。')}</span>
        </div>
        <div class='tip-operation'>
          <bk-button
            size='small'
            theme='primary'
            onClick={this.confirm}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button
            size='small'
            onClick={this.cancel}
          >
            {this.$t('取消')}
          </bk-button>
        </div>
      </div>
    );
  }
}
