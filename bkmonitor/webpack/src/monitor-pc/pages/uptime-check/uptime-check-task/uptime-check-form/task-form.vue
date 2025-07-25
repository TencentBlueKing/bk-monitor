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
    v-bkloading="{ isLoading: isLoading }"
    class="task-form"
  >
    <div class="task-form-content">
      <section v-show="!formDone.show">
        <div class="uptime-form-item">
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('所属') }}
          </div>
          <div class="item-container">
            <bk-select
              v-model="task.business"
              class="reset-width"
              :clearable="false"
              :disabled="ccBizId !== 0"
              @change="handleChangeBiz"
            >
              <bk-option
                v-for="item in filterBizList"
                :id="item.id"
                :key="item.id"
                :name="item.text"
              />
            </bk-select>
            <span
              v-show="requiredOptions.business"
              class="validate-hint"
            >
              {{ $t('选择所属空间') }}
            </span>
          </div>
        </div>
        <div class="uptime-form-item">
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('任务名称') }}
          </div>
          <div class="item-container">
            <verify-input
              class="reset-width"
              :show-validate.sync="requiredOptions.name"
              :validator="{ content: nameErrorMsg }"
            >
              <!-- <bk-input v-model="task.name" @blur="requiredOptions.name = !Boolean(task.name)"></bk-input> -->
              <bk-input
                v-model.trim="task.name"
                @blur="validateName"
              />
            </verify-input>
          </div>
        </div>
        <div class="uptime-form-item">
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('协议') }}
          </div>
          <div class="item-container">
            <bk-radio-group
              v-model="protocol.value"
              @change="handleChangeProtocol"
            >
              <bk-radio
                v-for="(item, index) in protocol.data"
                :key="index"
                class="protocol-radio"
                :value="item"
              >
                <span
                  v-if="item !== 'ICMP'"
                  style="font-size: 12px"
                  >{{ item === 'HTTP' ? `${item}(S)` : item }}</span
                >
                <span
                  v-else
                  v-bk-tooltips.bottom="$t('功能依赖1.10.x及以上版本的bkmonitorbeat')"
                  style="font-size: 12px"
                  class="radio-icmp-tips"
                >
                  {{ item }}
                </span>
              </bk-radio>
            </bk-radio-group>
          </div>
        </div>
        <div class="uptime-form-item http-selector-wrap">
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('目标') }}
          </div>
          <div class="item-container">
            <http-target
              v-if="protocol.value === 'HTTP'"
              :method="httpTarget.method"
              :urls="httpTarget.url_list"
              @methodChange="handleHttpMethodChange"
              @urlChange="handleHttpUrlChange"
            />
            <tcp-target
              v-else
              ref="tcpTarget"
              :default-value="tcpTarget"
              @addTarget="handleAddTcpTarget"
            />
            <div
              v-show="requiredOptions.target"
              :style="{ color: '#f56c6c' }"
              class="item-container-tips"
            >
              {{ $t('添加拨测目标') }}
            </div>
          </div>
        </div>
        <div
          v-if="protocol.value === 'HTTP'"
          class="uptime-form-item http-selector-wrap"
        >
          <div
            v-en-class="'mw-170'"
            class="item-label"
          >
            {{ $t('参数设置') }}
          </div>
          <div class="item-container">
            <http-editor
              ref="http-selector"
              :key="httpEditorKey"
              class="http-selector"
              :is-edit="true"
              :method-list="methodList"
              :need-settings="false"
              :value="httpConfig"
              behavior="normal"
              need-ssl-checkbox
              @change="handleHttpConfigChange"
            />
          </div>
        </div>
        <div
          v-show="protocol.value === 'HTTP' && task.method === 'POST'"
          class="uptime-form-item submit-content"
        >
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('提交内容') }}
          </div>
          <div class="item-container">
            <bk-input
              v-model="task.submitContent"
              class="reset-width"
              placeholder='发送的内容格式：k1=v1;k2=v2，或者一段JSONObject，如: {"key":"value"}'
              type="textarea"
              @blur="requiredOptions.submitContent = !Boolean(task.submitContent)"
              @focus="requiredOptions.submitContent = false"
            />
            <span
              v-show="requiredOptions.submitContent"
              class="validate-hint"
            >
              {{ $t('填写提交内容') }}
            </span>
          </div>
        </div>
        <div
          v-show="protocol.value !== 'HTTP' && protocol.value !== 'ICMP'"
          class="uptime-form-item"
        >
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('端口') }}
          </div>
          <div class="item-container">
            <verify-input
              class="reset-width"
              :show-validate.sync="requiredOptions.port"
              :validator="{ content: $t('输入合法的端口') }"
            >
              <bk-input
                v-model="task.port"
                :max="65535"
                :min="1"
                :show-controls="true"
                type="number"
                @blur="validatePort"
              />
            </verify-input>
          </div>
        </div>
        <div
          v-show="protocol.value === 'UDP'"
          class="uptime-form-item"
        >
          <div
            v-en-class="'mw-170'"
            class="item-label"
          >
            {{ $t('请求内容') }}
          </div>
          <div class="item-container request">
            <verify-input
              :show-validate.sync="requiredOptions.requestContent"
              :validator="{ content: $t('输入合法的十六进制请求内容') }"
            >
              <bk-compose-form-item>
                <bk-select
                  v-model="requestFormat"
                  style="width: 92px"
                  :clearable="false"
                  @change="() => validateRequestContent(task.requestContent)"
                >
                  <bk-option
                    v-for="item in resFormatOptions"
                    :id="item.id"
                    :key="item.id"
                    :name="item.name"
                  />
                </bk-select>
                <bk-input
                  v-model="task.requestContent"
                  class="request-width"
                  :placeholder="
                    $t(requestFormat === 'hex' ? '十六进制的请求内容，如3a47534b422d644c' : '原始请求内容, 如echo')
                  "
                  @blur="() => validateRequestContent(task.requestContent)"
                />
              </bk-compose-form-item>
            </verify-input>
          </div>
        </div>
        <div class="uptime-form-item">
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('拨测节点') }}
          </div>
          <div class="item-container">
            <verify-input
              :show-validate.sync="requiredOptions.nodes"
              :validator="{ content: $t('选择拨测节点') }"
            >
              <bk-select
                ref="taskNodeSelect"
                v-model="task.nodes"
                class="reset-width"
                :clearable="false"
                :loading="nodeListLoading"
                :multiple="true"
                @change="() => (requiredOptions.nodes = false)"
              >
                <bk-option
                  v-for="item in node[task.business]"
                  :id="item.id"
                  :key="item.id"
                  :disabled="Boolean(item.status === '-1')"
                  :name="item.name + ' ' + item.ip"
                >
                  <div class="node-option">
                    <span>{{ item.name + ' ' + item.ip }}</span>
                    <span v-if="!!item.version">v{{ item.version }}</span>
                  </div>
                </bk-option>
                <div
                  slot="extension"
                  class="item-input-create"
                  @click="handleCreateTaskNode"
                >
                  <i class="bk-icon icon-plus-circle" />{{ $t('新建拨测节点') }}
                </div>
              </bk-select>
            </verify-input>
          </div>
        </div>
        <div class="uptime-form-item">
          <div
            v-en-class="'mw-170'"
            class="item-label item-required"
          >
            {{ $t('超时设置') }}
          </div>
          <div class="item-container timeout">
            <verify-input
              :show-validate.sync="requiredOptions.timeout"
              :validator="timeoutValidate"
            >
              <bk-input
                v-model.number="task.timeout"
                style="width: 120px"
                type="number"
                @blur="handleValidateTimeout"
              >
                <div
                  slot="append"
                  class="unit"
                >
                  ms
                </div>
              </bk-input>
            </verify-input>
            <div
              v-bk-tooltips.top="$t('超过该时长未正常采集数据时，系统判定该任务为不可用状态！')"
              class="hint-icon"
            >
              <span class="icon-monitor icon-tips icon" />
            </div>
          </div>
        </div>
        <div class="uptime-form-item last-item">
          <div
            v-en-class="'mw-170'"
            class="item-label group"
          >
            {{ $t('任务组') }}
          </div>
          <div class="item-container">
            <bk-select
              v-model="task.groups"
              class="reset-width"
              :multiple="true"
              :placeholder="$t('选择想要加入的任务组')"
            >
              <bk-option
                v-for="item in groupList"
                :id="item.id"
                :key="item.id"
                class="reset-width"
                :name="item.name"
              />
            </bk-select>
          </div>
        </div>
        <div class="uptime-form-item text-item">
          <div
            v-en-class="'mw-170'"
            class="item-label"
          />
          <div class="item-container item-advance">
            <bk-button
              style="font-size: 12px"
              text
              @click="isShowAdvanced = !isShowAdvanced"
            >
              {{ isShowAdvanced ? $t('隐藏高级选项') : $t('显示高级选项') }}
            </bk-button>
          </div>
        </div>
        <!-- 高级选项 -->
        <transition name="advanced-option-fade">
          <div
            v-show="isShowAdvanced"
            class="uptime-form-item advanced-option"
          >
            <advanced-option
              ref="advancedRef"
              :options="advancedOptions"
              :protocol="protocol.value"
            />
          </div>
        </transition>
        <div class="uptime-form-item">
          <div
            v-en-class="'mw-170'"
            class="item-label"
          />
          <div class="item-container">
            <bk-button
              v-authority="{ active: !authority.MANAGE_AUTH }"
              class="btn-submit"
              :disabled="nodeListLoading || isLoading || isSubmit"
              :icon="isSubmit ? 'loading' : ''"
              theme="primary"
              @click="authority.MANAGE_AUTH ? submit() : handleShowAuthorityDetail()"
            >
              {{ submitBtnText }}
            </bk-button>
            <bk-button @click="cancel">
              {{ $t('取消') }}
            </bk-button>
          </div>
        </div>
      </section>
      <polling-loading
        :show.sync="pollingObj.show"
        :status="pollingObj.status"
      />
      <section v-show="formDone.show">
        <task-form-done
          :edit-id="toEditId"
          :error-msg="formDone.errorMsg"
          :status="formDone.status"
          :table-data="formDone.data"
          :type="operatorType"
          @back-add="handleBackToAdd"
          @clear-task-data="handleClearTaskData"
          @enforce-save="handleEnforceSave"
        />
      </section>
    </div>
  </div>
