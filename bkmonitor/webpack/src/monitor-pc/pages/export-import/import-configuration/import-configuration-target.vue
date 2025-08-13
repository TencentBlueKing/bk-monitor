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
  <article
    v-bkloading="{ isLoading: loading }"
    class="strategy-config-target"
  >
    <section
      ref="targetContainer"
      class="target-container"
    >
      <div class="target-container-lable">
        {{ $t('监控目标') }}
      </div>
      <topo-selector
        ref="topoSelector"
        class="topo-selector"
        :height="targetContainerHeight"
        :hidden-dynamic-group="false"
        :target-object-type="targetType"
        :tree-height="targetContainerHeight"
        @check-change="handleCheckedChange"
      />
    </section>
    <section class="target-footer">
      <bk-button
        class="btn"
        :disabled="!checkedData.length || !historyId"
        theme="primary"
        @click="handleSave"
      >
        {{ $t('保存') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </section>
  </article>
</template>

<script>
import { mapActions } from 'vuex';

import TopoSelector from '../../../components/ip-selector/business/topo-selector-new.vue';

export default {
  name: 'ImportConfigurationTarget',
  components: {
    TopoSelector,
  },
  props: {
    // 历史任务ID
    historyId: {
      type: [Number, String],
      default: 0,
      required: true,
    },
    // 实例类型
    targetType: {
      type: String,
      default: 'INSTANCE',
      required: true,
    },
  },
  data() {
    return {
      loading: false,
      checkedData: [],
      targetNodeType: 'TOPO',
      targetContainerHeight: 0,
    };
  },
  mounted() {
    this.targetContainerHeight = this.$refs.targetContainer.clientHeight;
  },
  methods: {
    ...mapActions('import', ['addMonitorTarget']),
    /**
     * 选择器勾选节点事件
     * @param {Array} checkedData 选中节点数据
     */
    handleCheckedChange(checkedData) {
      this.checkedData = checkedData.data;
      this.targetNodeType = checkedData.type;
    },
    /**
     * 获取统一添加监控目标请求参数
     */
    getParams() {
      // 字段名
      let field = '';
      let targetValue = this.checkedData;
      const hostTargetFieldType = {
        TOPO: 'host_topo_node',
        INSTANCE: 'ip',
        SERVICE_TEMPLATE: 'host_service_template',
        SET_TEMPLATE: 'host_set_template',
        DYNAMIC_GROUP: 'dynamic_group',
      };
      const serviceTargetFieldType = {
        TOPO: 'service_topo_node',
        SERVICE_TEMPLATE: 'service_service_template',
        SET_TEMPLATE: 'service_set_template',
      };
      if (this.targetType === 'HOST') {
        field = hostTargetFieldType[this.targetNodeType];
      } else {
        field = serviceTargetFieldType[this.targetNodeType];
      }
      if (this.targetNodeType === 'DYNAMIC_GROUP') {
        targetValue = this.checkedData.map(({ id, bk_obj_id }) => ({ bk_inst_id: id, bk_obj_id }));
      }

      return {
        import_history_id: Number(this.historyId),
        target: [
          [
            {
              field,
              method: 'eq',
              value: targetValue,
            },
          ],
        ],
      };
    },
    // 批量修改采集目标
    async handleSave() {
      const params = this.getParams();
      this.loading = true;
      const success = await this.addMonitorTarget(params).catch(() => false);
      this.loading = false;
      if (success) {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('添加成功'),
        });
        this.$router.push({ name: 'export-import' });
      }
    },
    handleCancel() {
      this.$router.back();
    },
  },
};
</script>

<style lang="scss" scoped>
@import '../../../theme/index';

.strategy-config-target {
  height: calc(100vh - 100px);
  padding: 10px 0 0 10px;
  color: $defaultFontColor;

  .select-tips {
    display: flex;
    margin: 0 0 15px 96px;

    i {
      margin-right: 6px;
      font-size: 16px;
      color: $unsetIconColor;
    }
  }

  .target-container {
    display: flex;
    height: 80%;
    margin-bottom: 20px;

    &-lable {
      margin-right: 40px;
      font-size: 14px;
    }

    :deep(.topo-selector) {
      width: calc(100% - 126px);
    }

    .topo-selector {
      flex: 1;
      margin-right: 20px;
    }
  }

  .target-footer {
    margin-left: 96px;

    .btn {
      margin-right: 8px;
    }
  }
}
</style>
