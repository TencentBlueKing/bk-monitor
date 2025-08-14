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
  <bk-sideslider
    class="collector-config-detail"
    :is-show="sideShow"
    :quick-close="true"
    :width="900"
    @update:isShow="handleHidden"
  >
    <div
      slot="header"
      class="detail-header"
    >
      <span
        v-if="!loading && basicInfo"
        class="detail-header-title"
      >
        {{ `${$t('采集详情')} - #${basicInfo.id} ${name}` }}
        <bk-alert class="hint-alert">
          <i18n
            slot="title"
            path="数据采集好了，去 {0}"
          >
            <span
              style="color: #3a84ff; cursor: pointer"
              @click="handleJump"
            >
              {{ $t('查看数据') }}
            </span>
          </i18n>
        </bk-alert>
      </span>
      <span v-else>{{ $t('加载中...') }}</span>
      <div
        v-if="sideData && Object.keys(sideData).length"
        class="operation"
      >
        <bk-button
          v-if="basicInfo && basicInfo.bk_biz_id === $store.getters.bizId"
          v-authority="{ active: !authority.MANAGE_AUTH && sideData.status !== 'STOPPED' }"
          style="width: 88px; margin-right: 8px"
          :disabled="sideData.status === 'STOPPED'"
          :outline="true"
          theme="primary"
          @click="
            authority.MANAGE_AUTH || sideData.status === 'STOPPED'
              ? sideData.status !== 'STOPPED' && handleToEdit()
              : handleShowAuthorityDetail()
          "
        >
          {{ $t('button-编辑') }}
        </bk-button>
        <history-dialog
          v-if="!loading"
          :list="historyList"
        />
      </div>
    </div>
    <div
      slot="content"
      v-bkloading="{ isLoading: loading }"
      class="detail-content"
    >
      <div class="detail-content-tab clearfix">
        <span
          v-en-style="'min-width: 120px'"
          class="tab-item"
          :class="{ 'tab-active': active === 0 }"
          @click="active = 0"
        >
          {{ $t('基本信息') }}
        </span>
        <span
          v-en-style="'min-width: 120px'"
          class="tab-item"
          :class="{ 'tab-active': active === 1 }"
          @click="active = 1"
        >
          {{ $t('采集目标') }}
        </span>
      </div>
      <div class="detail-content-wrap">
        <div
          v-show="active === 0"
          class="basic-info"
        >
          <ul
            v-if="basicInfo"
            class="basic-info-detail"
          >
            <li
              v-for="(item, key) in basicInfoMap"
              :key="key"
              class="detail-item"
            >
              <div
                v-en-style="'width: 120px'"
                class="detail-item-label"
                :class="{ 'detail-item-name': key === 'name' }"
              >
                {{ item }}：
              </div>
              <span
                v-if="key === 'name'"
                v-authority="{ active: !authority.MANAGE_AUTH }"
                style="line-height: 32px"
                class="detail-item-val"
                @click="authority.MANAGE_AUTH ? handleEditLabel(key) : handleShowAuthorityDetail()"
              >
                <span
                  v-if="!input.show"
                  class="name-wrapper"
                >
                  <span
                    v-bk-tooltips.top="basicInfo[key]"
                    class="config-name"
                    >{{ basicInfo[key] }}
                  </span>
                  <i
                    v-if="!input.show"
                    class="icon-monitor icon-bianji col-name-icon"
                  />
                </span>
                <bk-input
                  v-if="input.show"
                  :ref="'input' + key"
                  v-model="input.copyName"
                  v-bk-clickoutside="handleTagClickout"
                  style="width: 150px"
                  :maxlength="50"
                  @keydown="handleLabelKey"
                />
              </span>
              <span
                v-if="key === 'id'"
                class="detail-item-val"
              >
                {{ basicInfo[key] }}
              </span>
              <span
                v-if="key === 'label_info'"
                class="detail-item-val"
              >
                {{ basicInfo[key] }}
              </span>
              <span
                v-if="key === 'collect_type'"
                class="detail-item-val"
              >
                {{ basicInfo[key] }}
              </span>
              <template v-if="key === 'plugin_display_name'">
                <template v-if="basicInfo && basicInfo.collect_type !== 'Log'">
                  <span
                    v-bk-tooltips.top="basicInfo['plugin_id'] + '(' + basicInfo[key] + ')'"
                    class="detail-item-val plugin-id"
                  >
                    {{ basicInfo['plugin_id'] + '(' + basicInfo[key] + ')' }}
                  </span>
                  <i
                    v-if="!input.show"
                    v-authority="{ active: !authority.PLUGIN_MANAGE_AUTH }"
                    style="margin-top: -4px"
                    class="icon-monitor icon-bianji col-name-icon"
                    @click="handleToEditPlugin"
                  />
                </template>
                <span v-else>{{ basicInfo[key] }}</span>
              </template>
              <span
                v-if="key === 'period'"
                class="detail-item-val"
              >
                {{ basicInfo[key] }}s
              </span>
              <span
                v-if="key === 'update_user'"
                class="detail-item-val"
              >
                {{ basicInfo[key] }}
              </span>
              <span
                v-if="key === 'update_time'"
                class="detail-item-val"
              >
                {{ basicInfo[key] }}
              </span>
              <span
                v-if="key === 'bk_biz_id'"
                class="detail-item-val bizname"
              >
                {{ getBizInfo(basicInfo[key]) }}
              </span>
              <div
                v-if="key === 'log_path' || key === 'filter_patterns'"
                class="detail-item-log"
              >
                <template v-if="basicInfo[key].length">
                  <span
                    v-for="(word, index) in basicInfo[key]"
                    :key="index"
                  >
                    {{ word }}
                  </span>
                </template>
                <span v-else>--</span>
              </div>
              <span
                v-if="key === 'charset'"
                class="detail-item-val"
              >
                {{ basicInfo[key] }}
              </span>
              <div
                v-if="key === 'rules'"
                class="detail-item-log"
              >
                <span
                  v-for="(word, index) in basicInfo[key]"
                  :key="index"
                >
                  {{ `${word.name}=${word.pattern}` }}
                </span>
              </div>
              <template v-if="basicInfo && basicInfo.collect_type === 'Process'">
                <span
                  v-if="key === 'match'"
                  class="detail-item-val process"
                >
                  <template v-if="basicInfo[key] === 'command'">
                    <div class="match-title">{{ matchType[basicInfo[key]] }}</div>
                    <ul class="param-list">
                      <li class="param-list-item">
                        <span class="item-name">{{ $t('包含') }}</span>
                        <span class="item-content">{{ basicInfo.match_pattern }}</span>
                      </li>
                      <li class="param-list-item">
                        <span class="item-name">{{ $t('排除') }}</span>
                        <span class="item-content">{{ basicInfo.exclude_pattern }}</span>
                      </li>
                      <li class="param-list-item">
                        <span class="item-name">{{ $t('维度提取') }}</span>
                        <span class="item-content">{{ basicInfo.extract_pattern }}</span>
                      </li>
                    </ul>
                  </template>
                  <template v-else>
                    <div class="match-title">{{ matchType[basicInfo[key]] }}</div>
                    <div>{{ `${$t('PID的绝对路径')}：${basicInfo.pid_path}` }}</div>
                  </template>
                </span>
                <span
                  v-if="key === 'process_name'"
                  class="detail-item-val"
                >
                  {{ basicInfo[key] }}
                </span>
                <span
                  v-if="key === 'port_detect'"
                  class="detail-item-val"
                >
                  {{ basicInfo[key] }}
                </span>
              </template>
            </li>
          </ul>
          <div
            v-if="runtimeParams.length"
            class="param-label"
          >
            {{ $t('运行参数') }} :
          </div>
          <ul
            v-if="runtimeParams.length"
            class="param-list"
          >
            <li
              v-for="(item, index) in runtimeParams"
              :key="index"
              class="param-list-item"
            >
              <span class="item-name">{{ item.name }}</span>
              <span
                v-if="['password', 'encrypt'].includes(item.type)"
                class="item-content"
              >
                ******
              </span>
              <span
                v-else
                class="item-content"
              >
                {{ (item.type === 'file' ? item.value.filename : item.value) || '--' }}
              </span>
            </li>
          </ul>
          <div
            :style="{ marginTop: runtimeParams.length ? '24px' : '14px' }"
            class="metric-label"
          >
            {{ $t('预览') }} :
          </div>
          <right-panel
            v-for="(table, index) in metricList"
            :key="index"
            class="metric-wrap"
            :class="{ 'no-bottom': table.collapse }"
            :collapse="table.collapse"
            need-border
            @change="handleCollapseChange(index)"
          >
            <div
              slot="title"
              class="metric-wrap-title"
            >
              {{ getTitle(table) }}
            </div>
            <bk-table
              class="metric-wrap-table"
              :data="table.list"
              :empty-text="$t('无数据')"
            >
              <bk-table-column
                width="150"
                :label="$t('指标/维度')"
              >
                <template slot-scope="scope">
                  {{ scope.row.metric === 'metric' ? $t('指标（Metric）') : $t('维度（Dimension）') }}
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('英文名')"
                min-width="150"
              >
                <template slot-scope="scope">
                  <span :title="scope.row.englishName">{{ scope.row.englishName || '--' }}</span>
                </template>
              </bk-table-column>
              <bk-table-column
                :label="$t('别名')"
                min-width="150"
              >
                <template slot-scope="scope">
                  <span :title="scope.row.aliaName">{{ scope.row.aliaName || '--' }}</span>
                </template>
              </bk-table-column>
              <bk-table-column
                width="80"
                :label="$t('类型')"
              >
                <template slot-scope="scope">
                  <span :title="scope.row.type">{{ scope.row.type || '--' }}</span>
                </template>
              </bk-table-column>
              <bk-table-column
                width="100"
                :label="$t('单位')"
              >
                <template slot-scope="scope">
                  <span :title="scope.row.unit">{{ scope.row.unit || '--' }}</span>
                </template>
              </bk-table-column>
            </bk-table>
          </right-panel>
        </div>
        <div
          v-show="active === 1"
          class="collect-target"
        >
          <!-- <right-panel need-border> -->
          <!-- 复制目标 -->
          <div
            v-if="targetInfo.table_data && targetInfo.table_data.length"
            class="copy-target"
          >
            <bk-button
              :text="true"
              size="small"
              theme="primary"
              @click="handleCopyTarget"
              >{{ $t('复制目标') }}</bk-button
            >
          </div>
          <bk-table
            v-if="['TOPO', 'SET_TEMPLATE', 'SERVICE_TEMPLATE'].includes(targetInfo.target_node_type)"
            :data="targetInfo.table_data"
            :empty-text="$t('无数据')"
          >
            <bk-table-column
              width="140"
              :label="$t('节点名称')"
              prop="bk_inst_name"
            />
            <bk-table-column
              width="100"
              :label="basicInfo.target_object_type === 'SERVICE' ? $t('实例数') : $t('主机数')"
              align="right"
              prop="count"
            >
              <template slot-scope="scope">
                <div style="padding-right: 10px">
                  {{ scope.row.count }}
                </div>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('分类')"
              min-width="150"
            >
              <template slot-scope="scope">
                <template v-if="scope.row.labels.length">
                  <span
                    v-for="(item, index) in scope.row.labels"
                    :key="index"
                    class="classifiy-label"
                  >
                    <span class="label-name">{{ item.first }}</span>
                    <span class="label-name">{{ item.second }}</span>
                  </span>
                </template>
                <span v-else>--</span>
              </template>
            </bk-table-column>
          </bk-table>
          <bk-table
            v-else-if="targetInfo.target_node_type === 'INSTANCE'"
            :data="targetInfo.table_data"
            :empty-text="$t('无数据')"
          >
            <bk-table-column
              width="320"
              label="IP"
              prop="display_name"
              show-overflow-tooltip
            />
            <bk-table-column
              width="100"
              :label="$t('Agent状态')"
              prop="agent_status"
            >
              <template slot-scope="scope">
                <span :style="{ color: scope.row.agent_status === 'normal' ? '#2DCB56' : '#EA3636' }">
                  {{ scope.row.agent_status === 'normal' ? $t('正常') : $t('异常') }}
                </span>
              </template>
            </bk-table-column>
            <bk-table-column
              :label="$t('管控区域')"
              min-width="150"
            >
              <template slot-scope="scope">
                <span :title="scope.row.bk_cloud_name">{{ scope.row.bk_cloud_name || '--' }}</span>
              </template>
            </bk-table-column>
          </bk-table>
          <!-- </right-panel> -->
        </div>
      </div>
    </div>
  </bk-sideslider>
