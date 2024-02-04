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
    class="plugin-detail-wrapper"
    v-bkloading="{ isLoading: isLoading }"
  >
    <common-nav-bar
      :route-list="routeList"
      need-back
      :position-text="positionText"
      need-copy-link
      nav-mode="copy"
    />
    <div class="plugin-detail-content">
      <monitor-tab
        :active.sync="tabActive"
        @tab-change="handleTabChange"
      >
        <template slot="setting">
          <bk-alert
            class="hint-alert"
            title="消息的提示文字"
          >
            <i18n
              slot="title"
              path="插件制作好了，去 {0}"
            >
              <span
                style="color: #3a84ff; cursor: pointer;"
                @click="handleJump"
              >{{ $t('数据采集') }}</span>
            </i18n>
          </bk-alert>
        </template>
        <bk-tab-panel
          :label="$t('插件详情')"
          name="detail"
          key="detail"
        >
          <div class="content-wrapper">
            <div class="operator">
              <bk-button
                v-if="canEdit"
                style="width: 88px;"
                theme="primary"
                outline
                v-authority="{ active: !authority.MANAGE_AUTH }"
                @click="authority.MANAGE_AUTH ? handleEdit() : handleShowAuthorityDetail()"
              >
                {{ $t('编辑') }}
              </bk-button>
              <history-dialog
                :list="paramConf.list"
                :show-callback="handleLook"
              />
            </div>
            <div
              v-show="tabActive === 'detail'"
              class="plugin-info"
              ref="pluginInfo"
            >
              <div class="info-item">
                <div class="item-label">
                  {{ $t('所属') }}
                </div>
                <div class="item-container">
                  {{ businessName }}
                </div>
                <div class="logo">
                  <img
                    class="logo-img"
                    v-if="pluginInfo.logo"
                    :src="`data:image/png;base64,${pluginInfo.logo}`"
                    alt=''
                  >
                  <div
                    class="logo-text"
                    v-else
                  >
                    <span class="text-content">{{ pluginInfo.plugin_id.slice(0, 1).toUpperCase() }}</span>
                  </div>
                </div>
              </div>
              <div class="info-item">
                <div class="item-label">
                  {{ $t('插件ID') }}
                </div>
                <div class="item-container">
                  {{ pluginInfo.plugin_id }}
                  <span
                    class="public-plugin"
                    v-if="!pluginInfo.bk_biz_id"
                  > {{ $t('( 公共插件 )') }}</span>
                </div>
              </div>
              <div class="info-item">
                <div class="item-label">
                  {{ $t('插件别名') }}
                </div>
                <div class="item-container">
                  {{ pluginInfo.plugin_display_name }}
                </div>
              </div>
              <div class="info-item">
                <div class="item-label">
                  {{ $t('插件类型') }}
                </div>
                <div class="item-container">
                  {{ pluginType[pluginInfo.plugin_type] }}
                </div>
              </div>
              <!-- <div class="info-item" v-if="pluginInfo.plugin_type === 'DataDog'">
                    <div class="item-label"> {{ $t('支持系统') }} </div>
                    <div class="item-container">
                        {{pluginInfo.os_type_list.join('、')}}
                    </div>
                </div> -->
              <div
                class="info-item align-top"
                v-if="['Exporter', 'DataDog'].includes(pluginInfo.plugin_type)"
              >
                <div class="item-label">
                  {{ $t('上传内容') }}
                </div>
                <div class="item-container">
                  <div class="exporter">
                    <template v-for="(collector, key) in pluginInfo.collector_json">
                      <div
                        v-if="collector && collector.file_name"
                        class="file-wrapper"
                        :key="key"
                      >
                        <div class="icon-wrapper">
                          <span :class="['item-icon', 'icon-monitor', `icon-${key}`]" />
                        </div>
                        <div class="file-name">
                          {{ collector.file_name }}
                        </div>
                      </div>
                    </template>
                  </div>
                </div>
              </div>
              <div
                class="info-item align-top"
                v-if="['Script', 'JMX', 'DataDog'].includes(pluginInfo.plugin_type)"
              >
                <div class="item-label label-upload">
                  {{ $t('采集配置') }}
                </div>
                <div
                  :class="{ 'item-container': true, 'editor-wrapper': ['Script'].includes(pluginInfo.plugin_type) }"
                  ref="collectorConfig"
                >
                  <template v-if="['Script'].includes(pluginInfo.plugin_type)">
                    <ul
                      class="system-tabs"
                      v-if="pluginInfo.plugin_type === 'Script'"
                    >
                      <template v-for="(collector, key) in pluginInfo.systemList">
                        <li
                          :class="['system-tab', { active: collectorConf.active === collector }]"
                          :key="key"
                          v-if="collector"
                          @click="viewCollectorConf(collector)"
                        >
                          <span>{{ collector }}</span>
                        </li>
                      </template>
                    </ul>
                    <div class="script-type">
                      <span>{{ collectorConf.type }}</span>
                    </div>
                    <monaco-editor
                      full-screen
                      :options="editorOptions"
                      v-model="collectorConf.content"
                      language="shell"
                    />
                  </template>
                  <div
                    class="jmx"
                    v-if="['JMX', 'DataDog'].includes(pluginInfo.plugin_type)"
                  >
                    <pre class="jmx-code">
{{ pluginInfo.collector_json.config_yaml }}
</pre>
                  </div>
                </div>
              </div>
              <template v-if="pluginInfo.plugin_type === 'Exporter'">
                <div class="info-item">
                  <div class="item-label">
                    {{ $t('绑定端口') }}
                  </div>
                  <div class="item-container">
                    <span>{{ pluginInfo.port }}</span>
                    <span class="item-exporter-desc"> {{ $t('变量为“${host}”') }} </span>
                  </div>
                </div>
                <div class="info-item">
                  <div class="item-label">
                    {{ $t('绑定主机') }}
                  </div>
                  <div class="item-container">
                    <span>{{ pluginInfo.host }}</span>
                    <span class="item-exporter-desc"> {{ $t('变量为“${host}”') }} </span>
                  </div>
                </div>
              </template>
              <div :class="{ 'info-item': true, 'multiple-lin': isMultipleLin }">
                <div
                  :class="{ 'item-label': true, 'label-param': pluginInfo.config_json.length, 'multiple-lin': isMultipleLin }"
                >
                  {{ $t('定义参数') }}
                </div>
                <div
                  class="item-container"
                  v-if="isShowParam"
                  ref="pluginParams"
                >
                  <template v-for="(param, index) in pluginInfo.config_json">
                    <span
                      v-if="!param.hasOwnProperty('visible')"
                      :class="{ 'item-param': true, 'multiple-lin': param.multipleLin }"
                      :key="index"
                      @click="viewParam(param)"
                    >
                      {{ param.name || param.description }}
                    </span>
                  </template>
                </div>
                <div
                  class="item-container no-param"
                  v-else
                >
                  <span class="param-text"> {{ $t('未定义') }} </span>
                </div>
              </div>
              <div class="info-item">
                <div class="item-label">
                  {{ $t('远程采集') }}
                </div>
                <div class="item-container">
                  <span v-if="pluginInfo.is_support_remote"> {{ $t('支持') }} </span>
                  <span v-else> {{ $t('不支持') }} </span>
                </div>
              </div>
              <div class="info-item">
                <div class="item-label">
                  {{ $t('分类') }}
                </div>
                <div class="item-container">
                  {{ pluginInfo.label }}
                </div>
              </div>
              <div class="info-item desc-editor">
                <div class="item-label">
                  {{ $t('描述') }}
                </div>
                <div class="item-container">
                  <div class="md-editor">
                    <viewer
                      :value="pluginInfo.description_md"
                      height="515px"
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        </bk-tab-panel>
        <bk-tab-panel
          :label="$t('指标维度')"
          name="metric"
          key="metric"
        >
          <div class="content-wrapper">
            <div
              class="operator"
              v-show="tabActive === 'metric'"
            >
              <bk-button
                theme="primary"
                outline
                v-authority="{ active: !authority.MANAGE_AUTH }"
                @click="authority.MANAGE_AUTH ? handleToMertic() : handleShowAuthorityDetail()"
              >
                {{ $t('设置指标&维度') }}
              </bk-button>
            </div>
            <div
              class="metric-group"
              :class="{ 'active-group': show }"
              v-for="group in pluginInfo.metric_json"
              :key="group.table_name"
            >
              <div class="group-header">
                <div
                  class="left-box"
                  @click="show = !show"
                >
                  <i
                    class="bk-icon group-icon"
                    :class="show ? 'icon-right-shape' : 'icon-down-shape'"
                  />
                  <div class="group-name">
                    {{ group.table_name }}({{ group.table_desc }})
                  </div>
                  <div class="group-num">
                    <i18n path="共{0}个指标，{1}个维度">
                      <span class="num-blod">{{ metricNum(group.fields) }}</span>
                      <span class="num-blod">{{ dimensionNum(group.fields) }}</span>
                    </i18n>
                  </div>
                </div>
              </div>
              <div class="table-box">
                <div class="left-table">
                  <bk-table
                    :data="group.fields"
                    :outer-border="false"
                  >
                    <bk-table-column
                      :label="$t('指标/维度')"
                      width="120"
                    >
                      <template slot-scope="scope">
                        <div v-if="scope.row.monitor_type === 'metric'">
                          {{ $t('指标') }}
                        </div>
                        <div v-else>
                          {{ $t('维度') }}
                        </div>
                      </template>
                    </bk-table-column>
                    <bk-table-column
                      :label="$t('英文名')"
                      min-width="100"
                      prop="name"
                    />
                    <bk-table-column
                      :label="$t('别名')"
                      min-width="100"
                    >
                      <template slot-scope="scope">
                        {{ scope.row.description || '--' }}
                      </template>
                    </bk-table-column>
                    <bk-table-column
                      :label="$t('类型')"
                      min-width="60"
                      prop="type"
                    />
                    <bk-table-column
                      :label="$t('单位')"
                      min-width="60"
                    >
                      <template slot-scope="scope">
                        {{ scope.row.unit || '--' }}
                      </template>
                    </bk-table-column>
                    <bk-table-column
                      :label="$t('启/停')"
                      width="100"
                    >
                      <template slot-scope="scope">
                        <div class="is-active">
                          <div
                            class="active-status"
                            :class="scope.row.is_active ? 'green' : 'red'"
                          />
                          <div>{{ scope.row.is_active ? $t('启用') : $t('停用') }}</div>
                        </div>
                      </template>
                    </bk-table-column>
                  </bk-table>
                </div>
              </div>
            </div>
          </div>
        </bk-tab-panel>
      </monitor-tab>
    </div>
    <view-param
      :list="paramConf.list"
      :visible.sync="paramConf.isShow"
      :title="$t('定义参数')"
    />
  </div>
