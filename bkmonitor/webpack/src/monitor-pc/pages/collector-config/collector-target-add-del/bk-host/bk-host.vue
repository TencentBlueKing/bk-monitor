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
    v-if="initConfig"
    class="hosts"
  >
    <div style="margin-bottom: 10px">
      {{ $t('设备IP列表') }}
    </div>
    <bk-tag-input
      v-if="data.collect_type === 'SNMP'"
      v-model="snmpTargets"
      style="margin-bottom: 20px"
      :allow-auto-match="true"
      :allow-create="true"
      :has-delete-icon="true"
      :placeholder="$t('输入采集目标主机')"
    />
    <div
      v-else
      ref="topoSelectorWrapper"
      class="topo-selector-wrapper"
    >
      <monitor-ip-selector
        v-if="ipSelectorPanels.length && topoSelectorHeight > 10"
        :style="{ height: topoSelectorHeight + 'px' }"
        :class="countInstanceType === 'service_instance' ? 'service-instance-selector' : ''"
        :count-instance-type="countInstanceType"
        :enable-origin-data="true"
        :node-table-custom-column-list="serviceInstanceColumnList"
        :original-value="originValue"
        :panel-list="ipSelectorPanels"
        :service-template-table-custom-column-list="serviceInstanceColumnList"
        :set-template-table-custom-column-list="serviceInstanceColumnList"
        :show-view-diff="true"
        :value="ipCheckValue"
        @change="handleIpChange"
        @targetTypeChange="handleTargetTypeChange"
      />
      <!-- <topo-selector
        :tree-height="topoSelectorHeight"
        :height="topoSelectorHeight"
        preview-width="25%"
        :preview-range="[150, 800]"
        left-panel-width="30%"
        :target-node-type="selector.targetNodeType"
        :target-object-type="selector.targetObjectType"
        :checked-data="selector.checkedData"
        ref="topoSelector"
      >
      </topo-selector> -->
    </div>
    <div
      v-if="config.supportRemote"
      style="margin-bottom: 10px"
    >
      {{ $t('采集器主机') }}
    </div>
    <div
      v-if="config.supportRemote"
      class="select-private-host"
    >
      <div
        class="left"
        @click="handleShow"
      >
        <span
          v-if="remoteHost.ip"
          class="ip"
          >{{ remoteHost.ip }}</span
        >
        <span v-else> {{ $t('添加采集插件运行主机') }} </span>
        <!-- <span style="color: #3A84FF; cursor: pointer;" @click="handleShow">使用选择器</span> -->
      </div>
      <div class="right">
        <bk-checkbox
          v-model="remoteHost.isCollectingOnly"
          :disabled="!remoteHost.ip"
        >
          {{ $t('采集专有主机') }}
          <span
            v-bk-tooltips.top="
              $t('专有采集主机 使用整个服务器的50%的资源,其他情况都只是使用10%的资源并且不超过单CPU资源.')
            "
            class="icon-monitor icon-tips"
          />
        </bk-checkbox>
      </div>
    </div>
    <div class="footer">
      <bk-button
        :loading="checkPluginLoading"
        theme="primary"
        @click.stop="handleStart"
      >
        {{ $t('开始下发') }}
      </bk-button>
      <bk-button @click="handleCancel">
        {{ $t('取消') }}
      </bk-button>
    </div>
    <select-host
      :conf.sync="conf"
      :filter="searchFn"
      :get-host="getHost"
      @confirm="handleSelect"
    />
  </div>
</template>
<script>
// import TopoSelector from '../../../../components/ip-selector/business/topo-selector-new';
import { checkPluginVersion, saveCollectConfig } from 'monitor-api/modules/collecting';
import { getNodesByTemplate, hostAgentStatus } from 'monitor-api/modules/commons';
import { deepClone } from 'monitor-common/utils';

import MonitorIpSelector from '../../../../components/monitor-ip-selector/monitor-ip-selector';
import { transformMonitorToValue, transformValueToMonitor } from '../../../../components/monitor-ip-selector/utils';
import SelectHost from '../../../plugin-manager/plugin-instance/set-steps/components/select-host';

