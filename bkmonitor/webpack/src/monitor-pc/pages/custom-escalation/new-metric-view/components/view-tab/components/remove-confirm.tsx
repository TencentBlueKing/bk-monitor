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

import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

interface IEmit {
  onSubmit: (id: string) => void;
}
interface IProps {
  data: {
    id: string;
    name: string;
  };
}
@Component
export default class RemoveConfirm extends tsc<IProps, IEmit> {
  @Prop({ type: Object, required: true }) readonly data: IProps['data'];

  @Ref('popoverRef') readonly popoverRef: any;

  isActive = false;

  handleShow() {
    this.isActive = true;
  }

  handleHidden() {
    this.isActive = false;
  }

  handleClickStop(event: Event) {
    event.stopImmediatePropagation();
    event.stopPropagation();
    this.popoverRef.showHandler();
  }

  handleSubmit() {
    this.$emit('submit', this.data.id);
  }

  handleCancel() {
    this.popoverRef.hideHandler();
  }

  render() {
    return (
      <bk-popover
        ref='popoverRef'
        tippyOptions={{
          placement: 'bottom-start',
          distance: 4,
          hideOnClick: true,
          onShow: this.handleShow,
          onHidden: this.handleHidden,
        }}
        theme='light'
        trigger='click'
      >
        <div
          style='height: 40px'
          class={{
            'is-active': this.isActive,
          }}
          onClick={this.handleClickStop}
        >
          {this.$slots.default}
        </div>
        <div
          style='min-width: 280px'
          slot='content'
        >
          <div style='font-size: 16px; color: #313238; line-height: 24px'>{this.$t('确认删除该视图？')}</div>
          <div style='font-size: 12px; color: #4D4F56; line-height: 20px; margin-top: 16px'>
            <div>
              {this.$t('视图名称：')}
              {this.data.name}
            </div>
            <div>{this.$t('删除后，不可恢复，请谨慎操作！')}</div>
          </div>
          <div style='display: flex; margin-top: 22px; justify-content: flex-end; padding-bottom: 8px'>
            <bk-button
              size='small'
              theme='danger'
              onClick={this.handleSubmit}
            >
              {this.$t('删除')}
            </bk-button>
            <bk-button
              style='margin-left: 8px'
              size='small'
              onClick={this.handleCancel}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </div>
      </bk-popover>
    );
  }
}
