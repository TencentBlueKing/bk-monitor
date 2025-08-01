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
import { Component, Emit, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import BkUserSelector from '@blueking/user-selector';
import { deepClone } from 'monitor-common/utils/utils';

import './user-selector.scss';

export interface IGroupListItem {
  display_name: string;
  id: string;
  type: string;
  children: {
    display_name: string;
    id: string;
    members?: { display_name?: string; id?: string }[];
    type: string;
    username: string;
  }[];
}

interface IEvents {
  onDraggableChange?: boolean;
  onChange?: {
    // 用户组
    id: string; // 用户id
    name: string; // 用户名
    type: 'group' | 'user';
  }[];
}

interface IProps {
  color?: string;
  groupList?: IGroupListItem[];
  hasDrag?: boolean;
  value?: string[];
}

@Component
export default class UserSelector extends tsc<IProps, IEvents> {
  @Prop({ type: Array, default: () => [] }) readonly groupList: IGroupListItem[];
  @Prop({ default: () => [], type: Array }) value: string[];
  @Prop({ default: false, type: Boolean }) hasDrag: boolean;
  @Prop({ default: '#ff5656', type: String }) color: string;

  @Ref('userSelector') userSelectorRef: BkUserSelector;

  localValue = [];
  isFocus = false;
  focusHeight = 0;

  get bkUrl() {
    return `${window.site_url}rest/v2/commons/user/list_users/`;
  }
  created() {
    this.localValue = [...this.value];
  }

  handleFocus() {
    this.isFocus = true;
    this.$nextTick(() => {
      this.focusHeight = this.userSelectorRef.$el.querySelector('.user-selector-container').clientHeight + 2;
    });
  }

  handleBlur() {
    this.isFocus = false;
    this.focusHeight = 0;
  }

  @Emit('change')
  async handleChange() {
    await this.$nextTick(() => {
      this.focusHeight = this.userSelectorRef.$el.querySelector('.user-selector-container').clientHeight + 2;
    });
    const tempPromise = () =>
      new Promise(resolve => {
        setTimeout(() => {
          resolve(true);
        }, 300);
      });
    /* 回车时人员选择器的详细数据有延迟故等待50ms */
    await tempPromise();
    const allMap = new Map();
    this.userSelectorRef.currentUsers.forEach(item => {
      allMap.set(item.username, { id: item.username, name: item.display_name, type: 'user' });
    });
    this.groupList.forEach(item => {
      item.children.forEach(child => {
        allMap.set(child.id, { id: child.id, name: child.display_name, type: 'group' });
      });
    });
    return this.localValue.map(id => allMap.get(id));
  }

  @Emit('draggableChange')
  handleDraggableChange(v: boolean) {
    return v;
  }

  handleClear() {
    this.handleChange();
  }

  render() {
    return (
      <div class='duty-user-selector-component'>
        <div
          style={{
            borderLeft: `4px solid ${this.color}`,
            height: this.focusHeight ? `${this.focusHeight}px` : '100%',
          }}
          class={['left-wrap', { focus: this.isFocus }]}
          onMouseenter={() => this.handleDraggableChange(true)}
          onMouseleave={() => this.handleDraggableChange(false)}
        >
          {this.hasDrag && <span class='icon-monitor icon-mc-tuozhuai' />}
        </div>
        <BkUserSelector
          ref='userSelector'
          class='bk-user-selector'
          v-model={this.localValue}
          api={this.bkUrl}
          defaultAlternate={() => deepClone(this.groupList)}
          displayDomain={false}
          displayTagTips={false}
          emptyText={window.i18n.t('无匹配人员')}
          fastClear={true}
          panelWidth={300}
          placeholder={window.i18n.t('选择通知对象')}
          renderList={this.renderUserSelectorList}
          renderTag={this.renderUserSelectorTag}
          tagClearable={false}
          tagTipsContent={this.handleTabTips}
          onBlur={this.handleBlur}
          onChange={this.handleChange}
          onClear={this.handleClear}
          onFocus={this.handleFocus}
        />
      </div>
    );
  }

  /* 以下为人员选择器tag样式 */
  renderUserSelectorTag(h, tag) {
    const groupName = this.getDefaultUsername(this.groupList, tag.username);
    const renderTag = {
      display_name: groupName || tag.user?.display_name || tag.username,
      id: tag.username,
      type: groupName ? 'group' : '',
    };
    return this.renderPublicCode(h, renderTag, 'tag', 'text', 'avatar');
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
    return this.renderPublicCode(h, renderListItem, 'user-sort-list-component-bk-selector-member', 'text', 'avatar');
  }
  // tag提示
  handleTabTips(val) {
    return this.getDefaultUsername(this.groupList, val) || val;
  }
  getDefaultUsername(list, val) {
    for (const item of list) {
      if (item.username === val) return item.display_name;
      if (item.children?.length) return this.getDefaultUsername(item.children, val);
    }
  }
  renderPublicCode(h, node, parentClass, textClass, avatarClass) {
    return h('div', { class: parentClass }, [
      node.logo
        ? h('img', {
            class: avatarClass,
            attrs: { src: node.logo },
          })
        : h('i', {
            class:
              node.type === 'group'
                ? 'icon-monitor icon-mc-user-group only-img'
                : 'icon-monitor icon-mc-user-one only-img',
          }),
      h('span', { class: textClass }, node.type === 'group' ? node.display_name : `${node.id} (${node.display_name})`),
    ]);
  }
}
