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
    v-bkloading="{ isLoading: selector.loading }"
    class="topo-selector"
    v-bind="$attrs"
  >
    <ip-select
      v-if="defaultActive !== undefined"
      ref="ipSelect"
      :default-active="selector.defaultActive"
      :tab-disabled="selector.tabDisabled"
      :min-width="minWidth"
      :max-width="maxWidth"
      :height="height"
      :active-unshow="[3]"
      :is-show-tree-loading="false"
      :is-show-table-loading="false"
      :get-default-data="getDefaultData"
      :get-fetch-data="getFetchData"
      :is-instance="isInstance"
      :is-extranet="isExtranet"
      :topo-height="topoHeight"
      @change-input="handleChangeInput"
      @active-select-change="handleActiveSelectChange"
    >
      <template #static-ip-panel>
        <slot
          name="static-ip-panel"
          v-bind="{
            data: selector.staticTableData,
          }"
        >
          <bk-table
            class="static-ip-table"
            :data="selector.staticTableData"
            :empty-text="$t('无数据')"
          >
            <bk-table-column
              prop="ip"
              label="IP"
              min-width="190"
            />
            <bk-table-column
              :label="$t('状态')"
              width="135"
            >
              <template slot-scope="scope">
                <div
                  :class="[
                    'col-status',
                    {
                      success: scope.row.agentStatus === 'normal',
                      error: scope.row.agentStatus === 'abnormal',
                      'not-exist': scope.row.agentStatus === 'not_exist',
                    },
                  ]"
                >
                  {{ agentStatusMap[scope.row.agentStatus] }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              prop="cloudName"
              :label="$t('管控区域')"
            />
            <bk-table-column
              :label="$t('操作')"
              align="center"
              width="100"
            >
              <template slot-scope="scope">
                <bk-button
                  text
                  @click="handleDeleteStaticIp(scope.row, scope.$index)"
                >
                  {{ $t('移除') }}
                </bk-button>
              </template>
            </bk-table-column>
          </bk-table>
        </slot>
      </template>
      <template #dynamic-topo-panel>
        <slot
          name="dynamic-topo-panel"
          v-bind="{
            data: selector.dynamicTopoTableData,
          }"
        >
          <bk-table
            class="dynamic-topo-table"
            :data="selector.dynamicTopoTableData"
            :empty-text="$t('无数据')"
          >
            <bk-table-column
              prop="nodePath"
              :label="$t('节点名称')"
              min-width="200"
            >
              <template slot-scope="scope">
                <!-- {{scope.row.nodePath}} -->
                <div class="col-text">
                  {{ scope.row.nodePath }}
                  <!-- <div class="col-text-start">{{handleSubstr(scope.row.nodePath, 'start')}}</div>
                  <div class="col-text-next" dir="rtl">{{handleSubstr(scope.row.nodePath, 'end')}}</div> -->
                </div>
              </template>
            </bk-table-column>
            <!-- 只有监控目标选择了服务才显示改项目 -->
            <!-- <bk-table-column prop="count" :label="$t('服务实例')" width="100" v-if="getObjectType === 'SERVICE'"></bk-table-column> -->
            <bk-table-column
              prop="count"
              :label="$t('Agent异常')"
              width="100"
            >
              <template slot-scope="scope">
                <!-- <div>
                    共<span style="font-weight: bold;color: #3A84FF;"> {{scope.row.count}} </span>{{isInstance ? $t('个实例') : $t('台主机')}}
                    <span v-if="scope.row.agentErrorCount !== 0">（<span style="font-weight: bold;color: #EA3636;"> {{scope.row.agentErrorCount}} </span>{{isInstance ? $t('个实例异常') : $t('台Agent异常')}}）</span>
                </div> -->
                <div>
                  <span :class="[scope.row.agentErrorCount ? 'error' : 'not-exist']">
                    {{ scope.row.agentErrorCount }}
                  </span>
                  /
                  <span>
                    {{ scope.row.count }}
                  </span>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('分类')"
              min-width="120"
            >
              <template slot-scope="scope">
                <div class="col-label">
                  <div
                    v-for="(item, index) in scope.row.labels"
                    :key="index"
                    class="col-label-container"
                  >
                    {{ item.first }}：{{ item.second }}
                  </div>
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('操作')"
              align="center"
              width="100"
            >
              <template slot-scope="scope">
                <bk-button
                  text
                  @click="handleDeleteDynamicTopo(scope.row, scope.$index)"
                >
                  {{ $t('移除') }}
                </bk-button>
              </template>
            </bk-table-column>
          </bk-table>
        </slot>
      </template>
      <template #change-input>
        <div
          v-if="!!changeInput && isRigthIp && $refs.ipSelect.curItem.type === 'staticInput'"
          class="err-tips"
        >
          {{ $t('IP格式有误或不存在，检查后重试！') }}
        </div>
        <div
          v-if="!!changeInput && isRigthIpExtranet && $refs.ipSelect.curItem.type === 'staticExtranet'"
          class="err-tips"
        >
          {{ $t('IP格式有误或内网IP，检查后重试！') }}
        </div>
      </template>
      <template #search-noData>
        <span> {{ $t('搜索结果为空！') }} </span>
        <span style="color: #c4c6cc"> {{ $t('建议检查关键字是否准确') }} </span>
      </template>
      <template #static-extranet-panel="staticExtranet">
        <slot name="static-extranet-panel">
          <bk-table
            class="static-ip-table"
            :data="staticExtranet.data"
            :empty-text="$t('无数据')"
          >
            <bk-table-column
              prop="ip"
              label="IP"
              min-width="190"
            />
            <bk-table-column
              :label="$t('操作')"
              align="center"
              width="100"
            >
              <template slot-scope="scope">
                <bk-button
                  text
                  @click="handleDeleteExtranetIp(scope.row, scope.$index)"
                >
                  {{ $t('移除') }}
                </bk-button>
              </template>
            </bk-table-column>
          </bk-table>
        </slot>
      </template>
    </ip-select>
  </div>
