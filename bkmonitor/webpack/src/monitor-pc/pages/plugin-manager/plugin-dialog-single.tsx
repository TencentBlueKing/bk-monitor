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
import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './plugin-dialog-single.scss';

interface PluginDialogSingleProps {
  dialog: {
    show: boolean;
    title: string;
    percent: number;
    name: string;
    status: number;
    size: number;
    loading: boolean;
    update: boolean;
    data: any;
  };
}

interface PluginDialogSingleEvents {
  onHandlePluginAdd: (data: any) => void;
  onHandleSetUpdatePlugin: () => void;
  onHandlePluginEdit: (id: number) => void;
  onHandleHideDialog: () => void;
}

@Component
export default class PluginDialogSingle extends tsc<PluginDialogSingleProps, PluginDialogSingleEvents> {
  @Prop({ default: () => ({}) }) dialog: PluginDialogSingleProps['dialog'];

  get isSuperUser() {
    return this.$store.getters.isSuperUser;
  }

  get canIUpdatePlubin() {
    // conflict_title:
    // 1.导入版本不大于当前版本
    // 2.插件类型冲突
    // 3.远程采集配置项冲突
    // 4.插件已关联%s个采集配置
    // 5.导入插件与当前插件内容完全一致
    const arr = this.dialog.data.conflict_ids;
    // 2 3 5 为不需强制更新插件
    const flag = [2, 3, 5].some(item => arr.toString().indexOf(`${item}`) > -1);
    return !flag;
  }

  handleCreateNewPlugin() {
    const { data } = this.dialog;
    if (data.is_official) {
      this.$emit('handleSetUpdatePlugin');
    } else {
      this.handleHideDialog();
      this.$emit('handlePluginAdd', data);
    }
  }

  handleUpdatePlugin() {
    const { data } = this.dialog;
    if (data.is_official && this.dialog.update) {
      this.$emit('handleSetUpdatePlugin');
    } else {
      this.handleHideDialog();
      this.$emit('handlePluginEdit', data.plugin_id);
    }
  }

  handleHideDialog() {
    this.$emit('handleHideDialog');
  }

  handleToEdit() {
    // 非官方, 具有完整签名去更新插件
    const { data } = this.dialog;
    this.handleHideDialog();
    this.$router.push({
      name: 'plugin-update',
      params: {
        pluginData: data
      }
    });
  }

  render() {
    return (
      <bk-dialog
        v-model={this.dialog.show}
        show-footer={false}
        mask-close={false}
        on-after-leave={this.handleHideDialog}
        ext-cls='plugin-manager-dialog'
        header-position='left'
        width='480'
      >
        <template slot='header'>
          <div class='dialog-title'>{this.dialog.title}</div>
        </template>
        <div class='dilog-container'>
          <div class='dialog-content'>
            <span class='icon-monitor icon-CPU dialog-content-icon' />
            <div class='dialog-content-desc'>
              <div class='desc-name'>
                <span
                  class='desc-name-set'
                  v-bk-overflow-tips
                >
                  {this.dialog.name}
                </span>
                {this.dialog.status > 1 && <span class='desc-name-size'>{this.dialog.size}</span>}
              </div>
              {this.dialog.status === 1 && (
                <bk-progress
                  class='desc-process'
                  percent={this.dialog.percent}
                  show-text={false}
                  size='small'
                  color='#3A84FF'
                />
              )}
            </div>
          </div>
          {this.dialog.percent === 1 && (
            <div class='dialog-loading'>
              <span
                class={[
                  'icon-monitor',
                  'loading-icon',
                  [2, 4, 5].includes(this.dialog.status) ? 'icon-tixing' : 'icon-loading'
                ]}
                style={{
                  'animation-iteration-count': this.dialog.status === 1 ? 'infinite' : 0,
                  color: this.dialog.status === 2 || this.dialog.status === 4 ? '#EA3636' : '#3A84FF'
                }}
              />
              {this.dialog.status === 1 && <span class='loading-text'> {this.$t('上传中...')} </span>}
              {this.dialog.status === 2 && (
                <span class='loading-text'>
                  {this.dialog.status === 2 ? this.$t('上传失败，请重试') : this.$t('上传完成')}
                </span>
              )}
              {this.dialog.status === 4 && (
                <div>
                  <span style='color: #ea3636'>
                    {this.$t('注意: 插件ID冲突')}
                    {this.dialog.data.conflict_title ? `,${this.dialog.data.conflict_title}` : ''}：
                  </span>
                  {this.dialog.data.conflict_detail}
                </div>
              )}

              {this.dialog.status === 5 && <div>{this.dialog.data.conflict_detail}</div>}
            </div>
          )}
          {this.dialog.data.conflict_detail && (
            <div class='dialog-footer'>
              {/* 非官方插件更新操作 */}
              {!this.dialog.data.is_official && this.dialog.data.is_safety && this.canIUpdatePlubin && (
                <bk-button
                  class='dialog-footer-btn'
                  theme='primary'
                  onClick={this.handleToEdit}
                >
                  {this.$t('更新插件')}
                </bk-button>
              )}

              <bk-button
                class='dialog-footer-btn'
                theme='success'
                onClick={this.handleCreateNewPlugin}
              >
                {this.$t('创建插件')}
              </bk-button>
              <bk-button
                v-if='dialog.update && dialog.data.is_official && isSuperUser'
                onClick={this.handleUpdatePlugin}
                loading={this.dialog.loading}
                class='dialog-footer-btn'
                theme='primary'
              >
                {this.$t('更新至现有插件')}
              </bk-button>
              <bk-button
                class='dialog-footer-btn'
                onClick={this.handleHideDialog}
              >
                {' '}
                {this.$t('取消')}{' '}
              </bk-button>
            </div>
          )}
        </div>
      </bk-dialog>
    );
  }
}
