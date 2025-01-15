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
  <div class="done">
    <done :options="options">
      <template #text>
        <div
          v-if="nodeType === 'INSTANCE'"
          class="fix-same-code"
        >
          <span class="text fix-same-code">
            {{ $t('共成功{type}了', { type: options.type }) }}
            <span class="num success">{{ options.successTotal }}</span> {{ suffixName }}</span
          >
          <span class="fix-same-code text"
            >,{{ $t('失败') }} <span class="num fail fix-same-code">{{ options.failTotal }}</span>
            {{ suffixName }}</span
          >
        </div>
        <div
          v-else
          class="fix-same-code"
        >
          <span class="text fix-same-code">
            {{ $t('共成功{type}了', { type: options.type }) }} <span class="num">{{ hosts.contents.length }}</span>
            {{ $t('个节点内的') }} <span class="num success fix-same-code">{{ options.successTotal }}</span>
            {{ suffixName }}</span
          >
          <span class="fix-same-code text"
            >,{{ $t('失败') }} <span class="num fail">{{ options.failTotal }}</span> {{ suffixName }}</span
          >
        </div>
      </template>
      <template #footer>
        <bk-button
          v-if="type !== 'STARTED'"
          theme="primary"
          @click="handleGoStrategy"
        >
          {{ $t('button-策略配置') }}
        </bk-button>
        <bk-button
          v-if="false"
          theme="primary"
        >
          {{ $t('视图配置') }}
        </bk-button>
        <bk-button @click="close">
          {{ $t('button-关闭') }}
        </bk-button>
      </template>
    </done>
  </div>
</template>
<script>
import Done from '../../collector-add/config-done/loading-done';

export default {
  name: 'StopDone',
  components: {
    Done,
  },
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    hosts: {
      type: Object,
      default: () => ({}),
    },
    type: {
      type: String,
      default: 'STOPPED',
    },
  },
  data() {
    return {
      options: {
        loading: false,
        status: true,
        title: this.$t('配置已停用'),
        text: '',
        type: '',
        successTotal: 0,
        failTotal: 0,
      },
      nodeType: 'INSTANCE',
    };
  },
  computed: {
    suffixName() {
      return this.data.objectTypeEn === 'HOST' ? this.$t('台主机') : this.$t('个实例');
    },
  },
  created() {
    const type = {
      STARTED: this.$t('停用'),
      STOPPED: this.$t('启用'),
      CREATE: this.$t('创建'),
      ROLLBACK: this.$t('回滚'),
      UPGRADE: this.$t('升级'),
    };
    this.options.type = type[this.type];
    this.options.title = `${this.$t('配置已')}${this.options.type}`;
    this.nodeType = this.data.nodeType;
    this.options.failTotal = this.hosts.headerData.failedNum;
    this.options.successTotal = this.hosts.headerData.successNum;
  },
  methods: {
    close() {
      this.$router.back();
    },
    handleGoStrategy() {
      this.$router.push({
        name: 'strategy-config-add',
        params: {
          baseInfo: {
            scenario: this.data.serviceLabel,
            name: this.data.name,
          },
        },
      });
    },
  },
};
</script>
<style lang="scss" scoped>
.done {
  padding-top: 84px;

  :deep(.bk-button) {
    margin-right: 10px;
  }

  .text {
    color: #63656e;
  }

  .num {
    color: #3a84ff;
  }

  .success {
    color: #2dcb56;
  }

  .fail {
    color: #ea3636;
  }
}
</style>
