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
import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './view-save.scss';

@Component
export default class ViewSave extends tsc<object> {
  @Ref('popoverRef') popoverRef: any;

  isActive = false;
  isShowCreateDialog = false;
  createFormData = {
    name: '',
  };
  createRules = Object.freeze({
    name: [
      {
        required: true,
        message: this.$t('必填项'),
        trigger: 'blur',
      },
    ],
  });

  handleShow() {
    this.isActive = true;
  }
  handleHidden() {
    this.isActive = false;
  }
  handleShowPanel() {
    this.popoverRef.showHandler();
  }

  handleShowCreate() {
    this.isShowCreateDialog = true;
    this.createFormData.name = '';
  }
  handleCancelCreate() {
    this.isShowCreateDialog = false;
  }
  handleSubmitCreate() {
    console.log('handleSubmitCreate');
  }

  render() {
    return (
      <div
        class={{
          'metric-view-view-save-btn': true,
          'is-active': this.isActive,
        }}
        onClick={this.handleShowPanel}
      >
        <bk-popover
          ref='popoverRef'
          tippyOptions={{
            placement: 'bottom-start',
            distance: 10,
            arrow: false,
            hideOnClick: true,
            onShow: this.handleShow,
            onHidden: this.handleHidden,
          }}
          placement='bottom'
          theme='light metric-view-view-save-panel'
          trigger='manual'
        >
          <i class='icon-monitor icon-a-savebaocun' />
          <div slot='content'>
            <div class='item'>{this.$t('覆盖当前视图')}</div>
            <div
              class='item'
              onClick={this.handleShowCreate}
            >
              {this.$t('另存为新视图')}
            </div>
          </div>
        </bk-popover>
        <bk-dialog
          width={480}
          v-model={this.isShowCreateDialog}
          draggable={false}
          header-position='left'
          render-directive='if'
          rules={this.createRules}
          scrollable={false}
          title={this.$t('另存为新视图')}
        >
          <bk-form
            form-type='vertical'
            model={this.createFormData}
          >
            <bk-form-item
              label={this.$t('视图名称')}
              required
            >
              <bk-input v-model={this.createFormData.name} />
            </bk-form-item>
          </bk-form>
          <div slot='footer'>
            <bk-button
              theme='primary'
              onClick={this.handleSubmitCreate}
            >
              {this.$t('确定')}
            </bk-button>
            <bk-button
              style='margin-left: 8px'
              onClick={this.handleCancelCreate}
            >
              {this.$t('取消')}
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  }
}
