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
  <span
    class="monitor-export"
    @click="handleExport"
  >
    <slot>{{ $t('导出') }}</slot>
  </span>
</template>
<script lang="ts">
import type { CreateElement } from 'vue';

import { Component, Emit, Vue } from 'vue-property-decorator';

@Component({ name: 'MonitorExport' })
export default class MonitorExport extends Vue {
  render(h: CreateElement) {
    return h(
      'span',
      {
        class: {
          'monitor-export': true,
        },
        on: {
          click: this.handleExport,
        },
      },
      String(this.$t('导出'))
    );
  }
  @Emit('click')
  handleExport(): Function {
    return (data: any, fileName: string) => {
      if (!data) return;
      const downlondEl = document.createElement('a');
      const blob = new Blob([JSON.stringify(data, null, 4)]);
      const fileUrl = URL.createObjectURL(blob);
      downlondEl.href = fileUrl;
      downlondEl.download = fileName || 'metric.json';
      downlondEl.style.display = 'none';
      document.body.appendChild(downlondEl);
      downlondEl.click();
      document.body.removeChild(downlondEl);
    };
  }
}
</script>

<style lang="scss" scoped>
.monitor-export {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  margin: 0 10px;
  color: #3a84ff;
  border-radius: 2px;

  &:hover {
    cursor: pointer;
  }
}
</style>
