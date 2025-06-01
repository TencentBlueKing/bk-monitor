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

import BkUserSelectorOrigin from '@blueking/bk-user-selector/vue2';

import { getUserComponentConfig } from '../../common/user-display-name';

import type { IUserGroup } from './user-group';
import type { ConfigOptions } from '@blueking/bk-user-display-name';

import '@blueking/bk-user-selector/vue2/vue2.css';

interface IBkUserSelectorProps {
  apiBaseUrl?: string;
  modelValue?: string[];
  multiple?: boolean;
  draggable?: boolean;
  tenantId?: string;
  userGroup?: IUserGroup[];
  onChange?: (value: string[]) => void;
}

const BkUserSelector: (props: IBkUserSelectorProps) => JSX.Element = BkUserSelectorOrigin as any as (
  props: IBkUserSelectorProps
) => JSX.Element;

@Component({
  name: 'user-selector',
})
export default class UserSelector extends tsc<
  { userIds: string[]; userGroupList: IUserGroup[]; userGroup: string[]; multiple: boolean; draggable: boolean },
  { onChange: string[] }
> {
  @Prop({ type: Array, default: () => [] }) readonly userGroupList: IUserGroup[];
  @Prop({ type: Array, default: () => [] }) readonly userGroup: string[];
  @Prop({ type: Boolean, default: true }) readonly multiple: boolean;
  @Prop({ type: Boolean, default: false }) readonly draggable: boolean;
  @Model('change', { type: Array, default: () => [] }) userIds: string[];
  componentConfig: Partial<ConfigOptions> = {};
  created() {
    this.componentConfig = getUserComponentConfig();
  }
  onChange(value: string[]) {
    this.$emit('change', value);
  }
  render() {
    if (!this.componentConfig.apiBaseUrl) return undefined;
    return (
      <BkUserSelector
        apiBaseUrl={this.componentConfig.apiBaseUrl}
        draggable={this.draggable}
        modelValue={this.userIds}
        multiple={this.multiple}
        tenantId={this.componentConfig.tenantId}
        userGroup={this.userGroupList}
        onChange={this.onChange}
      />
    );
  }
}
