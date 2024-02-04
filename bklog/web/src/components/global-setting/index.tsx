/*
 * Tencent is pleased to support the open source community by making BK-LOG 蓝鲸日志平台 available.
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 * BK-LOG 蓝鲸日志平台 is licensed under the MIT License.
 *
 * License for BK-LOG 蓝鲸日志平台:
 * --------------------------------------------------------------------
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
 * and to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 * The above copyright notice and this permission notice shall be included in all copies or substantial
 * portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT
 * LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN
 * NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY,
 * WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE
 */

import { Component as tsc } from 'vue-tsx-support';
import {
  Component,
  Model,
  Prop,
} from 'vue-property-decorator';
import { Dialog } from 'bk-magic-vue';
import MaskingSetting from '../log-masking/masking-setting';
import './index.scss';

interface IMenuItem {
  id: string;
  name: string;
  href?: string;
}

interface IProps {
  value: boolean;
  /** 左侧menu list 不设置则不显示左侧栏 */
  menuList?: IMenuItem[];
  /** 选中的左侧栏项 */
  activeMenu?: string;
}

@Component
export default class MaskingDialog extends tsc<IProps> {
  @Model('change', { type: Boolean, default: false }) value: IProps['value'];
  @Prop({ default: () => [], type: Array }) readonly menuList: IMenuItem[];
  @Prop({ default: '', type: String }) readonly activeMenu: string;

  get showAlert() {
    return this.$store.state.showAlert;
  }

  handleCloseDialog() {
    this.$store.commit('updateIsShowGlobalDialog', false);
  }

  getContentPanel(activeMenu: string) {
    switch (activeMenu) {
      case 'masking-setting':
        return <MaskingSetting style={'padding: 20px 24px;'} />;
      default:
        return this.$slots.default;
    }
  }

  render() {
    return (
      <Dialog
        value={this.value}
        render-directive="if"
        width="100%"
        scrollable
        show-mask={false}
        show-footer={false}
        draggable={false}
        close-icon={false}
        ext-cls="masking-dialog"
        position={{
          top: this.showAlert ? 90 : 50,
          left: 0,
        }}
      >
        <div class={`masking-container ${this.showAlert ? 'is-show-notice' : ''}`}>
          <div class="masking-title">
            <div></div>
            <span>{this.$t('全局设置')}</span>
            <div class="bk-icon icon-close" onClick={this.handleCloseDialog}></div>
          </div>
          <div class="center-box">
            <div
              class='left-panel'
              style={{ display: this.menuList?.length ? 'flex' : 'none' }}
            >
              {this.menuList.map(item => (
                <div
                  class={`menu-item ${this.activeMenu === item.id ? 'active-menu' : ''}`}
                  key={item.id}
                  onClick={() => this.activeMenu !== item.id && this.$emit('menuChange', item)}
                >
                  {this.$t(item.name)}
                </div>
              ))}
            </div>
            <div class='content-panel'>{this.getContentPanel(this.activeMenu)}</div>
          </div>
        </div>
      </Dialog>
    );
  }
}
