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

import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import type { AlarmTemplateListItem } from '../../typing';

import './alarm-delete-confirm.scss';

export interface AlarmDeleteConfirmEvent {
  /** 确认删除的 Promise */
  promiseEvent: Promise<any>;
  /** 失败回调 */
  errorCallback: () => void;
  /** 成功回调 */
  successCallback: () => void;
}
interface AlarmDeleteConfirmEmit {
  /** 取消按钮点击事件 */
  onCancel: () => void;
  /** 确认按钮点击事件 */
  onConfirm: (templateId: AlarmTemplateListItem['id'], confirmEvent: AlarmDeleteConfirmEvent) => void;
}

interface AlarmDeleteConfirmProps {
  /** 想要删除的 告警模板ID */
  templateId: AlarmTemplateListItem['id'];
  /** 想要删除的 告警模板名称 */
  templateName: AlarmTemplateListItem['name'];
}

@Component
export default class AlarmDeleteConfirm extends tsc<AlarmDeleteConfirmProps, AlarmDeleteConfirmEmit> {
  /** 想要删除的 告警模板ID */
  @Prop({ type: [String, Number] }) templateId: AlarmTemplateListItem['id'];
  /** 想要删除的 告警模板名称 */
  @Prop({ type: String }) templateName: AlarmTemplateListItem['name'];

  /** 是否在请求删除状态中 */
  loading = false;

  /**
   * @description 点击取消按钮，触发取消操作
   */
  @Emit('cancel')
  cancel() {
    return;
  }

  /**
   * @description 点击确认按钮，触发删除操作
   * 进入 loading 状态，并将事件往上抛出
   * 事件对象中包含 Promise 对象以及更改 状态的方法
   */
  handleConfirm() {
    this.loading = true;
    let successCallback = null;
    let errorCallback = null;
    const promiseEvent = new Promise((res, rej) => {
      successCallback = res;
      errorCallback = rej;
    })
      .then(() => {
        this.loading = false;
      })
      .catch(() => {
        this.loading = false;
      });

    this.$emit('confirm', this.templateId, {
      promiseEvent,
      successCallback,
      errorCallback,
    });
  }

  render() {
    return (
      <div class='alarm-delete-confirm-tip'>
        <div class='tip-title'>
          <span>{this.$t('确认删除该告警模板？')}</span>
        </div>
        <div class='tip-confirm-info'>
          <div class='tip-confirm-info-item'>
            <span class='info-item-label'>{`${this.$t('告警模板')}:`}</span>
            <span class='info-item-value'>{this.templateName}</span>
          </div>
        </div>
        <div class='tip-description'>
          <span>{this.$t('删除后，不可恢复，请确认。')}</span>
        </div>
        <div class='tip-operation'>
          <bk-button
            loading={this.loading}
            size='small'
            theme='primary'
            onClick={this.handleConfirm}
          >
            {this.$t('确定')}
          </bk-button>
          <bk-button
            loading={this.loading}
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