</template>

<script lang="js">
import {
  getHostInstanceByIp,
  getHostInstanceByNode,
  getServiceInstanceByNode,
  getTopoTree,
} from 'monitor-api/modules/commons';

import IpSelect from '../../../../components/ip-select/ip-select';

const EVENT_ACTIVESELECTCHANGE = 'active-select-change';

export default {
  name: 'TopoSelector',
  components: {
    IpSelect,
  },
  props: {
    mode: {
      type: String,
      default: 'add',
      validator: v => ['add', 'edit', 'clone'].includes(v),
    },
    // 是否是实例
    isInstance: {
      type: Boolean,
    },
    idKey: {
      type: String,
      default: 'id',
    },
    instanceType: String,
    // 默认选择下拉框
    defaultActive: {
      type: Number,
      required: true,
    },
    // 0 静态 1 动态 -1 都可以
    tabDisabled: {
      type: Number,
      default: -1,
    },
    // 默认选中项（编辑）
    checkedData: {
      type: Array,
      default: () => [],
    },
    // 默认的表单数据，clone回写
    tableData: {
      type: Array,
      default: () => [],
    },
    minWidth: {
      type: [Number, String],
      default: 850,
    },
    maxWidth: {
      type: [Number, String],
      default: 9999,
    },
    height: {
      type: [Number, String],
      default: 460,
    },
    isExtranet: {
      type: Boolean,
      default: false,
    },
    // 非编辑状态下默认展开树节点
    defaultExpandNode: {
      type: [Array, Number], // Array类型：需要展开节点的ID, String类型：展开层次
      default() {
        return 1;
      },
      validator(value) {
        if (typeof value === 'number') {
          return value > 0;
        }
        return true;
      },
    },
    topoHeight: {
      type: Number,
      default: 310,
    },
  },
  data() {
    return {
      selector: {
        loading: false,
        type: '',
        defaultActive: 0,
        tabDisabled: -1,
        apiMap: {
          'static-topo': 'host',
          'static-ip': 'host',
          'dynamic-topo': '',
        },
        treeData: [],
        checkedData: [],
        disabledData: [],
        tableData: [],
        staticTreeData: [],
        dynamicTopoTreeData: [],
        staticCheckedData: [],
        dynamicTopoCheckedData: [],
        staticTableData: [],
        dynamicTopoTableData: [],
        staticMap: new Map(),
        dynamicTopoMap: new Map(),
        defaultExpandNode: 1,
      },
      agentStatusMap: {
        normal: `Agent ${this.$t('正常')}`,
        abnormal: `Agent ${this.$t('异常')}`,
        not_exist: `Agent ${this.$t('未安装')}`,
      },
      changeInput: false,
      has: [],
      isRigthIp: false,
      isRigthIpExtranet: false,
    };
  },
  computed: {
    // ...mapGetters(['getObjectType'])
    // dynamicTopoCountLabel () {
    //     return this.isInstance ? this.$t('当前实例数') : this.$t('当前主机数')
    // }
  },
  watch: {
    defaultActive: {
      handler: 'handleDefaultActiveChange',
      immediate: true,
    },
    tabDisabled: {
      handler: 'handleTabDisabled',
      immediate: true,
    },
    'selector.checkedData': {
      handler: 'handleCheckedChange',
      immediate: true,
      deep: true,
    },
    changeInput: {
      handler: 'handleInputValueChange',
    },
    'selector.tableData': {
      handler: 'handletTableDataChange',
      // immediate: true,
      deep: true,
    },
    defaultExpandNode: {
      handler: 'handleDefaultExpandNodeChange',
      immediate: true,
    },
  },
  methods: {
    handleInputValueChange() {
      this.isRigthIp = false;
      this.isRigthIpExtranet = false;
    },
    handleChangeInput(v) {
      this.changeInput = v;
    },
    handleCheckedChange(v) {
      this.$emit('has-checked-data', v);
    },
    handleDefaultActiveChange(v) {
      this.selector.defaultActive = v;
    },
    handleTabDisabled(v) {
      this.selector.tabDisabled = v;
    },
    async getDefaultData(type) {
      const { selector } = this;
      selector.type = type;
      this.$emit('type-change', type);

      // 获取 treeData
      // selector.loading = true
      this.$emit('loading-change', true);
      const isNeedGetSelectorData = this.mode === 'edit' && ['static-topo', 'dynamic-topo'].includes(type);
      if ((type === 'static-topo' || type === 'static-ip') && !selector.staticTreeData.length) {
        await this.getTopoTree(selector.apiMap[type])
          .then(data => {
            selector.treeData = data;
            selector.staticTreeData = data;
          })
          .catch(err => {
            throw err.message || err.data.message;
          })
          .finally(() => {
            selector.loading = false;
            this.$emit('loading-change', isNeedGetSelectorData);
          });
      } else if (type === 'dynamic-topo' && !selector.dynamicTopoTreeData.length) {
        await this.getTopoTree(selector.apiMap[type])
          .then(data => {
            selector.treeData = data;
            selector.dynamicTopoTreeData = data;
          })
          .catch(err => {
            throw err.message || err.data.message;
          })
          .finally(() => {
            selector.loading = false;
            this.$emit('loading-change', isNeedGetSelectorData);
          });
      }
      // 编辑
      if (isNeedGetSelectorData) {
        // 回显数据
        if (this.isExtranet) {
          let ipArr = this.getAllIpByTree(selector.treeData);
          ipArr = Array.from(new Set(ipArr));
          const extranetIp = [];
          this.checkedData.forEach(item => {
            const res = ipArr.find(id => id === this.handleGetId(item));
            if (!res) {
              extranetIp.push(item.ip);
            }
          });
          this.$emit('extranet-data-change', extranetIp);
          this.$refs.ipSelect.setStaticExtranetData(extranetIp);
        }
        await this.handleBackDisplayData();
      }

      if (this.mode === 'clone') {
        this.tableData.forEach((item, index) => {
          this.selector.staticMap.set(this.checkedData[index], item);
        });
        selector.staticTableData = this.tableData;
        selector.tableData = this.tableData;
        selector.checkedData = this.checkedData;
      }
      // selector.loading = false
      this.$emit('loading-change', false);
      return {
        treeData: selector.treeData,
        checkedData: selector.checkedData,
        disabledData: selector.disabledData,
        tableData: selector.tableData,
        defaultExpandNode: selector.defaultExpandNode,
      };
    },
    async handleBackDisplayData() {
      const { selector } = this;
      await this.getSelectorData(selector.type, this.checkedData, selector.treeData)
        .then(data => {
          const { ipSelect } = this.$refs;
          if (selector.type === 'static-topo') {
            selector.checkedData = data.staticCheckedData;
            selector.staticCheckedData = data.staticCheckedData;
            selector.tableData = data.staticTableData;
            selector.staticTableData = data.staticTableData;
            if (ipSelect) {
              ipSelect.setCurActivedCheckedData(data.staticCheckedData);
              ipSelect.setCurActivedTableData(data.staticTableData);
            }
          } else {
            selector.checkedData = data.dynamicTopoCheckedData;
            selector.dynamicTopoCheckedData = data.dynamicTopoCheckedData;
            selector.tableData = data.dynamicTopoTableData;
            selector.dynamicTopoTableData = data.dynamicTopoTableData;
            if (ipSelect) {
              ipSelect.setCurActivedCheckedData(data.dynamicTopoCheckedData);
              ipSelect.setCurActivedTableData(data.dynamicTopoTableData);
            }
          }
        })
        .finally(() => {
          selector.loading = false;
          this.$emit('loading-change', false);
        });
    },
    /**
     * @desc 添加至列表/选中节点时触发本事件，必须返回 `tableData` 字段
     */
    async getFetchData(type, payload) {
      const { selector } = this;
      const node = payload.data || payload;
      const { staticTableData } = this.selector;
      let nodes = [];
      const ipList = [];
      const { has } = this;
      // tab 切换
      if (type !== selector.type) {
        selector.type = type;
        this.$emit('type-change', type);
        if (type === 'static-topo' && !selector.staticTreeData.length) {
          await this.getTopoTree(selector.apiMap[type])
            .then(data => {
              selector.staticTreeData = data;
              selector.staticMap.clear();
            })
            .catch(err => {
              throw err.message || err.data.message;
            })
            .finally(() => {
              selector.loading = false;
            });
        } else if (type === 'dynamic-topo' && !selector.dynamicTopoTreeData.length) {
          await this.getTopoTree(selector.apiMap[type])
            .then(data => {
              selector.dynamicTopoTreeData = data;
              selector.dynamicTopoMap.clear();
            })
            .catch(err => {
              throw err.message || err.data.message;
            })
            .finally(() => {
              selector.loading = false;
            });
        }
      }
      if (type === 'static-topo') {
        // 静态拓扑
        const isService = this.instanceType !== 'service';
        const statciNodeKey = this.instanceType !== 'service' ? 'ip' : 'service_instance_id';
        if (Object.hasOwn(node, statciNodeKey)) {
          // IP 节点
          nodes = isService
            ? this.getSameIpNodesByIp(this.handleGetId(node), selector.staticTreeData)
            : this.getSameServiceInstance(node.service_instance_id, selector.staticTreeData);
        } else {
          // 非 IP 节点
          if (node.children?.length) {
            const tmp = this.getIpNodes(node.children, statciNodeKey); // 将子节点中有 IP 的节点筛选出来
            tmp.forEach(item => {
              // 将有相同 IP 的节点筛选出来
              nodes = isService
                ? nodes.concat(this.getSameIpNodesByIp(this.handleGetId(item), selector.staticTreeData))
                : nodes.concat(this.getSameServiceInstance(item.service_instance_id, selector.staticTreeData));
            });
          }
        }
        if (payload.checked) {
          // 勾选
          nodes.forEach(item => !selector.staticMap.has(item.id) && selector.staticMap.set(item.id, item));
        } else {
          // 取消勾选
          nodes.forEach(item => selector.staticMap.has(item.id) && selector.staticMap.delete(item.id));
        }
      } else if (type === 'dynamic-topo') {
        // 动态拓扑
        if (payload.checked) {
          // 勾选
          // 父子去重，若某个节点其父节点被选中，
          // 则将该节点从 dynamicTopoMap 中删除，只保留父节点
          const children = this.findChildren(node);
          children.forEach(item => {
            selector.dynamicTopoMap.has(item.id) && selector.dynamicTopoMap.delete(item.id);
          });
          !selector.dynamicTopoMap.has(node.id) && selector.dynamicTopoMap.set(node.id, node);
        } else {
          // 取消勾选
          selector.dynamicTopoMap.has(node.id) && selector.dynamicTopoMap.delete(node.id);
        }
      } else if (type === 'static-ip') {
        staticTableData.forEach(item => {
          ipList.push({ ip: item.ip, bkCloudId: item.bkCloudId });
        });
        const rightIpList = node.goodList;
        const errorIpList = node.errList;
        if (rightIpList.length) {
          rightIpList.forEach(rightIpItem => {
            if (staticTableData.find(item => item.ip === rightIpItem)) {
              // 右边的表格存在IP
              has.push(rightIpItem);
            } else {
              ipList.push({ ip: rightIpItem });
              this.isRigthIp = false;
            }
          });
        } else if (errorIpList.length) {
          this.isRigthIp = true;
        }
        let ipMap = [];
        ipList.forEach(item => {
          const onlyIp = typeof item.bkCloudId === 'undefined';
          const ipArr = this.getSameIpNodesByIp(this.handleGetId(item, onlyIp), selector.staticTreeData, [], onlyIp);
          ipMap = ipMap.concat(ipArr);
        });
        ipMap.forEach(item => !selector.staticMap.has(item.id) && selector.staticMap.set(item.id, item));
      } else if (type === 'static-extranet') {
        const data = [];
        node.goodList.forEach(item => {
          const ipMap = this.getSameIpNodesByIp(item, selector.staticTreeData);
          if (ipMap.length) {
            // node.goodList.splice(index, 1)
            node.errList.push(item);
          } else {
            data.push({ extranet: true, ip: item });
          }
        });
        selector.tableData = data;
        const extranetData = data.map(item => item.ip);
        this.$emit('extranet-data-change', extranetData);
        this.$refs.ipSelect.staticExtranet.defaultText = ' ';
        this.$nextTick(() => {
          this.$refs.ipSelect.staticExtranet.defaultText = node.errList.join('\n');
        });
        this.isRigthIpExtranet = !!node.errList.length;
      }
      if (['static-ip', 'static-topo'].includes(type)) {
        selector.staticCheckedData = [...selector.staticMap.keys()];
        selector.checkedData = selector.staticCheckedData;
        if (this.instanceType !== 'service' && (selector.checkedData.length || ipList.length)) {
          // selector.loading = true
          this.$emit('loading-change', true);
          const ip = type === 'static-ip' ? ipList : selector.staticMap;
          await this.getSelectorTableData(type, ip)
            .then(data => {
              if (data.length) {
                selector.tableData = data;
                selector.staticTableData = data;
                if (type === 'static-ip') {
                  node.goodList.forEach(ip => {
                    if (!selector.staticTableData.some(item => item.ip === ip)) {
                      node.errList.push(ip);
                      this.isRigthIp = true;
                    }
                  });
                  this.$refs.ipSelect.staticInput.defaultText = ' ';
                }
              } else {
                selector.checkedData = [];
              }
            })
            .finally(() => {
              if (type === 'static-ip') {
                this.$refs.ipSelect.staticInput.defaultText = node.errList.join('\n');
              }
              this.$emit('loading-change', false);
              selector.loading = false;
            });
        } else if (this.instanceType === 'service') {
          const serviceTableData = [...this.selector.staticMap.values()].filter(item => !item.children);
          selector.tableData = [];
          serviceTableData.forEach(item => {
            if (!selector.tableData.find(instance => instance.service_instance_id === item.service_instance_id)) {
              selector.tableData.push(item);
            }
          });
          selector.staticTableData = selector.tableData;
        } else {
          selector.tableData = [];
          selector.staticTableData = [];
        }
      } else if (type === 'dynamic-topo') {
        selector.checkedData = [...selector.dynamicTopoMap.keys()];
        selector.dynamicTopoCheckedData = selector.checkedData;
        if (selector.checkedData.length) {
          // selector.loading = true
          this.$emit('loading-change', true);
          await this.getSelectorTableData(type, selector.dynamicTopoMap)
            .then(data => {
              selector.tableData = data;
              selector.dynamicTopoTableData = data;
            })
            .catch(() => {})
            .finally(() => {
              selector.loading = false;
              this.$emit('loading-change', false);
            });
        } else {
          selector.tableData = [];
          selector.dynamicTopoTableData = [];
        }
      }
      this.$emit('checked-change', selector.checkedData);
      return {
        checkedData: selector.checkedData,
        tableData: selector.tableData,
      };
    },
    getTopoTree(type, id) {
      const bizId = id || this.$store.getters.bizId;
      const params = {
        bk_biz_id: bizId,
      };
      if (type) {
        params.instance_type = type;
        params.remove_empty_nodes = true;
      }
      if (this.instanceType === 'service') {
        params.instance_type = 'service';
      }
      return getTopoTree(params);
    },
    getHostInstanceByIp(nodes, idList = []) {
      const bizIds = idList.length ? idList : [this.$store.getters.bizId];
      return getHostInstanceByIp({ ip_list: nodes, bk_biz_ids: bizIds });
    },
    getHostInstanceByNode(nodes) {
      return getHostInstanceByNode({ node_list: nodes });
    },
    getServiceInstanceByNode(nodes) {
      return getServiceInstanceByNode({ node_list: nodes });
    },
    getSameIpNodesByIp(ip, treeData, nodes = [], onlyIp = false) {
      treeData.forEach(item => {
        if (Object.hasOwn(item, 'ip') && this.handleGetId(item, onlyIp) === ip) {
          nodes.push(item);
        } else if (item.children?.length) {
          this.getSameIpNodesByIp(ip, item.children, nodes, onlyIp);
        }
      });
      return nodes;
    },
    getSameServiceInstance(serviceInstId, treeData, nodes = []) {
      treeData.forEach(item => {
        if (Object.hasOwn(item, 'service_instance_id') && item.service_instance_id === serviceInstId) {
          nodes.push(item);
        } else if (item.children?.length) {
          this.getSameServiceInstance(serviceInstId, item.children, nodes);
        }
      });
      return nodes;
    },
    getNodesByInstId(instId, objId, treeData, nodes = []) {
      treeData.forEach(item => {
        if (item.bk_inst_id === instId && item.bk_obj_id === objId) {
          nodes.push(item);
        } else if (item.children?.length) {
          this.getNodesByInstId(instId, objId, item.children, nodes);
        }
      });
      return nodes;
    },
    getNodesByMap(type, nodesMap) {
      const res = [];
      if (type === 'static-topo') {
        // 静态拓扑
        nodesMap.forEach(
          item =>
            !res.find(v => v.ip === item.ip && v.bk_cloud_id === item.bk_cloud_id) &&
            res.push({ ip: item.ip, bk_cloud_id: item.bk_cloud_id, bk_supplier_id: item.bk_supplier_id })
        );
      } else if (type === 'static-ip') {
        // 静态 IP
        nodesMap.forEach(item => !res.find(v => v.ip === item.ip) && res.push({ ip: item.ip }));
      } else if (type === 'dynamic-topo') {
        // 动态拓扑
        nodesMap.forEach(item =>
          res.push({
            bk_inst_id: item.bk_inst_id,
            bk_inst_name: item.bk_inst_name,
            bk_obj_id: item.bk_obj_id,
            bk_obj_name: item.bk_obj_name,
            bk_biz_id: item.bk_biz_id,
          })
        );
      }
      return res;
    },
    handleDeleteStaticIp(row, index) {
      const { staticTreeData, staticTableData, staticMap } = this.selector;
      // 将 `staticTreeData` 中有相同 IP 的节点筛选出来，并从 `staticMap` 中删除
      const nodes =
        this.instanceType !== 'service'
          ? this.getSameIpNodesByIp(this.handleGetId(row), staticTreeData)
          : this.getSameServiceInstance(row.service_instance_id, staticTreeData);
      nodes.forEach(item => staticMap.has(item.id) && staticMap.delete(item.id));
      // 重新赋值选中数据
      const checkedData = [...staticMap.keys()];
      this.selector.checkedData = checkedData;
      this.selector.staticCheckedData = checkedData;
      this.$refs.ipSelect.setCurActivedCheckedData(checkedData, 'static-topo');
      // 删除表格数据
      staticTableData.splice(index, 1);
      this.$refs.ipSelect.setCurActivedTableData(staticTableData);
      this.$emit('checked-change', checkedData);
    },
    handleDeleteDynamicTopo(row, index) {
      const { dynamicTopoTableData, dynamicTopoMap } = this.selector;
      // 从 `dynamicTopoMap` 找到当前数据，并将其从中删除
      const node = [...dynamicTopoMap.values()].find(item => item.bk_inst_id === row.bkInstId) || {};
      dynamicTopoMap.has(node.id) && dynamicTopoMap.delete(node.id);
      // 重新赋值选中数据
      this.selector.dynamicTopoCheckedData = [...dynamicTopoMap.keys()];
      this.selector.checkedData = this.selector.dynamicTopoCheckedData;
      this.$refs.ipSelect.setCurActivedCheckedData([...dynamicTopoMap.keys()]);
      // 删除表格数据
      dynamicTopoTableData.splice(index, 1);
      this.$refs.ipSelect.setCurActivedTableData(dynamicTopoTableData);
      this.$emit('checked-change', this.selector.checkedData);
    },
    handleIpData(data) {
      const res = [];
      Array.isArray(data) &&
        data.forEach(item => {
          res.push({
            ip: item.ip,
            agentStatus: item.agent_status,
            bkCloudId: item.bk_cloud_id,
            cloudName: item.bk_cloud_name,
            osType: item.bk_os_type,
            bkSupplierId: item.bk_supplier_id,
            nodePath: item.node_path,
          });
        });
      return res;
    },
    handleNodeData(data) {
      const res = [];
      Array.isArray(data) &&
        data.forEach(item => {
          res.push({
            bkInstId: item.bk_inst_id,
            bkObjId: item.bk_obj_id,
            name: item.bk_inst_name,
            nodePath: item.node_path,
            count: item.count,
            labels: item.labels,
            agentErrorCount: item.agent_error_count || item.instance_error_count || 0,
          });
        });
      return res;
    },
    getIpNodes(data, key, nodes = []) {
      data.forEach(item => {
        if (Object.hasOwn(item, key) && item[key]) {
          nodes.push(item);
        } else if (item.children?.length) {
          this.getIpNodes(item.children, key, nodes);
        }
      });
      return nodes;
    },
    async getSelectorTableData(type, nodesMap) {
      // 将选中的节点传给后台，以获取状态、区域、当前主机数、分组标签等数据
      let tableData = [];
      if (['static-ip', 'static-topo'].includes(type)) {
        const params = type === 'static-ip' ? nodesMap : this.getNodesByMap(type, nodesMap);
        await this.getHostInstanceByIp(params)
          .then(data => {
            this.handleErrIp(type, params, data);
            tableData = this.handleIpData(data);
          })
          .catch(() => {});
      } else {
        if (!this.isInstance) {
          await this.getHostInstanceByNode(this.getNodesByMap(type, nodesMap))
            .then(data => {
              tableData = this.handleNodeData(data);
            })
            .catch(() => {});
        } else {
          await this.getServiceInstanceByNode(this.getNodesByMap(type, nodesMap))
            .then(data => {
              tableData = this.handleNodeData(data);
            })
            .catch(() => {});
        }
      }
      return tableData;
    },
    handleErrIp(type, params, data) {
      if (type === 'static-ip' && params.length !== data.length) {
        params.forEach(item => {
          this.isRigthIp = !data.find(el => item.ip === el.ip);
        });
      }
    },
    findChildren(parent) {
      return parent.children.reduce(
        (prev, cur) => prev.concat(cur.children?.length ? this.findChildren(cur) : cur),
        []
      );
    },
    async getSelectorData(type, checkedData, treeData) {
      let nodes = [];
      const selector = {
        checkedData: [],
        staticCheckedData: [],
        dynamicTopoCheckedData: [],
        tableData: [],
        staticTableData: [],
        dynamicTopoTableData: [],
      };
      if (['static-ip', 'static-topo'].includes(type)) {
        checkedData.forEach(item => {
          nodes = nodes.concat(this.getSameIpNodesByIp(this.handleGetId(item), treeData));
        });
      } else {
        let tmpNodes = [];
        checkedData.forEach(item => {
          tmpNodes = tmpNodes.concat(this.getNodesByInstId(item.bk_inst_id, item.bk_obj_id, treeData));
        });
        // 排除重复
        tmpNodes.forEach(item => {
          checkedData.find(v => v.bk_inst_id === item.bk_inst_id && v.bk_obj_id === item.bk_obj_id) && nodes.push(item);
        });
      }
      if (['static-ip', 'static-topo'].includes(type)) {
        const { staticMap } = this.selector;
        nodes.forEach(item => !staticMap.has(item.id) && staticMap.set(item.id, item));
        selector.staticCheckedData = [...staticMap.keys()];
        await this.getSelectorTableData(this.selector.type, staticMap)
          .then(data => {
            selector.staticTableData = data;
          })
          .catch(() => {});
      } else {
        const { dynamicTopoMap } = this.selector;
        nodes.forEach(item => !dynamicTopoMap.has(item.id) && dynamicTopoMap.set(item.id, item));
        selector.dynamicTopoCheckedData = [...dynamicTopoMap.keys()];
        await this.getSelectorTableData(this.selector.type, dynamicTopoMap)
          .then(data => {
            selector.dynamicTopoTableData = data;
          })
          .catch(() => {});
      }
      return selector;
    },
    handleServiceInstanceData(result, selector) {
      selector.tableData = result.tableData;
      selector.staticTableData = result.tableData;
      selector.checkedData = result.checkedData;
      selector.staticCheckedData = result.checkedData;
      this.$emit('checked-change', selector.checkedData);
    },
    getCheckedData() {
      const { type, staticTableData, dynamicTopoTableData } = this.selector;
      return ['static-ip', 'static-topo'].includes(type) ? staticTableData : dynamicTopoTableData;
    },
    handletTableDataChange() {
      this.$emit('table-data-change', this.selector.tableData);
      this.$emit('topo-checkd-change', this.selector.checkedData, this.selector.type);
    },
    handleDefaultExpandNodeChange(v) {
      this.selector.defaultExpandNode = v;
    },
    handleActiveSelectChange({ newValue, oldValue }) {
      this.$emit(EVENT_ACTIVESELECTCHANGE, {
        newValue,
        oldValue,
      });
    },
    handleGetId(item, onlyIp = false) {
      if (onlyIp) return item.ip;
      if (typeof item.bkCloudId !== 'undefined') {
        return `${item.bkCloudId}-${item.ip}`;
      }
      return typeof item.bk_cloud_id === 'undefined' ? item.ip : `${item.bk_cloud_id}-${item.ip}`;
    },
    handleDeleteExtranetIp(row, index) {
      this.$refs.ipSelect.staticExtranet.tableData.splice(index, 1);
      this.$emit('extranet-data-change', row.ip, 'del');
    },
    getAllIpByTree(treeData, nodes = []) {
      treeData.forEach(item => {
        if (Object.hasOwn(item, 'ip')) {
          nodes.push(this.handleGetId(item));
        } else if (item.children?.length) {
          this.getAllIpByTree(item.children, nodes);
        }
      });
      return nodes;
    },
    clearAllTableData() {
      if (this.selector.staticTableData.length) {
        this.selector.staticTableData.forEach((item, index) => {
          this.handleDeleteStaticIp(item, index);
        });
      }
      if (this.$refs.ipSelect.staticExtranet.tableData.length) {
        this.$refs.ipSelect.staticExtranet.tableData.forEach((item, index) => {
          this.handleDeleteExtranetIp(item, index);
        });
      }
    },
    handleSubstr(str, type) {
      let res = '';
      const mid = str.substr(str.length / 2, 1);
      if (type === 'start') {
        res = mid === '/' ? `${str.substr(0, str.length / 2)}/` : str.substr(0, str.length / 2);
      } else {
        res = mid === '/' ? str.substr(str.length / 2 + 1) : str.substr(str.length / 2);
      }
      return res;
    },
    // 重置虚拟滚动
    resize() {
      this.$refs?.ipSelect?.resize?.();
    },
  },
};
</script>

<style lang="scss">
.topo-selector {
  :deep(.err-tips) {
    width: 100%;
    margin: -7px 0 13px;
    color: #ea3636;
    text-align: left;
  }
  // height: 460px;
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
        height: 20px;
        padding: 2px 6px;
        margin-right: 2px;
        font-size: 12px;
        background: #f0f1f5;
        border-radius: 2px;
      }
    }

    .error {
      color: #ea3636;
    }

    .not-exist {
      color: #c4c6cc;
    }

    .col-text {
      // display: flex;
      // width: 100%;
      // align-items: center;
      // justify-content: flex-start;
      overflow: hidden;
      text-overflow: ellipsis;
      word-break: break-all;
      white-space: nowrap;

      &-start {
        max-width: 50%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      &-next {
        flex: auto;
        overflow: hidden;
        text-align: left;
        text-overflow: clip;
        white-space: nowrap;
        direction: rtl;

        &::before {
          display: inline;
          margin-left: -6px;
          font-size: 12px;
          content: 'v';
          opacity: 0;
        }
      }
    }
  }
}
</style>
