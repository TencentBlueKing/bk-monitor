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
        <div class="success-container">
          <i18n
            :path="`对该配置${textMap[type]},成功{0}${data.target_object_type === 'HOST' ? '台主机' : '个实例'},失败{1}${data.target_object_type === 'HOST' ? '台主机' : '个实例'}`"
          >
            <span class="success-total"> {{ successTotal }} </span>
            <span class="fail-total"> {{ failTotal }} </span>
          </i18n>
        </div>
      </template>
      <template #footer>
        <bk-button
          key="123"
          theme="primary"
          @click="handleGoStrategy"
        >
          {{ $t('button-策略配置') }}
        </bk-button>
        <!-- <bk-button theme="primary" v-if="false"> {{ $t('视图配置') }} </bk-button> -->
        <bk-button @click="handleClose">
          {{ $t('button-关闭') }}
        </bk-button>
      </template>
    </done>
  </div>
</template>
<script>
import Done from '../../collector-add/config-done/loading-done';

export default {
  name: 'AddDelDone',
  components: {
    Done,
  },
  props: {
    data: {
      type: Object,
      default: () => ({
        config_info: {},
        headerData: {},
        contents: [],
      }),
    },
    config: Object,
    step: {
      type: Number,
      default: 2,
    },
    type: {
      type: String,
      default: 'ADD_DEL',
    },
    hosts: {
      type: Object,
      default: () => ({}),
    },
    diffData: {
      type: Object,
      default: () => ({}),
    },
  },
  data() {
    return {
      options: {
        loading: false,
        status: true,
        title: this.$t('操作完成'),
        text: '',
      },
      textMap: {
        ROLLBACK: '增/删目标',
        ADD_DEL: '增/删目标',
        EDIT: '编辑',
      },
      isCloseOut: false,
      successTotal: 0,
      failTotal: 0,
    };
  },
  created() {
    this.successTotal = this.hosts.headerData.successNum;
    this.failTotal = this.hosts.headerData.failedNum;
  },
  methods: {
    handleClose() {
      this.$router.push({
        name: 'collect-config',
      });
    },
    handleGoStrategy() {
      this.$router.push({
        name: 'strategy-config-add',
        params: {
          baseInfo: {
            scenario: this.config.params.label,
            name: this.config.params.name,
          },
        },
      });
    },
  },
};
</script>
<style lang="scss" scoped>
.done {
  padding-top: 80px;

  .success-total {
    color: #2dcb56;
  }

  .fail-total {
    color: #ea3636;
  }

  :deep(.bk-button) {
    margin-right: 10px;
  }
}
</style>
