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
    ref="configSet"
    v-bkloading="{ isLoading: loading }"
    class="config-set"
  >
    <div class="set-edit">
      <div
        v-if="config.mode === 'edit'"
        class="edit-item"
      >
        <div
          v-en-style="'min-width: 100px'"
          class="item-label"
        >
          ID
        </div>
        <div class="item-container">
          {{ info.id }}
        </div>
      </div>
      <div class="edit-item">
        <div
          v-en-style="'min-width: 100px'"
          class="item-label label-required"
        >
          {{ $t('所属') }}
        </div>
        <div class="item-container">
          <verify-input
            :show-validate.sync="rules.bizId.validate"
            :validator="{ content: rules.bizId.message }"
          >
            <bk-select
              v-model="info.bizId"
              class="reset-big-width"
              :disabled="!canSelectBusiness"
              :placeholder="$t('选择业务')"
              @change="handleSelectToggle(arguments, info.bizId, rules.bizId)"
            >
              <bk-option
                v-for="item in businessList"
                :id="item.id"
                :key="item.id"
                :name="item.text"
              />
            </bk-select>
          </verify-input>
        </div>
      </div>
      <div class="edit-item">
        <div
          v-en-style="'min-width: 100px'"
          class="item-label label-required"
        >
          {{ $t('名称') }}
        </div>
        <div class="item-container">
          <verify-input
            :show-validate.sync="rules.name.validate"
            :validator="{ content: rules.name.message }"
          >
            <bk-input
              v-model.trim="info.name"
              class="reset-big-width"
              :placeholder="$t('输入采集任务名')"
              @change="validateField(info.name, rules.name)"
            />
          </verify-input>
        </div>
      </div>
      <div class="edit-item">
        <div
          v-en-style="'min-width: 100px'"
          class="item-label label-required"
        >
          {{ $t('插件') }}
        </div>
        <div class="item-container">
          <plugin-selector
            :id="pluginSelectorObj.id"
            :key="pluginSelectorObj.key"
            :disabled="disabled"
            :list="pluginSelectorObj.list"
            :loading="pluginListLoading"
            @change="handlePluginChange"
          />
        </div>
      </div>
      <div class="edit-item">
        <div
          v-en-style="'min-width: 100px'"
          class="item-label label-required"
        >
          {{ $t('采集对象') }}
        </div>
        <div class="item-container">
          <bk-select
            v-model="info.objectId"
            class="reset-big-width"
            :clearable="false"
            :disabled="disabled || pluginSelectorObj.objectIdDisable"
            :loading="pluginListLoading"
            @selected="handleObjectIdChange"
          >
            <bk-option-group
              v-for="(group, index) in objectTypeOptions"
              :key="index"
              :name="group.name"
            >
              <bk-option
                v-for="option in group.children"
                :id="option.id"
                :key="option.id"
                :name="option.name"
              />
            </bk-option-group>
          </bk-select>
        </div>
      </div>
      <div class="edit-item">
        <div
          v-en-style="'min-width: 100px'"
          class="item-label"
        >
          {{ $t('采集周期') }}
        </div>
        <div class="item-container">
          <verify-input
            :show-validate.sync="rules.period.validate"
            :validator="{ content: rules.period.message }"
          >
            <cycle-input
              v-model="info.period"
              class="reset-width custom-cycle"
              :need-auto="false"
              default-unit="m"
            />
          </verify-input>
        </div>
      </div>
      <div class="edit-item">
        <div
          v-en-style="'min-width: 100px'"
          class="item-label label-required"
        >
          {{ $t('采集超时') }}
        </div>
        <div class="item-container">
          <verify-input
            :show-validate.sync="rules.timeout.validate"
            :validator="{ content: rules.timeout.message }"
          >
            <bk-input
              v-model.number="info.timeout"
              class="reset-width"
              :show-controls="false"
              type="number"
              @blur="validateField(info.timeout, rules.timeout)"
            >
              <template slot="append">
                <span
                  v-en-style="'min-width: 58px'"
                  class="timeout-unit"
                  >{{ $t('秒') }}</span
                >
              </template>
            </bk-input>
          </verify-input>
        </div>
      </div>
      <!-- 日志类型 -->
      <collector-log
        v-if="info.collectType === 'Log'"
        ref="collectorLog"
        :log-data="logData"
        @log-can-save="handleLogSave"
      />
      <!-- process 类型 -->
      <process-params
        v-else-if="info.collectType === 'Process'"
        ref="process"
        :process-params="processParams"
        @change="handleProcessParamsChange"
      />
      <template v-if="info.plugin.type === 'Exporter'">
        <div
          v-show="Object.keys(info.host || {}).length"
          class="edit-item edit-item-host"
        >
          <div
            v-en-style="'min-width: 100px'"
            class="item-label label-required label-param"
          >
            {{ $t('绑定主机') }}
          </div>
          <div class="item-container">
            <div class="param-container">
              <verify-input
                class="param-item"
                :show-validate.sync="rules.host.validate"
                :validator="{ content: rules.host.message }"
                position="right"
              >
                <bk-input
                  v-model.trim="info.host.default"
                  class="reset-big-width"
                  @blur="validateHost"
                >
                  <template slot="prepend">
                    <bk-popover placement="top">
                      <div class="prepend-text">${host}=</div>
                      <div slot="content">
                        <div>{{ $t('参数名称') }} : {{ info.host.name }}</div>
                        <div>{{ $t('参数类型') }} : {{ paramType[info.host.mode] }}</div>
                        <div>{{ $t('参数说明') }} : {{ info.host.description || '--' }}</div>
                      </div>
                    </bk-popover>
                  </template>
                </bk-input>
              </verify-input>
            </div>
          </div>
        </div>
        <div
          v-show="Object.keys(info.port).length"
          class="edit-item edit-item-port"
        >
          <div
            v-en-style="'min-width: 100px'"
            class="item-label label-param"
          >
            {{ $t('绑定端口') }}
          </div>
          <div class="item-container">
            <div class="param-container">
              <verify-input
                class="param-item"
                :show-validate.sync="validateParam(info.port).validate"
                :validator="{ content: validateParam(info.port).message }"
                position="right"
              >
                <bk-input
                  v-model.trim="info.port.default"
                  class="reset-big-width"
                  @blur="info.port.default !== '' && validateParam(info.port)"
                >
                  <template slot="prepend">
                    <bk-popover
                      :tippy-options="tippyOptions"
                      placement="top"
                    >
                      <div class="prepend-text">${port}=</div>
                      <div slot="content">
                        <div>{{ $t('参数名称') }} : {{ info.port.name }}</div>
                        <div>{{ $t('参数类型') }} : {{ paramType[info.port.mode] }}</div>
                        <div>{{ $t('参数说明') }} : {{ info.port.description || '--' }}</div>
                      </div>
                    </bk-popover>
                  </template>
                </bk-input>
              </verify-input>
            </div>
          </div>
        </div>
      </template>
      <div
        v-show="info.plugin.id && !['Log', 'Process'].includes(info.collectType)"
        class="edit-item"
      >
        <div
          v-en-style="'min-width: 100px'"
          class="item-label label-param"
        >
          {{ $t('运行参数') }}
        </div>
        <div
          v-if="info.plugin.configJson.length"
          class="item-container"
        >
          <!-- {{ info.plugin.id ===  }} -->
          <div class="container-tips">
            {{ $t('参数的填写也可以使用CMDB变量') }}&nbsp;&nbsp;<span @click="handleVariableTable">
              {{ $t('点击查看推荐变量') }}
            </span>
          </div>
          <div class="param-container">
            <template v-for="(item, index) in info.plugin.configJson">
              <template v-if="item.auth_json !== undefined">
                <!-- snmp多用户 -->
                <auto-multi
                  :key="index"
                  :allow-add="!(info.collectType === 'SNMP')"
                  :param-type="paramType"
                  :souce-data="item.auth_json"
                  :template-data="SnmpAuthTemplate"
                  :tips-data="tipsData"
                  @canSave="snmpAuthCanSave"
                  @triggerData="triggerAuthData"
                />
              </template>
              <template v-else-if="item.auth_priv">
                <verify-input
                  v-if="item.auth_priv[curAuthPriv] && item.auth_priv[curAuthPriv].need"
                  :key="index"
                  class="param-item"
                  :show-validate.sync="item.validate.isValidate"
                  :validator="item.validate"
                  position="right"
                >
                  <!-- 自动补全 -->
                  <auto-complete-input
                    v-model.trim="item.default"
                    class="reset-big-width"
                    :config="item"
                    :cur-auth-priv="curAuthPriv"
                    :tips-data="tipsData"
                    :type="item.type"
                    @autoHandle="autoHandle"
                    @blur="handleParamValidate(item)"
                    @curAuthPriv="handleAuthPriv"
                  >
                    <template slot="prepend">
                      <bk-popover
                        :tippy-options="tippyOptions"
                        placement="top"
                      >
                        <div class="prepend-text">
                          {{ item.name || item.description }}
                        </div>
                        <div slot="content">
                          <div>{{ $t('参数名称') }} : {{ item.name }}</div>
                          <div>{{ $t('参数类型') }} : {{ paramType[item.mode] }}</div>
                          <div>{{ $t('参数说明') }} : {{ item.description || '--' }}</div>
                        </div>
                      </bk-popover>
                    </template>
                  </auto-complete-input>
                </verify-input>
              </template>
              <template v-else-if="item.type === 'service' || item.type === 'host'" />
              <template v-else>
                <verify-input
                  :key="index"
                  class="param-item"
                  :show-validate.sync="item.validate.isValidate"
                  :validator="item.validate"
                  position="right"
                >
                  <!-- 自动补全 -->
                  <auto-complete-input
                    v-model.trim="item.default"
                    class="reset-big-width"
                    :config="item"
                    :cur-auth-priv="curAuthPriv"
                    :tips-data="tipsData"
                    :type="item.type"
                    @autoHandle="autoHandle"
                    @curAuthPriv="handleAuthPriv"
                    @error-message="msg => handleErrorMessage(msg, item)"
                    @file-change="file => configJsonFileChange(file, item)"
                    @input="handleInput(item)"
                    @passwordInputName="handlePasswordInputName"
                  >
                    <template slot="prepend">
                      <bk-popover
                        :tippy-options="tippyOptions"
                        placement="top"
                      >
                        <div :class="{ 'prepend-text': true, required: item.required }">
                          {{ item.name || item.description }}
                        </div>
                        <div slot="content">
                          <div>{{ $t('参数名称') }} : {{ item.name }}</div>
                          <div>{{ $t('参数类型') }} : {{ paramType[item.mode] }}</div>
                          <div>{{ $t('参数说明') }} : {{ item.description || '--' }}</div>
                        </div>
                      </bk-popover>
                    </template>
                  </auto-complete-input>
                </verify-input>
              </template>
            </template>
          </div>
        </div>
        <div
          v-else
          class="item-container"
        >
          <div class="no-param">
            <i class="icon-monitor icon-hint param-icon" />
            <span class="param-text"> {{ $t('由于插件定义时未定义参数，此处无需填写。') }} </span>
          </div>
        </div>
      </div>
      <div
        v-show="info.plugin.id && !['Log', 'Process'].includes(info.collectType) && showDmsInsert"
        class="edit-item"
      >
        <div
          v-en-style="'min-width: 100px'"
          class="item-label label-param"
        >
          {{ $t('维度注入') }}
        </div>
        <div class="item-container">
          <template v-for="(item, index) in info.plugin.configJson">
            <template v-if="item.type === 'service'">
              <div
                :key="index"
                class="dms-insert-category"
              >
                <div :class="{ 'container-tips': true, required: item.required }">
                  {{ $t('服务实例标签') }}
                </div>
                <div class="param-container">
                  <tag-switch
                    v-for="(value, key) in item.default"
                    :key="key"
                    :show-validate="item.validate.isValidate"
                    :tag-label="key"
                    :value="item.default[key]"
                    @input="val => handleTagInput(item, key, val)"
                  />
                </div>
                <span
                  v-show="item.validate.isValidate"
                  style="color: #ff5656"
                  >{{ item.validate.content }}</span
                >
              </div>
            </template>
            <template v-else-if="item.type === 'host'">
              <div
                :key="index"
                class="dms-insert-category"
              >
                <div :class="{ 'container-tips': true, required: item.required }">
                  {{ $t('主机字段') }}
                </div>
                <div class="param-container">
                  <tag-switch
                    v-for="(value, key) in item.default"
                    :key="key"
                    :show-validate="item.validate.isValidate"
                    :tag-label="key"
                    :value="item.default[key]"
                    @input="val => handleTagInput(item, key, val)"
                  />
                </div>
                <span
                  v-show="item.validate.isValidate"
                  style="color: #ff5656"
                  >{{ item.validate.content }}</span
                >
              </div>
            </template>
          </template>
        </div>
      </div>
      <div class="edit-item">
        <div
          v-en-style="'min-width: 100px'"
          class="item-label"
        />
        <div class="item-container">
          <div class="btn-container">
            <bk-button
              v-if="!['Log', 'Process'].includes(info.collectType) && info.collectType !== 'SNMP_Trap'"
              v-show="isShowPreview"
              class="btn-preview"
              theme="default"
              @click="handlePreview"
            >
              {{ $t('button-预览') }}
            </bk-button>
            <bk-popconfirm
              width="200"
              :content="$tc('确认采集下发?')"
              :disabled="!canNext || info?.plugin?.type !== 'K8S'"
              :tippy-options="tippyOptions"
              placement="top"
              trigger="click"
              @confirm="handleTencentCloudNext"
            >
              <bk-button
                :class="['btn-next', { disabled: !canNext }]"
                :disabled="!canNext"
                theme="primary"
                @click="handleNext"
              >
                {{ $t('下一步') }}
              </bk-button>
            </bk-popconfirm>
            <bk-button @click="handleCancel">
              {{ $t('取消') }}
            </bk-button>
          </div>
        </div>
      </div>
    </div>
    <div
      :style="{ right: !btn.show ? -(descWidth + 1) + 'px' : '0px' }"
      class="set-desc"
    >
      <div
        :style="{ left: btn.show ? '-23px' : '-24px' }"
        class="set-desc-btn"
        @click="handleIntroductionShow"
      >
        <div
          class="icon"
          :class="{ 'icon-show': !btn.show }"
        >
          <i class="icon-monitor icon-double-up" />
        </div>
        <!-- <div class="text"> {{ $t('插件说明') }} </div> -->
      </div>
      <div
        :style="{ 'flex-basis': descWidth + 'px', width: descWidth + 'px' }"
        class="set-desc-box"
        data-tag="resizeTarget"
        @mousedown="handleMouseDown"
        @mousemove="handleMouseMove"
        @mouseout="handleMouseOut"
      >
        <collector-introduction
          :key="introduction.content"
          :introduction="introduction"
        />
        <div
          v-show="resizeState.show"
          :style="{ left: descWidth - resizeState.left + 'px' }"
          class="resize-line"
        />
      </div>
    </div>
    <indicator-preview :options="options" />
    <variable-table
      v-if="tipsData && tipsData.length"
      :is-show-variable-table.sync="isShowVariableTable"
      :variable-data="tipsData"
    />
  </div>
