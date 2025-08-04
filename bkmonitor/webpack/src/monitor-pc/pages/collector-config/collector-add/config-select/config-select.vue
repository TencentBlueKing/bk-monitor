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
    class="config-select"
  >
    <template v-if="config.set.data.collectType === 'SNMP'">
      <div style="margin-bottom: 10px">
        {{ $t('设备IP列表') }}
      </div>
      <bk-tag-input
        v-model="snmpTargets"
        :allow-auto-match="true"
        :allow-create="true"
        :has-delete-icon="true"
        :paste-fn="handleTargetsPaste"
        :placeholder="$t('输入采集目标主机')"
        @change="handleSnmpTargetChange"
      />
    </template>
    <div
      v-else
      ref="selectContainer"
      class="select-container"
    >
      <!-- <div class="select-tips"><i class="icon-monitor icon-tips"></i> {{ $t('动态：只能选择节点，采集目标按节点动态变更。静态：只能选择主机IP，采集目标不会变更。') }}</div> -->
      <!-- <topo-selector
        ref="topoSelector"
        :mode="selector.mode"
        :type="selectorType"
        :is-instance="selector.isInstance"
        :tab-disabled="selector.tabDisabled"
        :default-active="selector.defaultActive"
        :checked-data="selector.checkedData"
        @type-change="(type) => selectorType = type"
        @checked-change="handleCheckedChange"
        @loading-change="(status) => loading = status">
      </topo-selector> -->
      <!-- <topo-selector
        :tree-height="selectContainerHeight"
        :height="selectContainerHeight"
        preview-width="25%"
        :preview-range="[150, 800]"
        left-panel-width="30%"
        :target-node-type="selector.targetNodeType"
        :target-object-type="selector.targetObjectType"
        :checked-data="selector.checkedData"
        ref="topoSelector"
      > -->
      <!-- </topo-selector> -->
      <monitor-ip-selector
        v-if="ipSelectorPanels.length && selectContainerHeight > 100"
        :style="{ height: selectContainerHeight + 'px' }"
        :class="countInstanceType === 'service_instance' ? 'service-instance-selector' : ''"
        :count-instance-type="countInstanceType"
        :enable-origin-data="true"
        :node-table-custom-column-list="serviceInstanceColumnList"
        :original-value="originValue"
        :panel-list="ipSelectorPanels"
        :service-template-table-custom-column-list="serviceInstanceColumnList"
        :set-template-table-custom-column-list="serviceInstanceColumnList"
        :show-view-diff="$route.name === 'collect-config-edit'"
        :value="ipCheckValue"
        @change="handleIpChange"
        @targetTypeChange="handleTargetTypeChange"
      />
    </div>
    <div :class="['remote-container', { 'is-snmp': config.set.data.collectType === 'SNMP' }]">
      <div
        v-if="config.set.supportRemote"
        class="remote-hint"
      >
        <bk-switcher
          v-model="info.isUseRemoteHost"
          size="small"
        />
        <span class="hint-text"> {{ $t('使用远程运行主机') }} </span>
        <i
          v-bk-tooltips="remoteHostTooltips"
          class="icon-monitor icon-tips hint-icon"
        />
      </div>
      <div
        v-if="config.set.data.collectType === 'SNMP' && info.isUseRemoteHost"
        style="margin-top: 10px"
      >
        {{ $t('采集器主机') }}
      </div>
      <div
        v-show="info.isUseRemoteHost"
        class="remote-host"
      >
        <div class="host-input">
          <div
            style="flex-grow: 1"
            @click="handleShowSelector"
          >
            <span
              v-if="!info.remoteCollectingHost.ip"
              class="host-placeholder"
            >
              {{ $t('添加采集插件运行主机') }}
            </span>
            <span v-else>{{ info.remoteCollectingHost.ip }}</span>
          </div>
          <i
            v-if="info.remoteCollectingHost.ip"
            class="bk-icon icon-close-circle-shape clear-icon"
            @click="handleClearIp"
          />
        </div>
        <div
          v-en-style="'min-width: 230px'"
          class="host-pro"
        >
          <bk-checkbox
            v-model="info.remoteCollectingHost.isCollectingOnly"
            class="pro-checkbox"
            :disabled="!canSelectProHost"
          >
            {{ $t('采集专有主机') }}
          </bk-checkbox>
          <i
            v-bk-tooltips="proHostTooltips"
            class="icon-monitor icon-tips host-hint-icon"
          />
        </div>
      </div>
    </div>
    <div class="btn-container">
      <bk-button
        class="btn-previous"
        @click="handlePrevious"
      >
        {{ $t('上一步') }}
      </bk-button>
      <bk-button
        class="btn-delivery"
        :disabled="!canDelivery"
        :loading="checkPluginLoading"
        theme="primary"
        @click="handleDelivery"
      >
        {{ $t('开始下发') }}
      </bk-button>
      <!-- <bk-button @click="handleCancel"> {{ $t('取消') }} </bk-button> -->
    </div>
    <select-host
      :conf.sync="selectHostConf"
      :filter="searchFn"
      :get-host="getHost"
      @confirm="handleHostConfirm"
    />
  </div>
