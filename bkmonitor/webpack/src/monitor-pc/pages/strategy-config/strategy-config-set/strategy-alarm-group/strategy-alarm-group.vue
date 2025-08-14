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
  <div class="strategy-alarm-group">
    <bk-tag-input
      :placeholder="$t('选择告警组')"
      :list="alarmGroupList"
      save-key="id"
      trigger="focus"
      display-key="name"
      search-key="name"
      :tpl="renderAlarmGroupList"
      :tag-tpl="renderAlarmGroupTag"
    />
  </div>
</template>
<script lang="tsx">
import { Component, Prop, Vue } from 'vue-property-decorator';

import type MonitorVue from '../../../../types';

@Component({
  name: 'StrategyAlarmGroup',
})
export default class StrategyAlarmGroup extends Vue<MonitorVue> {
  @Prop(Array)
  // 告警组列表
  alarmGroupList: Array<any>;

  // tag渲览函数
  renderAlarmGroupTag(node: any): Vue.VNode {
    return this.$createElement(
      'div',
      {
        class: {
          tag: true,
        },
      },
      node.name
    );
  }

  renderAlarmGroupList(node, ctx, highlightKeyword) {
    return this.$createElement(
      'div',
      {
        class: {
          'bk-selector-node': true,
          'bk-selector-member': true,
        },
      },
      [
        this.$createElement(
          'span',
          {
            class: {
              text: true,
            },
            domProps: {
              domPropsInnerHTML: `${highlightKeyword(node.name)}`,
            },
          },
          `${highlightKeyword(node.name)}`
        ),
      ]
    );
  }
}
</script>
<style lang="scss" scoped>
.tag-list {
  > li {
    height: 22px;
  }
}

.strategy-alarm-group {
  width: 100%;

  :deep(.key-node) {
    /* stylelint-disable-next-line declaration-no-important */
    background: none !important;

    /* stylelint-disable-next-line declaration-no-important */
    border: 0 !important;
  }

  .tag {
    height: 22px;
    padding: 4px 10px;
    line-height: 16px;
    text-align: center;
    background: #f0f1f5;
    border-radius: 2px;
  }
}

.bk-selector-list {
  .bk-selector-member {
    display: flex;
    align-items: center;
    padding: 0 10px;
  }
}
</style>
