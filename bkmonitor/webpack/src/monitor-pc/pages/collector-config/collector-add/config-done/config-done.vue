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
        <div v-if="isTencentCloudPlugin">
          {{ $tc('已成功下发采集配置') }}
        </div>
        <div v-else-if="nodeType === 'INSTANCE'">
          <span class="text">
            <i18n :path="`共成功{0}了{1}${suffixName}`">
              {{ $t(options.type) }}
              <span class="num success">{{ options.successTotal }}</span>
            </i18n>
          </span>
          <span class="text">
            ,
            <i18n :path="`失败{0}${suffixName}`">
              <span class="num fail">{{ options.failTotal }}</span>
            </i18n>
          </span>
        </div>
        <div v-else>
          <span class="text">
            <i18n :path="`共成功{0}了{1}个节点内的{2}${suffixName}`">
              {{ $t(options.type) }}
              <span class="num">{{ hosts.contents.length }}</span>
              <span class="num success">{{ options.successTotal }}</span>
            </i18n>
          </span>
          <span class="text">
            ,
            <i18n :path="`失败{0}${suffixName}`">
              <span class="num fail">{{ options.failTotal }}</span>
            </i18n>
          </span>
        </div>
      </template>
      <template #footer>
        <bk-button
          v-if="config.data && config.data.id"
          theme="primary"
          @click="handleGoConfigView"
        >
          {{ $t('可视化') }}
        </bk-button>
        <bk-button
          v-authority="{ active: !authority.STRATEGY_VIEW_AUTH }"
          theme="primary"
          @click="
            authority.STRATEGY_VIEW_AUTH
              ? handleGoStrategy()
              : handleShowAuthorityDetail(collectAuth.STRATEGY_VIEW_AUTH)
          "
        >
          {{ $t('button-策略配置') }}
        </bk-button>
        <!-- <bk-button theme="primary" v-if="false"> {{ $t('视图配置') }} </bk-button> -->
        <bk-button @click="close">
          {{ $t('button-关闭') }}
        </bk-button>
      </template>
    </done>
  </div>
</template>
<script>
import Done from './loading-done';

export default {
  name: 'StopDone',
  components: {
    Done,
  },
  inject: ['authority', 'handleShowAuthorityDetail', 'collectAuth'],
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    hosts: {
      type: Object,
      default: () => ({
        config_info: {},
        contents: [],
        headerData: {},
      }),
    },
    type: {
      type: String,
      default: 'ADD',
    },
    config: {
      type: Object,
      default() {
        return {};
      },
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
      return this.hosts.config_info.target_object_type === 'HOST' ? '台主机' : '个实例';
    },
    // 是否是腾讯云插件
    isTencentCloudPlugin() {
      return this.config.set.data.plugin.type === 'K8S';
    },
  },
  created() {
    const type = {
      STOPPED: '启用',
      STARTED: '停用',
      UPGRADE: '升级',
      CREATE: '新增',
      ADD: '新增',
      EDIT: '编辑',
      ROLLBACK: '回滚',
    };
    this.options.type = type[this.type];
    this.options.title = this.$t(`配置已${type[this.type]}`);
    if (this.isTencentCloudPlugin) return;
    this.nodeType = this.data.nodeType;
    this.options.successTotal = this.hosts.headerData.successNum;
    this.options.failTotal = this.hosts.headerData.failedNum;
  },
  methods: {
    close() {
      // this.$router.back()
      this.$router.push({
        name: 'collect-config',
      });
    },
    handleGoStrategy() {
      const setData = this.config.set.data;
      this.$router.push({
        name: 'strategy-config-add',
        params: {
          baseInfo: {
            scenario: setData.objectId,
            name: setData.name,
          },
        },
      });
    },
    // 点击检查视图跳转
    handleGoConfigView() {
      if (this.config.data.id) {
        this.$router.push({
          name: 'collect-config-view',
          params: {
            id: this.config.data.id,
          },
          query: {
            name: this.config.set.data.name,
          },
        });
      }
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