</template>

<script>
import { collectConfigDetail, getCollectVariables } from 'monitor-api/modules/collecting';
import { listCollectorPlugin, retrieveCollectorPlugin } from 'monitor-api/modules/model';
import { deepClone, random } from 'monitor-common/utils/utils';
import { createNamespacedHelpers } from 'vuex';

import CycleInput from '../../../../components/cycle-input/cycle-input.tsx';
import VerifyInput from '../../../../components/verify-input/verify-input.vue';
import formLabelMixin from '../../../../mixins/formLabelMixin';
import { SET_NAV_ROUTE_LIST } from '../../../../store/modules/app';
import { SET_INFO_DATA, SET_OBJECT_TYPE } from '../../../../store/modules/collector-config';
import TagSwitch from '../../../plugin-manager/plugin-instance/set-steps/tag-switch.vue';
import AutoCompleteInput from './auto-complete-input';
import AutoMulti from './auto-multi';
import CollectorIntroduction from './collector-introduction';
import CollectorLog from './collector-log';
import PERIOD_LIST from './data';
import IndicatorPreview from './indicator-preview';
import PluginSelector, { LOG_PLUGIN_ID, PROCESS_PLUGIN_ID } from './plugin-selector.tsx';
import ProcessParams from './process-params.vue';
import * as snmp from './snmp';
import VariableTable from './variable-table';

const { mapMutations, mapGetters } = createNamespacedHelpers('collector-config');

