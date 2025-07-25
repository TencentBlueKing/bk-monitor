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

import _ from 'lodash';
import { updateSceneView } from 'monitor-api/modules/scene_view';

import './index.scss';

interface IEmit {
  onSuccess: () => void;
}

interface IProps {
  payload: Record<string, any>;
  sceneId: string;
  viewId: string;
  viewList: {
    id: string;
    name: string;
  }[];
}

@Component
export default class ViewSave extends tsc<IProps, IEmit> {
  @Prop({ type: String, required: true }) readonly sceneId: IProps['sceneId'];
  @Prop({ type: Object, default: () => ({}) }) readonly payload: IProps['payload'];
  @Prop({ type: String, required: true }) readonly viewId: IProps['viewId'];
  @Prop({ type: Array, required: true }) readonly viewList: IProps['viewList'];

  @Ref('popoverRef') readonly popoverRef: any;
  @Ref('createFormRef') readonly createFormRef: any;
  @Ref('inputRef') readonly inputRef: any;

  isCreateSubmiting = false;
  isActive = false;
  isShowCreateDialog = false;
  createFormData = {
    name: '',
  };

  get createRules() {
    return Object.freeze({
      name: [
        {
          required: true,
          message: this.$t('必填项'),
          trigger: 'change',
        },
        {
          validator: (value: string) => {
            return _.every(this.viewList, item => item.name !== value);
          },
          message: this.$t('视图名称重复'),
          trigger: 'change',
        },
      ],
    });
  }

  get currentSelectViewInfo() {
    return this.viewList.find(item => item.id === this.viewId) || { id: 'default', name: 'default' };
  }

  get isDefaultView() {
    return this.viewId === 'default';
  }

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
    setTimeout(() => {
      this.inputRef.focus();
    });
  }
  handleCancelCreate() {
    this.isShowCreateDialog = false;
  }
  async handleSubmitCreate() {
    this.isCreateSubmiting = true;
    try {
      await this.createFormRef.validate();
      await updateSceneView({
        scene_id: this.sceneId,
        id: `custom_view_${Date.now()}`,
        type: 'detail',
        config: {
          options: this.payload,
        },
        ...this.createFormData,
      });
      this.isShowCreateDialog = false;
      this.$bkMessage({
        theme: 'success',
        message: this.$t('新视图保存成功'),
      });
      this.$emit('success');
    } finally {
      this.isCreateSubmiting = false;
    }
  }

  async handleEdit() {
    await updateSceneView({
      scene_id: this.sceneId,
      type: 'detail',
      config: {
        options: this.payload,
      },
      ...this.currentSelectViewInfo,
    });
    this.$bkMessage({
      theme: 'success',
      message: this.$t('当前视图保存成功'),
    });
    this.$emit('success');
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
            zIndex: 999,
          }}
          placement='bottom'
          theme='light metric-view-view-save-panel'
          trigger='manual'
        >
          <i class='icon-monitor icon-a-savebaocun' />
          <div slot='content'>
            {!this.isDefaultView && (
              <div
                class='item'
                onClick={this.handleEdit}
              >
                {this.$t('覆盖当前视图')}
              </div>
            )}
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
          scrollable={false}
          title={this.$t('另存为新视图')}
        >
          <bk-form
            ref='createFormRef'
            form-type='vertical'
            {...{
              props: {
                model: this.createFormData,
                rules: this.createRules,
              },
            }}
          >
            <bk-form-item
              error-display-type='normal'
              label={this.$t('视图名称')}
              property='name'
              required
            >
              <bk-input
                ref='inputRef'
                v-model={this.createFormData.name}
                maxlength={30}
                show-word-limit={true}
              />
            </bk-form-item>
          </bk-form>
          <div slot='footer'>
            <bk-button
              loading={this.isCreateSubmiting}
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