</template>
<script>
import HttpEditor from 'fta-solutions/pages/setting/set-meal/set-meal-add/components/http-editor/http-editor';
import {
  createUptimeCheckTask,
  deployUptimeCheckTask,
  listUptimeCheckGroup,
  listUptimeCheckNode,
  retrieveUptimeCheckTask,
  runningStatusUptimeCheckTask,
  testUptimeCheckTask,
  updateUptimeCheckTask,
} from 'monitor-api/modules/model';
import { random, transformDataKey } from 'monitor-common/utils/utils';

import PollingLoading from '../../../../components/polling-loading/polling-loading';
import VerifyInput from '../../../../components/verify-input/verify-input';
import authorityMixinCreate from '../../../../mixins/authorityMixin';
import { SET_NAV_ROUTE_LIST } from '../../../../store/modules/app';
import { allSpaceRegex, emojiRegex } from '../../../../utils/index';
import * as uptimeAuth from '../../authority-map';
import AdvancedOption, { RESPONSE_FORMAT_OPTIONS } from './advanced-option';
import HttpTarget from './http-target';
import TaskFormDone from './task-form-done';
import TcpTarget from './tcp-target';

export default {
  name: 'TaskForm',
  components: {
    AdvancedOption,
    VerifyInput,
    TaskFormDone,
    PollingLoading,
    HttpEditor,
    HttpTarget,
    TcpTarget,
  },
  mixins: [authorityMixinCreate(uptimeAuth)],
  beforeRouteEnter(to, from, next) {
    next(vueModule => {
      const vm = vueModule;
      if (!Object.keys(vm.backup || {}).length) {
        !vm.isLoading && vm.handleInitTaskForm();
      } else if (vm.id) {
        vm.updateNav(`${vm.$t('编辑')} - ${vm.task.name}`);
      }
      if (from.name === 'uptime-check-node-add' || from.name === 'uptime-check') {
        vm.isLoading = true;
        vm.getNodeList();
      }
    });
  },
  beforeRouteLeave(to, from, next) {
    this.formDone = {
      show: false,
      status: 'success',
      errorMsg: '',
      data: [],
    };
    if (to.name !== 'uptime-check-node-add') {
      this.backup = {};
      this.advancedOptions = {};
      this.isShowAdvanced = false;
      this.httpTarget = {
        url_list: [],
        method: 'GET',
      };
      this.tcpTarget = {
        ip_list: [],
        url_list: [],
        node_list: [],
        target_ip_type: 0,
        dns_check_mode: 'all',
      };
    }
    next();
  },
  props: {
    id: [Number, String],
  },
  data() {
    return {
      task: {
        business: Number.parseInt(this.$store.getters.bizId, 10),
      },
      backup: {},
      taskInfo: {},
      protocol: {
        data: ['HTTP', 'TCP', 'UDP', 'ICMP'],
        value: 'HTTP',
      },
      requiredOptions: {
        business: false,
        name: false,
        timeout: false,
        nodes: false,
        urls: false,
        port: false,
        requestContent: false,
        submitContent: false,
        target: false,
      },
      nameErrorMsg: '',
      isShowAdvanced: false,
      advancedOptions: {},
      ccBizId: Number.parseInt(this.$store.getters.bizId, 10),
      // 拨测节点信息
      node: {},
      groupList: [],
      isSubmit: false,
      isLoading: false,
      formDone: {
        show: false,
        status: 'success',
        errorMsg: '',
        data: [],
      },
      uptimeCheckMetricMap: {
        task_duration: this.$t('响应时间'),
        response_code: this.$t('期望响应码'),
        message: this.$t('期望响应内容'),
        available: this.$t('单点可用率'),
      },
      createprocess: {
        isCreate: false,
        id: '',
      },
      pollingObj: {
        status: {
          failMsg: '',
          msg: '',
        },
        show: false,
      },
      toEditId: '',
      methodList: ['GET', 'POST', 'DELETE', 'PUT', 'PATCH'],
      httpConfig: null,
      httpEditorKey: random(10),
      resFormatOptions: RESPONSE_FORMAT_OPTIONS,
      requestFormat: 'hex',
      httpTarget: {
        url_list: [],
        method: 'GET',
      },
      tcpTarget: {
        ip_list: [],
        url_list: [],
        node_list: [],
        target_ip_type: 0,
        dns_check_mode: 'all',
      },
      // 该变量记录上一个访问 拔测节点 数据的 id，避免重复请求。
      previousBizId: -1,
      nodeListLoading: false,
    };
  },
  computed: {
    filterBizList() {
      return this.$store.getters.bizList.filter(item => +item.bk_biz_id === +this.task.business);
    },
    submitBtnText() {
      if (!this.isSubmit) {
        return this.$t('提交');
      }
      return this.id ? this.$t('编辑中...') : this.$t('创建中...');
    },
    operatorType() {
      return this.id ? 'edit' : 'add';
    },
    maxAvailableDurationLimit() {
      return this.$store.getters.maxAvailableDurationLimit;
    },
    timeoutValidate() {
      return {
        content:
          `${this.$t('设置超时时间')}，${this.$t('最小值:')}0ms (${this.$t('不包含')})` +
          `，${this.$t('最大值：{limit}ms', this.maxAvailableDurationLimit)}`,
      };
    },
  },
  watch: {
    id: {
      handler() {
        !this.isLoading && this.handleInitTaskForm();
      },
    },
  },
  methods: {
    handleHttpUrlChange(v) {
      this.httpTarget.url_list = v;
      this.requiredOptions.target = false;
    },
    handleHttpMethodChange(v) {
      this.httpTarget.method = v;
      this.httpConfig.method = v;
    },
    handleBackToAdd() {
      this.formDone.show = false;
      this.setDefaultData();
    },
    async handleInitTaskForm() {
      this.isLoading = true;
      const id = this.$route.query.taskId || this.id;
      this.updateNav(this.$t('加载中...'));
      this.generationFormField();
      this.handleSetBusiness();
      this.getNodeList();
      await listUptimeCheckGroup()
        .then(data => {
          this.groupList = data;
        })
        .catch(() => {
          this.isLoading = false;
        });
      if (!Array.isArray(this.task.groups)) {
        this.task.groups = [];
      }
      if (this.$route.params.groupName) {
        const item = this.groupList.find(item => item.name === this.$route.params.groupName);
        item && this.task.groups.push(item.id);
      }
      if (this.$route.query.groupId) {
        const item = this.groupList.find(item => item.id === Number(this.$route.query.groupId));
        item && this.task.groups.push(item.id);
      }
      // 基于当前的配置信息进行拨测任务的新建
      // 获取当前task数据
      if (id) {
        await this.getTaskInfo(id);
        if (this.$route.query.taskId) {
          this.updateNav(this.$t('route-新建拨测任务'));
        } else {
          this.updateNav(`${this.$t('编辑')} - ${this.task.name}`);
        }
      } else {
        this.updateNav(this.$t('route-新建拨测任务'));
      }
      this.isLoading = false;
    },
    cancel() {
      this.$router.back();
    },
    handleChangeBiz() {
      this.getNodeList();
    },
    handleChangeProtocol(val) {
      this.task = {
        ...this.backup[val],
        business: this.task.business,
        name: this.task.name || '',
        groups: this.task.groups || [],
        nodes: this.task.nodes || [],
        timeout: this.task.timeout || 3000,
      };
      if (!this.task.business) {
        this.task.business = +this.$store.getters.bizId;
      }
      if (this.requiredOptions.timeout) {
        this.requiredOptions.timeout = false;
      }
    },
    generationFormField() {
      const tpl = {
        business: '',
        protocol: 'HTTP',
        name: '',
        method: 'GET',
        urls: '',
        submitContent: '',
        port: '',
        nodes: [],
        requestContent: '',
        timeout: 3000,
        groups: [],
        target: [],
      };
      const protocols = ['HTTP', 'TCP', 'UDP', 'ICMP'];
      protocols.forEach(item => {
        tpl.protocol = item;
        this.backup[item] = JSON.parse(JSON.stringify(tpl));
      });
      this.task = this.backup.HTTP;
      this.httpConfig = null;
      this.httpEditorKey = random(10);
    },
    /** 校验请求数据格式 */
    validateRequestContent(requestContent, hasReturn = false) {
      let isFailed = false;
      if (!!requestContent && this.requestFormat === 'hex') {
        isFailed = Boolean(requestContent.length % 2) || !/^[a-fA-F0-9]+$/.test(requestContent.trim());
      } else {
        this.requiredOptions.requestContent = false;
      }
      if (!hasReturn) {
        this.requiredOptions.requestContent = isFailed;
      } else {
        return !isFailed;
      }
    },
    // 获取拨测节点信息
    getNodeList() {
      if (this.previousBizId === Number(this.task.business)) return Promise.resolve();
      this.previousBizId = Number(this.task.business);
      this.nodeListLoading = true;
      listUptimeCheckNode({ bk_biz_id: this.task.business })
        .then(data => {
          this.$set(this.node, `${this.task.business}`, data);
          const curNode = this.node[this.task.business].map(item => item.id);
          const len = this.task.nodes.length - 1;
          for (let i = len; i >= 0; i--) {
            if (!curNode.includes(this.task.nodes[i])) {
              this.task.nodes.splice(i, 1);
            }
          }
          this.$route.params?.taskId && this.task.nodes.push(this.$route.params.taskId);
          this.isLoading = false;
          return data;
        })
        .catch(err => err)
        .finally(() => {
          this.nodeListLoading = false;
        });
    },
    // 获取任务组信息
    getGroupList() {
      return listUptimeCheckGroup().then(data => {
        this.groupList = data;
      });
    },
    updateNav(name = '') {
      const routeList = [
        {
          name,
          id: '',
        },
      ];
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
    },
    async getTaskInfo(id) {
      const data = await retrieveUptimeCheckTask(id).catch(() => {
        this.isLoading = false;
      });
      if (!data) {
        this.$bkMessage({
          theme: 'error',
          message: this.$t('没有找到对应的数据'),
        });
        this.$router.push({
          name: 'uptime-check',
        });
      } else {
        this.backFillData({ ...data, name: this.$route.query.taskId ? '' : data.name });
        !this.$route.query.taskId && this.updateNav(`${this.$t('编辑')} - ${data.name}`);
      }
    },
    submit() {
      if (!this.validate(this.protocol.value)) {
        this.isSubmit = true;
        // 提交必须经过以下步骤：测试 -> 保存 -> 部署
        const params = this.getParams(this.protocol.value);
        // 无论参数是否变更，都走一样的流程
        this.handleCreateTaskSubmit(params);
      }
    },
    // 创建task时提交流程
    async handleCreateTaskSubmit(params, isEnforceSave = false) {
      const startTime = +new Date();
      if (!isEnforceSave) {
        this.toEditId = '';
        this.pollingObj.status.msg = this.$t('下发中...');
        // 测试
        const testResult = await this.test(params);
        if (!testResult) return (this.pollingObj.show = false);
      }
      // 保存
      const saveStatus = await this.save(this.getParams(this.protocol.value, 'SAVE'));
      this.formDone.data = this.getMetricDataFromData(saveStatus);
      // 发布
      const depolyRes = await this.depoly(saveStatus.id).catch(() => false);
      if (depolyRes && !depolyRes.result) {
        // 发布失败
        this.toEditId = saveStatus.id;
        return this.showErrorPage(depolyRes.message);
      }
      this.pollingObj.show = true;
      // 轮训拨测任务状态
      const polling = (taskId, callBack) => {
        const nowTime = +new Date();
        // 发布五分钟超时
        const isTimeout = (nowTime - startTime) / 1000 / 60 > 5;
        if (isTimeout) {
          this.toEditId = saveStatus.id;
          return callBack({ status: 'timeout', message: this.$t('下发拨测任务超时') });
        }
        runningStatusUptimeCheckTask(taskId)
          .then(data => {
            if (data.status === 'running' || data.status === 'start_failed') {
              data.status === 'start_failed' && (this.toEditId = saveStatus.id);
              callBack(data);
            } else {
              // 轮询事件间隔10S
              const timer = setTimeout(() => {
                polling(taskId, callBack);
                clearTimeout(timer);
              }, 10000);
            }
          })
          .catch(err => {
            callBack(err);
          });
      };
      polling(saveStatus.id, res => {
        this.pollingObj.show = false;
        // 拨测服务发布成功
        if (res.status === 'running') {
          this.$bkMessage({
            theme: 'success',
            message: this.$t('部署成功'),
          });
          this.isSubmit = false;
          this.formDone.status = 'success';
          this.formDone.show = true;
        } else {
          const msg = this.handleErrorMessage(res);
          this.showErrorPage(msg);
        }
      });
    },
    handleErrorMessage(res) {
      let errorMsg = '';
      if (res.error_log?.length) {
        errorMsg = res.error_log.reduce((pre, item) => (pre += `${item}<br/>`), '');
      } else {
        errorMsg = res.message || '';
      }
      return errorMsg;
    },
    showErrorPage(msg) {
      this.pollingObj.show = false;
      this.isLoading = false;
      this.isSubmit = false;
      this.formDone.status = 'error';
      this.formDone.errorMsg = msg;
      this.formDone.show = true;
    },
    /**
     * 检查配置是否有更改
     */
    validateChange(newData, oldData) {
      delete oldData.location;
      const newKeys = Object.keys(newData);
      const oldKeys = Object.keys(oldData);
      if (newKeys.length !== oldKeys.length) {
        return true;
      }
      for (let i = 0; i < newKeys.length; i++) {
        const key = newKeys[i];
        const newVal = newData[key];
        const oldVal = oldData[key];
        if (typeof newVal !== 'undefined' && typeof oldVal === 'undefined') {
          return true;
        }
        if (typeof newVal === 'string' || typeof newVal === 'number' || typeof newVal === 'boolean') {
          if (newVal !== oldVal) {
            return true;
          }
        } else if (key === 'nodes' && Array.isArray(newVal) && Array.isArray(oldVal)) {
          const newNodes = newVal.sort((a, b) => a - b).join('');
          const oldNodes = oldVal.sort((a, b) => a - b).join('');
          if (newNodes !== oldNodes) {
            return true;
          }
        } else if (key === 'headers') {
          const newHeaders = JSON.stringify(newVal);
          const oldHeaders = JSON.stringify(oldVal);
          if (newHeaders !== oldHeaders) {
            return true;
          }
        }
      }
      return false;
    },
    test(params) {
      return testUptimeCheckTask(params, { needMessage: false }).catch(err => {
        this.isLoading = false;
        this.isSubmit = false;
        this.formDone.status = 'error';
        this.formDone.errorMsg = err.message || '';
        this.formDone.show = true;
      });
    },
    save(params) {
      const id = this.createprocess.isCreate ? this.createprocess.id : this.id;
      const ajaxFn = id
        ? updateUptimeCheckTask(id, params, { needMessage: false })
        : createUptimeCheckTask(params, { needMessage: false });
      return ajaxFn.catch(err => {
        this.isLoading = false;
        this.isSubmit = false;
        this.formDone.errorMsg = err.message || err.data.message || '';
        this.formDone.status = 'error';
        this.formDone.show = true;
      });
    },
    depoly(id) {
      return deployUptimeCheckTask(id, {}, { needRes: true })
        .then(res => Promise.resolve(res))
        .catch(err => {
          if (!this.id) {
            this.createprocess.isCreate = true;
            this.createprocess.id = id;
          }
          this.pollingObj.show = false;
          this.isLoading = false;
          this.isSubmit = false;
          this.formDone.errorMsg = err.message || err.data.message || '';
          this.formDone.status = 'error';
          this.formDone.show = true;
          return Promise.reject(err);
        });
    },
    getConfig(advanced) {
      const config = {
        period: advanced.period,
        ...this.$refs.tcpTarget?.getValue(),
      };
      if (this.protocol.value === 'ICMP') {
        config.max_rtt = this.task.timeout;
        config.total_num = advanced.total_num;
        config.size = advanced.size;
        return config;
      }
      config.timeout = this.task.timeout;
      config.response = advanced.response || '';
      config.response_format = advanced.response_format;
      if (this.protocol.value === 'HTTP') {
        /** HTTP(s)提交参数 */
        const { headers, body, authorize, queryParams } = this.httpConfig;
        config.method = this.httpTarget.method;
        config.url_list = this.httpTarget.url_list;
        config.headers = transformDataKey(headers, true);
        config.body = transformDataKey(body, true);
        config.authorize = transformDataKey(authorize, true);
        config.query_params = transformDataKey(queryParams, true);
        config.response_code = advanced.response_code;
      } else {
        config.port = this.task.port.toString().trim();
        if (this.protocol.value === 'UDP') {
          config.request = this.task.requestContent ? this.task.requestContent.trim() : '';
          config.request_format = this.requestFormat;
          config.wait_empty_response = advanced.wait_empty_response;
        }
      }
      return config;
    },
    /**
     * @desc 获取参数
     * @param {String} protocol - 协议：'HTTP'，'TCP'，'UDP'
     * @param {String} type - 类型：'TEST'-测试，'SAVE'-保存
     */
    getParams(protocol, type = 'TEST') {
      const { task } = this;
      const advanced = this.$refs.advancedRef.getValue();
      const config = this.getConfig(advanced);
      const params = {
        bk_biz_id: task.business,
        protocol: this.protocol.value,
        node_id_list: task.nodes.filter(item => !!item),
        config,
      };
      if (type === 'SAVE') {
        params.location = advanced.location;
        params.name = task.name.trim();
        params.group_id_list = task.groups;
      }
      return params;
    },
    /** http选择器配置 */
    validateHttpConfig() {
      if (!this.httpTarget.url_list?.length) {
        this.requiredOptions.target = true;
        return false;
      }
      // const validate = this.httpTarget.url_list.every(url => /^(((ht|f)tps?):\/\/)[\w-]+(\.[\w-]+)+([\w.,@?^=%&:/~+#-{}]*[\w@?^=%&/~+#-{}])?$/.test(url));
      this.requiredOptions.target = false;
      return true;
    },
    validateTcpTarget() {
      const data = this.$refs.tcpTarget?.getValue();
      let validate = true;
      if (!data || (!data.node_list?.length && !data.ip_list?.length && !data.url_list?.length)) {
        validate = false;
      }
      this.requiredOptions.target = !validate;
      return validate;
    },
    validate(protocol = 'HTTP') {
      let fields = ['business', 'name', 'nodes', 'timeout'];
      const rules = {
        business: val => Boolean(val),
        name: () => this.validateName(),
        nodes: val => Boolean(val.length),
        timeout: val => this.handleValidateTimeout(val),
      };
      if (protocol === 'HTTP') {
        fields = fields.concat(['httpConfig']);
        rules.httpConfig = this.validateHttpConfig;
      } else {
        rules.target = this.validateTcpTarget;
        fields = fields.concat(['target']);
        if (protocol !== 'ICMP') {
          // 校验端口是否合法
          rules.port = v =>
            /^([1-9]\d{0,4}|[1-5]\d{5}|6[0-4]\d{4}|65[0-4]\d{3}|655[0-2]\d{2}|6553[0-5])$/.test(v.toString().trim());
        }
        if (protocol === 'TCP') {
          fields = fields.concat(['port']);
        } else if (protocol === 'UDP') {
          fields = fields.concat(['port', 'requestContent']);
          // rules.requestContent = val => !(val.length % 2) && /^[a-fA-F0-9]+$/.test(val.trim());
          rules.requestContent = val => this.validateRequestContent(val, true);
        }
      }
      const result = [];
      fields.forEach(field => {
        const fn = rules[field];
        this.requiredOptions[field] = !fn(this.task[field]);
        result.push(this.requiredOptions[field]);
      });
      return result.includes(true);
    },
    // 回显form数据
    backFillData(data) {
      const { config } = data;
      this.task.business = data.bk_biz_id;
      this.protocol.value = data.protocol;
      this.task.name = data.name;
      this.task.groups = data.groups.map(group => group.id);
      data.nodes.forEach(node => {
        if (!this.node[data.bk_biz_id]) {
          this.task.nodes.push(node.id);
        } else {
          const sameNode = this.node[data.bk_biz_id].find(item => item.id === node.id);
          if (sameNode && !this.task.nodes.some(id => id === node.id) && node.id) {
            this.task.nodes.push(node.id);
          }
        }
      });
      if (this.protocol.value === 'HTTP') {
        this.task.timeout = config.timeout;
        const { method, url_list, headers, body, authorize, query_params } = config;
        this.httpConfig = {
          method,
          url: url_list[0] || '',
          headers: transformDataKey(headers),
          body: transformDataKey(body),
          authorize: transformDataKey(authorize),
          queryParams: transformDataKey(query_params),
        };
        this.httpTarget.url_list = url_list;
        this.httpTarget.method = method;
      } else {
        const { url_list = [], ip_list = [], node_list = [], target_ip_type, output_fields, dns_check_mode } = config;
        this.tcpTarget = {
          url_list,
          ip_list,
          node_list,
          target_ip_type,
          output_fields,
          dns_check_mode,
        };
        if (this.protocol.value === 'ICMP') {
          this.task.timeout = config.max_rtt;
        } else {
          this.task.timeout = config.timeout;
          this.task.port = config.port;
          if (this.protocol.value === 'UDP') {
            this.task.requestContent = config.request;
            this.requestFormat = config.request_format;
          }
        }
      }
      config.location = data.location;
      this.advancedOptions = config;
    },
    getMetricDataFromData(data) {
      if (!data) return [];
      return Object.keys(this.uptimeCheckMetricMap)
        .map(key => {
          const metricData = {
            metric: key,
            label: this.uptimeCheckMetricMap[key],
            resultTableId: `uptimecheck.${data.protocol.toLowerCase()}`,
            resultTableLabel: 'uptimecheck',
            relatedId: data.id,
            relatedName: data.name,
            status: 1,
            detail: '',
            value: '',
          };
          if (['available', 'task_duration'].includes(key)) {
            metricData.detail = this.$t('已配置'); // ${this.uptimeCheckMetricMap[key]}
            metricData.value = data[this.uptimeCheckMetricMap[key]] || '';
          } else if (key === 'response_code' && data.protocol.toLowerCase() === 'http') {
            metricData.detail = data.config.response_code ? this.$t('已配置') : this.$t('未配置');
            metricData.value = data.config.response_code || '';
            metricData.status = data.config.response_code ? 1 : 0;
          } else if (key === 'message' && data.protocol.toLowerCase() !== 'icmp') {
            metricData.detail = data.config.response ? this.$t('已配置') : this.$t('未配置');
            metricData.value = data.config.response || '';
            metricData.status = data.config.response ? 1 : 0;
          }
          return metricData;
        })
        .filter(item => item.detail || data.protocol.toLowerCase() === 'http');
    },
    handleFail(msg) {
      this.$bkMessage({
        theme: 'error',
        message: msg,
        ellipsisLine: 0,
      });
      this.isLoading = false;
    },
    handleSetBusiness() {
      switch (this.operatorType) {
        case 'edit':
          this.task.business =
            this.$route.params.bizId === undefined ? this.$store.getters.bizId : this.$route.params.bizId;
          break;
        case 'add':
          this.task.business = this.$store.getters.bizId;
          break;
      }
    },
    handleClearTaskData(v) {
      if (v) {
        this.updateNav(this.$t('route-新建拨测任务'));
        this.advancedOptions = {};
        this.setDefaultData();
        this.handleInitTaskForm();
      }
      if (this.operatorType === 'edit' && v) {
        this.$router.push({
          name: 'uptime-check-task-add',
        });
      }
      this.formDone.show = false;
    },
    handleCreateTaskNode() {
      const dropInstance = this.$refs.taskNodeSelect?.$refs.selectDropdown.instance;
      if (dropInstance?.state.isVisible) {
        dropInstance.hide(0);
      }
      this.$router.push({
        name: 'uptime-check-node-add',
      });
    },
    setDefaultData() {
      this.protocol.value = 'HTTP';
      this.requiredOptions = {
        business: false,
        name: false,
        timeout: false,
        nodes: false,
        urls: false,
        port: false,
        requestContent: false,
        submitContent: false,
        target: false,
        httpConfig: false,
      };
      this.isShowAdvanced = false;
      this.$refs.advancedRef.setDefaultData();
      this.createprocess = {
        isCreate: false,
        id: '',
      };
    },
    handleValidateTimeout() {
      this.requiredOptions.timeout =
        !this.task.timeout || this.task.timeout <= 0 || this.task.timeout > this.maxAvailableDurationLimit;
      return !this.requiredOptions.timeout;
    },
    validateName() {
      let isPass = true;
      if (!this.task.name || allSpaceRegex(this.task.name)) {
        isPass = false;
        this.requiredOptions.name = true;
        this.nameErrorMsg = this.$t('必填项');
      } else if (this.task.name.length > 50) {
        isPass = false;
        this.requiredOptions.name = true;
        this.nameErrorMsg = this.$t('注意：最大值为50个字符');
      } else if (emojiRegex(this.task.name)) {
        isPass = false;
        this.requiredOptions.name = true;
        this.nameErrorMsg = this.$t('不能输入emoji表情');
      } else {
        isPass = true;
        this.requiredOptions.name = false;
        this.nameErrorMsg = '';
      }
      return isPass;
    },
    validatePort() {
      const port = +this.task.port;
      this.requiredOptions.port = !(0 < port && port <= 65535);
    },
    handleAddTcpTarget() {
      this.requiredOptions.target = false;
    },
    handleHttpConfigChange(httpConfig) {
      this.httpConfig = httpConfig;
    },
    /* 判断udp节点版本是否大于2.7.3.184 */
    isMoreThanVersion(versions) {
      const nums = [1000, 100, 10, 1];
      const maxVersion = '2.7.3.184';
      const maxVersionNum = maxVersion.split('.').reduce((pre, cur, index) => pre + +cur * nums[index], 0);
      const updNodeVersionNums = versions.map(item => {
        const numFn = v => (v ? v.split('.').reduce((pre, cur, index) => pre + +cur * nums[index], 0) : 0);
        return numFn(item);
      });
      return updNodeVersionNums.sort((a, b) => b - a)[0] >= maxVersionNum;
    },
    /* 强制保存 */
    handleEnforceSave() {
      const params = this.getParams(this.protocol.value);
      // 无论参数是否变更，都走一样的流程
      this.handleCreateTaskSubmit(params, true);
    },
  },
};
</script>
<style lang="scss" scoped>
/* stylelint-disable no-descending-specificity */
.task-form {
  min-height: calc(100vh - 100px);
  padding: 16px;
  padding-top: 12px;

  .task-form-content {
    width: 100%;
    min-height: calc(100vh - 100px);
    padding: 24px 20px 16px 0;
    background-color: #fff;
    border-radius: 2px;
  }

  .uptime-form-item {
    display: flex;
    flex-direction: row;
    align-items: center;
    width: 100%;
    margin-bottom: 20px;
    color: #63656e;

    &.ip-selector {
      align-items: flex-start;

      .target {
        width: 90%;
      }

      .out-line {
        outline: 1px solid #dcdee5;
      }

      :deep(.left-content) {
        .left-content-wrap {
          height: 230px;

          .static-topo {
            margin-top: 0;
          }
        }
      }

      .ip-input-layout {
        :deep(.left-content-wrap) {
          height: auto;
        }
      }

      :deep(.left-tab) {
        display: none;
      }

      :deep(.ip-select-right) {
        background-image:
          linear-gradient(-90deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%),
          linear-gradient(0deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%);
        border-top: 1px solid #dcdee5;

        .right-wrap {
          border-top: 0;
        }
      }

      :deep(.right-empty) {
        margin-top: 120px;
      }
    }

    &.http-selector-wrap {
      align-items: flex-start;

      .item-label {
        margin-top: 5px;
      }

      .http-selector {
        width: 680px;

        :deep(.http-header-wrap) {
          padding-top: 0;
          margin-top: 0;

          .arrow {
            display: none;
          }

          .http-header-main {
            background-color: #f5f7fa;

            .header-body {
              .select-wrap {
                margin-left: 0;
              }

              .header-body-type {
                display: flex;
                align-items: center;
                justify-content: space-between;
              }
            }
          }
        }

        :deep(.http-method-url) {
          display: none;
          width: 680px;
          padding-top: 0;

          .select {
            margin-top: 2px;
          }
        }

        .http-header-wrap {
          .http-header-main {
            background-color: initial;
          }
        }
      }
    }

    &.advanced-option {
      margin-bottom: 0;
    }

    &.submit-content {
      align-items: start;
    }

    .item-label {
      flex: 0 0 100px;
      margin-right: 15px;
      font-size: 12px;
      text-align: right;

      &.mw-170 {
        min-width: 170px;
      }

      &.item-required:after {
        position: relative;
        left: 5px;
        font-size: 12px;
        color: red;
        content: '*';
      }

      &.group {
        padding-right: 6px;
      }
    }

    .item-container {
      position: relative;
      width: 100%;

      :deep(.ip-select) {
        /* stylelint-disable-next-line declaration-no-important*/
        height: 340px !important;
      }

      .need-border {
        :deep(.ip-select-right) {
          border-bottom: 1px solid #dcdee5;
        }
      }

      &.item-advance {
        display: flex;
        align-items: center;
        height: 18px;
      }

      :deep(.tooltips-icon) {
        top: 8px;
        right: 5px;
      }

      &.timeout {
        display: inline-flex;
        align-items: center;

        :deep(.tooltips-icon) {
          top: 8px;
          right: 38px;
        }

        .timeout-select {
          width: 160px;
        }

        .hint-icon {
          display: inline-block;
          width: 18px;
          height: 18px;
          margin-left: 11px;
          line-height: 18px;
          cursor: pointer;
          fill: #fff;

          .icon-monitor {
            font-size: 16px;
          }
        }
      }

      .icon-tips:hover {
        color: #3a84ff;
      }

      :deep(.bk-form-radio) {
        margin-right: 20px;
        margin-bottom: 0;

        .icon-check {
          &::before {
            content: none;
          }
        }
      }

      .validate-hint {
        position: absolute;
        font-size: 12px;
        color: red;
      }

      .reset-width {
        width: 503px;
        background-color: #fff;
      }

      .unit {
        width: 32px;
        height: 32px;
        font-size: 14px;
        line-height: 31px;
        color: #63656e;
        text-align: center;
      }

      .protocol-radio {
        width: 82px;

        .radio-icmp-tips {
          border-bottom: 1px dashed #000;
        }
      }

      .method-radio {
        width: 82px;
        margin-right: 15px;
      }

      .btn-submit {
        margin-right: 10px;
      }

      :deep(.bk-button-icon-loading::before) {
        content: '';
      }

      .item-container-tips {
        margin-top: 6px;
      }

      &.target {
        :deep(.bk-select) {
          width: unset;
        }

        .topo-selector {
          /* min-width: 1100px; */
        }
      }

      &.request {
        .bk-select {
          /* stylelint-disable-next-line declaration-no-important */
          background-color: initial !important;

          /* stylelint-disable-next-line declaration-no-important */
          border-top-left-radius: 2px !important;

          /* stylelint-disable-next-line declaration-no-important */
          border-bottom-left-radius: 2px !important;
        }
      }

      .request-width {
        width: 412px;
      }
    }

    .icon {
      font-size: 16px;
    }
  }

  .last-item {
    margin-bottom: 17px;
  }

  .text-item {
    margin-bottom: 18px;
  }

  .advanced-option-fade {
    &-enter-active {
      transition: opacity 0.5s cubic-bezier(0.25, 1, 0.25, 1);
    }

    &-leave-active,
    &-enter,
    &-leave-to {
      opacity: 0;
    }
  }
}

.node-option {
  display: flex;
  justify-content: space-between;
}
</style>