</template>
<script>
import { frontendCollectConfigDetail, renameCollectConfig } from 'monitor-api/modules/collecting';
import { copyText } from 'monitor-common/utils/utils.js';

import HistoryDialog from '../../../components/history-dialog/history-dialog';
import RightPanel from '../../../components/ip-select/right-panel';
import { PLUGIN_MANAGE_AUTH } from '../authority-map';

export default {
  name: 'CollectorConfigDetail',
  components: {
    RightPanel,
    HistoryDialog,
  },
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    sideData: {
      type: Object,
      default() {
        return {};
      },
    },
    sideShow: Boolean,
  },
  data() {
    return {
      active: 0,
      loading: false,
      basicInfo: null,
      metricList: [],
      runtimeParams: [],
      targetInfo: {},
      basicInfoMap: {
        name: this.$t('配置名称'),
        id: 'ID',
        label_info: this.$t('对象'),
        collect_type: this.$t('采集方式'),
        plugin_display_name: this.$t('插件'),
        period: this.$t('采集周期'),
        update_user: this.$t('操作者'),
        update_time: this.$t('最近更新时间'),
        bk_biz_id: this.$t('所属'),
      },
      input: {
        show: false,
        copyName: '',
      },
      name: '',
      matchType: {
        command: this.$t('命令行匹配'),
        pid: this.$t('PID文件'),
      },
    };
  },
  computed: {
    bizList() {
      return this.$store.getters.bizList;
    },
    historyList() {
      if (!this.basicInfo) return [];
      return [
        { label: this.$t('创建人'), value: this.basicInfo.create_user || '--' },
        { label: this.$t('创建时间'), value: this.basicInfo.create_time || '--' },
        { label: this.$t('最近更新人'), value: this.basicInfo.update_user || '--' },
        { label: this.$t('修改时间'), value: this.basicInfo.update_time || '--' },
      ];
    },
  },
  watch: {
    sideShow(v) {
      v ? this.getDetailData() : this.handleHidden();
    },
  },
  created() {
    // this.getDetailData();
  },
  beforeDestroy() {
    this.handleHidden();
  },
  methods: {
    getBizInfo(id) {
      const item = this.bizList.find(i => i.id === id) || {};
      return item ? `${item.text}(${item.type_name})` : '--';
    },
    getDetailData() {
      if (!this.sideShow) return;
      this.loading = true;
      frontendCollectConfigDetail({ id: this.sideData.id })
        .then(data => {
          const sideDataId = { id: this.sideData.id };
          this.basicInfo = { ...data.basic_info, ...sideDataId };
          if (data.extend_info.log) {
            this.basicInfo = { ...this.basicInfo, ...data.extend_info.log };
            !this.basicInfo.filter_patterns && (this.basicInfo.filter_patterns = []);
            this.basicInfoMap = {
              ...this.basicInfoMap,
              log_path: this.$t('日志路径'),
              filter_patterns: this.$t('排除规则'),
              rules: this.$t('关键字规则'),
              charset: this.$t('日志字符集'),
            };
          }
          if (data.extend_info.process) {
            const { process: processInfo } = data.extend_info;
            this.basicInfoMap = {
              ...this.basicInfoMap,
              match: this.$t('进程匹配'),
              process_name: this.$t('进程名'),
              port_detect: this.$t('端口探测'),
            };
            const {
              match_type: matchType,
              process_name: processName,
              port_detect: portDetect,
              match_pattern: matchPattern,
              exclude_pattern: excludePattern,
              extract_pattern: extractPattern,
              pid_path: pidPath,
            } = processInfo;
            this.basicInfo = {
              ...this.basicInfo,
              match: matchType,
              match_pattern: matchPattern,
              exclude_pattern: excludePattern,
              extract_pattern: extractPattern,
              pid_path: pidPath,
              process_name: processName || '--',
              port_detect: `${portDetect}`,
            };
          }
          data.metric_list.forEach((item, index) => {
            item.collapse = index === 0;
          });
          this.metricList = data.metric_list;
          this.runtimeParams = data.runtime_params;
          this.targetInfo = data.target_info;
          this.input.copyName = data.basic_info.name;
          this.name = data.basic_info.name;
        })
        .catch(err => {
          this.$bkMessage({
            theme: 'error',
            message: err.message || this.$t('获取数据出错了'),
          });
          this.$emit('set-hide', false);
        })
        .finally(() => {
          this.loading = false;
        });
    },
    handleHidden() {
      this.name = '';
      this.$emit('set-hide', false);
    },
    handleCollapseChange(v) {
      this.metricList.forEach((item, index) => {
        if (index === v) {
          item.collapse = !item.collapse;
        } else {
          item.collapse = false;
        }
      });
    },
    handleLabelKey(v, e) {
      if (e.code === 'Enter' || e.code === 'NumpadEnter') {
        this.handleTagClickout();
      }
    },
    handleTagClickout() {
      const data = this.basicInfo;
      const { copyName } = this.input;
      if (copyName.length && copyName !== data.name) {
        this.handleUpdateConfigName(data, copyName);
      } else {
        data.copyName = data.name;
        this.input.show = false;
      }
    },
    handleEditLabel(key) {
      this.input.show = true;
      this.$nextTick().then(() => {
        this.$refs[`input${key}`][0].focus();
      });
    },
    handleUpdateConfigName(data, copyName) {
      this.loading = true;
      renameCollectConfig({ id: data.id, name: copyName }, { needMessage: false })
        .then(() => {
          this.basicInfo.name = copyName;
          this.name = copyName;
          this.$emit('update-name', data.id, copyName);
          this.$bkMessage({
            theme: 'success',
            message: this.$t('修改成功'),
          });
        })
        .catch(err => {
          this.$bkMessage({
            theme: 'error',
            message: err.message || this.$t('发生错误了'),
          });
        })
        .finally(() => {
          this.input.show = false;
          this.loading = false;
        });
    },
    handleToEditPlugin() {
      if (!this.authority.PLUGIN_MANAGE_AUTH) {
        this.handleShowAuthorityDetail(PLUGIN_MANAGE_AUTH);
      } else {
        this.$emit('edit-plugin', this.basicInfo);
      }
    },
    handleToEdit() {
      this.$emit('edit', this.basicInfo.id);
    },
    getTitle(table) {
      if (this.$i18n.locale !== 'enUS') {
        return `${table.id}（${table.name}）`;
      }
      return table.id;
    },
    handleCopyTarget() {
      let copyStr = '';
      if (['TOPO', 'SET_TEMPLATE', 'SERVICE_TEMPLATE'].includes(this.targetInfo.target_node_type)) {
        this.targetInfo.table_data.forEach(item => {
          copyStr += `${item.bk_inst_name}\n`;
        });
      } else if (this.targetInfo.target_node_type === 'INSTANCE') {
        this.targetInfo.table_data.forEach(item => {
          copyStr += `${item.display_name || item.ip}\n`;
        });
      }
      copyText(copyStr, msg => {
        this.$bkMessage({
          message: msg,
          theme: 'error',
        });
        return;
      });
      this.$bkMessage({
        message: this.$t('复制成功'),
        theme: 'success',
      });
    },
    handleJump() {
      this.$router.push({
        name: 'collect-config-view',
        params: {
          id: this.basicInfo.id,
          title: this.basicInfo.name,
        },
        query: {
          name: this.basicInfo.name,
          customQuery: JSON.stringify({
            pluginId: this.basicInfo.pluginId,
            bizId: this.basicInfo.bk_biz_id,
          }),
        },
      });
    },
  },
};
</script>
<style lang="scss" scoped>
.collector-config-detail {
  .detail-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-right: 24px;

    &-title {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;

      .hint-alert {
        display: inline-block;
        background: #fff;
        border-color: transparent;

        :deep(.icon-info) {
          margin-right: 5px;
          color: #979ba5;
        }
      }
    }

    .operation {
      font-size: 0;
    }
  }

  .detail-content {
    height: calc(100vh - 80px);
    padding: 18px 30px;
    overflow: auto;
    font-size: 12px;
    color: #63656e;
    background: #fff;

    &-tab {
      display: flex;
      align-items: center;
      height: 36px;
      font-size: 12px;
      color: #63656e;
      border-bottom: 1px solid #dcdee5;

      .tab-item {
        display: flex;
        flex: 0 0 auto;
        align-items: center;
        justify-content: center;
        min-width: 80px;
        height: 36px;
        cursor: pointer;
        border-bottom: 2px solid transparent;

        &.tab-active {
          color: #3a84ff;
          border-bottom-color: #3a84ff;
        }
      }
    }

    &-wrap {
      padding-top: 17px;

      .basic-info {
        &-detail {
          overflow: hidden;

          .detail-item {
            display: flex;
            align-items: flex-start;
            float: left;
            width: 100%;
            min-height: 20px;
            margin-bottom: 10px;

            &-val {
              padding-top: 2px;

              .name-wrapper {
                display: flex;
                align-items: flex-start;
                width: 210px;
              }

              .config-name {
                display: inline-block;
                max-width: calc(100% - 24px);
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
              }

              &.bizname {
                margin-top: -2px;
              }

              &.process {
                display: block;
                width: 100%;
                margin-top: -2px;

                .match-title {
                  margin-bottom: 10px;
                }
              }
            }

            &-log {
              display: flex;
              flex-direction: column;
            }

            &-label {
              display: inline-block;
              min-width: 86px;
              margin-right: 14px;
              color: #979ba5;
              text-align: right;
            }

            &:last-child::after {
              clear: both;
              zoom: 1;
              content: ' ';
            }

            &-name {
              padding-top: 10px;
            }
          }

          .plugin-id {
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
          }

          .col-name-icon {
            font-size: 24px;
            color: #dcdee5;

            &:hover {
              color: #3a84ff;
              cursor: pointer;
            }
          }
        }

        .param-label,
        %param-label {
          margin: 14px 0 10px;
          color: #979ba5;
        }

        .param-list {
          border: 1px solid #dcdee5;
          border-radius: 2px;

          &-item {
            display: flex;
            align-items: center;

            &:not(:last-child) {
              border-bottom: 1px solid #dcdee5;
            }

            .item-name {
              width: 50%;
              height: 30px;
              padding-left: 20px;
              line-height: 32px;
              color: #979ba5;
              background: #fafbfd;
              border-right: 1px solid #dcdee5;
            }

            .item-content {
              width: 50%;
              padding-left: 20px;
            }
          }
        }

        .metric-label {
          margin-top: 24px;

          @extend %param-label;
        }

        .metric-wrap {
          margin-bottom: 10px;

          &.no-bottom {
            border-bottom: 0;
          }

          &-title {
            line-height: 14px;
          }
        }
      }

      .collect-target {
        .classifiy-label {
          display: inline-block;
          margin: 3px;
          font-size: 12px;
          background: #fafbfd;
          border: 1px solid #dcdee5;
          border-radius: 2px;

          .label-name {
            display: inline-block;
            height: 24px;
            padding: 0 7px;
            line-height: 24px;
            text-align: center;

            &:first-child {
              background: #fff;
              border-right: 1px solid #dcdee5;
            }
          }
        }

        .copy-target {
          display: flex;
          margin-bottom: 10px;
        }
      }
    }
  }
}
</style>