export default {
  name: 'ConfigSet',
  components: {
    VerifyInput,
    IndicatorPreview,
    CollectorIntroduction,
    VariableTable,
    AutoCompleteInput,
    CollectorLog,
    AutoMulti,
    ProcessParams,
    CycleInput,
    PluginSelector,
    TagSwitch,
  },
  mixins: [formLabelMixin],
  inject: ['authority', 'handleShowAuthorityDetail', 'collectAuth'],
  props: {
    config: {
      type: Object,
      default: () => {},
    },
    /** 是否为克隆采集 */
    isClone: {
      type: Boolean,
      default: false,
    },
  },
  data() {
    return {
      loading: false,
      isShowVariableTable: false,
      info: {
        bizId: window.cc_biz_id,
        name: '',
        objectType: 'SERVICE',
        objectGroupType: 'services',
        objectId: '',
        objectTypeList: [],
        period: 60,
        timeout: 60,
        collectType: '',
        isShowHost: false,
        isShowPort: false,
        host: {},
        port: {},
        plugin: {
          id: '',
          type: '',
          descMd: '',
          isOfficial: false,
          isSafety: false,
          createUser: '',
          updateUser: '',
          metricJson: [],
          configJson: [],
          osTypeList: [],
          snmpv: '',
        },
      },
      objectTypeOptions: [],
      rules: {
        bizId: {
          validate: false,
          message: '',
          rule: [{ required: true, message: this.$t('必选项') }],
        },
        name: {
          validate: false,
          message: '',
          rule: [
            { required: true, message: this.$t('必填项') },
            { required: true, message: this.$t('注意：最大值为50个字符'), validator: this.validateName },
          ],
        },
        objectType: {
          validate: false,
          message: '',
          rule: [{ required: true, message: this.$t('必填项') }],
        },
        period: {
          validate: false,
          message: '',
          rule: [{ required: false, message: this.$t('必选项') }],
        },
        timeout: {
          validate: false,
          message: '',
          rule: [
            { required: true, message: this.$t('必选项') },
            { required: true, message: this.$t('超时时间配置不能大于周期'), validator: this.validateTimeout },
          ],
        },
        collectType: {
          validate: false,
          message: '',
          rule: [{ required: true, message: this.$t('必选项') }],
        },
        plugin: {
          validate: false,
          message: '',
          rule: [{ required: true, message: this.$t('必选项') }],
        },
        host: {
          validate: false,
          message: '',
          rule: [
            { required: true, message: this.$t('必填项') },
            { required: true, message: this.$t('注意: 必填字段不能为空'), validator: this.validateIp },
          ],
        },
        ip: {
          validate: false,
          message: '',
          rule: [{ required: true, message: this.$t('注意: 必填字段不能为空'), validator: this.validateIp }],
        },
        port: {
          validate: false,
          message: '',
          rule: [{ required: true, message: this.$t('输入合法的端口'), validator: this.validatePort }],
        },
        user: {
          validate: false,
          message: '',
          rule: [{ required: false, message: this.$t('必填项') }],
        },
        password: {
          validate: false,
          message: '',
          rule: [{ required: false, message: this.$t('必填项') }],
        },
      },
      collectTypeList: [],
      filterPluginList: [],
      pluginList: [],
      allPluginList: [],
      options: {
        isShow: false,
        data: [],
        isOfficial: false,
      },
      pluginTypeMap: {
        Exporter: 'Exporter',
        Script: 'Script',
        JMX: 'JMX',
        DataDog: 'DataDog',
        // 'Built-In': 'BK-Monitor',
        Pushgateway: 'BK-Pull',
        Log: 'Log',
        Process: 'Process',
        SNMP_Trap: 'SNMP Trap',
        SNMP: 'SNMP',
      },
      paramType: {
        collector: this.$t('采集器参数'),
        opt_cmd: this.$t('命令行参数'),
        pos_cmd: this.$t('位置参数'),
        env: this.$t('环境变量参数'),
        listen_cmd: this.$t('监听参数'),
        dms_insert: this.$t('维度注入'),
      },
      tippyOptions: {
        distance: 10,
      },
      others: {},
      introduce: {
        [this.$t('主机')]: this.$t('采集的数据为主机操作系统相关的，如CPU NET。'),
        [this.$t('服务')]: this.$t('采集的数据为CMDB中服务模块下的服务实例数据，可以支持多实例的采集，如mysql redis。'),
      },
      btn: {
        show: true,
        introduction: true,
      },
      methodMd:
        // biome-ignore lint/style/useTemplate: <explanation>
        `${this.$t('插件类型是蓝鲸监控丰富支持采集能力的一种表现，插件的类型将越来越丰富。 往下具体介绍当前每种类型特点')}。\n\n` +
        '### Exporter\n\n' +
        `${this.$t('Exporter是用于暴露第三方服务的metrics给Prometheus。是Prometheus中重要的一个组件。按蓝鲸监控插件的规范就可以将开源的Exporter插件变成蓝鲸监控的采集能力。 运行的Exporter是go的二进制程序，需要启动进程和占用端口')}。\n\n` +
        '### Script\n\n' +
        `${this.$t('Script就是由用户自定义脚本进行Metrics采集。只要符合监控的标准格式就可以把数据采集上来。 支持的脚本有：')}\n\n` +
        `* Linux Shell，Python，${this.$t('自定义')}\n\n` +
        `* Windows Shell，Python，VBS，PowerShell,${this.$t('自定义')}\n\n` +
        `${this.$t('自定义是直接执行，不用解释器进行执行。 如 ./脚本')}\n\n` +
        '### DataDog\n\n' +
        `${this.$t('Datadog是一个一站式云端性能监控平台，拥有丰富的采集能力。蓝鲸监控兼容了Datadog的采集能力，当前用户不能自定义插件。因为Datadog是由python编写，需要有python可运行环境，不需要占用端口')}。\n\n` +
        '### JMX\n\n' +
        `${this.$t('JMX可以采集任何开启了JMX服务端口的java进程的服务状态，通过jmx采集java进程的jvm信息，包括gc耗时、gc次数、gc吞吐、老年代使用率、新生代晋升大小、活跃线程数等信息')}。\n\n` +
        '### BK-pull\n\n' +
        `${this.$t('BK-pull主要是解决那些只暴露了端口服务的数据源。 通过pull拉取目标的数据')}。\n\n` +
        '### Log\n\n' +
        `${this.$t('Log主要是围绕日志相关的内容进行数据的采集，比如日志关键字等')}。`,
      resizeState: {
        show: false,
        ready: false,
        left: 0,
        dragging: false,
        minWidth: 400,
        maxWidth: 800,
      },
      descWidth: 400,
      tipsData: [], //  插件参数提示数据
      logCanSave: false, //  日志关键词采集能否保存
      logData: {}, // 日志回填数据
      processParams: {},
      isSnmpSelected: false, // 是否已选择snmp 插件
      // snmp 回填数据
      snmpData: {},
      // 是否可下一步
      SnmpCanSave: false,
      SnmpAuthCanSave: false,
      // snmp插件列表
      SnmpVersion: snmp.SnmpVersion,
      SnmpAuthTemplate: [],
      curAuthPriv: '',
      snmpIsOk: false,

      /* 插件选择器 */
      pluginSelectorObj: {
        list: [],
        id: '',
        key: random(8),
        objectIdDisable: false,
      },
      pluginListLoading: false, // 新增情况下判断是否正在获取插件列表
    };
  },
  computed: {
    ...mapGetters(['infoData']),
    businessList() {
      if (!this.canSelectBusiness) {
        return this.$store.getters.bizList.filter(biz => +biz.id === +this.info.bizId);
      }
      return this.$store.getters.bizList;
    },
    // 是否显示指标预览
    isShowPreview() {
      return this.info.plugin.id !== '';
    },
    // 能否下一步
    canNext() {
      if (this.info.collectType === 'Log') {
        return this.info.plugin.id !== '' && this.logCanSave;
      }
      if (this.info.collectType === 'SNMP_Trap') {
        if (this.info.plugin.snmpv === 'snmp_v3') {
          return this.SnmpOther() && this.SnmpCanSave && this.SnmpAuthCanSave;
        }
        return this.SnmpOther() && this.SnmpCanSave;
      }
      if (this.info.collectType === 'SNMP') {
        const snmpAuthIsOk = +this.info.plugin?.collectorJson?.snmp_version === 3 ? this.SnmpAuthCanSave : true;
        return this.info.name !== '' && this.info.plugin.id !== '' && snmpAuthIsOk && this.snmpIsOk;
      }
      if (this.info.plugin?.configJson?.some(item => item.validate?.isValidate)) return false;
      return this.info.plugin.id !== '' && this.validateHost();
    },
    // 编辑模式下，采集方式和采集配置不可变
    disabled() {
      return this.pluginListLoading || (this.config.mode === 'edit' && !this.isClone);
    },
    canSelectBusiness() {
      return !this.disabled && this.$store.getters.bizId === 0; // window.bizId === 0 全业务
    },
    canSelectPlugin() {
      return !this.disabled && this.info.collectType !== ''; // 采集方式不为空
    },
    periodList() {
      return PERIOD_LIST;
    },
    introduction() {
      let introduction = {};
      if (this.info.collectType === 'Log') {
        introduction = this.getLogIntroduction();
        return introduction;
      }
      if (
        this.info.collectType === 'SNMP_Trap' &&
        this.info.plugin.snmpv !== '' &&
        this.info.plugin.snmpv !== undefined
      ) {
        introduction = this.getSnmpIntroduction();
        return introduction;
      }
      const { configJson, metricJson, id, descMd, ...others } = this.info.plugin;

      if (id) {
        introduction = {
          ...others,
          content: descMd || this.methodMd,
          pluginId: id,
          type: 'bkmonitor.models.fta.plugin',
        };
      } else {
        introduction = { type: 'method', content: this.methodMd };
      }
      return introduction;
    },
    showDmsInsert() {
      return this.info.plugin.configJson.some(item => item.mode === 'dms_insert');
    },
  },
  watch: {
    'info.objectGroupType': {
      // 更新采集对象组的类型
      handler: 'handleUpdateObjectType',
      immediate: true,
    },
  },
  async created() {
    this.infoData && (this.info = deepClone(this.infoData));
    if (this.objectTypeOptions.length === 0) {
      await this.$store.dispatch('collector-config/getCollectorObject').then(data => {
        this.info.objectTypeList = data;
        this.objectTypeOptions = data;
        const { objectId } = this.$route.params;
        if (objectId) {
          this.handleSetObjTypeById(objectId);
          this.info.objectId = objectId;
        }
      });
    }
    if (!this.info.objectId && !this.$route.params.pluginId) {
      this.info.objectId = 'component';
    }
    this.getVariableData();
  },
  mounted() {
    this.updateNav(this.config.mode === 'edit' ? this.$t('编辑') : this.$t('新建采集'));
    this.handleSetPlugin();
    if (this.config.mode === 'edit') {
      this.bizId = this.config.data.bizId;
    } else {
      if (Number.parseInt(this.$store.getters.bizId, 10) === 0) {
        this.info.bizId = '';
      }
    }
    this.handleConfig(this.config);
    this.resizeState.maxWidth = this.$refs.configSet.clientWidth;
    // this.initFormLabelWidth()
  },
  beforeDestroy() {
    document.body.style.cursor = '';
    this.resizeState.dragging = false;
    this.resizeState.show = false;
    this.resizeState.ready = false;
  },
  methods: {
    ...mapMutations([SET_OBJECT_TYPE, SET_INFO_DATA]),
    //  获取日志右边栏展示的内容
    snmpAuthCanSave(is) {
      this.SnmpAuthCanSave = is;
    },
    triggerAuthData(v) {
      if (this.info.plugin.configJson) {
        this.info.plugin.configJson.forEach(item => {
          if (item.auth_json) {
            return (item.auth_json = v);
          }
          return { ...item };
        });
      }
    },
    // 获取当前AuthPriv选项用于联动
    handleAuthPriv(val) {
      this.curAuthPriv = val;
      this.autoHandle();
    },
    // 校验snmptrap运行参数
    //
    SnmpVersionValidate() {
      if (this.config.set.mode === 'edit') {
        this.autoHandle();
        this.SnmpCanSave = false;
      } else {
        this.autoHandle();
      }
    },
    autoHandle() {
      if (this.info.collectType === 'SNMP_Trap') {
        this.SnmpCanSave = this.SnmpValidate();
      } else if (this.info.collectType === 'SNMP') {
        this.snmpIsOk = this.handleSnmpParamValidate();
      }
    },
    SnmpOther() {
      return this.info.plugin.snmpv !== '' && this.info.plugin.snmpv !== undefined && this.info.name !== '';
    },
    SnmpValidate() {
      const { plugin } = this.info;
      let result = false;
      if (plugin.configJson.length !== 0) {
        if (plugin.snmpv === 'snmp_v1' || plugin.snmpv === 'snmp_v2c') {
          result = plugin.configJson.every(item => {
            if (item.key !== snmp.community) {
              return item.type === 'file' ? item.default.value !== '' : item.default !== '';
            }
            return true;
          });
        } else {
          result = plugin.configJson.every(item => {
            if (item.auth_json === undefined && item.key !== snmp.community) {
              return item.type === 'file' ? item.default.value !== '' : item.default !== '';
            }
            return true;
          });
          // const excludeValidateMap = {
          //   authPriv: ['context_name'],
          //   authNoPriv: ['context_name', 'privacy_protocol', 'privacy_passphrase'],
          //   noAuthNoPriv: ['context_name', 'privacy_protocol',
          //     'privacy_passphrase', 'authentication_protocol', 'authentication_passphrase']
          // }
          // result = plugin.configJson.every((item) => {
          //   if (!excludeValidateMap[this.curAuthPriv].includes(item.key)) {
          //     return item.type === 'file' ? item.default.value !==  '' : item.default !== ''
          //   }
          //   return true
          // })
        }
      } else {
        result = false;
      }
      return result;
      // if ()
    },
    handleSnmpParamValidate() {
      const { plugin } = this.info;
      const version = plugin.collectorJson.snmp_version;

      for (const item of plugin.configJson) {
        if ([1, 2].includes(+version)) {
          if (item.default === '') {
            return false;
          }
        } else {
          const includesMap = ['port', 'host'];
          if (includesMap.includes(item.key) && item.default === '') {
            return false;
          }
        }
      }
      return true;
    },
    //  获取日志右边栏展示的内容
    getLogIntroduction() {
      return {
        pluginId: this.$t('日志关键字采集'),
        type: 'bkmonitor.models.fta.plugin',
        isOfficial: true,
        isSafety: true,
        osTypeList: ['linux', 'windows'],
        content:
          // biome-ignore lint/style/useTemplate: <explanation>
          `## ${this.$t('功能介绍')}\n\n` +
          `${this.$t('日志关键字插件，通过对于日志文件的关键匹配进行计数，并且存储最近一条原始日志内容。')}\n\n` +
          `${this.$t('采集后的日志关键字数据可以在视图中查看变化趋势，也可以在策略里面配置告警规则。')}\n\n` +
          `## ${this.$t('关键字规则配置方法')}\n\n` +
          `### ${this.$t('参考例子:')}\n\n` +
          `### ${this.$t('原始日志:')}\n\n` +
          '```\nm=de4x5 init_module: Input/output error\n```\n\n' +
          `### ${this.$t('关键字规则:')}\n\n` +
          '```\nm=(?P<moudle>.*) init_module: Input/output error\n```\n\n' +
          `${this.$t('就会得到关键字并和 moudle=de4x5 匹配的次数。')}\n\n`,
      };
    },
    getSnmpIntroduction() {
      const snmpIntroduction = {
        snmp_v1:
          // biome-ignore lint/style/useTemplate: <explanation>
          '## SNMP Trap V1\n\n' +
          `### ${this.$t('功能介绍')}\n\n` +
          `${this.$t('snmp trap 将默认搭建 snmp trap server 接收不同设备的发送的事件数据。默认端口为 162。注意选择对应的 snmp 版本,本版本为 V1。')}\n\n` +
          `### ${this.$t('参数说明')}\n\n` +
          `* ${this.$t('Trap服务端口： 是trap接收的端口，默认为 162')}\n\n` +
          `* ${this.$t('绑定地址')}： ${this.$t('trap服务启动时绑定的地址，默认为0.0.0.0，如果要指定网卡，需要使用CMDB变量来使用如：')}` +
          '```{{ target.host.bk_host_innerip }}```\n\n' +
          `* ${this.$t('Yaml配置文件：是通过命令行工具将mib文件转换的yaml配置文件。')}\n\n` +
          `* ${this.$t('团体名')}： Community\n\n` +
          `* ${this.$t('是否汇聚')}：${this.$t('默认是开启的，采集周期内默认相同的内容会汇聚到成一条并且计数。')}\n\n\n`,
        snmp_v2c:
          // biome-ignore lint/style/useTemplate: <explanation>
          '## SNMP Trap V2c\n\n' +
          `### ${this.$t('功能介绍')}\n\n` +
          `${this.$t('snmp trap 将默认搭建 snmp trap server 接收不同设备的发送的事件数据。默认端口为 162。注意选择对应的 snmp 版本, 本版本为 V2c。')}\n\n` +
          `### ${this.$t('参数说明')}\n\n` +
          `* ${this.$t('Trap服务端口： 是trap接收的端口，默认为 162')}\n\n` +
          `* ${this.$t('绑定地址')}： ${this.$t('trap服务启动时绑定的地址，默认为0.0.0.0，如果要指定网卡，需要使用CMDB变量来使用如：')}` +
          '```{{ target.host.bk_host_innerip }}```\n\n' +
          `* ${this.$t('Yaml配置文件：是通过命令行工具将mib文件转换的yaml配置文件。')}\n` +
          `* ${this.$t('团体名')}： Community \n` +
          `* ${this.$t('是否汇聚')}：${this.$t('默认是开启的，采集周期内默认相同的内容会汇聚到成一条并且计数。')}\n\n\n`,
        snmp_v3:
          // biome-ignore lint/style/useTemplate: <explanation>
          `## ${this.$t('SNMP Trap V3')}\n\n` +
          `### ${this.$t('功能介绍')}\n\n` +
          `${this.$t('snmp trap 将默认搭建 snmp trap server 接收不同设备的发送的事件数据。默认端口为 162。注意选择对应的 snmp 版本, 本版本为 V3。')}\n\n` +
          `### ${this.$t('参数说明')}\n\n` +
          `* ${this.$t('Trap服务端口： 是trap接收的端口，默认为 162')}\n` +
          `* ${this.$t('绑定地址')}： ${this.$t('trap服务启动时绑定的地址，默认为0.0.0.0，如果要指定网卡，需要使用CMDB变量来使用如：')}` +
          '```{{ target.host.bk_host_innerip }}```\n' +
          `* ${this.$t('Yaml配置文件：是通过命令行工具将mib文件转换的yaml配置文件。')}\n` +
          `* ${this.$t('上下文名称')} Context name\n` +
          `* ${this.$t('安全名')} Security name\n` +
          `* ${this.$t('安全级别')} Security level ， ${this.$t('选项有')} noAuthNoPriv， authNoPriv ， authPriv\n` +
          `* ${this.$t('验证协议')} Authentication protocol， ${this.$t('选项有')} MD5，SHA，DES，AES\n` +
          `* ${this.$t('验证口令')} Authentication passphrase\n` +
          `* ${this.$t('隐私协议')} Privacy protocol ,${this.$t('选项有')} DES ， AES\n` +
          `* ${this.$t('私钥')} Privacy paasphrase\n` +
          `* ${this.$t('设备ID')} Engine ID}\n` +
          `* ${this.$t('是否汇聚')}：${this.$t('默认是开启的，采集周期内默认相同的内容会汇聚到成一条并且计数。')}\n\n`,
      };
      return {
        pluginId: this.$t('snmp trap'),
        type: 'plugin',
        isOfficial: true,
        isSafety: true,
        osTypeList: ['linux', 'windows'],
        content: snmpIntroduction[this.info.plugin.snmpv],
      };
    },
    handleLogSave(v) {
      this.logCanSave = v;
      if (this.config.mode === 'add') {
        this.info.plugin.id = v ? 'default_log' : '';
      }
    },
    handleMouseDown(e) {
      if (this.resizeState.ready) {
        let { target } = event;
        while (target && target.dataset.tag !== 'resizeTarget') {
          target = target.parentNode;
        }
        this.resizeState.show = true;
        const rect = e.target.getBoundingClientRect();
        document.onselectstart = () => {
          return false;
        };
        document.ondragstart = () => {
          return false;
        };
        const handleMouseMove = event => {
          this.resizeState.dragging = true;
          this.resizeState.left = rect.right - event.clientX;
        };
        const handleMouseUp = () => {
          if (this.resizeState.dragging) {
            const { minWidth, left } = this.resizeState;
            this.resizeState.left = left < minWidth ? minWidth : left;
            this.resizeState.left = Math.min(this.resizeState.left, this.$refs.configSet.clientWidth);
            this.descWidth = this.resizeState.left;
          }
          document.body.style.cursor = '';
          this.resizeState.dragging = false;
          this.resizeState.show = false;
          this.resizeState.ready = false;
          document.removeEventListener('mousemove', handleMouseMove);
          document.removeEventListener('mouseup', handleMouseUp);
          document.onselectstart = null;
          document.ondragstart = null;
        };
        document.addEventListener('mousemove', handleMouseMove);
        document.addEventListener('mouseup', handleMouseUp);
      }
    },
    handleMouseMove() {
      if (this.btn.show) {
        let { target } = event;
        while (target && target.dataset.tag !== 'resizeTarget') {
          target = target.parentNode;
        }
        const rect = target.getBoundingClientRect();
        const bodyStyle = document.body.style;
        if (rect.width > 12 && event.pageX - rect.left < 8) {
          bodyStyle.cursor = 'col-resize';
          this.resizeState.ready = true;
        }
      }
    },
    handleMouseOut() {
      document.body.style.cursor = '';
      this.resizeState.ready = false;
    },
    validateField(value, ruleMap) {
      const { rule } = ruleMap;
      const res = {
        validate: false,
        message: '',
      };

      for (let i = 0; i < rule.length; i++) {
        const item = rule[i];
        if (item.required && value === '') {
          // 空值
          res.validate = true;
          ruleMap.validate = true;
          res.message = item.message;
          ruleMap.message = item.message;
          return res;
        }
        if (item.required && value && item.validator && typeof item.validator === 'function') {
          // 非空有校验器
          res.validate = !item.validator(value);
          ruleMap.validate = !item.validator(value);
          if (ruleMap.validate) {
            res.message = item.message;
            ruleMap.message = item.message;
            return res;
          }
        }
      }
      // v3.2
      // rule.forEach((item) => {
      //   if (item.required && value === '') { // 空值
      //     res.validate = true
      //     ruleMap.validate = true
      //     res.message = item.message
      //     ruleMap.message = item.message
      //     return res
      //   } if (item.required && value
      //                   && item.validator && typeof item.validator === 'function') { // 非空有校验器
      //     res.validate = !item.validator(value)
      //     ruleMap.validate = !item.validator(value)
      //     if (ruleMap.validate) {
      //       res.message = item.message
      //       ruleMap.message = item.message
      //       return res
      //     }
      //   }
      // })
      ruleMap.validate = false;
      return res;
    },
    validate() {
      const { info } = this;
      const { rules } = this;
      const includeFields = ['bizId', 'name', 'objectType', 'period', 'collectType', 'timeout'];
      const keys = Object.keys(rules);
      for (const item of keys) {
        // validate=false 时需要重新触发校验，不校验运行参数部分
        !rules[item].validate && includeFields.includes(item) && this.validateField(info[item], rules[item]);
      }
      let configValidate = false;
      if (this.info?.plugin?.configJson) {
        const configValidateList = [];
        for (const item of this.info.plugin.configJson) {
          if (!(item.auth_json === undefined)) {
            configValidateList.push(this.handleParamValidate(item));
          }
          if (item.type === 'file') {
            configValidateList.push(this.handleParamValidate(item));
          } else {
            configValidateList.push(this.handleInput(item));
          }
        }
        configValidate = configValidateList.some(item => item.validate);
      }
      return keys.every(item => rules[item].validate === false) && !configValidate;
    },
    validateStrLength(str, length = 50) {
      const cnLength = (str.match(/[\u4e00-\u9fa5]/g) || []).length; // 汉字占 2 个字符
      const enLength = (str || '').length - cnLength;
      return cnLength * 2 + enLength > length;
    },
    validateName(value) {
      return !this.validateStrLength(value);
    },
    validateTimeout(value) {
      return value <= this.info.period;
    },
    validateIp(value) {
      return value.trim().length > 0;
    },
    validatePort(value) {
      return /^([1-9]\d{0,4}|[1-5]\d{5}|6[0-4]\d{4}|65[0-4]\d{3}|655[0-2]\d{2}|6553[0-5])$/.test(value); // 0~65535
    },
    validateParam(value) {
      const { rules } = this;
      let res = {
        validate: false,
      };
      if (value.default !== '') {
        // 不为空才交给是否符合规则
        if (['host', 'ip'].includes(value.name)) {
          res = this.validateField(value.default, rules.ip);
        } else if (value.name === 'port') {
          res = this.validateField(value.default, rules.port);
        }
      } else {
        rules.ip.validate = false;
        rules.port.validate = false;
      }
      return res;
    },
    handleParamValidate(item) {
      const { rules } = this;
      let res = {
        validate: false,
      };
      if (item.type === 'file') {
        res.validate = item.validate.isValidate;
        return res;
      }
      if (item.default !== '' || ['host', 'ip', 'port'].includes(item.name)) {
        // 不为空才交给是否符合规则
        if (['host', 'ip'].includes(item.name)) {
          res = this.validateField(item.default, rules.ip);
        } else if (item.name === 'port') {
          res = this.validateField(item.default, rules.port);
        }
      } else {
        rules.ip.validate = false;
        rules.port.validate = false;
      }
      if (item.validate === undefined) {
        return res;
      }
      item.validate.isValidate = res.validate;
      item.validate.content = res.message;
      return res;
    },
    validateHost() {
      // 插件类型为 'Exporter' 需要校验绑定主机
      const hostRule = this.rules.host;
      if (this.info.plugin.type === 'Exporter') {
        return this.validateField(this.info.host.default, hostRule);
      }
      hostRule.validate = false;
      return true;
    },
    // 以上为校验器
    // 选择框折叠时触发校验
    handleSelectToggle(toggle, value, rulesMap) {
      if (!toggle) {
        this.validateField(value, rulesMap);
      }
    },
    // 采集方式发生改变
    handleCollectTypeChange(newV, oldV) {
      if (oldV && newV !== oldV) {
        // 采集方式改变时，清空已有的插件信息
        this.handleDelPLugin();
        this.handleSnmpPugin();
        if (this.info.collectType === 'SNMP_Trap') {
          this.$set(this.info.plugin, 'snmpv', '');
        }
      }
      // 筛选插件列表
      this.filterPluginList = this.allPluginList.filter(
        item => item.pluginType === newV && item.labelInfo.second_label === this.info.objectId
      );
      this.pluginList = this.filterPluginList.slice();
      this.handleSnmpPugin();
      // process类型插件后端内置
      if (newV === 'Process') {
        this.info.plugin.id = 'default_process';
      }
    },
    // SNMP
    handleSnmpPugin() {
      if (this.info.collectType === 'SNMP_Trap') {
        this.isSnmpSelected = true;
        // if (!isFirst) {
        //   this.$set(this.info.plugin, 'snmpv', '')
        // }
      }
    },
    handleDelPLugin() {
      const { plugin } = this.info;
      plugin.id = '';
      plugin.type = '';
      plugin.descMd = '';
      plugin.isOfficial = false;
      plugin.isSafety = false;
      plugin.createUser = '';
      plugin.updateUser = '';
      plugin.configJson = [];
      plugin.metricJson = [];
      plugin.osTypeList = [];
      this.$refs.selectPluin && (this.$refs.selectPluin.selectedNameCache = '');
    },
    // 选择插件版本时触发
    async handleSnmpVersion(id) {
      this.info.plugin.id = id;
      const index = 2;
      this.curAuthPriv = snmp.AuthPrivList[index];
      this.pluginTypeInfo(id, false, true);
      this.SnmpCanSave = false;
      this.SnmpVersionValidate();
    },
    // 选择插件时触发
    // biome-ignore lint/style/useDefaultParameterLast: <explanation>
    async handlePluginClick(val, loading = true, needSetConfig = true, curPluginType) {
      const { mode } = this.config;
      if (curPluginType === 'SNMP_Trap') {
        if (this.isSnmpSelected) {
          this.$set(this.info.plugin, 'snmpv', '');
        }
        this.isSnmpSelected = true;
      } else {
        if (mode === 'edit' || this.isClone) {
          this.$set(this.info.plugin, 'snmpv', `snmp_${this.snmpData.version}`);
          this.isSnmpSelected = true;
        } else {
          this.isSnmpSelected = false;
        }
        await this.pluginTypeInfo(val, loading, needSetConfig);
      }
      // this.initFormLabelWidth()
    },
    async getVariableData() {
      if (!this.tipsData?.length) {
        const data = await getCollectVariables().catch(() => []);
        this.tipsData = data;
      }
    },
    async pluginTypeInfo(val, _loading, needSetConfig) {
      // 获取提示输入数据
      this.loading = true;
      // 先去获取有关的所有插件，并处理数据
      await this.getPluginInfo(val)
        .then(data => {
          const { plugin } = this.info;
          const { configJson, host, port, isShowHost, isShowPort } = this.handlePluginConfigJson(
            data.plugin_type,
            data.config_json
          );
          plugin.type = data.plugin_type;
          plugin.descMd = data.description_md;
          plugin.isOfficial = data.is_official;
          plugin.isSafety = data.is_safety;
          plugin.createUser = data.create_user;
          plugin.updateUser = data.update_user;
          plugin.metricJson = data.metric_json || [];
          if (needSetConfig) {
            if (data.plugin_type === 'SNMP_Trap') {
              plugin.configJson = (configJson || []).map(item => {
                if (item.auth_json !== undefined) {
                  if (this.config.mode === 'edit' || this.isClone) {
                    this.SnmpAuthTemplate = deepClone(
                      item.template_auth_json[0].map(item => ({
                        ...item,
                        validate: { isValidate: false, content: '' },
                      }))
                    );
                  } else {
                    this.SnmpAuthTemplate = deepClone(
                      item.auth_json[0].map(item => ({ ...item, validate: { isValidate: false, content: '' } }))
                    );
                  }
                  plugin.SnmpAuthTemplate = this.SnmpAuthTemplate;
                  return {
                    auth_json: item.auth_json.map(items =>
                      items.map(item => ({
                        ...item,
                        validate: {
                          isValidate: false,
                          content: '',
                        },
                      }))
                    ),
                  };
                }
                return {
                  ...item,
                  validate: {
                    isValidate: false,
                    content: '',
                  },
                };
              });
            } else if (data.plugin_type === 'SNMP') {
              this.info.plugin.collectorJson = data.collector_json;
              plugin.configJson = (configJson || []).map(item => {
                this.SnmpAuthTemplate = [];
                if (item.auth_json !== undefined) {
                  if (this.config.mode === 'edit' || this.isClone) {
                    const authJson = item.auth_json;
                    for (const _item of authJson) {
                      for (const p of set) {
                        const mode = p.mode === 'collector' ? 'collector' : 'plugin';
                        const paramDefault = this.info.params[mode][p.key];
                        p.default = paramDefault;
                      }
                    }
                    return item;
                  }
                  return {
                    auth_json: [item.auth_json].map(items =>
                      items.map(item => ({
                        ...item,
                        validate: {
                          isValidate: false,
                          content: '',
                        },
                      }))
                    ),
                  };
                }
                if (this.config.mode === 'edit' || this.isClone) {
                  const mode = item.mode === 'collector' ? 'collector' : 'plugin';
                  const paramDefault = this.info.params[mode][item.key];
                  item.default = paramDefault;
                }

                return {
                  ...item,
                  validate: {
                    isValidate: false,
                    content: '',
                  },
                };
              });
            } else {
              plugin.configJson = (configJson || []).map(item => {
                try {
                  if (this.config.mode === 'edit' || this.isClone) {
                    const mode = item.mode === 'collector' ? 'collector' : 'plugin';
                    const paramDefault = this.info.params[mode][item.key || item.name];
                    if (item.type === 'file') {
                      item.default = paramDefault.filename;
                      item.file_base64 = paramDefault.file_base64;
                    } else {
                      item.default = paramDefault;
                    }
                  }
                } catch (error) {
                  console.log(error);
                }

                const result = {
                  ...item,
                  validate: {
                    isValidate: false,
                    content: '',
                  },
                };
                return result;
              });
            }
          }
          plugin.osTypeList = data.os_type_list || [];
          if (this.config.mode !== 'edit') {
            this.info.isShowHost = isShowHost;
            this.info.isShowPort = isShowPort;
            this.info.host = host;
            this.info.port = port;
            this.info.plugin.supportRemote = data.is_support_remote;
          }
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => (this.loading = false));
    },
    // 指标预览显示，传参options
    handlePreview() {
      const { plugin } = this.info;
      const { options } = this;
      options.pluginId = plugin.id;
      options.data = plugin.metricJson;
      options.isOfficial = plugin.isOfficial;
      options.isShow = true;
    },
    handleCancel() {
      this.$router.push({
        name: 'collect-config',
      });
    },
    validateProcessParams() {
      if (this.info.collectType === 'Process') {
        return this.$refs.process?.validate?.();
      }
      return true;
    },
    handleNext() {
      if (this.info.plugin.type === 'K8S') return;
      // 清空缓存的info
      this[SET_INFO_DATA](null);
      if (this.validate() && this.validateProcessParams()) {
        if (this.info.collectType === 'Log') {
          this.info.log = this.$refs.collectorLog.getLogParams();
          this.info.log.log_path = this.info.log.log_path.map(path => path.trim());
        } else if (this.info.collectType === 'Process') {
          this.info.process = this.processParams;
        }
        this.$emit('update:config', {
          ...this.config,
          set: { data: this.info, others: this.others, mode: 'edit', supportRemote: this.info.plugin.supportRemote },
        });
        this.$emit('next');
      }
    },
    handleTencentCloudNext() {
      this[SET_INFO_DATA](null);
      if (this.validate()) {
        this.$emit('update:config', {
          ...this.config,
          set: { data: this.info, others: this.others, mode: 'edit', supportRemote: this.info.plugin.supportRemote },
        });
        this.$emit('tencentCloudNext');
      }
    },
    async setEditOrCloneConfig(v, collectDetail) {
      // 编辑
      const {
        updateParams: { pluginId },
      } = v.data;
      if (collectDetail) {
        this.setPluginSelector(collectDetail);
        await this.handlePluginClick(pluginId, true, true);
      }
      if (collectDetail.collect_type === 'SNMP') {
        this.snmpIsOk = this.handleSnmpParamValidate();
        this.SnmpAuthCanSave = true;
      }
    },
    //
    async handleConfig(v) {
      this.loading = true;
      const { set } = v;
      const { id } = v.data;
      let collectDetail;
      const promiseList = [];
      this.others = set.others || {};
      if (id) {
        promiseList.push(this.getConfigInfo(id).then(data => (collectDetail = data)));
      }
      const handlePluginPageParams = () => {
        // 插件详情跳转过来
        if (!this.isClone && v.mode === 'add' && v.data?.updateParams?.pluginId) {
          const res = this.pluginSelectorObj.list.find(item => item.plugin_id === v.data.updateParams.pluginId);
          res && this.handlePluginChange(res);
        }
      };
      // 编辑的时候只获取单个插件
      if (this.config.mode === 'edit') {
        const pluginId = this.config.data?.updateParams?.pluginId;
        promiseList.push(
          retrieveCollectorPlugin(pluginId)
            .then(v => {
              this.pluginSelectorObj.list = [v];
              this.pluginSelectorObj.key = random(8);
              this.allPluginList = this.handlePluginList([v]);
            })
            .catch(() => {
              this.pluginSelectorObj.list = [];
              this.pluginSelectorObj.key = random(8);
              this.allPluginList = this.handlePluginList([]);
            })
        );
      } else {
        // 异步获取所有的插件列表 加速渲染
        if (!this.pluginSelectorObj.list?.length) {
          this.pluginListLoading = true;
          this.getPluginList()
            .then(() => {
              this.info.collectType && this.handleCollectTypeChange(this.info.collectType);
            })
            .catch(() => {})
            .finally(() => {
              if (this.isClone) {
                this.setEditOrCloneConfig(v, collectDetail);
              }
              handlePluginPageParams();
              this.pluginListLoading = false;
            });
        }
      }
      await Promise.allSettled(promiseList);
      // 从下一个页面跳转过来（上一步）
      if (set.mode === 'edit') {
        this.stepSetpluginSelector(set);
        this.info = set.data;
        if (set.data.log) {
          this.logData = set.data.log;
          this.logCanSave = true;
        } else if (set.data.process) {
          this.processParams = set.data.process;
        } else if (set.data.collectType === 'SNMP_Trap') {
          this.isSnmpSelected = true;
          const { plugin } = set.data;
          this.info.plugin.id = plugin.id;
          if (plugin.snmpv === this.SnmpVersion[2].id) {
            this.SnmpAuthTemplate = plugin.SnmpAuthTemplate;
            plugin.configJson.map(item => {
              if (item.key === 'security_level') {
                this.curAuthPriv = item.default;
              }
            });
          }
          this.SnmpCanSave = true;
          this.SnmpAuthCanSave = true;
        }
        if (set.data.collectType === 'SNMP') {
          this.snmpIsOk = this.handleSnmpParamValidate();
          this.SnmpAuthCanSave = true;
        }
      } else if (v.mode === 'edit') {
        // 编辑
        this.setEditOrCloneConfig(v, collectDetail);
      } else {
        handlePluginPageParams();
      }
      this.loading = false;
    },

    // 处理配置信息
    handleConfigInfo(data) {
      const pluginInfo = data.plugin_info;
      const { collector, plugin } = data.params;
      const tmpConfigJson = pluginInfo.config_json;
      // 将插件信息中 configJson 的值，改为 data.params 中对应的值
      for (const item of tmpConfigJson) {
        if (item.mode === 'collector') {
          item.default = collector[item.name];
        } else {
          item.default = plugin[item.name];
        }
      }
      const { configJson, host, port, isShowHost, isShowPort } = this.handlePluginConfigJson(
        pluginInfo.plugin_type,
        tmpConfigJson
      );
      if (data.collect_type === 'Log') {
        this.logData = data.params.log;
      } else if (data.collect_type === 'Process') {
        this.processParams = data.params.process;
      } else if (data.collect_type === 'SNMP_Trap') {
        this.snmpData = data.params.snmp_trap;
      }
      return {
        info: {
          id: data.id,
          bizId: data.bk_biz_id,
          name: data.name,
          objectType: data.target_object_type,
          objectId: data.label,
          period: collector.period,
          timeout: +(collector.timeout || 60),
          collectType: data.collect_type,
          isShowHost,
          isShowPort,
          host,
          port,
          params: data.params,
          plugin: {
            collectorJson: pluginInfo.collector_json,
            id: pluginInfo.plugin_id,
            type: pluginInfo.plugin_type,
            descMd: pluginInfo.description_md, //
            isOfficial: pluginInfo.is_official,
            isSafety: pluginInfo.is_safety,
            createUser: pluginInfo.create_user,
            updateUser: pluginInfo.update_user,
            metricJson: pluginInfo.metric_json,
            configJson: (configJson || []).map(item => ({
              ...item,
              validate: {
                isValidate: false,
                content: '',
              },
            })),
            osTypeList: pluginInfo.os_type_list,
            supportRemote: pluginInfo.is_support_remote,
          },
        },
        others: {
          targetNodeType: data.target_node_type,
          // targetNodes: data.target_nodes,
          targetNodes: data.target,
          remoteCollectingHost: data.remote_collecting_host,
        },
      };
    },
    // 获取插件列表
    getPluginList() {
      this.loading = true;
      const params = {
        search_key: '',
        plugin_type: '',
        page: 1,
        page_size: 1000,
        order: '-update_time',
        status: 'release',
        with_virtual: true,
      };
      return new Promise((resolve, reject) => {
        listCollectorPlugin(params)
          .then(data => {
            resolve(data);
            const { count } = data;
            const { list } = data;
            if (count) {
              const collectTypeList = [];
              for (const item of Object.keys(count)) {
                const set = this.pluginTypeMap[item];
                if (set) {
                  collectTypeList.push({
                    name: item,
                    alias: set,
                  });
                }
              }
              this.collectTypeList = collectTypeList;
            }
            this.pluginSelectorObj.list = list;
            this.pluginSelectorObj.key = random(8);
            this.allPluginList = this.handlePluginList(list);
          })
          .catch(err => {
            this.loading = false;
            reject(err);
          });
      });
    },
    // 处理插件列表数据
    handlePluginList(data) {
      const res = [];
      if (data.length) {
        for (const item of data) {
          res.push({
            pluginId: item.plugin_id,
            pluginDisplayName: item.plugin_display_name,
            pluginType: item.plugin_type,
            isOfficial: item.is_official,
            createUser: item.create_user,
            updateUser: item.update_user,
            updateTime: item.update_time,
            labelInfo: item.label_info,
          });
        }
      }
      return res;
    },
    // 获取插件信息
    async getPluginInfo(id) {
      // 编辑模式下的插件详细数据可以省略请求
      if (this.config.mode === 'edit' && this.pluginSelectorObj.list.length) {
        const pluginInfo = this.pluginSelectorObj.list.find(item => item.plugin_id === id);
        if (pluginInfo?.metric_json) return pluginInfo;
      }
      this.loading = true;
      return retrieveCollectorPlugin(id)
        .then(data => {
          this.pluginSelectorObj.list.push(data);
          return data;
        })
        .finally(() => {
          this.loading = false;
        });
    },
    setNavTitle(data) {
      this.$store.commit(
        'app/SET_NAV_TITLE',
        `${this.$t('route-' + '编辑配置').replace('route-', '')} - #${data.id} ${data.name}`
      );
    },
    updateNav(name = '') {
      const routeList = [];
      routeList.push({
        name,
        id: '',
      });
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
    },
    //  获取采集配置信息（编辑）
    getConfigInfo(id) {
      this.loading = true;
      return new Promise(resolve => {
        collectConfigDetail({ id })
          .then(data => {
            this.setNavTitle(data);
            const { info, others } = this.handleConfigInfo(data);
            this.updateNav(this.isClone ? this.$t('新建采集') : `${this.$t('编辑')} ${data.name}`);
            if (data.params.snmp_trap) {
              this.curAuthPriv = data.params.snmp_trap.security_level;
              this.SnmpCanSave = true;
              this.SnmpAuthCanSave = true;
            }
            if (this.isClone) info.name = `${info.name}_copy`;
            this.info = info;
            this.others = others;
            resolve(data);
          })
          .catch(() => {
            this.loading = false;
            resolve(false);
          });
      });
    },
    handlePluginConfigJson(type, configs = []) {
      let configJson = [];
      // snmp 多用户
      const snmpAuthJson = [];
      let host = null;
      let port = null;
      // 如果是插件类型为 'Exporter'，则显示绑定主机和绑定端口
      const data = configs.map(item => {
        if (item.type === 'file' && typeof item.default === 'object' && item.key !== 'yaml') {
          const temp = deepClone(item.default);
          item.default = temp.filename;
          item.file_base64 = temp.file_base64;
        }
        return item;
      });
      if (type === 'Exporter') {
        for (const item of data) {
          if (item.mode === 'collector' && item.name === 'host') {
            host = item;
          } else if (item.mode === 'collector' && item.name === 'port') {
            port = item;
          } else {
            configJson.push(item);
          }
        }
      } else if (type === 'SNMP_Trap') {
        configJson.push(...data);
        // data.forEach((item) => {
        //   if (item.auth_json !== undefined){
        //     snmpAuthJson = item.auth_json
        //   } else {
        //     configJson.push(item)
        //   }
        // })
      } else if (type === 'SNMP' && this.config.mode === 'edit') {
        configJson = data.map(item => {
          if (item.auth_json)
            item.auth_json = [item.auth_json.map(set => ({ ...set, validate: { isValidate: false, content: '' } }))];
          return item;
        });
        // configJson.push(...data)
      } else {
        configJson.push(...data);
      }
      return {
        configJson,
        host,
        port,
        isShowHost: host !== null,
        isShowPort: port !== null,
        snmpAuthJson,
      };
    },
    handleFilterPlugin(v) {
      const keyword = (v || '').toLowerCase();
      this.filterPluginList = this.pluginList.filter(
        item =>
          item.pluginId.toLowerCase().indexOf(keyword) > -1 ||
          (item.pluginDisplayName || '').toLowerCase().indexOf(keyword) > -1
      );
    },
    handleToAddPlugin() {
      this[SET_INFO_DATA](this.info);
      this.$router.push({
        name: 'plugin-add',
        params: { objectId: this.info.objectId },
      });
    },
    async handleSetPlugin() {
      const { params } = this.$route;
      if (params.pluginType) {
        this.info.collectType = params.pluginType;
      }
      if (params.pluginType && params.pluginId) {
        this.info.objectId = params.objectId;
        await this.handlePluginClick(params.pluginId);
        this.info.plugin.id = params.pluginId;
      }
    },
    handleIntroductionShow() {
      this.btn.show = !this.btn.show;
    },
    handleObjectIdChange(val) {
      // 获取选中的采集对象组的类型
      const groupObj = this.objectTypeOptions.find(
        item => item.children.length && item.children.findIndex(child => child.id === val) > -1
      );
      // 更新采集对象组类型
      this.handleUpdateObjectType(groupObj.id);
      if (this.info.collectType && this.info.collectType !== 'SNMP_Trap') {
        this.handleDelPLugin();
        if (this.info.collectType === 'Log') {
          // 更新采集方式为log的提交状态
          this.logCanSave && this.handleLogSave(true);
        } else if (this.info.collectType === 'Process' && val !== 'host_process') {
          // Process采集方式只有在采集对象为host_process(进程)时生效
          this.info.collectType = '';
        }
        this.filterPluginList = this.allPluginList.filter(
          item => item.pluginType === this.info.collectType && item.labelInfo.second_label === val
        );
        this.pluginList = this.filterPluginList.slice();
      } else {
        this.handleSnmpPugin();
      }
      this.handleSetObjTypeById(val);
    },
    handleSetObjTypeById(val) {
      this.info.objectType = this.objectTypeOptions.some(
        item => item.id === 'services' && item.children.some(set => set.id === val)
      )
        ? 'SERVICE'
        : 'HOST';
    },
    handleVariableTable() {
      this.isShowVariableTable = true;
    },
    handleUpdateObjectType(v) {
      this[SET_OBJECT_TYPE](v === 'services' ? 'SERVICE' : '');
    },
    handleProcessParamsChange(params) {
      this.processParams = params;
    },
    configJsonFileChange(file, item) {
      item.default = file.name;
      item.file_base64 = file.fileContent;
    },
    handleErrorMessage(msg, item) {
      item.validate.isValidate = !!msg;
      item.validate.content = msg;
    },
    handlePasswordInputName(val) {
      this.$emit('passwordInputName', val);
    },

    /* 编辑时回填插件选择 */
    setPluginSelector(data) {
      if (data.collect_type === 'Log') {
        this.pluginSelectorObj.id = LOG_PLUGIN_ID;
        this.pluginSelectorObj.objectIdDisable = false;
      } else if (data.collect_type === 'Process') {
        this.pluginSelectorObj.id = PROCESS_PLUGIN_ID;
        this.pluginSelectorObj.objectIdDisable = true;
      } else if (data.collect_type === 'SNMP_Trap') {
        this.pluginSelectorObj.id = `snmp_${data.params.snmp_trap.version}`;
        this.pluginSelectorObj.objectIdDisable = false;
      } else {
        this.pluginSelectorObj.id = data.plugin_info.plugin_id;
        this.pluginSelectorObj.objectIdDisable = true;
      }
      this.pluginSelectorObj.key = random(8);
    },

    /* 从选择目标回来时回填插件选择 */
    stepSetpluginSelector(set) {
      if (set.data.log) {
        this.pluginSelectorObj.id = LOG_PLUGIN_ID;
      } else if (set.data.process) {
        this.pluginSelectorObj.id = PROCESS_PLUGIN_ID;
        this.pluginSelectorObj.objectIdDisable = true;
      } else {
        const { plugin } = set.data;
        if (set.data.collectType === 'SNMP_Trap') {
          this.pluginSelectorObj.id = plugin.snmpv;
          this.pluginSelectorObj.objectIdDisable = false;
        } else {
          this.pluginSelectorObj.id = plugin.id;
          this.pluginSelectorObj.objectIdDisable = true;
        }
      }
      this.pluginSelectorObj.key = random(8);
    },

    /* 选择插件 */
    handlePluginChange(pluginInfo) {
      const collectChange = () => {
        this.info.collectType = pluginInfo.plugin_type;
        // 采集方式改变时，清空已有的插件信息
        this.handleDelPLugin();
        this.handleSnmpPugin();
        if (pluginInfo.plugin_type === 'SNMP_Trap') {
          this.$set(this.info.plugin, 'snmpv', '');
        }
        this.filterPluginList = this.allPluginList.filter(
          item => item.pluginType === pluginInfo.plugin_type && item.labelInfo.second_label === this.info.objectId
        );
        this.pluginList = this.filterPluginList.slice();
        // process类型插件后端内置
        if (pluginInfo.plugin_type === 'Process') {
          this.info.plugin.id = 'default_process';
        }
      };
      this.pluginSelectorObj.id = pluginInfo.plugin_id;
      if (pluginInfo.label_info) {
        // 指定采集对象
        this.info.objectId = pluginInfo.label_info.second_label;
        collectChange();
        this.info.plugin.id = pluginInfo.plugin_id;
        this.pluginSelectorObj.objectIdDisable = true;
        this.handlePluginClick(pluginInfo.plugin_id, false, true, pluginInfo.plugin_type);
      } else {
        // 不指定采集对象
        this.pluginSelectorObj.objectIdDisable = false;
        collectChange();
        if (pluginInfo.plugin_type === 'Log') {
          this.info.plugin.id = '';
        } else if (pluginInfo.plugin_type === 'SNMP_Trap') {
          this.info.plugin.id = '';
          this.info.plugin.snmpv = pluginInfo.plugin_id;
          this.handleSnmpVersion(pluginInfo.plugin_id);
        } else if (pluginInfo.plugin_type === 'Process') {
          /* 进程需要指定采集对象 */
          this.info.plugin.id = PROCESS_PLUGIN_ID;
          this.pluginSelectorObj.objectIdDisable = true;
          this.info.objectId = 'host_process';
        }
      }
      this.handleSetObjTypeById(this.info.objectId);
    },
    handleTagInput(item, key, val) {
      item.default[key] = val;
      if (Object.values(item.default).some(val => !val)) {
        item.validate.isValidate = true;
        item.validate.content = this.$t('标签格式应为key:value');
      } else {
        item.validate.isValidate = false;
      }
    },
    handleInput(item) {
      const valid = {
        content: '',
        validate: false,
      };
      if (item.required) {
        if (typeof item.default === 'object') {
          valid.validate = Array.isArray(item.default) ? !item.default.length : !Object.keys(item.default).length;
        } else {
          valid.validate = !item.default;
        }

        valid.validate && (valid.content = this.$t('必填项'));
      }
      item.validate = {
        content: valid.content,
        isValidate: valid.validate,
      };
      return valid;
    },
  },
};
</script>

<style lang="scss" scoped>
/* stylelint-disable no-descending-specificity */
.config-set {
  position: relative;
  display: flex;
  overflow: hidden;
  background-image: linear-gradient(270deg, #dcdee5 1px, rgba(0, 0, 0, 0) 1px, rgba(0, 0, 0, 0) 100%);
  background-size: 100% 100%;

  .set-edit {
    flex: 1;
    min-width: 529px;
    height: calc(100vh - 102px);
    padding: 41px 35px 41px 42px;
    overflow: auto;

    .edit-item {
      display: flex;
      align-items: center;
      min-height: 32px;
      margin-bottom: 20px;

      &.edit-item-host,
      &.edit-item-port {
        margin-bottom: 0px;
      }

      .item-label {
        position: relative;
        min-width: 75px;
        height: 32px;
        margin-right: 34px;
        font-size: 12px;
        line-height: 32px;
        color: #63656e;
        text-align: right;

        &.label-required:after {
          position: absolute;
          right: -9px;
          font-size: 12px;
          color: #f00;
          content: '*';
        }

        &.label-param {
          align-self: flex-start;
        }
      }

      .item-container {
        .container-tips {
          padding: 7px 0 9px 0;
          color: #63656e;

          &.required {
            position: relative;
            width: max-content;

            &::after {
              position: absolute;
              top: 7px;
              right: -9px;
              color: red;
              content: '*';
            }
          }

          span {
            color: #3a84ff;
            cursor: pointer;
          }
        }

        :deep(.reset-width) {
          width: 320px;

          &.custom-cycle {
            .cycle-unit {
              min-width: 32px;
              background-color: #f2f4f8;

              &::before {
                background-color: #c4c6cc;
              }

              &.line-active {
                &::before {
                  background-color: #3a84ff;
                }
              }

              &.unit-active {
                border-color: #3a84ff;
                box-shadow: 0 0 4px rgba(58, 132, 255, 0.4);
              }
            }
          }
        }

        .reset-big-width {
          width: 500px;
        }

        :deep(.bk-select.is-disabled) {
          background: #fafbfd;
          border-color: #dcdee5;
        }

        .type-radio {
          width: 94px;

          :deep(.icon-check:before) {
            content: '';
          }
        }

        .dms-insert-category {
          width: 500px;

          :deep(.param-container) {
            flex-direction: row;
          }
        }

        :deep(.param-container) {
          display: flex;
          flex-direction: column;
          font-size: 12px;

          .param-item {
            margin-bottom: 5px;

            @media only screen and (min-width: 1720px) {
              .reset-width {
                width: 438px;
              }
            }

            :last-child {
              margin-bottom: 0;
            }

            .group-prepend,
            .file-input-wrap .prepend {
              width: auto;
              max-width: 50%;
              background: #fafbfd;

              .bk-tooltip,
              .bk-tooltip-ref {
                width: 100%;
              }

              :deep(.prepend-text) {
                padding: 0 20px;
                overflow: hidden;
                text-overflow: ellipsis;
                font-size: 12px;
                line-height: 30px;
                white-space: nowrap;
              }
            }

            :deep(.group-prepend),
            :deep(.file-input-wrap .prepend) {
              width: auto;
              max-width: 50%;
              background: #fafbfd;

              .bk-tooltip,
              .bk-tooltip-ref {
                width: 100%;
              }

              :deep(.prepend-text) {
                padding: 0 20px;
                overflow: hidden;
                text-overflow: ellipsis;
                font-size: 12px;
                line-height: 30px;
                white-space: nowrap;
              }
            }

            :deep(.bk-form-input) {
              width: 100%;
            }
          }

          .prepend-text {
            padding: 0 20px;
            overflow: hidden;
            text-overflow: ellipsis;
            font-size: 12px;
            line-height: 30px;
            white-space: nowrap;

            &.required {
              position: relative;

              &::after {
                position: absolute;
                top: -1px;
                right: 7px;
                color: red;
                content: '*';
              }
            }
          }
        }

        :deep(.bk-radio-text:before) {
          position: absolute;
          top: 20px;
          left: 20px;
          width: 30px;
          height: 1px;
          content: ' ';
          border-bottom: 1px dashed #c4c6cc;
          border-bottom-left-radius: 2px;
        }

        .is-empty {
          .bk-select {
            border-color: #ff5656;
          }

          :deep(.tooltips-icon) {
            top: 8px;
          }
        }

        .btn-container {
          font-size: 0;

          .btn-preview {
            margin-right: 10px;
          }

          .btn-next {
            margin-right: 10px;

            &.disabled {
              color: #fff;
              background: #dcdee5;
            }
          }
        }

        .no-param {
          display: inline-flex;
          align-items: center;
          width: auto;
          height: 32px;

          .param-icon {
            width: 16px;
            height: 16px;
            font-size: 16px;
            color: #ffa327;
          }

          .param-text {
            height: 16px;
            margin-left: 7px;
            font-size: 12px;
            color: #63656e;
          }
        }

        .timeout-unit {
          display: flex;
          align-items: center;
          justify-content: center;
          min-width: 30px;
          height: 100%;
          font-size: 12px;
          background-color: #f2f4f8;
        }
      }
    }
  }

  .set-desc {
    position: absolute;
    right: 1px;
    z-index: 0;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    border-right: 1px solid #dcdee5;
    transition: right 0.3s;

    &-box {
      position: relative;
      right: 0;
      box-sizing: border-box;
      width: 400px;
      min-width: 400px;
      min-height: calc(100vh - 82px);
      border-left: 1px solid #dcdee5;
    }
  }

  .set-desc-show {
    right: -400px;
    border-right: 0;
  }

  .set-desc-btn {
    position: absolute;
    left: -24px;
    z-index: 9;
    width: 24px;
    height: 100px;
    padding-top: 43px;
    line-height: 100%;
    text-align: center;
    background: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 8px 0 0 8px;

    .icon {
      margin-bottom: 6px;
      font-size: 18px;
      color: #979ba5;
      transform: rotate(90deg);
    }

    &:hover {
      color: #3a84ff;
      cursor: pointer;
      background: #e1ecff;
      border-color: #3a84ff;

      .icon {
        color: #3a84ff;
      }
    }

    .icon-show {
      transform: rotate(-90deg);
    }
  }
}
</style>
