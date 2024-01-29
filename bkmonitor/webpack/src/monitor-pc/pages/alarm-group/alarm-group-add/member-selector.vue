<!--
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
-->
<template>
  <div :class="['member-selector-wrap', { 'is-error': isError }]">
    <bk-user-selector
      class="bk-user-selector"
      v-model="localValue"
      :panel-width="300"
      :placeholder="$t('选择通知对象')"
      :display-tag-tips="false"
      :display-domain="false"
      :tag-tips-content="handleTabTips"
      :tag-clearable="false"
      :fast-clear="true"
      :default-alternate="() => deepClone(groupList)"
      :empty-text="$t('无匹配人员')"
      :render-list="renderUserSelectorList"
      :render-tag="renderUserSelectorTag"
      :api="bkUrl"
      @focus="handleFocus"
      @change="emitLocalValue"
      @select-user="handleSelectUser"
    />
  </div>
</template>

<script lang="ts">
import { Component, Emit, Model, Prop, Vue, Watch } from 'vue-property-decorator';
import BkUserSelector from '@blueking/user-selector';
debugger
import { deepClone } from '../../../../monitor-common/utils/utils';

@Component({
  name: 'member-selector',
  components: {
    BkUserSelector
  }
})
export default class MemberSelector extends Vue {
  @Prop({ type: Array, default: () => [] }) readonly groupList: any;
  @Model('localValueChange', { type: Array, default: () => [] }) value: string[];

  localValue: string[] = [];

  deepClone: Function = null;

  // 人员选择器api地址
  get bkUrl() {
    return `${window.site_url}rest/v2/commons/user/list_users/`;
  }

  get isError() {
    return this.$parent?.validator?.state === 'error';
  }

  @Watch('value', { immediate: true })
  handleValueChange() {
    this.localValue = this.value;
  }

  @Emit('localValueChange')
  emitLocalValue() {
    return deepClone(this.localValue);
  }

  created() {
    this.deepClone = deepClone;
  }

  // 人员选择器tag render
  renderUserSelectorTag(h, tag) {
    const groupName = this.getDefaultUsername(this.groupList, tag.username);
    const renderTag = {
      display_name: groupName || tag.user?.display_name || tag.username,
      id: tag.username,
      type: groupName ? 'group' : ''
    };
    return this.renderMemberTag(renderTag, h);
  }
  renderMemberTag(e, h) {
    return this.renderPublicCode(e, 'tag', 'text', 'avatar', h);
  }
  renderPublicCode(e, t, n, r, h) {
    const o = h;
    return o('div', {
      class: t
    }, [e.logo ? o('img', {
      class: r,
      attrs: {
        src: e.logo
      }
    }) : o('i', {
      class: 'group' === e.type ? 'icon-monitor icon-mc-user-group only-img' : 'icon-monitor icon-mc-user-one only-img'
    }), 'group' === e.type ? o('span', {
      class: n
    }, [e.display_name]) : o('span', {
      class: n
    }, [e.id, ' (', e.display_name, ')'])]);
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
      display_name: user.display_name
    };
    return this.renderMerberList(renderListItem, h);
  }
  // tag提示
  handleTabTips(val) {
    return this.getDefaultUsername(this.groupList, val) || val;
  }
  // 查找display_name
  getDefaultUsername(list, val) {
    // eslint-disable-next-line no-restricted-syntax
    for (const item of list) {
      if (item.username === val) return item.display_name;
      if (item.children?.length) return this.getDefaultUsername(item.children, val);
    }
  }

  handleFocus() {
    this.$parent?.handlerFocus?.();
  }

  @Emit('select-user')
  handleSelectUser(value) {
    return value;
  }
}
</script>

<style lang="scss" scoped>
.tag,
.bk-selector-member {
  display: flex;
}

.member-selector-wrap {
  .bk-user-selector {
    width: 100%;

    :deep(.user-selector-selected) {
      background: none;

      .tag {
        display: inline-flex;
        align-items: center;

        .only-img {
          font-size: 16px;
        }
      }
    }
  }
}

.is-error {
  :deep(.user-selector-container) {
    border-color: #ff5656;
  }
}

:deep(.bk-form-control) {
  background: #fff;
}
</style>