</template>

<script>
import { checkPluginVersion, saveCollectConfig } from 'monitor-api/modules/collecting';
import { getNodesByTemplate, hostAgentStatus } from 'monitor-api/modules/commons';
import { deepClone } from 'monitor-common/utils';

import MonitorIpSelector from '../../../../components/monitor-ip-selector/monitor-ip-selector';
import { transformMonitorToValue, transformValueToMonitor } from '../../../../components/monitor-ip-selector/utils';
import SelectHost from '../../../plugin-manager/plugin-instance/set-steps/components/select-host';

export default {
  name: 'ConfigSelect',
  components: {
    SelectHost,
    MonitorIpSelector,
  },
  props: {
    config: {
      type: Object,
      default: () => {},
    },
    passwordInputChangeSet: {
      type: Set,
      default: () => new Set(),
    },
  },
  data() {
    return {
      loading: false,
      info: {
        isUseRemoteHost: false,
        targetNodeType: 'TOPO', // TOPO, INSTANCE
        remoteCollectingHost: {
          ip: '',
          bkCloudId: '',
          bkSupplierId: '',
          isCollectingOnly: true,
        },
        targetNodes: [],
      },
      remoteHostTooltips: {
        content: this.$t('默认就是采集目标与采集程序运行在一起，在有单独的采集主机或者权限限制需要远程采集的方式。'),
        placement: 'top',
      },
      proHostTooltips: {
        content: this.$t('使用整个服务器的50%的资源，其他情况都只是使用10%的资源并且不超过单CPU资源。'),
        placement: 'top',
      },
      selector: {
        mode: 'add',
        targetNodeType: 'TOPO',
        targetObjectType: 'HOST',
        checkedData: [],
      },
      selectHostConf: {
        isShow: false,
      },
      agentStatusMap: {
        normal: `Agent ${this.$t('正常')}`,
        abnormal: `Agent ${this.$t('异常')}`,
        not_exist: `Agent ${this.$t('未安装')}`,
      },
      snmpTargets: [],
      ipv4Reg:
        /^((\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5]).){3}(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])(?::(?:[0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$/,
      selectContainerHeight: 0,
      checkPluginLoading: false,
      ipCheckValue: {},
      originValue: undefined,
      ipSelectorPanels: [],
      ipTargetType: 'TOPO',
      countInstanceType: 'host',
    };
  },
  computed: {
    canSelectProHost() {
      // 以下情况可以选择【采集专有主机】：
      // 1. 已经选择远程主机。
      return this.info.remoteCollectingHost.ip !== '';
    },
    canDelivery() {
      // 以下情况可以下发：
      // 1. 没有启用【使用远程主机】；
      // 2. 已启用【使用远程主机】，且已经选择远程主机。
      const { info } = this;
      const { isUseRemoteHost } = info;
      const snmpTargetsIsOk =
        this.config.set.data.collectType === 'SNMP'
          ? !!this.snmpTargets.length && isUseRemoteHost && info.remoteCollectingHost.ip !== ''
          : true;
      return (!isUseRemoteHost || (isUseRemoteHost && info.remoteCollectingHost.ip !== '')) && snmpTargetsIsOk;
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
  created() {
    this.handleConfig(this.config);
    this.$nextTick(() => {
      if (this.$refs.selectContainer) {
        this.selectContainerHeight = this.$refs.selectContainer.clientHeight;
      }
    });
  },
  methods: {
    handlePrevious() {
      this.$emit('previous');
    },
    // 开始下发
    async handleDelivery() {
      const { info } = this;
      const { remoteCollectingHost } = info;
      if (!info.isUseRemoteHost && remoteCollectingHost) {
        remoteCollectingHost.ip = '';
        remoteCollectingHost.bkCloudId = '';
        remoteCollectingHost.bkSupplierId = '';
      }
      const params = this.config.set.data.collectType === 'SNMP' ? this.getSnmpParams() : this.getParams();
      this.selector.targetNodeType = this.ipTargetType;
      if (this.config.set.data.collectType === 'SNMP') {
        this.$emit('target', {
          bkObjType: this.selector.targetObjectType,
          target: this.snmpTargets,
          bkTargetType: this.selector.targetNodeType,
        });
      } else {
        // const target = this.$refs.topoSelector.getCheckedData();
        let target = transformValueToMonitor(this.ipCheckValue, this.ipTargetType);
        // 临时处理
        if (['SERVICE_TEMPLATE', 'SET_TEMPLATE'].includes(this.ipTargetType)) {
          target = await getNodesByTemplate({
            bk_inst_type: this.selector.targetObjectType,
            bk_obj_id: this.ipTargetType,
            bk_inst_ids: target.map(item => item.bk_inst_id),
          }).catch(() => []);
        }

        this.$emit('target', {
          bkObjType: this.selector.targetObjectType,
          target,
          bkTargetType: this.ipTargetType,
        });
      }
      const save = async () => {
        // 保存配置
        await this.saveConfig(params)
          .then(data => {
            this.selector.type = this.selectorType;
            this.saveData(this.config, this.info, data);
            this.$emit('next');
            this.loading = false;
          })
          .catch(() => {
            this.loading = false;
          });
      };
      /* 类型为进程采集是需要调用接口校验 */
      if (this.config.set.data.collectType === 'Process') {
        const checkPluginParams = {
          collect_type: 'Process',
          target_node_type: params.target_node_type,
          target_nodes: params.target_nodes,
        };
        this.checkPluginLoading = true;
        const checkPluginRes = await checkPluginVersion(checkPluginParams).catch(() => ({ result: false }));
        this.checkPluginLoading = false;
        if (checkPluginRes.result) {
          save();
        } else {
          const pluginNames = Object.keys(checkPluginRes.invalid_host || { '--': [] });
          const linkText = pluginNames
            .map(name => this.$t('{0}版本低于{1}', [name, checkPluginRes.plugin_version?.[name] || '--']))
            .join('、');
          const hostListText = (checkPluginRes.invalid_host?.[pluginNames[0]] || [])
            .map(target => target[0])
            .slice(0, 2)
            .join('、');
          const h = this.$createElement;
          this.$bkInfo({
            type: 'warning',
            title: this.$t('版本校验不通过'),
            subHeader: h('span', {}, [
              h('span', {}, this.$t('{0}等主机', [hostListText])),
              h(
                'a',
                {
                  style: { color: '#3a84ff', cursor: 'pointer' },
                  attrs: {
                    href: `${this.$store.getters.bkNodeManHost}#/plugin-manager/list`,
                    target: '_blank',
                  },
                  directives: [
                    {
                      name: 'bk-tooltips',
                      value: {
                        placements: ['top'],
                        content: this.$t('前往节点管理处理'),
                      },
                    },
                  ],
                },
                linkText
              ),
              h('span', {}, `，${this.$t('可能出现下发失败或无数据上报，是否继续下发')}？`),
            ]),
            maskClose: true,
            escClose: true,
            confirmFn: () => {
              save();
            },
          });
        }
        return;
      }
      await save();
    },
    handleCancel() {
      this.$router.back();
    },
    handleConfig(v) {
      const { selector } = this;
      const { set } = v;
      const setOthers = set.others;
      const { objectType } = set.data;
      const { targetNodes } = setOthers;
      const { targetNodeType } = setOthers;
      const { select } = v;
      selector.mode = v.mode;
      if (set.data.collectType === 'SNMP') {
        this.info.isUseRemoteHost = true;
        v.mode === 'edit' && (this.snmpTargets = setOthers.targetNodes.map(item => item.ip));
      }
      if (select.mode === 'edit') {
        this.info = select.data;
      } else if (v.mode === 'edit') {
        this.info = this.handleData(setOthers);
      }
      // 如果是非编辑态则初始化targetNodeType
      selector.targetNodeType = targetNodeType || 'TOPO';
      selector.targetObjectType = objectType; // 采集对象为服务时，只能选择动态
      selector.checkedData = targetNodes || [];
      this.ipCheckValue = this.transformMonitorToValueExpand(targetNodes || [], targetNodeType);
      this.originValue = targetNodes?.length ? deepClone(this.ipCheckValue) : undefined;
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
    },
    // 保存配置
    saveData(config, info, data) {
      const { mode } = config;
      const { selector } = this;
      const others = {
        selector,
      };
      config.data.id = data.id;
      if (mode === 'edit') {
        const diffNode = data.diff_node;
        others.added = diffNode.added;
        others.updated = diffNode.updated;
        others.removed = diffNode.removed;
        others.unchanged = diffNode.unchanged;
        others.allowRollback = data.can_rollback;
      }
      this.$emit('update:config', {
        ...config,
        select: {
          data: info,
          others,
          mode: 'edit',
        },
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

    transformValueToMonitorExpand(value, nodeType) {
      if (nodeType === 'DYNAMIC_GROUP') {
        return value.dynamic_group_list.map(item => ({
          bk_obj_id: item.bk_obj_id,
          bk_inst_id: item.id,
        }));
      }
      return transformValueToMonitor(value, nodeType);
    },

    // 获取要保存的数据
    getParams() {
      const setData = this.config.set.data;
      const pluginData = setData.plugin;
      const selectData = this.info;
      const { remoteCollectingHost } = selectData;

      // 获取选择的数据
      // const { type, data } = this.$refs.topoSelector.getCheckedData();

      selectData.targetNodes = this.transformValueToMonitorExpand(this.ipCheckValue, this.ipTargetType);

      // 编辑态下如果目标节点为空，则取默认
      selectData.targetNodeType =
        this.selector.mode === 'edit' && !selectData.targetNodes.length
          ? this.selector.targetNodeType
          : this.ipTargetType;

      const param = {
        collector: {
          period: setData.period,
          timeout: setData.timeout,
        },
        plugin: {},
      };
      const { collector, plugin } = param;
      if (setData.collectType === 'SNMP_Trap') {
        Reflect.set(param, 'snmp_trap', {});
        if (setData.plugin.snmpv) {
          this.$set(param.snmp_trap, 'version', setData.plugin.snmpv.split('_')[1]);
        }
      }
      pluginData.configJson.forEach(item => {
        if (setData.collectType === 'SNMP_Trap') {
          // SNMP_Trap 用 item.key 作为键名
          if (setData.plugin.snmpv === 'snmp_v3') {
            if (item.auth_json) {
              param.snmp_trap.auth_info = [];
              item.auth_json.forEach((items, index) => {
                param.snmp_trap.auth_info.push({});
                items.forEach(item => {
                  param.snmp_trap.auth_info[index][item.key] = item.default;
                });
              });
            } else {
              param.snmp_trap[item.key] = item.default;
            }
          } else {
            param.snmp_trap[item.key] = item.default;
          }
        } else {
          if (item.mode === 'collector') {
            // mode='collector' 时，将用户填写的运行参数存在 `param.collector` 对象中
            collector[item.name] = item.default;
          } else {
            // 否则，存在 `param.plugin` 对象中
            // 只有当前item为密码类型且处于passwordInputChangeSet中，才需要将值设置到plugin上
            if (['products', 'access_key', 'secret_key', 'region'].includes(item.field)) {
              plugin[item.field] = item.default;
            } else if (['encrypt', 'password'].includes(item.type)) {
              if (this.passwordInputChangeSet.has(item.name)) {
                plugin[item.name] = item.default;
              }
            } else {
              plugin[item.name] = item.default;
            }
            if (item.type === 'file') {
              plugin[item.name] = {
                filename: item.default,
                file_base64: item.file_base64,
              };
            }
          }
        }
      });
      if (setData.collectType === 'Log') {
        param.log = setData.log;
      } else if (setData.collectType === 'Process') {
        param.process = setData.process;
      }
      if (setData.isShowHost) {
        // 绑定主机
        collector[setData.host.name] = setData.host.default;
      }
      if (setData.isShowPort) {
        // 绑定端口
        collector[setData.port.name] = setData.port.default;
      }

      const params = {
        name: setData.name,
        bk_biz_id: setData.bizId,
        collect_type: setData.collectType,
        target_object_type: setData.objectType,
        plugin_id: pluginData.id,
        params: param,
        label: setData.objectId,
        target_node_type: selectData.targetNodeType,
        target_nodes: selectData.targetNodes,
        remote_collecting_host: remoteCollectingHost?.ip
          ? {
              ip: remoteCollectingHost.ip,
              is_collecting_only: remoteCollectingHost.isCollectingOnly,
              bk_cloud_id: remoteCollectingHost.bkCloudId,
              bk_supplier_id: remoteCollectingHost.bkSupplierId,
              bk_host_id: remoteCollectingHost.bk_host_id,
            }
          : null,
      };
      if (this.config.mode === 'edit' && setData.id) {
        // 编辑时，增加 `id` 字段
        params.id = setData.id;
      }
      return params;
    },
    getSnmpParams() {
      const setData = this.config.set.data;
      const pluginData = setData.plugin;
      const selectData = this.info;
      const { remoteCollectingHost } = selectData;
      const { configJson } = pluginData;

      const param = {
        collector: {
          period: setData.period,
          timeout: setData.timeout,
        },
        plugin: {},
      };
      const configJsonList = configJson.reduce((total, cur) => {
        if (cur.auth_json) {
          total.push(...cur.auth_json[0]);
        } else {
          total.push(cur);
        }
        return total;
      }, []);
      configJsonList.forEach(item => {
        if (item.mode === 'collector') {
          param.collector[item.key] = item.default;
        } else {
          param.plugin[item.key] = item.default;
        }
      });
      const params = {
        name: setData.name,
        bk_biz_id: setData.bizId,
        collect_type: setData.collectType,
        target_object_type: setData.objectType,
        plugin_id: pluginData.id,
        params: param,
        label: setData.objectId,
        target_node_type: 'INSTANCE',
        remote_collecting_host: remoteCollectingHost?.ip
          ? {
              ip: remoteCollectingHost.ip,
              is_collecting_only: remoteCollectingHost.isCollectingOnly,
              bk_cloud_id: remoteCollectingHost.bkCloudId,
              bk_supplier_id: remoteCollectingHost.bkSupplierId,
              bk_host_id: remoteCollectingHost.bk_host_id,
            }
          : null,
        target_nodes: this.snmpTargets.map(item => ({
          ip: item,
          bk_cloud_id: 0,
          bk_supplier_id: 0,
        })),
      };
      if (this.config.mode === 'edit' && setData.id) {
        // 编辑时，增加 `id` 字段
        params.id = setData.id;
      }
      return params;
    },
    //  保存配置接口
    saveConfig(params) {
      this.loading = true;
      return saveCollectConfig(params);
    },
    handleShowSelector() {
      this.selectHostConf.isShow = true;
    },
    handleHostConfirm(v) {
      const { remoteCollectingHost } = this.info;
      remoteCollectingHost.ip = v.ip;
      remoteCollectingHost.bkCloudId = v.cloudId;
      remoteCollectingHost.bkSupplierId = 0;
      remoteCollectingHost.bk_host_id = v.bk_host_id;
    },
    handleData(data) {
      const { remoteCollectingHost } = data;
      return {
        isUseRemoteHost: remoteCollectingHost ?? false,
        targetNodeType: data.targetNodeType,
        remoteCollectingHost: remoteCollectingHost
          ? {
              ip: remoteCollectingHost.ip,
              bkCloudId: remoteCollectingHost.bk_cloud_id,
              bkSupplierId: remoteCollectingHost.bk_supplier_id,
              isCollectingOnly: remoteCollectingHost.is_collecting_only,
            }
          : {
              ip: '',
              bkCloudId: '',
              bkSupplierId: '',
              isCollectingOnly: true,
            },
        targetNodes: data.targetNodes,
      };
    },
    // 获取主机
    getHost() {
      return hostAgentStatus();
    },
    // 分静态和动态拓扑
    handleCheckedData(type, data) {
      const checkedData = [];
      if (['static-ip', 'static-topo'].includes(type)) {
        data.forEach(item => {
          checkedData.push({
            ip: item.ip,
            bk_cloud_id: item.bkCloudId,
            bk_supplier_id: item.bkSupplierId,
          });
        });
      } else {
        data.forEach(item => {
          checkedData.push({
            bk_inst_id: item.bkInstId,
            bk_obj_id: item.bkObjId,
          });
        });
      }
      return checkedData;
    },
    handleClearIp() {
      this.info.remoteCollectingHost.ip = '';
    },
    // 远程主机搜索筛选
    searchFn(keyWord, data) {
      return keyWord ? data.filter(item => item.ip.indexOf(keyWord) > -1) : data;
    },
    handleSnmpTargetChange(valueList) {
      for (const item of valueList) {
        // ipv4
        const reg =
          /^((\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5]).){3}(\d|[1-9]\d|1\d\d|2[0-4]\d|25[0-5])(?::(?:[0-9]|[1-9][0-9]{1,3}|[1-5][0-9]{4}|6[0-4][0-9]{3}|65[0-4][0-9]{2}|655[0-2][0-9]|6553[0-5]))?$/;
        if (!reg.test(item)) {
          this.$bkMessage({ theme: 'error', message: this.$t('输入正常的IP') });
          this.$nextTick(() => {
            const i = this.snmpTargets.findIndex(item => !reg.test(item));
            this.snmpTargets.splice(i, 1);
          });
          break;
        }
      }
    },
    handleTargetsPaste(v) {
      const res = v
        .replace(/[,;\s]/g, ',')
        .split(',')
        .filter(item => !!item && this.ipv4Reg.test(item));
      this.snmpTargets.push(...res);
      return [];
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
.config-select {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 41px 60px;

  .select-container {
    flex: 1;

    .select-tips {
      display: flex;
      margin-bottom: 15px;
      color: #63656e;

      i {
        margin-right: 6px;
        font-size: 16px;
        color: #979ba5;
      }
    }

    .static-ip-table {
      .col-status {
        &.success {
          color: #2dcb56;
        }

        &.error {
          color: #ea3636;
        }

        &.not-exist {
          color: #c4c6cc;
        }
      }
    }

    .dynamic-topo-table {
      .col-label {
        .col-label-container {
          display: inline-flex;
          align-items: center;
          font-size: 12px;
          background: #fff;
          border: 1px solid #dcdee5;
          border-radius: 2px;

          .col-label-key {
            height: 24px;
            padding: 0 10px;
            line-height: 24px;
            background: #fafbfd;
          }

          .col-label-value {
            height: 24px;
            padding: 0 10px;
            line-height: 24px;
            border-left: 1px solid #dcdee5;
          }
        }
      }
    }
  }

  .remote-container {
    margin-top: 51px;

    .remote-hint {
      display: inline-flex;
      align-items: center;
      height: 24px;

      :deep(.bk-switcher.is-checked) {
        background: #3a84ff;
      }

      .hint-text {
        margin-left: 10px;
        color: #63656e;
      }

      .hint-icon {
        margin-left: 4px;
        font-size: 16px;
        color: #979ba5;
        cursor: pointer;
      }
    }

    .remote-host {
      display: flex;
      margin-top: 10px;

      .host-input {
        display: flex;
        align-items: center;
        justify-content: space-between;
        width: 100%;
        height: 42px;
        padding: 0 9px 0 20px;
        cursor: pointer;
        border: 1px solid #dcdee5;

        .host-placeholder {
          color: #c4c6cc;
        }

        span {
          height: 42px;
          line-height: 42px;
        }

        i {
          color: #c4c6cc;
        }

        &:hover {
          border: 1px solid #3a84ff;
        }
      }

      .host-pro {
        display: flex;
        align-items: center;
        min-width: 171px;
        height: 42px;
        line-height: 42px;
        text-align: center;
        background: #fafbfd;
        border: 1px solid #dcdee5;
        border-left: 0;
        border-radius: 0px 1px 1px 0px;

        .pro-checkbox {
          margin-left: 26px;
        }

        :deep(.bk-checkbox-text) {
          margin-left: 9px;
          font-size: 12px;
          color: #63656e;
        }

        .host-hint-icon {
          margin-left: 4px;
          font-size: 16px;
          color: #979ba5;
          cursor: pointer;
        }
      }
    }
  }

  .is-snmp {
    margin-top: 20px;
  }

  .btn-container {
    margin-top: 20px;
    font-size: 0;

    .btn-previous,
    .btn-delivery {
      margin-right: 10px;
    }
  }

  :deep(.ip-select-left .left-content-wrap) {
    height: calc(var(--height) - 135px);
  }

  :deep(.bk-big-tree) {
    height: 310px;
    overflow: auto;
  }
}
</style>