export default {
  name: 'BkHost',
  components: {
    SelectHost,
    MonitorIpSelector,
    // TopoSelector
  },
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    pageLoading: Boolean,
    step: {
      type: Number,
      default: 0,
    },
    diffData: {
      type: Object,
      default: () => ({}),
    },
    config: {
      type: Object,
      default: () => {},
    },
  },
  data() {
    return {
      initConfig: false,
      host: [],
      conf: {
        isShow: false,
      },
      remoteHost: {
        ip: '',
        bkSupplierId: 0,
        isCollectingOnly: false,
      },
      configDetail: {},
      selector: {
        mode: 'edit',
        targetNodeType: 'INSTANCE',
        targetObjectType: 'HOST',
        checkedData: [],
      },
      agentStatusMap: {
        normal: 'Agent 正常',
        abnormal: 'Agent 异常',
        not_exist: 'Agent 未安装',
      },
      isNoHost: false,
      nodesMap: new Map(),
      loading: false,
      snmpTargets: [],
      topoSelectorHeight: 0,
      checkPluginLoading: false,
      ipCheckValue: {},
      ipSelectorPanels: [],
      ipTargetType: 'TOPO',
      originValue: undefined,
      countInstanceType: 'host',
    };
  },
  computed: {
    dynamicTopoCountLabel() {
      return this.config.set.data.objectType === 'HOST' ? this.$t('当前主机数') : this.$t('当前实例数');
    },
    isSnmp() {
      return this.config.params.collect_type === 'SNMP';
    },
    serviceInstanceColumnList() {
      if (this.countInstanceType === 'service_instance') {
        return [
          {
            renderHead: h => h('span', this.$t('服务实例数')),
            renderCell: (h, row) => h('span', row.node.count || '--'),
          },
        ];
      }
      return undefined;
    },
  },
  watch: {
    config: {
      handler(v) {
        if (v.params.remote_collecting_host) {
          this.remoteHost.ip = v.params.remote_collecting_host.ip;
          this.remoteHost.bkCloudId = v.params.remote_collecting_host.bk_cloud_id;
          this.remoteHost.bkSupplierId = v.params.remote_collecting_host.bk_supplier_id;
          this.remoteHost.isCollectingOnly = v.params.remote_collecting_host.is_collecting_only;
          this.remoteHost.bk_host_id = v.params.remote_collecting_host.bk_host_id;
        } else {
          this.remoteHost.isCollectingOnly = true;
        }
        this.handleConfig(v);
        this.initConfig = true;
      },
      deep: true,
    },
  },
  methods: {
    // handleLoadingChange(status) {
    //   this.$emit('update:pageLoading', status)
    // },
    handleShow() {
      this.conf.isShow = true;
    },
    // handleIpChangeType(v) {
    //   this.selectorType = v
    //   // this.selector.type = v
    // },
    handleSelect(v) {
      this.remoteHost.ip = v.ip;
      this.remoteHost.bkCloudId = v.cloudId;
      this.remoteHost.bkSupplierId = v.supplierId;
      this.remoteHost.bk_host_id = v.bk_host_id;
    },
    handleConfig(v) {
      const { selector } = this;
      const { set } = v;
      const setOthers = set.others;
      const { objectType } = set.data;
      const { targetNodes, targetNodeType } = setOthers;
      selector.mode = v.mode;

      selector.targetNodeType = targetNodeType;
      selector.targetObjectType = objectType;

      this.$emit('update:pageLoading', false);
      this.isNoHost = !!targetNodes.length;
      selector.checkedData = targetNodes;
      if (this.isSnmp) this.snmpTargets = targetNodes.map(item => item.ip);
      this.ipCheckValue = this.transformMonitorToValueExpand(targetNodes || [], targetNodeType);
      this.originValue = deepClone(this.ipCheckValue);
      this.ipTargetType = selector.targetNodeType;
      if (objectType === 'SERVICE') {
        this.countInstanceType = 'service_instance';
        this.ipSelectorPanels = ['dynamicTopo', 'serviceTemplate', 'setTemplate'];
      } else {
        this.countInstanceType = 'host';
        this.ipSelectorPanels = [
          'staticTopo',
          'dynamicTopo',
          'serviceTemplate',
          'setTemplate',
          'manualInput',
          'dynamicGroup',
        ];
      }
      this.$nextTick(() => {
        this.topoSelectorHeight = this.$refs.topoSelectorWrapper.clientHeight;
      });
    },

    /** 接口动态分组类型参数修改，需单独处理 */
    transformMonitorToValueExpand(data, nodeType) {
      if (nodeType === 'DYNAMIC_GROUP') {
        return {
          dynamic_group_list: data.map(item => ({
            bk_obj_id: item.bk_obj_id,
            id: item.bk_inst_id || item.id,
          })),
        };
      }
      return transformMonitorToValue(data, nodeType);
    },

    /** 接口动态分组类型参数修改，需单独处理 */
    transformValueToMonitorExpand(value, nodeType) {
      if (nodeType === 'DYNAMIC_GROUP') {
        return value.dynamic_group_list.map(item => ({
          bk_obj_id: item.bk_obj_id,
          bk_inst_id: item.id,
        }));
      }
      return transformValueToMonitor(value, nodeType);
    },

    async handleStart() {
      let data = null;
      let type = null;
      if (!this.isSnmp) {
        data = this.transformValueToMonitorExpand(this.ipCheckValue, this.ipTargetType);
        type = this.ipTargetType;
        if (!data.length && !this.isNoHost) {
          this.$emit('update:diffData', { added: [], removed: [], updated: [], unchanged: [] });
          this.$emit('update:step', 1);
          this.$emit('update:needRollback', false);
          return;
        }
      }
      this.$emit('update:pageLoading', true);
      const params = { ...this.config.params };
      if (this.remoteHost.ip) {
        params.remote_collecting_host = {
          ip: this.remoteHost.ip,
          bk_cloud_id: this.remoteHost.bkCloudId,
          bk_supplier_id: this.remoteHost.bkSupplierId,
          bk_host_id: this.remoteHost.bk_host_id,
          is_collecting_only: this.remoteHost.isCollectingOnly,
        };
      }
      if (this.isSnmp) {
        params.target_nodes = this.snmpTargets.map(ip => ({
          ip,
          bk_cloud_id: 0,
          bk_supplier_id: 0,
        }));
      } else {
        params.target_nodes = data;
      }
      if (this.isSnmp) {
        params.target_node_type = 'INSTANCE';
      } else {
        // 没有选中数据，则使用初始类型
        params.target_node_type = !params.target_nodes.length ? this.selector.targetNodeType : type;
      }

      if (this.$refs.topoSelectorWrapper) {
        let target = this.transformValueToMonitorExpand(this.ipCheckValue, this.ipTargetType);
        // 临时处理
        if (['SERVICE_TEMPLATE', 'SET_TEMPLATE'].includes(this.ipTargetType)) {
          target = await getNodesByTemplate({
            bk_obj_id: this.ipTargetType,
            bk_inst_ids: target.map(item => item.bk_inst_id),
            bk_inst_type: this.selector.targetObjectType,
          }).catch(() => []);
        }

        this.$emit('target', {
          target,
          bkTargetType: this.ipTargetType,
          bkObjType: this.selector.targetObjectType,
        });
      } else if (this.isSnmp) {
        this.$emit('target', {
          target: this.snmpTargets,
          bkTargetType: this.selector.targetNodeType,
          bkObjType: this.selector.targetObjectType,
        });
      }
      const save = () => {
        this.$emit('update:pageLoading', true);
        const newParams = deepClone({ ...params });
        if (this.config.config_json?.length) {
          // 增删目标的情况下，需要剔除参数中的密码相关参数
          newParams?.params?.plugin &&
            Object.keys(newParams?.params?.plugin).forEach(key => {
              const filter = this.config.config_json.find(configJson => configJson.name === key);
              filter && filter.type === 'password' && delete newParams.params.plugin[key];
            });
        }
        saveCollectConfig({ id: this.data.id, ...newParams, operation: 'ADD_DEL' }, { needMessage: false })
          .then(data => {
            this.$emit('update:diffData', data.diff_node);
            this.$emit('update:step', 1);
            this.$emit('step-change', true, 0);
            this.$emit('update:pageLoading', false);
          })
          .catch(res => {
            this.$bkMessage(
              res.error_details || {
                theme: 'error',
                message: res.message || this.$t('系统出错了'),
                ellipsisLine: 0,
              }
            );
            this.$emit('update:pageLoading', false);
          });
      };
      // /* 类型为进程采集时需要调用接口校验  */
      if (this.config.params.collect_type === 'Process') {
        this.$emit('update:pageLoading', false);
        this.checkPluginLoading = true;
        const checkPluginRes = await checkPluginVersion({
          target_node_type: params.target_node_type,
          target_nodes: params.target_nodes,
          collect_type: 'Process',
        }).catch(() => ({ result: false }));
        this.checkPluginLoading = false;
        if (checkPluginRes.result) {
          save();
          return;
        }
        const pluginNames = Object.keys(checkPluginRes.invalid_host || { '--': [] });
        const linkText = pluginNames
          .map(pluginName =>
            this.$t('{0}版本低于{1}', [pluginName, checkPluginRes.plugin_version?.[pluginName] || '--'])
          )
          .join('、');
        const hostListText = (checkPluginRes.invalid_host?.[pluginNames[0]] || [])
          .map(target => target[0])
          .slice(0, 2)
          .join('、');
        const h = this.$createElement;
        this.$bkInfo({
          title: this.$t('版本校验不通过'),
          type: 'warning',
          escClose: true,
          maskClose: true,
          confirmFn: () => {
            save();
          },
          subHeader: h('span', {}, [
            h('span', {}, this.$t('{0}等主机', [hostListText])),
            h(
              'a',
              {
                style: {
                  cursor: 'pointer',
                  color: '#3a84ff',
                },
                attrs: {
                  target: '_blank',
                  href: `${this.$store.getters.bkNodeManHost}#/plugin-manager/list`,
                },
                directives: [
                  {
                    value: {
                      content: this.$t('前往节点管理处理'),
                      placements: ['top'],
                    },
                    name: 'bk-tooltips',
                  },
                ],
              },
              linkText
            ),
            h('span', {}, `，${this.$t('可能出现下发失败或无数据上报，是否继续下发')}？`),
          ]),
        });
        return;
      }
      save();
    },
    handleCancel() {
      this.$router.back();
    },
    getHost() {
      return hostAgentStatus();
    },
    searchFn(keyWord, data) {
      return keyWord ? data.filter(item => item.ip.indexOf(keyWord) > -1) : data;
    },
    handleIpChange(v) {
      this.ipCheckValue = v;
    },
    handleTargetTypeChange(v) {
      this.ipTargetType = v;
    },
  },
};
</script>
<style lang="scss" scoped>
.hosts {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 40px 56px 40px 60px;

  .topo-selector-wrapper {
    flex: 1;
    height: 100%;
    margin-bottom: 10px;

    :deep(.ip-select-left .left-content-wrap) {
      height: calc(var(--height) - 135px);
    }

    :deep(.bk-big-tree) {
      height: 310px;
      overflow: auto;
    }
  }

  .select-private-host {
    display: flex;
    height: 42px;

    .left {
      display: flex;
      flex-grow: 1;
      align-items: center;
      justify-content: space-between;
      padding: 0 20px;
      font-size: 12px;
      color: #c4c6cc;
      border: 1px solid #dcdee5;

      .ip {
        color: #63656e;
      }

      &:hover {
        border: 1px solid #3a84ff;
      }
    }

    .icon-tips {
      color: #979ba5;
    }

    .right {
      display: flex;
      align-items: center;
      justify-content: center;
      width: 200px;
      border: 1px solid #dcdee5;
      border-left: 0;
    }
  }

  .footer {
    margin-top: 20px;
    font-size: 0;

    :deep(.bk-button) {
      margin-right: 10px;
    }
  }

  :deep(.bk-checkbox-text) {
    /* stylelint-disable-next-line declaration-no-important */
    color: #63656e !important;
  }

  :deep(.group-append) {
    min-width: 170px;
    padding-left: 26px;
    line-height: 30px;

    .bk-checkbox-text {
      font-size: 12px;
    }
  }
}
</style>
