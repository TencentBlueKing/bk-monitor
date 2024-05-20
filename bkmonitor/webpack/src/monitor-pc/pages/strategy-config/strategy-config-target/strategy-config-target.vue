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
  <div
    v-bkloading="{ isLoading: loading }"
    class="strategy-config-target"
  >
    <!-- tips -->
    <!-- <div class="select-tips"><i class="icon-monitor icon-tips"></i>{{ $t('动态：只能选择节点，策略目标按节点动态变更。静态：只能选择主机IP，采集目标不会变更。') }}</div> -->
    <!-- IP选择器 -->
    <div
      ref="targetContainer"
      class="target-container"
    >
      <!-- <topo-selector
        v-if="isGetDetail"
        :max-width="850"
        ref="topoSelector"
        :mode="selector.mode"
        :type="selector.type"
        :is-instance="selector.isInstance"
        :tab-disabled="selector.tabDisabled"
        :default-active="selector.defaultActive"
        :checked-data="selector.checkedData"
        @type-change="handleTypeChange"
        @checked-change="handleCheckedChange"
        @loading-change="handleLoadingChange"
        @has-checked-data="handleChecked"
        @table-data-change="handleAngChange">
      </topo-selector> -->
      <topo-selector
        v-if="isGetDetail"
        ref="topoSelector"
        :tree-height="targetContainerHeight"
        :height="targetContainerHeight"
        :target-node-type="selector.targetNodeType"
        :target-object-type="selector.targetObjectType"
        :checked-data="selector.checkedData"
        :preview-width="230"
        :hidden-template="hiddenTemplate"
        @check-change="handleChecked"
      />
    </div>
    <div class="target-footer">
      <bk-button
        class="btn"
        theme="primary"
        :disabled="canSaveEmpty ? false : !checked.length"
        @click="handleSaveData"
      >
        {{ $t('保存') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </div>
  </div>
</template>

<script>
import { bulkEditStrategy, getTargetDetail } from 'monitor-api/modules/strategies';
import { createNamespacedHelpers } from 'vuex';

import TopoSelector from '../../../components/ip-selector/business/topo-selector-new';

const { mapGetters } = createNamespacedHelpers('strategy-config');
export default {
  name: 'StrategyConfigTarget',
  components: {
    TopoSelector,
  },
  props: {
    targetList: {
      type: Array,
      default() {
        return [];
      },
    },
    setConfig: {
      type: Object,
      default() {
        return {
          bizId: '',
          objectType: '',
          strategyId: 0,
        };
      },
    },
    // 是否允许保存空的目标
    canSaveEmpty: {
      type: Boolean,
      default: false,
    },
    hiddenTemplate: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      loading: false,
      isGetDetail: false,
      //   targetNodeTypeMap: {
      //     'static-ip': 'INSTANCE',
      //     'static-topo': 'INSTANCE',
      //     'dynamic-topo': 'TOPO',
      //     'dynamic-group': 'TOPO'
      //   },
      selector: {
        strategyId: null,
        bizId: 2,
        mode: 'add',
        targetObjectType: 'HOST',
        targetNodeType: 'INSTANCE',
        checkedData: [],
      },
      saveData: {
        targetNodes: [],
        targetNodeType: null,
      },
      isBack: false,
      checked: [],
      needCheck: true,
      changeNum: 0,
      targetContainerHeight: 560,
    };
  },
  computed: {
    ...mapGetters(['strategyParams']),
  },
  created() {
    this.handleConfig(this.setConfig);
    this.$nextTick(() => {
      this.targetContainerHeight = this.$refs.targetContainer.clientHeight || 560;
    });
  },
  methods: {
    // handleTypeChange(type) {
    //   this.selectorType = type
    //   this.selector.targetNodeType = this.targetNodeTypeMap[type]
    // },
    handleChecked(checkedData) {
      const { type, data = [] } = checkedData;
      this.checked = data;
      this.selector.targetNodeType = type;
    },
    // 创建/修改策略配置
    async handleSaveData() {
      if (this.setConfig.strategyId) {
        this.handleSaveFromList();
      } else {
        this.handleSaveFormSet();
      }
    },
    // 反馈选中目标的描述
    handleSetTargetDesc(params) {
      let message = '';
      let subMessage = '';

      const { target_nodes = [], target_node_type = 'TOPO', target_object_type } = params;
      if (!target_nodes.length) return { message, subMessage };

      if (['TOPO', 'SERVICE_TEMPLATE', 'SET_TEMPLATE'].includes(target_node_type)) {
        const count = target_nodes.reduce(
          (pre, item) => Array.from(new Set([...pre, ...(item.all_host || [])])),
          []
        ).length;
        const textMap = {
          TOPO: '{0}个节点',
          SERVICE_TEMPLATE: '{0}个服务模板',
          SET_TEMPLATE: '{0}个集群模板',
        };
        message = this.$t(textMap[target_node_type], [target_nodes.length]);
        // 暂时隐藏模板统计信息

        target_node_type === 'TOPO' &&
          (subMessage = `（ ${this.$t(target_object_type === 'SERVICE' ? '{0}个实例' : '{0}台主机', [count])} ）`);
      } else {
        message = this.$t('{0}台主机', [target_nodes.length]);
      }
      return {
        message,
        subMessage,
      };
    },
    // 来自编辑新增页面的保持
    handleSaveFormSet() {
      const params = this.getParams();
      this.$emit('message-change', this.handleSetTargetDesc(params));
      this.$emit('target-type-change', this.selector.targetNodeType);
      this.$emit('target-change', params.target_nodes);
    },
    // 来自列表增删目标
    async handleSaveFromList() {
      this.loading = true;
      const params = this.getParams();
      let field = '';
      // 判断是主机还是服务，静态还是动态
      const hostTargetFieldType = {
        TOPO: 'host_topo_node',
        INSTANCE: 'ip',
        SERVICE_TEMPLATE: 'host_service_template',
        SET_TEMPLATE: 'host_set_template',
      };
      const serviceTargetFieldType = {
        TOPO: 'service_topo_node',
        SERVICE_TEMPLATE: 'service_service_template',
        SET_TEMPLATE: 'service_set_template',
      };
      if (this.selector.targetObjectType === 'HOST') {
        field = hostTargetFieldType[params.target_node_type];
      } else {
        field = serviceTargetFieldType[params.target_node_type];
      }
      const targetValues = this.handleCheckedData(params.target_node_type, params.target_nodes);
      const target = targetValues.length
        ? [
            [
              {
                field,
                method: 'eq',
                value: targetValues,
              },
            ],
          ]
        : [];
      const success = await bulkEditStrategy({ id_list: [params.id], edit_data: { target } }).catch(() => false);
      success && this.$bkMessage({ theme: 'success', message: this.$t('修改成功') });
      this.$emit('save-change', true);
      this.handleCancel();
      this.loading = false;
    },
    // 获取策略详情数据
    async getStrategyConfig(id) {
      const config = {};
      const data = await getTargetDetail({ strategy_ids: [id] }).catch(() => []);
      config.bizId = this.$store.getters.bizId;
      // 动态拓扑可以从bk_target_detail字段获取，该字段含有名称，不用前段拼接
      config.targetNodes = data[id].target_detail;
      config.objectType = data[id].instance_type;
      config.targetNodeType = data[id].node_type;
      this.loading = false;
      return config;
    },
    // IP选择器派发的loading状态
    handleLoadingChange(status) {
      this.loading = status;
    },
    // 初始化
    async handleConfig(params) {
      this.loading = true;
      this.isGetDetail = false;
      const { selector } = this;
      if (+params.strategyId > 0) {
        selector.mode = 'edit';
        selector.strategyId = params.strategyId;
        const strategyConfig = await this.getStrategyConfig(params.strategyId);
        if (params.objectType === strategyConfig.objectType) {
          selector.targetNodeType = strategyConfig.targetNodeType;
          selector.targetNodes = strategyConfig.targetNodes;
          this.checked = strategyConfig.targetNodes || [];
        }
        this.isGetDetail = true;
      } else {
        this.isGetDetail = true;
        selector.mode = this.targetList.length ? 'edit' : 'add';
        selector.targetNodeType = params.targetType || (params.objectType === 'SERVICE' ? 'TOPO' : 'INSTANCE');
        selector.targetNodes = this.targetList;
        this.checked = this.targetList;
      }
      selector.targetObjectType = params.objectType || 'HOST';
      selector.checkedData = selector.targetNodes || [];
      this.loading = false;
    },
    // 获取要保存的数据
    getParams() {
      const { selector } = this;
      const { saveData } = this;
      // 转换成后台需要的类型
      // getCheckedData 获取IP选择器右边的数据
      const { type, data } = this.$refs.topoSelector.getCheckedData();
      saveData.targetNodes = data;

      // 编辑态下如果目标节点为空，则取默认type
      saveData.targetNodeType =
        this.selector.mode === 'edit' && !saveData.targetNodes.length ? this.selector.targetNodeType : type;

      const params = {
        id: selector.strategyId,
        bk_biz_id: selector.bizId,
        target_object_type: selector.targetObjectType,
        target_node_type: saveData.targetNodeType,
        target_nodes: saveData.targetNodes,
      };
      return params;
    },
    // // 选择框状态改变触发的事件
    // handleCheckedChange(checkedData) {
    //   const { selector } = this
    //   // const type = selector.type
    //   if (['static-ip', 'static-topo'].includes(this.selectorType) && checkedData.length) {
    //     // 如果是 'static-ip'，'static-topo' 类型，且有选中则禁用动态 tab
    //     selector.tabDisabled = 1
    //   } else if (this.selectorType === 'dynamic-topo' && checkedData.length) {
    //     // 如果是 'dynamic-topo' 类型，且有选中则禁用静态 tab
    //     selector.tabDisabled = 0
    //   } else if (!selector.isInstance && !checkedData.length) {
    //     // 如果采集对象不是服务，且没有选中则不禁用 tab
    //     selector.tabDisabled = -1
    //   }
    // },
    // 分静态和动态拓扑
    handleCheckedData(type, data) {
      const checkedData = [];
      if (type === 'INSTANCE') {
        data.forEach(item => {
          checkedData.push({
            bk_cloud_id: item.bk_cloud_id,
            ip: item.ip,
            bk_supplier_id: item.bk_supplier_id,
          });
        });
      } else {
        data.forEach(({ bk_obj_id, bk_inst_id }) => {
          checkedData.push({
            bk_obj_id,
            bk_inst_id,
          });
        });
      }
      return checkedData;
    },
    handleAngChange() {
      this.changeNum += 1;
    },
    handleCancel() {
      this.$emit('cancel', false);
    },
  },
};
</script>

<style lang="scss" scoped>
.strategy-config-target {
  color: #63656e;

  .select-tips {
    display: flex;
    margin: 15px 0;

    i {
      margin-right: 6px;
      font-size: 16px;
      color: #979ba5;
    }
  }

  .target-container {
    display: flex;
    height: 560px;
    margin-top: 15px;

    &-lable {
      margin-right: 40px;
      font-size: 14px;
    }
  }

  .target-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    height: 52px;

    .btn {
      margin-right: 8px;
    }
  }

  :deep(.ip-select-left) {
    .left-content-wrap {
      height: calc(var(--height) - 135px);
    }
  }

  :deep(.bk-big-tree) {
    height: 310px;
    overflow: auto;
  }
}
</style>
