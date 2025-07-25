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
import { Component, Model, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import BkUserSelectorOrigin, { type FormattedUser } from '@blueking/bk-user-selector/vue2';

import { getUserComponentConfig, USER_GROUP_TYPE } from '../../common/user-display-name';

import type { IUserGroup } from './user-group';
import type { ConfigOptions } from '@blueking/bk-user-display-name';

import './user-selector.scss';
import '@blueking/bk-user-selector/vue2/vue2.css';

interface IBkUserSelectorProps {
  [key: string]: any;
  apiBaseUrl?: string;
  draggable?: boolean;
  emptyText?: string;
  enableMultiTenantMode?: boolean;
  modelValue?: string | string[];
  multiple?: boolean;
  placeholder?: string;
  tenantId?: string;
  userGroup?: IUserGroup[];
  onChange?: (value: string[]) => void;
  renderListItem?: (_, userInfo: FormattedUser) => JSX.Element;
  renderTag?: (_, userInfo: FormattedUser) => JSX.Element;
}

const BkUserSelector: (props: IBkUserSelectorProps) => JSX.Element = BkUserSelectorOrigin as any as (
  props: IBkUserSelectorProps
) => JSX.Element;

@Component({
  name: 'user-selector',
})
export default class UserSelector extends tsc<
  {
    draggable?: boolean;
    emptyText?: string;
    multiple?: boolean;
    placeholder?: string;
    userGroup?: string[];
    userGroupList?: IUserGroup[];
    userIds: string | string[];
  },
  { onChange: string[] }
> {
  @Prop({ type: Array, default: () => [] }) readonly userGroupList: IUserGroup[];
  @Prop({ type: Array, default: () => [] }) readonly userGroup: string[];
  @Prop({ type: Boolean, default: true }) readonly multiple: boolean;
  @Prop({ type: Boolean, default: false }) readonly draggable: boolean;
  @Prop({ type: String }) readonly placeholder: string;
  @Prop({ type: String }) readonly emptyText: string;
  @Model('change', { type: [Array, String], default: () => [] }) userIds: string | string[];
  componentConfig: Partial<ConfigOptions> = {};
  get enableMultiTenantMode() {
    return window.enable_multi_tenant_mode ?? false;
  }
  created() {
    this.componentConfig = getUserComponentConfig();
  }
  onChange(value: string[]) {
    this.$emit('change', value);
  }

  /**
   * @description 区分人员/用户组前置icon渲染
   *
   */
  getPrefixIcon(h, userInfo) {
    let prefixIcon = h('span', { class: 'icon-monitor icon-mc-user-one no-img' });
    if (userInfo?.logo) {
      prefixIcon = h('img', {
        alt: userInfo.name,
        src: userInfo.logo,
      });
    } else if (USER_GROUP_TYPE.has(userInfo?.type)) {
      prefixIcon = h('span', { class: 'icon-monitor icon-mc-user-group no-img' });
    }
    return prefixIcon;
  }

  /**
   * @description 人员选择器下拉框列表项渲染
   *
   */
  listItemRender = (h, userInfo) => {
    const prefixIcon = this.getPrefixIcon(h, userInfo);
    return h('div', { class: 'user-selector-list-item' }, [
      h('div', { class: 'user-selector-list-prefix' }, prefixIcon),
      h('div', { class: 'user-selector-list-main' }, [
        h('span', { class: 'user-selector-list-item-name' }, userInfo.name),
      ]),
    ]);
  };

  /**
   * @description 人员选择器已选项 tag 渲染
   *
   */
  tagItemRender = (h, userInfo) => {
    const prefixIcon = this.getPrefixIcon(h, userInfo);
    return h('div', { class: 'user-selector-tag-item' }, [
      h('div', { class: 'user-selector-tag-prefix' }, prefixIcon),
      h('div', { class: 'user-selector-tag-main' }, [
        h('span', { class: 'user-selector-tag-item-name' }, userInfo.name),
      ]),
    ]);
  };

  render() {
    if (!this.componentConfig.apiBaseUrl) return undefined;
    return (
      <BkUserSelector
        class='monitor-user-selector-v2'
        apiBaseUrl={this.componentConfig.apiBaseUrl}
        draggable={this.draggable}
        emptyText={this.emptyText}
        enableMultiTenantMode={this.enableMultiTenantMode}
        modelValue={this.userIds}
        multiple={this.multiple}
        placeholder={this.placeholder}
        renderListItem={this.listItemRender}
        renderTag={this.tagItemRender}
        tenantId={this.componentConfig.tenantId}
        userGroup={this.userGroupList}
        onChange={this.onChange}
      />
    );
  }
}
