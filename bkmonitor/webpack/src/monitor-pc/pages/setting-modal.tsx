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
import { Component, Emit, Mixins, Prop, Provide, ProvideReactive } from 'vue-property-decorator';
import { ofType } from 'vue-tsx-support';

import MonitorDialog from 'monitor-ui/monitor-dialog';

import NoPermission from '../components/no-permission/no-permission';
import authorityMixinCreate from '../mixins/authorityMixin';
import * as ruleAuth from './authority-map';

import type { IMenuItem } from '../types';

import './setting-modal.scss';

const authorityMap = {
  ...ruleAuth,
};
interface ISettingModalEvent {
  onChange: boolean;
  onMenuChange: IMenuItem;
}
interface ISettingModalProps {
  // 选中的左侧栏项
  activeMenu?: string;
  // 左侧menu list 不设置则不显示左侧栏
  menuList?: IMenuItem[];
  // 是否显示
  show: boolean;
  // 标题
  title?: string;
  zIndex?: number;
  // 关闭前回调函数 函数返回值为true时正常关闭 false则不会关闭
  beforeClose?: () => Promise<boolean>;
}
@Component
class SettingModal extends Mixins(authorityMixinCreate(ruleAuth, 'created')) {
  @ProvideReactive('authority') authority: Record<string, boolean> = {};
  @Provide('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Provide('authorityMap') authorityMap = authorityMap;

  @Prop({ required: true, type: Boolean }) readonly show: boolean;
  @Prop({ default: '', type: String }) readonly title: string;
  @Prop({ default: () => [], type: Array }) readonly menuList: IMenuItem[];
  @Prop({ default: '', type: String }) readonly activeMenu: string;
  @Prop({ type: Function }) readonly beforeClose: () => Promise<boolean>;
  @Prop({ type: Number }) readonly zIndex: number;

  @Emit('change')
  async handleShow(v: boolean) {
    return v;
  }

  /**
   * @description: 处理设置弹层关闭
   */
  async handleClose() {
    try {
      let res = true;
      if (this.beforeClose) {
        res = await this.beforeClose();
      }
      !!res && this.handleShow(false);
    } catch (error) {
      console.log(error);
    }
  }

  getContentPanel(activeMenu: string) {
    switch (activeMenu) {
      case 'global-config':
        return this.authority.VIEW_GLOBAL_AUTH ? (
          this.$slots.default
        ) : (
          <NoPermission actionIds={this.authorityMap.VIEW_GLOBAL_AUTH} />
        );
      case 'healthz':
        return this.authority.VIEW_SELF_AUTH ? (
          this.$slots.default
        ) : (
          <NoPermission actionIds={this.authorityMap.VIEW_SELF_AUTH} />
        );
      case 'migrate-dashboard':
        return this.authority.VIEW_MIGRATE_DASHBOARD ? (
          this.$slots.default
        ) : (
          <NoPermission actionIds={this.authorityMap.VIEW_MIGRATE_DASHBOARD} />
        );
      // // 待补充迁移仪表盘及策略权限控制
      // return this.$slots.default;
      case 'calendar':
        return this.authority.VIEW_GLOBAL_AUTH ? (
          this.$slots.default
        ) : (
          <NoPermission actionIds={this.authorityMap.VIEW_GLOBAL_AUTH} />
        );
      case 'resource-register':
      case 'data-pipeline':
        return this.authorityMap.VIEW_GLOBAL_AUTH ? (
          this.$slots.default
        ) : (
          <NoPermission actionIds={this.authorityMap.VIEW_GLOBAL_AUTH} />
        );
      default:
        return this.$slots.default;
    }
  }

  render() {
    return (
      <MonitorDialog
        class='setting-modal'
        fullScreen={true}
        needFooter={false}
        needHeader={false}
        value={this.show}
        zIndex={this.zIndex}
        onChange={this.handleShow}
      >
        <div class='setting-modal-header'>
          {this.$t(this.title)}
          <i
            class='bk-icon icon-close close-icon'
            onClick={this.handleClose}
          />
        </div>
        <div class='setting-modal-body'>
          <div class='panel-wrapper'>
            <div
              style={{ display: this.menuList?.length ? 'flex' : 'none' }}
              class='left-panel'
            >
              {this.menuList.map(item => (
                <div
                  key={item.id}
                  class={`menu-item ${this.activeMenu === item.id ? 'active-menu' : ''}`}
                  onClick={() => this.activeMenu !== item.id && this.$emit('menuChange', item)}
                >
                  {this.$t(item.name)}
                </div>
              ))}
            </div>
            <div class='content-panel'>{this.getContentPanel(this.activeMenu)}</div>
          </div>
        </div>
      </MonitorDialog>
    );
  }
}

export default ofType<ISettingModalProps, ISettingModalEvent>().convert(SettingModal);
