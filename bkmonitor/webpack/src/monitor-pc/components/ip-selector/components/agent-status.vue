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
  <ul class="agent-status">
    <li
      v-for="(item, index) in data"
      :key="index"
    >
      <div v-if="type === 0">
        <span :class="['status-font', `status-${String(item.status).toLocaleLowerCase()}`]">
          {{ item.count }}
        </span>
        <span>{{ item.display || '--' }}</span>
        <span
          v-if="index !== data.length - 1"
          class="separator"
          >,
        </span>
      </div>
      <div v-else-if="type === 1">
        <span :class="['status-mark', `status-${String(item.status).toLocaleLowerCase()}`]" />
        <span>{{ item.display || '--' }}</span>
      </div>
      <div v-else>
        <span class="status-merit">
          <span> {{ $t('异常') }}:</span>
          <span :class="['status-count', !!item.errorCount ? 'status-terminated' : 'status-2']">
            {{ item.errorCount || 0 }}</span
          >
        </span>
        <span class="status-merit">
          <span>{{ $t('总数') }}:</span>
          <span class="status-total">{{ item.count || 0 }}</span>
        </span>
      </div>
    </li>
  </ul>
</template>
<script lang="ts">
import { Component, Prop, Vue } from 'vue-property-decorator';

import type { IAgentStatusData } from '../types/selector-type';

@Component({ name: 'agent-status' })
export default class AgentStatus extends Vue {
  @Prop({ default: 0, type: Number }) private readonly type!: 0 | 1 | 2;
  @Prop({ default: () => [], type: Array }) private readonly data!: IAgentStatusData[];
}
</script>
<style lang="scss" scoped>
@mixin normal {
  color: #3fc06d;
  background: #86e7a9;
  border-color: #3fc06d;
}

@mixin error {
  color: #ea3636;
  background: #fd9c9c;
  border-color: #ea3636;
}

@mixin unknown {
  color: #c4c6cc;
  background: #f0f1f5;
  border-color: #c4c6cc;
}

.separator {
  padding: 0 2px;
}

.agent-status {
  display: flex;
  align-items: center;
}

.status-mark {
  display: inline-block;
  width: 8px;
  height: 8px;
  margin-right: 8px;
  border: 1px solid;
  border-radius: 4px;
}

.status-font {
  font-weight: 700;

  /* stylelint-disable-next-line declaration-no-important */
  background: unset !important;
}

.status-count {
  /* stylelint-disable-next-line declaration-no-important */
  background: unset !important;
  // &::after {
  //   content: '/';
  //   color: #63656e;
  // }
}

.status-merit {
  display: inline-block;
  min-width: 48px;
  padding: 2px;

  .status-total {
    color: #3a84ff;
  }

  &:hover {
    background: rgb(234, 235, 239);
  }
}

.status-running,
.status-1 {
  @include normal;
}

.status-terminated,
.status-3 {
  @include error;
}

.status-unknown,
.status-2 {
  @include unknown;
}
</style>
