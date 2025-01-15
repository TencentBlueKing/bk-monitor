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
  <div class="all-overview">
    <bk-tab
      :active.sync="active"
      type="unborder-card"
      @tab-change="handleTabChange"
    >
      <bk-tab-panel
        v-for="(panel, index) in panels"
        v-bind="panel"
        :key="index"
      />
      <div>
        <uptimecheck
          v-if="active === 'uptimecheck'"
          :alarm="alarm"
        />
        <service
          v-if="active === 'service'"
          :alarm="alarm"
        />
        <os
          v-if="active === 'os'"
          :alarm="alarm"
        />
        <process
          v-if="active === 'process'"
          :alarm="alarm"
        />
      </div>
    </bk-tab>
  </div>
</template>
<script>
import Os from './os';
import Process from './process';
import Service from './service';
import Uptimecheck from './uptimecheck';

export default {
  name: 'AllOverview',
  components: {
    Uptimecheck,
    Service,
    Os,
    Process,
  },
  props: {
    selectedIndex: Number,
    alarm: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      panels: [
        { label: this.$t('拨测监控'), name: 'uptimecheck' },
        { label: this.$t('服务监控'), name: 'service' },
        { label: this.$t('进程监控'), name: 'process' },
        { label: this.$t('主机监控'), name: 'os' },
      ],
      active: 'uptimecheck',
    };
  },
  methods: {
    handleTabChange(v) {
      const indexMap = {
        uptimecheck: 0,
        service: 1,
        process: 2,
        os: 3,
      };
      this.$emit('update:selectedIndex', indexMap[v]);
    },
  },
};
</script>