</template>
<script>
import { mapActions, mapGetters } from 'vuex';
import { addListener, removeListener } from '@blueking/fork-resize-detector';

import { retrieveCollectorPlugin } from '../../../../monitor-api/modules/model';
import Viewer from '../../../../monitor-ui/markdown-editor/viewer.tsx';
import MonacoEditor from '../../../components/editors/monaco-editor';
import HistoryDialog from '../../../components/history-dialog/history-dialog';
import ViewParam from '../../../components/history-dialog/view-param.vue';
import MonitorTab from '../../../components/monitor-tab/monitor-tab';
import authorityMixinCreate from '../../../mixins/authorityMixin';
import CommonNavBar from '../../monitor-k8s/components/common-nav-bar';
import * as pluginManagerAuth from '../authority-map';

export default {
  name: 'PluginDetail',
  components: {
    MonacoEditor,
    Viewer,
    MonitorTab,
    HistoryDialog,
    CommonNavBar,
    ViewParam
  },
  mixins: [authorityMixinCreate(pluginManagerAuth)],
  props: {
    pluginId: String
  },
  data() {
    return {
      show: false,
      isLoading: true,
      tabActive: 'detail',
      paramConf: {
        list: [],
        isShow: false
      },
      editorOptions: {
        readOnly: true,
        width: '100%'
      },
      pluginInfo: {
        bk_biz_id: '',
        plugin_id: '',
        plugin_display_name: '',
        plugin_type: '',
        collector_json: {},
        systemList: [],
        config_json: [],
        metric_json: [],
        tag: '',
        description_md: '',
        config_version: 1,
        info_version: 1,
        host: '',
        label: '',
        port: '',
        logo: '',
        is_support_remote: false
      },
      collectorConf: {
        active: '',
        type: '',
        content: ''
      },
      configLabels: {
        mode: this.$t('参数类型'),
        name: this.$t('参数名称'),
        default: this.$t('默认值'),
        description: this.$t('参数说明')
      },
      types: {
        text: this.$t('文本'),
        password: this.$t('密码'),
        file: this.$t('文件'),
        switch: this.$t('开关'),
        service: this.$t('服务实例标签'),
        host: this.$t('主机字段')
      },
      pluginType: {
        Script: 'Script',
        JMX: 'JMX',
        Exporter: 'Exporter',
        DataDog: 'DataDog',
        'Built-In': 'BK-Monitor',
        Pushgateway: 'BK-Pull',
        SNMP: 'SNMP'
      },
      updateInfo: [],
      routeList: Object.freeze([{ id: 'plugin-detail', name: this.$t('插件详情') }]),
      isMultipleLin: false,
      canEdit: true,
      calculationSize: () => {}
    };
  },
  computed: {
    business() {
      const obj = {};
      const list = this.$store.getters.bizList.concat([{ id: 0, text: this.$t('全业务') }]);
      list.forEach((item) => {
        obj[item.id] = item.text;
      });
      return obj;
    },
    businessName() {
      return this.business[this.pluginInfo.bk_biz_id];
    },
    isShowParam() {
      return !!this.pluginInfo.config_json.find(item => !Object.prototype.hasOwnProperty.call(item, 'visible'));
    },
    positionText() {
      return `${this.$t('插件名')}: ${this.pluginInfo.plugin_id}`;
    },
    ...mapGetters('plugin-manager', ['osList', 'labels'])
  },
  watch: {
    isShowParam(val) {
      if (val) {
        this.calculationParamsHeight();
      }
    }
  },
  async created() {
    if (!this.$route.meta.title) {
      this.$store.commit(
        'app/SET_NAV_TITLE',
        `${this.$t('route-' + '插件详情').replace('route-', '')} - ${this.$route.params.pluginId}`
      );
    }
    await Promise.all([this.getOsList(), this.getLabels()]).catch(() => {
    });
    this.requestPluginDetail(this.$route.params.pluginId);
  },
  mounted() {
    this.calculationSize = () => {
      this.calculationEditWidth();
      this.calculationParamsHeight();
    };
    addListener(this.$refs.pluginInfo, this.calculationSize);
  },
  beforeDestroy() {
    removeListener(this.$refs.pluginInfo, this.calculationSize);
  },
  methods: {
    ...mapActions('plugin-manager', ['getOsList', 'getLabels']),
    handleTabChange(name) {
      this.tabActive = name;
    },
    handleEdit() {
      this.$router.push({
        name: 'plugin-edit',
        params: {
          pluginId: this.pluginInfo.plugin_id
        }
      });
    },
    handleToMertic() {
      this.$router.push({
        name: 'plugin-setmetric',
        params: {
          pluginId: this.$route.params.pluginId
        }
      });
    },
    handleLook() {
      this.paramConf.list = this.updateInfo;
    },
    calculationEditWidth() {
      this.editorOptions.width = this.$refs?.collectorConfig?.clientWidth;
    },
    /**
     * 计算参数列表高度，判断元素是否换行
     * 24为一行时的初始高度， 34为多行切回到1行时的高度
     */
    calculationParamsHeight() {
      const timer = setTimeout(() => {
        if (this.$refs.pluginParams) {
          const height = this.$refs.pluginParams.clientHeight;
          this.isMultipleLin = height > 24 || height === 34;
          this.pluginInfo.config_json.forEach((item) => {
            this.$set(
              item,
              'multipleLin',
              !Object.prototype.hasOwnProperty.call(item, 'visible') && this.isMultipleLin
            );
          });
        }
        clearTimeout(timer);
      }, 16);
    },
    /**
     * @desc 请求插件详情
     * @param {String} id - 插件 ID
     */
    requestPluginDetail(id) {
      retrieveCollectorPlugin(id)
        .then((data) => {
          this.handleData(data);
        })
        .finally(() => {
          this.isLoading = false;
        });
    },
    /**
     * @desc 查看采集配置
     * @param {String} key
     */
    viewCollectorConf(key) {
      if (this.pluginInfo.plugin_type === 'DataDog') {
        this.collectorConf.content = this.pluginInfo.collector_json.config_yaml;
        return;
      }
      const collectorJson = this.pluginInfo.collector_json[key];
      if (collectorJson) {
        const { collectorConf } = this;
        collectorConf.active = key;
        collectorConf.type = collectorJson.ext;
        const res = window.escape(window.atob(collectorJson.script_content_base64 || ''));
        collectorConf.content = window.decodeURIComponent(res);
      }
    },
    /**
     * @desc 查看参数
     * @param {Object} param
     */
    viewParam(param) {
      this.paramConf.list = [];
      Object.keys(this.configLabels).forEach((key) => {
        if (key === 'default') {
          let value = '';
          if (param.type === 'service' || param.type === 'host') {
            value = Object.entries(param[key]).map(item => `${item[0]}:${item[1]}`);
          } else {
            value = param[key];
          }
          this.paramConf.list.push({
            label: `${this.configLabels[key]}(${this.types[param.type]})`,
            value
          });
        } else {
          this.paramConf.list.push({
            label: this.configLabels[key],
            value: param[key]
          });
        }
      });
      this.paramConf.isShow = true;
    },
    parseUrlStr(url) {
      const obj = {};
      const pattern = /^https?:\/\/(([a-zA-Z0-9_-])+(\.)?)*(:\d+)?(\/((\.)?(\?)?=?&?[a-zA-Z0-9_-](\?)?)*)*$/i;
      if (url && pattern.test(url)) {
        const url = /^(?:([A-Za-z]+):)?(\/{0,3})([0-9.\-A-Za-z]+)(?::(\d+))?(?:\/([^?#]*))?(?:\?([^#]*))?(?:#(.*))?$/;
        const fields = ['url', 'scheme', 'slash', 'host', 'port', 'path', 'query', 'hash'];
        const result = url.exec(url);
        fields.forEach((item, index) => {
          obj[item] = result[index];
        });
      }
      return obj;
    },
    handleData(data) {
      // 转换is_diff_metric=true的指标type为diff用于展示
      data.metric_json.forEach((item) => {
        item.fields.forEach((set) => {
          if (set.monitor_type === 'metric' && set.is_diff_metric) {
            set.type = 'diff';
          }
        });
      });
      const pluginInfo = data;
      this.pluginInfo = data;
      const collectorJson = pluginInfo.collector_json;
      const configJson = pluginInfo.config_json;
      const type = data.plugin_type;
      this.canEdit = data.edit_allowed;
      if ((type === 'Script' || type === 'DataDog') && collectorJson) {
        // 默认选中非空的系统展示其脚本内容
        this.pluginInfo.systemList = Object.keys(collectorJson).filter(item => this.osList
          .find(sys => item === sys.os_type));
        this.pluginInfo.systemList.some(item => collectorJson[item] && this.viewCollectorConf(item));
      } else if (type === 'Exporter') {
        const hostParam = configJson.find(item => item.name === 'host') || {};
        const portParam = configJson.find(item => item.name === 'port') || {};
        pluginInfo.host = hostParam.default;
        pluginInfo.port = portParam.default;
      }
      this.updateInfo = [
        { label: this.$t('创建人'), value: data.create_user || '--' },
        { label: this.$t('创建时间'), value: data.create_time || '--' },
        { label: this.$t('最近更新人'), value: data.update_user || '--' },
        { label: this.$t('修改时间'), value: data.update_time || '--' }
      ];
      this.labels.forEach((item) => {
        const obj = item.children.find(v => v.id === data.label);
        if (obj) {
          this.pluginInfo.label = `${item.name}-${obj.name}`;
        }
      });
    },
    metricNum(data) {
      return data.filter(item => item.monitor_type === 'metric').length;
    },
    dimensionNum(data) {
      return data.filter(item => item.monitor_type === 'dimension').length;
    },
    handleJump() {
      this.$router.push({
        name: 'collect-config-add',
        params: {
          pluginId: this.pluginInfo.plugin_id
        }
      });
    }
  }
};
</script>
<style lang="scss" scoped>
.plugin-detail-wrapper {
  height: 100%;

  :deep(.bk-tab-section) {
    padding: 0;
  }

  .common-nav-bar {
    padding-left: 19px;
  }

  .plugin-detail-content {
    height: calc(100% - 52px - var(--notice-alert-height));
    padding: 16px;

    .hint-alert {
      background: #fff;
      border: none;
      box-shadow: 0 2px 4px 0 #1919290d;

      :deep(.icon-info) {
        margin-right: 5px;
        color: #979ba5;
      }
    }
  }
}


.operator {
  position: absolute;
  top: 16px;
  right: 24px;
  z-index: 999;
  font-size: 0;

  .history-container {
    margin-left: 8px;
  }
}

.active-group {
  height: 64px;
  overflow: hidden;
}

.content-wrapper {
  position: relative;
  padding: 16px 24px 20px 26px;
}

.metric-group {
  padding: 0 23px 30px 22px;
  margin-bottom: 8px;
  color: #63656e;
  background: #fff;
  box-shadow: 0 1px 2px 0 rgba(0, 0, 0, .1);
  transition: height .5s;

  .num-blod {
    font-weight: bold;
  }

  .group-header {
    display: flex;
    align-items: center;
    height: 64px;

    .left-box {
      display: flex;
      flex-grow: 1;
      align-items: center;
      height: 64px;
      cursor: pointer;

      .group-icon {
        margin-right: 6px;
        font-size: 15px;
      }

      .group-name {
        margin-right: 40px;
        font-size: 14px;
        font-weight: bold;
      }

      .group-num {
        color: #979ba5;
        cursor: default;
      }
    }
  }

  .table-box {
    display: flex;
    max-height: 427px;
    padding: 0 7px 0 8px;
    overflow-y: scroll;

    .left-table {
      width: 100%;

      .is-active {
        display: flex;
        align-items: center;

        .active-status {
          width: 8px;
          height: 8px;
          margin-right: 4px;
          border: 1px solid;
          border-radius: 50%;
        }

        .green {
          background: #70eab8;
          border-color: #10c178;
        }

        .red {
          background: #fd9c9c;
          border-color: #ea3636;
        }
      }
    }
  }
}

.plugin-info {
  padding-right: 40px;
  background: #fff;

  .info-item {
    position: relative;
    display: flex;
    flex-direction: row;
    align-items: center;
    margin-bottom: 20px;

    .item-label {
      flex: 0 0 116px;
      margin-right: 24px;
      font-size: 12px;
      color: #979ba5;
      text-align: right;

      &.label-param {
        align-self: flex-start;
        margin-top: 2px;
      }
    }

    &.align-top {
      align-items: flex-start;

      .item-label {
        margin-top: 7px;
      }
    }

    &.desc-editor {
      align-items: start;
      padding-bottom: 40px;
    }

    &:last-child {
      margin-bottom: 0;
    }

    .item-container {
      position: relative;
      flex: 1;
      overflow: hidden;
      font-size: 12px;
      color: #63656e;

      &.editor-wrapper {
        height: 395px;
      }

      .public-plugin {
        color: #c4c6cc;
      }

      .item-exporter-desc {
        height: 19px;
        margin-left: 10px;
        font-size: 14px;
        line-height: 19px;
        color: #c4c6cc;
      }

      .exporter {
        display: flex;
        flex-wrap: wrap;

        .file-wrapper {
          display: flex;
          align-items: center;
          width: 438px;
          height: 32px;
          background: #fafbfd;
          border: 1px solid #dcdee5;
          border-radius: 2px;

          .icon-wrapper {
            height: 100%;
            padding: 0 10px;

            .item-icon {
              position: relative;
              display: inline-block;
              width: 100%;
              height: 100%;
              overflow: hidden;
              font-size: 15px;
              line-height: 32px;
              text-align: center;
            }
          }

          .file-name {
            flex: 1;
            max-width: 394px;
            padding-right: 15px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          &:not(:last-child) {
            margin-right: 10px;
            margin-bottom: 10px;
          }
        }
      }

      .system-tabs {
        display: flex;
        align-items: center;
        padding: 0;
        margin: 0;
        background: #fafbfd;
        border: 1px solid #dcdee5;
        border-bottom: 0;

        .system-tab {
          flex: 0 0 140px;
          line-height: 42px;
          text-align: center;
          cursor: pointer;
          border-right: 1px solid #dcdee5;

          &.active {
            position: relative;
            background: #fff;

            &::after {
              position: absolute;
              left: 0;
              width: 100%;
              height: 2px;
              content: '';
              background: #3a84ff;
            }
          }
        }
      }

      .script-type {
        height: 32px;
        line-height: 32px;
        background: #202024;

        span {
          display: inline-block;
          padding: 0 20px;
          background-color: #313238;
        }
      }

      .jmx {
        max-height: 345px;
        padding: 16px 20px;
        overflow-y: scroll;
        background: #313238;
        border: 1px solid #dcdee5;
        border-radius: 2px;

        .jmx-code {
          padding: 0;
          margin: 0;
          font-size: 12px;
          line-height: 17px;
          color: #c4c6cc;
          border: 0;
        }
      }

      .item-param {
        display: inline-block;
        height: 24px;
        padding: 0 10px;
        margin-right: 10px;
        font-size: 12px;
        line-height: 24px;
        text-align: center;
        cursor: pointer;
        background-color: #f0f1f5;
        border-radius: 2px;

        &:hover {
          color: #3a84ff;
          background: #e1ecff;
        }
      }

      .table-container {
        .start {
          color: #2dcb56;
        }

        .stop {
          color: #c4c6cc;
        }
      }

      .md-editor {
        max-height: 537px;
        padding: 15px 40px 17px 20px;
        overflow-y: scroll;
        border: 1px solid #dcdee5;
        border-radius: 2px;
      }

      &.no-param {
        display: inline-flex;
        align-items: center;

        .param-icon {
          width: 16px;
          height: 16px;
          margin-right: 7px;
          color: #ffa327;
        }

        .param-text {
          height: 19px;
          line-height: 20px;
        }
      }

      .remote-checkbox {
        margin-bottom: 0px;
      }
    }

    .logo {
      position: absolute;
      top: 56px;
      right: 0;
      width: 84px;
      height: 84px;
      padding: 3px;
      background-color: #fafbfd;
      border: 1px solid #dcdee5;

      .logo-img {
        width: 100%;
        height: 100%;
      }

      .logo-text {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        height: 100%;
        background: #9cabc4;

        .text-content {
          width: 27px;
          height: 50px;
          font-size: 36px;
          font-weight: 600;
          line-height: 50px;
          color: #fff;
          text-align: center;
        }
      }
    }
  }

  .multiple-lin {
    margin-bottom: 10px;
  }
}
</style>
