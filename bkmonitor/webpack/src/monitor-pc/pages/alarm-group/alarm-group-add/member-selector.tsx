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
import { Component, Emit, Model, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import BkUserSelector from '@blueking/user-selector';
import { deepClone } from 'monitor-common/utils/utils';

import './member-selector.scss';

interface MemberSelectorProps {
  groupList?: any[];
  error?: false;
  value?: string[];
}

interface MemberSelectorEvents {
  onFocus: () => void;
}
@Component({
  name: 'member-selector',
  components: {
    BkUserSelector,
  },
})
export default class MemberSelector extends tsc<MemberSelectorProps, MemberSelectorEvents> {
  @Prop({ type: Array, default: () => [] }) readonly groupList: any;
  @Prop({ type: Boolean, default: false }) readonly error: boolean;
  @Model('localValueChange', { type: Array, default: () => [] }) value: string[];

  localValue: string[] = [];

  // 人员选择器api地址
  get bkUrl() {
    return `${window.site_url}rest/v2/commons/user/list_users/`;
  }

  @Watch('value', { immediate: true })
  handleValueChange() {
    this.localValue = this.value;
  }

  @Emit('localValueChange')
  emitLocalValue() {
    return deepClone(this.localValue);
  }

  // 人员选择器tag render
  renderUserSelectorTag(h, tag) {
    const groupName = this.getDefaultUsername(this.groupList, tag.username);
    const renderTag = {
      display_name: groupName || tag.user?.display_name || tag.username,
      id: tag.username,
      type: groupName ? 'group' : '',
    };
    return this.renderMemberTag(renderTag, h);
  }
  renderMemberTag(e, h) {
    return this.renderPublicCode(e, 'tag', 'text', 'avatar', h);
  }
  renderPublicCode(e, t, n, r, h) {
    const o = h;
    return o(
      'div',
      {
        class: t,
      },
      [
        e.logo
          ? o('img', {
              class: r,
              attrs: {
                src: e.logo,
              },
            })
          : o('i', {
              class:
                'group' === e.type
                  ? 'icon-monitor icon-mc-user-group only-img'
                  : 'icon-monitor icon-mc-user-one only-img',
            }),
        'group' === e.type
          ? o(
              'span',
              {
                class: n,
              },
              [e.display_name]
            )
          : o(
              'span',
              {
                class: n,
              },
              [e.id, ' (', e.display_name, ')']
            ),
      ]
    );
  }
  renderMerberList(e, h) {
    return this.renderPublicCode(e, 'bk-selector-node bk-selector-member only-notice', 'text', 'avatar', h);
  }
  // 人员选择器list render
  renderUserSelectorList(h, item) {
    const { user } = item;
    const renderListItem = {
      type: user.type,
      index: user.index,
      id: user.username,
      display_name: user.display_name,
    };
    return this.renderMerberList(renderListItem, h);
  }
  // tag提示
  handleTabTips(val) {
    return this.getDefaultUsername(this.groupList, val) || val;
  }
  // 查找display_name
  getDefaultUsername(list, val) {
    for (const item of list) {
      if (item.username === val) return item.display_name;
      if (item.children?.length) return this.getDefaultUsername(item.children, val);
    }
  }

  handleFocus() {
    this.$emit('focus');
  }

  @Emit('select-user')
  handleSelectUser(value) {
    return value;
  }

  render() {
    return (
      <div class={['member-selector-wrap', { 'is-error': this.error }]}>
        <bk-user-selector
          class='bk-user-selector'
          v-model={this.localValue}
          api={this.bkUrl}
          default-alternate={() => deepClone(this.groupList)}
          display-domain={false}
          display-tag-tips={false}
          empty-text={this.$t('无匹配人员')}
          fast-clear={true}
          panel-width={300}
          placeholder={this.$t('选择通知对象')}
          render-list={this.renderUserSelectorList}
          render-tag={this.renderUserSelectorTag}
          tag-clearable={false}
          tag-tips-content={this.handleTabTips}
          on-select-user={this.handleSelectUser}
          onChange={this.emitLocalValue}
          onFocus={this.handleFocus}
        />
      </div>
    );
  }
}
