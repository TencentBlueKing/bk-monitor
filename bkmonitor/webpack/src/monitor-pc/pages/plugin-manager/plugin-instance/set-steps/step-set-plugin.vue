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
    ref="stepPlugin"
    class="step-plugin"
    v-bkloading="{ isLoading: data.isEdit ? pluginLoading : false }"
  >
    <div class="step-plugin-item">
      <div class="item-label item-required">
        {{ $t('所属') }}
      </div>
      <div class="item-container">
        <bk-select
          class="biz"
          v-model="bizList.value"
          :clearable="false"
          :disabled="isPublicPlugin || data.isEdit || ccBizId !== 0"
          :list="bizList.list"
          display-key="text"
          id-key="id"
          enable-virtual-scroll
        >
          <!-- <bk-option
            v-for="(biz, index) in bizList.list"
            :id="biz.id"
            :key="index"
            :name="biz.text"
          /> -->
        </bk-select>
        <div class="plugin-logo">
          <logo :logo.sync="pluginBasicInfo.logo" />
        </div>
      </div>
    </div>
    <div class="step-plugin-item">
      <div class="item-label item-required">
        {{ $t('插件ID') }}
      </div>
      <div class="item-container plugin-id">
        <verify-input
          :show-validate.sync="pluginBasicInfo.isNameLegal"
          :validator="{ content: pluginBasicInfo.nameErrorMsg }"
        >
          <bk-input
            class="item-input"
            v-model="pluginBasicInfo.name"
            :disabled="disabledPluginId"
            :placeholder="$t('英文')"
            @blur="checkPluginId"
          />
        </verify-input>
        <bk-checkbox
          style="vertical-align: baseline"
          v-model="isPublicPlugin"
          v-authority="{ active: !authority.MANAGE_PUBLIC_AUTH }"
          :class="{
            'auth-disabled': !authority.MANAGE_PUBLIC_AUTH,
          }"
          :disabled="!authority.MANAGE_PUBLIC_AUTH"
          @change="handlePublicPluginChange"
          @click.native="
            !authority.MANAGE_PUBLIC_AUTH && handleShowAuthorityDetail(pluginManageAuth.MANAGE_PUBLIC_AUTH)
          "
        >
          {{ $t('设为公共插件') }}
        </bk-checkbox>
      </div>
    </div>
    <div class="step-plugin-item">
      <div class="item-label">
        {{ $t('插件别名') }}
      </div>
      <div class="item-container">
        <bk-input
          class="item-input"
          v-model="pluginBasicInfo.alias"
          :placeholder="$t('别名')"
        />
      </div>
    </div>
    <div class="step-plugin-item plugin-type">
      <div class="item-label item-required">
        {{ $t('插件类型') }}
      </div>
      <div
        ref="containerWidth"
        class="item-container"
      >
        <div class="bk-button-group">
          <bk-button
            v-for="(pluginType, index) in pluginBasicInfo.type.list"
            v-show="!pluginBasicInfo.type.notShowType.includes(pluginType.id)"
            :class="{ 'is-selected': pluginType.id === pluginBasicInfo.type.value }"
            :disabled="disabledPluginId && pluginType.name !== pluginBasicInfo.type.value"
            :key="index"
            @click="handlePluginChange(pluginType.id)"
          >
            {{ pluginType.name }}
          </bk-button>
        </div>
        <div
          v-if="pluginTypeDes"
          class="description"
        >
          {{ pluginTypeDes }}
          <span
            class="doc-link"
            @click="handleGotoLink(pluginBasicInfo.type.value)"
            >{{ $t('前往文档中心') }} <span class="icon-monitor icon-mc-link"
          /></span>
        </div>
      </div>
    </div>
    <div
      class="step-plugin-item label-bottom upload-package"
      v-show="['Exporter', 'DataDog'].includes(pluginBasicInfo.type.value)"
    >
      <div class="item-label item-required">
        {{ $t('上传内容') }}
      </div>
      <div class="item-container">
        <div
          style="margin: -8px 0 0 -10px"
          class="upload-container"
        >
          <div
            v-for="(system, index) in systemTabs.list"
            class="upload-item"
            v-show="pluginBasicInfo.type.value === 'Exporter'"
            :key="`${index}-Exporter`"
          >
            <mo-upload
              :collector="pluginBasicInfo.exporterCollector[system.name]"
              :is-edit="data.isEdit"
              :plugin-id="pluginBasicInfo.name"
              :plugin-type="pluginBasicInfo.type.value"
              :ref="`uploadFile-exporter-${index}`"
              :system="system.name"
            />
          </div>
          <div
            v-for="(system, index) in systemTabs.list"
            class="upload-item"
            v-show="pluginBasicInfo.type.value === 'DataDog'"
            :key="`${index}-DataDog`"
          >
            <mo-upload
              :collector="pluginBasicInfo.dataDogCollector[system.name]"
              :is-edit="data.isEdit"
              :plugin-id="pluginBasicInfo.name"
              :plugin-type="pluginBasicInfo.type.value"
              :ref="`uploadFile-datadog-${index}`"
              :system="system.name"
              @change="getCheckNameChange"
              @yaml="getYaml"
            />
          </div>
        </div>
      </div>
    </div>
    <div
      class="step-plugin-item label-bottom"
      v-show="['Script', 'JMX', 'DataDog'].includes(pluginBasicInfo.type.value)"
    >
      <div class="item-label item-required">
        {{ $t('采集配置') }}
      </div>
      <div class="item-container editor-wrapper">
        <new-plugin-monaco
          ref="newPluginMonaco"
          :mode="data.type"
          :systems="testSystemList"
          :type="pluginBasicInfo.type.value"
          :value="pluginMonaco.defaultValue"
          :width="pluginMonaco.width"
          @switcher-change="handleOsSwitcherChange"
        />
      </div>
    </div>
    <div
      class="step-plugin-item"
      v-show="pluginBasicInfo.type.value === 'Exporter'"
    >
      <div class="item-label item-required">
        {{ $t('绑定端口') }}
      </div>
      <div class="item-container">
        <verify-input
          class="run-port"
          :show-validate.sync="pluginBasicInfo.isPortLegal"
          :validator="{ content: $t('输入合法端口') }"
        >
          <param-card
            v-model="pluginBasicInfo.port"
            :placeholder="$t('输入端口')"
            title="${port}"
            @blur="pluginBasicInfo.isPortLegal = !portRgx.test(pluginBasicInfo.port.trim())"
          />
        </verify-input>
      </div>
    </div>
    <div
      class="step-plugin-item"
      v-show="pluginBasicInfo.type.value === 'Exporter'"
    >
      <div class="item-label">
        {{ $t('绑定主机') }}
      </div>
      <div class="item-container">
        <param-card
          v-model="pluginBasicInfo.bindUrl"
          :disabled="true"
          :placeholder="$t('输入主机')"
          title="${host}"
        />
      </div>
    </div>
    <div
      class="step-plugin-item"
      v-show="pluginBasicInfo.type.value === 'SNMP'"
    >
      <div class="item-label item-required">
        {{ $t('SNMP版本') }}
      </div>
      <div class="item-container editor-wrapper">
        <bk-select
          v-model="pluginBasicInfo.snmpVersion"
          :clearable="false"
        >
          <bk-option
            v-for="i in 3"
            :id="i"
            :key="i"
            :name="`v${i}`"
          />
        </bk-select>
      </div>
    </div>
    <div
      class="step-plugin-item"
      v-show="pluginBasicInfo.type.value === 'SNMP'"
    >
      <div class="item-label item-required">
        {{ $t('采集配置') }}
      </div>
      <div class="item-container editor-wrapper">
        <import-file
          class="snmp-yaml-import"
          :base64="false"
          :file-content="pluginBasicInfo.snmpConfig.content"
          :file-name="pluginBasicInfo.snmpConfig.name"
          :placeholder="$i18n.t('点击上传文件')"
          accept=".yaml"
          @change="handleFileChange"
        />
      </div>
    </div>
    <div
      ref="itemParam"
      :class="[
        'step-plugin-item',
        'define-param',
        hasDefineParam ? 'has-param' : '',
        pluginBasicInfo.type.value === 'Exporter' ? 'plugin-exporter' : '',
      ]"
    >
      <div
        :class="{ 'item-label': true, 'param-label': true, 'item-required': pluginBasicInfo.type.value === 'Exporter' }"
      >
        {{ $t('定义参数') }}
      </div>
      <div class="item-container">
        <div
          v-for="(param, index) in params"
          class="item-param"
          :key="index"
          @click="handleEditParam(param)"
        >
          <div class="wrapper">
            <span :class="{ 'param-name': true, required: param.required }">
              {{ param.alias || param.name }}
            </span>
            <span
              class="bk-icon icon-close-circle-shape"
              v-show="!param.disabled"
              @click.stop="handleDeleteParam(param)"
            />
          </div>
        </div>
        <template v-if="!['JMX', 'SNMP'].includes(pluginBasicInfo.type.value)">
          <span
            v-if="params.length"
            class="bk-icon icon-plus"
            @click="handleAddParam"
          />
          <span
            v-else
            class="add-params-text"
            @click="handleAddParam"
          >
            {{ $t('点击添加参数') }}
          </span>
        </template>
      </div>
    </div>
    <div
      class="step-plugin-item"
      v-show="pluginBasicInfo.type.value === 'Exporter'"
    >
      <div class="item-label" />
      <div class="item-container">
        <p class="exporter-tips">
          {{ $t('Exporter的类型插件需要使用${host} ${port}来定义启动参数。 如 --listen=${host}:${port}') }}
        </p>
      </div>
    </div>
    <div class="step-plugin-item">
      <div class="item-label item-required">
        {{ $t('分类') }}
      </div>
      <div class="item-container">
        <verify-input
          :show-validate="pluginBasicInfo.noLabel"
          :validator="{ content: $t('选择分类') }"
        >
          <bk-select
            v-model="pluginBasicInfo.label.value"
            :clearable="false"
            @change="validateLabel"
          >
            <bk-option-group
              v-for="(group, index) in pluginBasicInfo.label.list"
              :key="index"
              :name="group.name"
            >
              <bk-option
                v-for="(option, i) in group.children"
                :disabled="option.disabled"
                :id="option.id"
                :key="i"
                :name="option.name"
              >
                <div
                  v-bk-tooltips="{
                    content: $t('有采集任务时不允许修改'),
                    disabled: !option.disabled,
                    placement: 'right',
                    flip: false,
                  }"
                >
                  {{ option.name }}
                </div>
              </bk-option>
            </bk-option-group>
          </bk-select>
        </verify-input>
      </div>
    </div>
    <div class="step-plugin-item remote-collector">
      <div class="item-label">
        {{ $t('远程采集') }}
      </div>
      <div class="item-container">
        <bk-switcher
          v-model="remoteCollector"
          size="small"
        /><span>{{ $t('支持远程采集') }}</span>
        <span class="description">{{
          $t('（功能开启并保存成功后，将无法关闭，请确认是否支持远程采集后，谨慎开启！）')
        }}</span>
      </div>
    </div>
    <div
      style="align-items: normal"
      class="step-plugin-item"
    >
      <div class="item-label">
        {{ $t('描述') }}
      </div>
      <div class="item-container">
        <div class="markdown-editor">
          <editor
            v-model="pluginBasicInfo.desc"
            mode="wysiwyg"
          />
        </div>
      </div>
    </div>
    <div class="step-plugin-item next-step">
      <div class="item-label" />
      <div>
        <bk-button
          v-authority="{ active: !authority.MANAGE_AUTH }"
          :disabled="!!bkBtnIcon"
          :icon="bkBtnIcon"
          theme="primary"
          @click="authority.MANAGE_AUTH ? handleNextStep() : handleShowAuthorityDetail()"
        >
          {{ $t('下一步') }}
        </bk-button>
      </div>
    </div>
    <config-param
      :param="configParam.value"
      :param-list="params"
      :plugin-type="pluginBasicInfo.type.value"
      :show.sync="configParam.show"
      @confirm="handleConfirm"
    />
    <polling-loading
      :show.sync="registerDialog.show"
      :status="registerDialog.status"
    />
    <bk-dialog
      v-model="pluginChangeMsg.show"
      :close-icon="false"
      header-position="left"
    >
      <div class="change-description">
        <span class="title"> {{ $t('插件变更说明') }} </span>
        <bk-input
          v-model="pluginChangeMsg.msg"
          type="textarea"
        />
      </div>
      <div slot="footer">
        <bk-button
          :title="$t('确认')"
          theme="primary"
          @click="handleUpdateDesc"
          @keyup.enter="handleUpdateDesc"
        >
          {{ $t('确定') }}
        </bk-button>
        <bk-button
          style="margin-left: 8px"
          @click="handleCancelDesc"
        >
          {{ $t('取消') }}
        </bk-button>
      </div>
    </bk-dialog>
  </div>
</template>
<script>
import { addListener, removeListener } from '@blueking/fork-resize-detector';
import { queryAsyncTaskResult } from 'monitor-api/modules/commons';
import {
  checkIdCollectorPlugin,
  createCollectorPlugin,
  editCollectorPlugin,
  retrieveCollectorPlugin,
} from 'monitor-api/modules/model';
import { pluginRegister } from 'monitor-api/modules/plugin';
import Editor from 'monitor-ui/markdown-editor/editor.tsx';
import { mapActions, mapGetters } from 'vuex';

import PollingLoading from '../../../../components/polling-loading/polling-loading';
import VerifyInput from '../../../../components/verify-input/verify-input.vue';
import documentLinkMixin from '../../../../mixins/documentLinkMixin';
import formLabelMixin from '../../../../mixins/formLabelMixin';
import { SET_NAV_ROUTE_LIST } from '../../../../store/modules/app';
import * as pluginManageAuth from '../../authority-map';
import Logo from '../logo/logo';
import MoUpload from '../upload/upload';
import ConfigParam from './components/config-param';
import ImportFile from './components/import-file';
import NewPluginMonaco from './components/new-plugin-monaco';
import ParamCard from './components/param-card';

import './codemirror.css';

export default {
  name: 'StepSetPlugin',
  components: {
    MoUpload,
    ParamCard,
    Logo,
    VerifyInput,
    Editor,
    PollingLoading,
    ConfigParam,
    NewPluginMonaco,
    ImportFile,
  },
  mixins: [documentLinkMixin, formLabelMixin],
  inject: ['authority', 'handleShowAuthorityDetail'],
  props: {
    data: {
      type: Object,
      default: () => ({}),
    },
    show: {
      type: Boolean,
    },
    step: {
      type: Number,
      default: 0,
    },
  },
  data() {
    const url =
      process.env.NODE_ENV === 'development'
        ? process.env.proxyUrl + window.static_url
        : location.origin + window.static_url;
    return {
      pluginManageAuth,
      testSystemList: [],
      bkBtnIcon: '',
      staticUrl: url,
      initBackFillData: false,
      pluginData: {},
      pluginLoading: true,
      curCheckName: '',
      pluginMonaco: {
        selectedSystemList: [],
        defaultValue: {},
        yaml: '',
        width: 0,
      },
      pluginBasicInfo: {
        name: '',
        stage: null,
        isNameLegal: false,
        relatedConfCount: 0,
        bindUrl: '127.0.0.1',
        nameErrorMsg: this.$t('输入插件名称，仅以字母开头，仅支持字母、下划线和数字'),
        alias: '',
        logo: '',
        type: {
          list: [
            {
              id: 'Script',
              name: 'Script',
            },
            {
              id: 'JMX',
              name: 'JMX',
            },
            {
              id: 'Exporter',
              name: 'Exporter',
            },
            {
              id: 'DataDog',
              name: 'DataDog',
            },
            {
              id: 'Pushgateway',
              name: 'BK-Pull',
            },
            {
              id: 'SNMP',
              name: 'SNMP',
            },
          ],
          value: 'Script',
          notShowType: [],
        },
        port: '',
        params: [],
        jmxParams: [
          {
            name: 'port',
            mode: 'collector',
            alias: this.$t('监听端口'),
            type: 'text',
            default: '',
            description: '',
            disabled: true,
          },
          {
            name: 'jmx_url',
            mode: 'opt_cmd',
            type: 'text',
            alias: this.$t('连接字符串'),
            default: '',
            description: '',
            disabled: true,
          },
          {
            name: 'username',
            mode: 'opt_cmd',
            type: 'text',
            alias: this.$t('用户名'),
            default: '',
            description: '',
            disabled: true,
          },
          {
            name: 'password',
            mode: 'opt_cmd',
            type: 'password',
            alias: this.$t('密码'),
            default: '',
            description: '',
            disabled: true,
          },
        ],
        dataDogParams: [
          {
            name: 'python_path',
            type: 'text',
            mode: 'collector',
            default: 'python',
            description: 'Python 程序路径',
            disabled: true,
          },
        ],
        pushGatewayParams: [
          {
            name: 'metrics_url',
            mode: 'collector',
            type: 'text',
            alias: this.$t('采集URL'),
            default: '',
            description: '',
            disabled: true,
          },
          {
            name: 'username',
            mode: 'collector',
            type: 'text',
            alias: this.$t('用户名'),
            default: '',
            description: '',
            disabled: true,
          },
          {
            name: 'password',
            mode: 'collector',
            type: 'password',
            alias: this.$t('密码'),
            default: '',
            description: '',
            disabled: true,
          },
        ],
        snmpParams: {
          commons: [
            {
              name: this.$t('监听端口'),
              mode: 'collector',
              type: 'text',
              default: '',
              key: 'port',
              description: this.$t('监听端口'),
              disabled: true,
            },
            {
              name: this.$t('绑定地址'),
              mode: 'collector',
              type: 'text',
              default: '0.0.0.0',
              key: 'host',
              description: this.$t('绑定地址'),
              disabled: true,
            },
            {
              name: this.$t('设备端口'),
              mode: 'collector',
              type: 'text',
              default: '161',
              key: 'snmp_port',
              description: this.$t('snmp设备端口'),
              disabled: true,
            },
          ],
          1: [
            {
              name: 'community',
              mode: 'opt_cmd',
              type: 'text',
              default: 'public',
              key: 'community',
              description: this.$t('团体名'),
              disabled: true,
            },
          ],
          2: [
            {
              name: 'community',
              mode: 'opt_cmd',
              type: 'text',
              default: 'public',
              key: 'community',
              description: this.$t('团体名'),
              disabled: true,
            },
          ],
          3: [
            {
              name: this.$t('认证信息'),
              mode: 'opt_cmd',
              type: 'text',
              default: '',
              key: 'auth_json',
              description: this.$t('认证信息'),
              disabled: true,
              auth_json: [
                {
                  default: '',
                  mode: 'opt_cmd',
                  type: 'text',
                  key: 'security_name',
                  name: this.$t('安全名'),
                  description: this.$t('安全名'),
                },
                {
                  default: '',
                  mode: 'opt_cmd',
                  type: 'text',
                  key: 'context_name',
                  name: this.$t('上下文名称'),
                  description: this.$t('上下文名称'),
                },
                {
                  default: 'noAuthNoPriv',
                  election: ['authPriv', 'authNoPriv', 'noAuthNoPriv'],
                  mode: 'opt_cmd',
                  type: 'list',
                  key: 'security_level',
                  name: this.$t('安全级别'),
                  description: this.$t('安全级别'),
                },
                {
                  default: 'AES',
                  election: ['MD5', 'SHA', 'DES', 'AES'],
                  mode: 'opt_cmd',
                  type: 'list',
                  key: 'authentication_protocol',
                  name: this.$t('验证协议'),
                  description: this.$t('验证协议'),
                  auth_priv: {
                    noAuthNoPriv: {
                      need: false,
                    },
                    authNoPriv: {
                      need: true,
                      election: ['MD5', 'SHA'],
                    },
                    authPriv: {
                      need: true,
                      election: ['MD5', 'SHA', 'DES', 'AES'],
                    },
                  },
                },
                {
                  default: '',
                  mode: 'opt_cmd',
                  type: 'text',
                  key: 'authentication_passphrase',
                  name: this.$t('验证口令'),
                  description: this.$t('验证口令'),
                  auth_priv: {
                    noAuthNoPriv: {
                      need: false,
                    },
                    authNoPriv: {
                      need: true,
                    },
                    authPriv: {
                      need: true,
                    },
                  },
                },
                {
                  default: 'AES',
                  election: ['DES', 'AES'],
                  mode: 'opt_cmd',
                  type: 'list',
                  key: 'privacy_protocol',
                  name: this.$t('隐私协议'),
                  description: this.$t('隐私协议'),
                  auth_priv: {
                    NoAuthNoPriv: {
                      need: false,
                    },
                    authNoPriv: {
                      need: false,
                    },
                    authPriv: {
                      need: true,
                      election: ['DES', 'AES'],
                    },
                  },
                },
                {
                  default: '',
                  mode: 'opt_cmd',
                  type: 'text',
                  key: 'privacy_passphrase',
                  name: '私钥',
                  description: '私钥',
                  auth_priv: {
                    noAuthNoPriv: {
                      need: false,
                    },
                    authNoPriv: {
                      need: false,
                    },
                    authPriv: {
                      need: true,
                    },
                  },
                },
              ],
            },
          ],
        },
        snmpVersion: '1', // 1 | 2 | 3 snmp插件的版本参数
        snmpConfig: {
          name: '',
          content: '',
        },
        label: {
          list: [],
          value: '',
        },
        infoVersion: null,
        configVersion: null,
        scriptCollector: {},
        noLabel: false,
        exporterCollector: {},
        dataDogCollector: {},
        jmxCollector: {},
        metricJson: [],
        isPortLegal: false,
        desc: '',
      },
      portRgx: /^([1-9]\d{0,4}|[1-5]\d{5}|6[0-4]\d{4}|65[0-4]\d{3}|655[0-2]\d{2}|6553[0-5])$/,
      remoteCollector: false,
      disabledRemote: false,
      isContentEmpty: false,
      isPublicPlugin: false,
      bizList: {
        list: [],
        value: +this.$store.getters.bizId,
      },
      ccBizId: +this.$store.getters.bizId,
      systemTabs: {
        list: [],
      },
      hasHostPort: true,
      field: [],
      tag: {
        value: '',
        error: false,
      },
      hasDefineParam: false,
      configParam: {
        show: false,
        value: {},
        title: this.$t('定义参数'),
        type: 'param',
        isEdit: false,
        index: 0,
      },
      registerDialog: {
        show: false,
        status: {
          msg: this.$t('保存中...'),
          failMsg: '',
        },
      },
      pluginChangeMsg: {
        show: false,
        isChange: true,
        msg: '',
      },
      reservedWord: [],
      isImport: false,
    };
  },
  computed: {
    ...mapGetters('plugin-manager', ['pluginConfigCache']),
    isSuperUser() {
      return this.$store.getters.isSuperUser;
    },
    params() {
      const info = this.pluginBasicInfo;
      const param = {
        JMX: info.jmxParams,
        Script: info.params,
        Exporter: info.params,
        DataDog: [...info.dataDogParams, ...info.params],
        Pushgateway: [...info.pushGatewayParams, ...info.params],
        SNMP: [...info.snmpParams.commons, ...info.snmpParams[info.snmpVersion]],
      };
      return param[info.type.value];
    },
    disabledEditConfig() {
      return this.pluginBasicInfo.type.value === 'JMX' || this.pluginBasicInfo.type.value === 'Pushgateway';
    },
    disabledPluginId() {
      return this.data.isEdit || this.data.back;
    },
    isPrivate() {
      return this.pluginBasicInfo.type.value === 'DataDog' || this.pluginBasicInfo.type.value === 'Built-In';
    },
    mdContent() {
      return `### ${this.$t('依赖说明')}

> ${this.$t('说明运行该插件的环境依赖，如运行在哪个版本上，只支持哪些版本的采集等')}。

${this.$t('如')}：
* ${this.$t('版本支持')}: Apache 2.x
* ${this.$t('环境依赖')}: Python

#### ${this.$t('配置说明')}

> ${this.$t('运行该插件需要进行哪些配置。如Apache的status的设置')}。

#### ${this.$t('采集原理')}

> ${this.$t('说明采集的原理过程，可以更好的方便使用')}

${this.$t('如')}：
${this.$t('采集器将定期访问 http://127.0.0.1/server-status 以获取Apache的指标数据')}。`;
    },
    pluginTypeDes() {
      const des = {
        Script: this.$t('由用户自定义脚本实现数据采集，标准输出监控的数据格式即可。 更多介绍'),
        JMX: this.$t('对于开启了JMX的服务，可以方便进行配置制作自己的插件。更多介绍'),
        Exporter: this.$t('Prometheus的Exporter采集组件，可以快速转化为蓝鲸的插件。 更多介绍'),
        DataDog: this.$t('Datadog的采集Agent，可以快速的转化为蓝鲸的插件。更多介绍'),
        Pushgateway: this.$t('可以定义远程拉取的插件，如拉取pushgateway的数据。更多介绍'),
      };
      return des[this.pluginBasicInfo.type.value];
    },
    needRegister() {
      return !this.isEdit || this.pluginBasicInfo.status === 'draft' || !this.pluginData.sameConfig;
    },
  },
  async created() {
    this.updateNavData(this.data.pluginId ? `${this.$t('编辑')}` : this.$t('新建插件'));
    // 预设采集选择的分类
    this.pluginBasicInfo.label.value = this.$route.params.objectId;
    this.defaultCheckOptions();
    this.pluginBasicInfo.desc = this.mdContent;
    this.bizList.list = this.$store.getters.bizList.slice();
    this.bizList.list.unshift({ id: 0, text: this.$t('全业务') });
    this.pluginLoading = true;
    const list = [this.getOsList(), this.getLabels(), this.getReservedWords()];
    const resultList = await Promise.all(list).catch(() => false);
    if (resultList) {
      this.getSystemTabs(resultList[0]);
      this.getLabelList(resultList[1]);
      this.reservedWord = resultList[2];
    } else {
      this.pluginLoading = false;
      return;
    }
    if (this.data.pluginId) {
      await this.getPluginInfo().catch(() => false);
    } else if (this.data.pluginData) {
      this.backFillData(this.data.pluginData);
    }
    if (this.data.type === 'import') {
      this.checkPluginId();
    }
    this.pluginLoading = false;
  },

  mounted() {
    this.pluginMonaco.width = this.$refs.containerWidth.clientWidth;
    addListener(this.$refs.stepPlugin, this.calculationEditorWidth);
    this.$nextTick().then(() => {
      this.initFormLabelWidth();
      if (this.data.type === 'import') {
        this.resetScroll();
      }
    });
  },
  beforeDestroy() {
    removeListener(this.$refs.stepPlugin, this.calculationEditorWidth);
  },
  methods: {
    ...mapActions('plugin-manager', ['getOsList', 'getLabels', 'getReservedWords']),
    // 点击设为公共插件触发
    handlePublicPluginChange(v) {
      this.isPublicPlugin = v;
      this.bizList.value = v ? 0 : +this.$store.getters.bizId;
    },
    /**
     * 由于monaco宽度无法自适应，父容器被monaco撑开，无法获取页面size后真实的容器宽度，
     * 所以使用容器兄弟元素的宽度
     */
    calculationEditorWidth() {
      this.pluginMonaco.width = this.$refs.containerWidth.clientWidth;
    },
    /**
     * @description 添加参数
     * @param { Object } param
     */
    handleConfirm(param) {
      if (this.configParam.isEdit) {
        this.pluginBasicInfo.params.splice(this.configParam.index, 1, param);
      } else {
        this.pluginBasicInfo.params.push(param);
      }
      if (this.pluginBasicInfo.type.value === 'Exporter') {
        this.validateExporterParam();
      }
      this.$nextTick(() => {
        this.hasDefineParam = this.$refs.itemParam.clientHeight > 40;
      });
    },

    /**
     * @description 删除参数
     * @param { Number } index
     */
    handleDeleteParam(param) {
      const ind = this.pluginBasicInfo.params.findIndex(item => item === param);
      this.pluginBasicInfo.params.splice(ind, 1);
    },
    /**
     * @description 切换插件
     * @param { String } val
     */
    handlePluginChange(val) {
      this.pluginBasicInfo.type.value = val;
      if (val === 'Pushgateway') {
        this.pluginBasicInfo.params = this.pluginBasicInfo.params.filter(item => item.mode === 'dms_insert');
      }
      if (!this.data.isEdit && !this.initBackFillData) {
        this.remoteCollector = val === 'JMX' || val === 'Pushgateway' || val === 'SNMP';
      }
      if (!this.data.isEdit && this.disabledRemote && !this.initBackFillData) {
        this.disabledRemote = false;
      }
      if (this.initBackFillData && typeof val === 'string') {
        this.initBackFillData = false;
      }
    },
    /**
     * @description 显示添加参数的dialog
     */
    handleAddParam() {
      this.configParam.show = true;
      this.configParam.isEdit = false;
      this.configParam.value = {};
    },
    /**
     * @description 检查插件ID是否合法
     */
    async checkPluginId() {
      const { pluginBasicInfo } = this;
      if (pluginBasicInfo.name && !pluginBasicInfo.isNameLagal) {
        const res = await checkIdCollectorPlugin(
          { plugin_id: this.pluginBasicInfo.name.trim() },
          { needRes: true, needMessage: false, needTraceId: false }
        ).catch(error => error);
        this.pluginBasicInfo.isNameLegal = !res.result;
        this.pluginBasicInfo.nameErrorMsg = this.$t(res.message);
      } else if (!this.pluginBasicInfo.name) {
        this.pluginBasicInfo.nameErrorMsg = this.$t(
          '输入插件名称，仅以字母开头，仅支持字母、下划线和数字, 长度不能超过30个字符'
        );
        this.pluginBasicInfo.isNameLegal = true;
      }
      return !this.pluginBasicInfo.isNameLegal;
    },
    /**
     * @description 编辑参数
     */
    handleEditParam(param) {
      this.configParam.value = param;
      const ind = this.pluginBasicInfo.params.findIndex(item => item === param);
      this.configParam.index = ind;
      this.configParam.show = true;
      this.configParam.isEdit = true;
    },
    /**
     * @description 获取datadog文件的checkname
     */
    getCheckNameChange(name) {
      this.curCheckName = name;
    },
    /**
     * @description 获取Datadog的yaml
     * @param { String } yaml
     * @param { String } system
     */
    getYaml(yaml, system) {
      if (this.pluginBasicInfo.type.value === 'DataDog') {
        this.pluginMonaco[system] = yaml;
        let text = '';
        this.systemTabs.list.forEach(sys => {
          text += `\n${this.pluginMonaco[sys.name] || ''}`;
        });
        this.$set(this.pluginMonaco.defaultValue, 'DataDog', { text, lang: 'yaml' });
      }
    },
    bkMessage(theme, message, delay = 3000) {
      this.$bkMessage({ theme, message, delay, isSingleLine: false, ellipsisLine: 0 });
    },
    /** 更新面包屑 */
    updateNavData(name = '') {
      if (!name) return;
      const routeList = [];
      routeList.push({
        name,
        id: '',
      });
      this.$store.commit(`app/${SET_NAV_ROUTE_LIST}`, routeList);
    },
    /**
     * @description 获取插件信息
     */
    async getPluginInfo() {
      if (!this.data.pluginId) return;
      this.updateNavData(`${this.$t('编辑')} ${this.data.pluginId}`);
      this.pluginLoading = true;
      const result = await retrieveCollectorPlugin(this.data.pluginId).catch(() => {
        this.pluginLoading = false;
      });
      if (result) {
        this.backFillData(result);
        const msg = `${this.$t('上次变更，版本号')}${result.config_version}.${result.info_version},
                        ${this.$t('最近更新人')}:${result.update_user},${this.$t('修改时间')}:${result.update_time}`;
        this.$bus.$emit('showmsg', msg);
      }
      this.resetScroll();
    },
    resetScroll() {
      const timer = setTimeout(() => {
        this.$bus.$emit('resetscroll');
        this.pluginLoading = false;
        clearTimeout(timer);
      }, 500);
    },
    /**
     * @description 回填参数
     * @param { Object } plugin
     */
    backFillData(plugin) {
      this.initBackFillData = true;
      this.pluginBasicInfo.is_split_measurement = plugin.is_split_measurement;
      this.pluginBasicInfo.enable_field_blacklist = plugin.enable_field_blacklist;
      this.pluginBasicInfo.name = plugin.plugin_id;
      this.pluginBasicInfo.stage = plugin.stage;
      this.pluginBasicInfo.logo = plugin.logo ? `data:image/png;base64,${plugin.logo}` : plugin.plugin_id.slice(0, 1);
      this.pluginBasicInfo.alias = plugin.plugin_display_name;
      this.pluginBasicInfo.type.value = plugin.plugin_type;
      this.pluginBasicInfo.desc = plugin.description_md;
      this.pluginBasicInfo.label.value = plugin.label;
      this.bizList.value =
        plugin.bk_biz_id === undefined || !this.$store.getters.isSuperUser
          ? this.$store.getters.bizId
          : plugin.bk_biz_id;
      this.pluginBasicInfo.configVersion = plugin.config_version;
      this.pluginBasicInfo.metricJson = plugin.metric_json;
      this.pluginBasicInfo.infoVersion = plugin.info_version;
      this.pluginBasicInfo.signature = plugin.signature || '';
      this.pluginBasicInfo.status = plugin.status || '';
      this.remoteCollector = plugin.is_support_remote; // 用户是否勾选了远程采集
      this.disabledRemote = plugin.is_support_remote; // 判断远程采集是否可以操作，该值只取决于返回数据
      this.pluginChangeMsg.msg = plugin.version_log;
      this.isImport = this.data.type === 'import';
      this.pluginBasicInfo.relatedConfCount = plugin.related_conf_count; // 插件关联的配置数量
      this.pluginBasicInfo.label.list.forEach(item => {
        const hasLabel = item.children.some(child => child.id === plugin.label);
        item.children.forEach(child => {
          if (plugin.related_conf_count && this.data.isEdit) {
            child.disabled = !hasLabel;
          } else {
            child.disabled = false;
          }
        });
      });
      // 全业务，`公共插件` 为 true
      this.pluginMonaco.defaultValue = {};
      this.isPublicPlugin = plugin.bk_biz_id === 0;
      if (plugin.plugin_type === 'Exporter') {
        this.pluginBasicInfo.exporterCollector = plugin.collector_json;
      } else if (plugin.plugin_type === 'Script') {
        const keys = Object.keys(plugin.collector_json);
        this.pluginMonaco.selectedSystemList = keys.filter(item => this.systemTabs.list.some(sys => sys.name === item));
        this.pluginMonaco.selectedSystemList.forEach(key => {
          const jsonObj = plugin.collector_json[key];
          this.pluginMonaco.defaultValue[key] = {
            text: window.decodeURIComponent(window.escape(window.atob(jsonObj.script_content_base64 || ''))),
            lang: jsonObj.type,
          };
        });
      } else if (['JMX', 'DataDog'].includes(plugin.plugin_type)) {
        this.pluginBasicInfo.dataDogCollector = plugin.collector_json;
        this.curCheckName = plugin.collector_json.datadog_check_name;
        this.pluginMonaco.defaultValue[plugin.plugin_type] = {
          text: plugin.collector_json.config_yaml,
          lang: 'yaml',
        };
      } else if (plugin.plugin_type === 'SNMP') {
        this.pluginBasicInfo.snmpVersion = plugin.collector_json.snmp_version;
        this.pluginBasicInfo.snmpConfig.name = plugin.collector_json.filename;
        this.pluginBasicInfo.snmpConfig.content = plugin.collector_json.config_yaml;
      }
      plugin.config_json.forEach(item => {
        if (
          typeof item.visible === 'undefined' &&
          (plugin.plugin_type !== 'DataDog' || item.name !== 'python_path') &&
          item.mode !== 'collector'
        ) {
          this.pluginBasicInfo.params.push(item);
        } else if (item.name === 'port') {
          this.pluginBasicInfo.port = item.default;
        }
      });
      this.defaultCheckOptions();
      this.$nextTick(() => {
        this.hasDefineParam = this.$refs.itemParam.clientHeight > 40;
      });
    },
    /**
     * @description 生成插件参数
     */
    generationPluginParams() {
      const pluginBasicInfo = JSON.parse(JSON.stringify(this.pluginBasicInfo));
      const params = {
        bk_biz_id: this.isPublicPlugin ? 0 : this.bizList.value,
        plugin_id: pluginBasicInfo.name.trim(),
        plugin_display_name: pluginBasicInfo.alias ? pluginBasicInfo.alias.trim() : '',
        plugin_type: pluginBasicInfo.type.value,
        logo: pluginBasicInfo.logo.length > 1 ? pluginBasicInfo.logo : '',
        collector_json: null,
        config_json: this.deleteDisabled(this.params),
        metric_json: pluginBasicInfo.metricJson || [],
        label: pluginBasicInfo.label.value,
        version_log: this.pluginChangeMsg.msg || '',
        signature: pluginBasicInfo.signature || '',
        is_support_remote: this.remoteCollector,
        description_md: pluginBasicInfo.desc,
        related_conf_count: pluginBasicInfo.relatedConfCount, // 关联的配置数量
        config_version_old: pluginBasicInfo.configVersion, // 版本对比信息
        enable_field_blacklist: pluginBasicInfo.enable_field_blacklist, // 是否开启自动采集新增指标
        is_split_measurement: pluginBasicInfo.is_split_measurement, // 开启新增指标的提示是否需要隐藏
      };
      this.getCollectorJsonParam(params, pluginBasicInfo);
      this.getConfigParam(params, pluginBasicInfo);
      return params;
    },
    /**
     * @description 获取config_json 参数
     * @param { Object } params
     * @param { Object } pluginBasicInfo
     */
    getConfigParam(params, pluginBasicInfo) {
      const sameConfig = {
        default: '127.0.0.1',
        mode: 'collector',
        type: 'text',
        name: 'host',
        description: this.$t('监听IP'),
        visible: false,
      };
      if (params.plugin_type === 'JMX') {
        params.config_json = this.deleteDisabled(pluginBasicInfo.jmxParams);
        params.config_json.unshift(sameConfig);
      } else if (params.plugin_type === 'Exporter') {
        params.config_json.unshift(sameConfig, {
          default: `${pluginBasicInfo.port.trim()}`,
          mode: 'collector',
          type: 'text',
          name: 'port',
          description: this.$t('监听端口'),
          visible: false,
        });
      }
    },
    /**
     * @description 删除传给后台的config_json里面的disabled
     * @param { Object } params
     */
    deleteDisabled(params) {
      return params.map(item => {
        delete item.disabled;
        return item;
      });
    },
    /**
     * @description 获取collector_json 参数
     * @param { Object } params
     * @param { Object } pluginBasicInfo
     */
    getCollectorJsonParam(params, pluginBasicInfo) {
      let yaml = '';
      if (['JMX', 'DataDog', 'Script'].includes(params.plugin_type)) {
        const contents = this.$refs.newPluginMonaco.getScriptContents();
        if (contents) {
          if (params.plugin_type === 'Script') {
            params.collector_json = {};
            contents.forEach(item => {
              const { system } = item;
              this.pluginMonaco.selectedSystemList.push(item.system);
              const { lang } = item;
              params.collector_json[system] = {
                filename: lang.lang === 'custom' ? pluginBasicInfo.name : `${pluginBasicInfo.name}.${lang.abb}`,
                type: lang.lang,
                script_content_base64: window.btoa(unescape(encodeURI(lang.text.replace(/\r\n/g, '\n')))),
              };
            });
          } else {
            params.collector_json = { config_yaml: contents[0].text };
            yaml = contents[0].text;
          }
        }
      } else if (params.plugin_type === 'SNMP') {
        params.collector_json = {
          snmp_version: pluginBasicInfo.snmpVersion,
          filename: pluginBasicInfo.snmpConfig.name,
          config_yaml: pluginBasicInfo.snmpConfig.content,
        };
      } else if (params.plugin_type === 'Pushgateway') {
        params.collector_json = {};
      }
      if (['Exporter', 'DataDog'].includes(params.plugin_type)) {
        params.collector_json = this.getUploadFile(yaml);
      }
    },
    /**
     * @description 获取系统列表
     * @param { Array } data
     */
    getSystemTabs(data) {
      data.forEach(os => {
        const osObj = {
          name: os.os_type,
          val: os.os_type,
          id: os.os_type_id,
        };
        if (os.os_type === 'linux') {
          this.systemTabs.list.unshift(osObj);
        } else if (os.os_type === 'windows' && this.systemTabs.list[0]) {
          this.systemTabs.list.splice(1, 0, osObj);
        } else if (os.os_type === 'aix' && this.systemTabs.list[1]) {
          this.systemTabs.list.splice(2, 0, osObj);
        } else {
          this.systemTabs.list.push(osObj);
        }
        this.testSystemList.push(os.os_type);
      });
      this.data.type === 'create' && (this.pluginMonaco.selectedSystemList = [this.systemTabs.list[0].val]);
    },
    /**
     * @description 获取标签列表
     * @param { Array } data
     */
    getLabelList(data) {
      this.pluginBasicInfo.label.list = data.map(item => ({
        ...item,
        children: item.children.map(label => ({ disabled: false, ...label })),
      }));
    },
    // 获取exportrt脚本上传文件信息
    getUploadFile(yaml) {
      const collectorJson = {};
      let hasfile = false;
      const name = this.pluginBasicInfo.type.value === 'Exporter' ? 'Exporter' : 'DataDog';
      this.systemTabs.list.forEach((system, index) => {
        const componentName = `uploadFile-${name.toLowerCase()}-${index}`;
        const [{ fileDesc }] = this.$refs[componentName];
        if (fileDesc) {
          hasfile = true;
          collectorJson[system.name] = fileDesc;
        }
      });
      if (hasfile && name === 'DataDog') {
        collectorJson.config_yaml = yaml;
        collectorJson.datadog_check_name = this.curCheckName;
      }
      return collectorJson;
    },
    /**
     * @description 通过轮询注册插件
     */
    registerPlugin(data) {
      const pluginStatus = typeof this.pluginBasicInfo.stage === 'undefined' ? false : data.stage === 'release';
      const polling = (params, callBack) => {
        queryAsyncTaskResult(params)
          .then(data => {
            if (!data.is_completed) {
              const timer = setTimeout(() => {
                polling(params, callBack);
                clearTimeout(timer);
              }, 1500);
            }
            callBack(data);
          })
          .catch(err => {
            const result = {
              is_completed: true,
              state: 'FAILURE',
              data: err.data,
              message: err.message,
            };
            callBack(result);
          });
      };
      return new Promise((resolve, reject) => {
        if (!this.pluginData.sameInfo || !this.pluginData.sameConfig || !pluginStatus) {
          this.registerDialog.show = true;
          this.registerDialog.status.msg = this.$t('生成中...');
          const params = {
            plugin_id: this.pluginData.pluginId,
            config_version: this.pluginData.config_version,
            info_version: this.pluginData.info_version,
          };
          pluginRegister(params, { isAsync: true })
            .then(data => {
              polling(data, data => {
                if (data.is_completed && data.state === 'SUCCESS') {
                  this.pluginData.is_completed = data.is_completed;
                  if (data.data?.token?.length) {
                    this.pluginData.token = data.data.token;
                    resolve(data);
                  } else {
                    this.registerDialog.status.msg = this.$t('插件包生成失败, 没有返回插件token数据');
                    this.registerDialog.status.failMsg = this.$t('插件包生成失败, 没有返回插件token数据');

                    reject(this.$t('没有返回插件token数据'));
                  }
                } else if (data.is_completed && data.state === 'FAILURE') {
                  this.registerDialog.status.msg = this.$t('生成插件包失败');
                  this.registerDialog.status.failMsg = data.message;
                  reject(data.message);
                }
              });
            })
            .catch(err => {
              this.registerDialog.status.msg = this.$t('生成插件包失败');
              this.registerDialog.status.failMsg = err.message || this.$t('生成插件包失败');
              reject(err);
            });
        } else {
          resolve(this.$t('插件无需再次注册'));
        }
      });
    },
    handleUpdateDesc() {
      this.pluginChangeMsg.show = false;
      this.pluginChangeMsg.isChange = false;
      setTimeout(() => {
        this.registerDialog.show = true;
        this.handleEditOperator();
      }, 400);
    },
    /**
     * @description 填写变更信息后，提交修改
     */
    async handleEditOperator() {
      this.pluginData = this.generationPluginParams();
      const result = await this.createPlugin().catch(() => false);
      if (result) {
        if (this.needRegister) {
          this.handleRegisterFlow(result);
        } else {
          this.registerDialog.show = false;
          this.$emit('update:data', this.pluginData);
          this.$bus.$emit('next');
        }
      }
      this.pluginChangeMsg.isChange = true;
    },
    /**
     * @description 注册插件
     */
    async handleRegisterFlow(data) {
      const result = await this.registerPlugin(data).catch(() => false);
      if (result) {
        this.$emit('update:data', this.pluginData);
        this.$bus.$emit('next');
        this.registerDialog.show = false;
      }
    },
    /**
     * @description 创建参插件
     */
    createPlugin() {
      this.pluginLoading = true;
      const isEdit = this.data.isEdit || this.pluginData.isEdit;
      //   const params = isEdit || this.data.back ? [this.pluginBasicInfo.name, this.pluginData] : [this.pluginData]
      let importPluginConfig = null;
      if (this.$route.name === 'plugin-update' || this.pluginConfigCache) {
        importPluginConfig = {
          collector_json: this.pluginConfigCache.collector_json,
          config_json: this.pluginConfigCache.config_json,
          is_support_remote: this.pluginConfigCache.is_support_remote,
        };
      }
      // 导入插件信息
      let importPluginMetricJson = null;
      if (this.$route.params.isImportPlugin) {
        importPluginMetricJson = this.pluginConfigCache.metric_json;
      }
      const params =
        isEdit || this.data.back
          ? [
              this.pluginBasicInfo.name,
              {
                ...this.pluginData,
                import_plugin_config: importPluginConfig,
                import_plugin_metric_json: importPluginMetricJson || [],
              },
            ]
          : [
              {
                ...this.pluginData,
                import_plugin_config: importPluginConfig,
                import_plugin_metric_json: importPluginMetricJson || [],
              },
            ];
      const ajax = isEdit || this.data.back ? editCollectorPlugin : createCollectorPlugin;
      this.registerDialog.status.failMsg = '';
      return ajax(...params)
        .then(data => {
          this.addPluginDataProp(data);
          if (
            this.data.isEdit &&
            (!this.pluginData.sameConfig || !this.pluginData.sameInfo) &&
            this.pluginBasicInfo.stage === 'release' &&
            this.pluginChangeMsg.isChange
          ) {
            this.pluginChangeMsg.show = true;
            // 编辑关键选项，返回reject，阻止注册，让用户选填修改信息，等再次确认时注册插件
            return Promise.reject(data);
          }
          this.registerDialog.status.msg = this.$t('保存中...');
          return Promise.resolve(data);
        })
        .finally(() => {
          this.pluginLoading = false;
        });
    },
    /**
     * @description 获取插件版本
     */
    getPluginVersion() {
      this.pluginData.sameInfo = this.pluginBasicInfo.infoVersion === this.pluginData.info_version;
      this.pluginData.sameConfig = this.pluginBasicInfo.configVersion === this.pluginData.config_version;
      this.pluginData.update = !this.pluginData.sameConfig; // true表示需要重新调试插件
      this.pluginData.is_completed = this.pluginData.sameConfig && this.pluginBasicInfo.stage === 'release'; // true表示插件不需要注册
    },
    /**
     * @description 处理创建插件返回参数
     */
    addPluginDataProp(data) {
      if (this.pluginBasicInfo.type.value !== 'Script') {
        this.pluginData.port = this.pluginBasicInfo.port;
        this.pluginData.url = '127.0.0.1';
      }
      this.pluginData.status = this.pluginBasicInfo.status || '';
      this.pluginData.isEdit = this.data.isEdit;
      this.pluginData.type = this.data.type;
      this.pluginData.enable_field_blacklist = data.enable_field_blacklist;
      this.pluginData.update = false; // 默认false
      this.pluginData.from = 'bkmonitor.models.fta.plugin';
      this.pluginData.systemList = [];
      this.$set(this.pluginData, 'is_completed', false);
      this.pluginData.pluginId = this.pluginBasicInfo.name;
      this.pluginData.config_version = data.config_version;
      this.pluginData.info_version = data.info_version;
      this.pluginData.need_debug = data.need_debug;
      this.pluginData.metric_json = this.pluginBasicInfo.metricJson;
      this.getPluginVersion();
      this.systemTabs.list.forEach(system => {
        if (['JMX', 'DataDog', 'Pushgateway', 'SNMP'].includes(this.pluginBasicInfo.type.value)) {
          if (data.os_type_list.some(os => os === system.name)) {
            this.pluginData.systemList.push({
              os_type: system.name,
              os_id: system.id,
            });
          }
        } else if (this.pluginBasicInfo.type.value === 'Script') {
          if (this.pluginMonaco.selectedSystemList.includes(system.name)) {
            this.pluginData.systemList.push({
              os_type: system.name,
              os_id: system.id,
            });
          }
        } else if (this.pluginBasicInfo.type.value === 'Exporter') {
          if (this.pluginData.collector_json[system.name]) {
            this.pluginData.systemList.push({
              os_type: system.name,
              os_id: system.id,
            });
          }
        }
      });
    },
    /**
     * @description 验证必填参数项
     */
    validateRequired(key, empty) {
      this.pluginBasicInfo[empty] = false;
      if (key === 'name') {
        const name = this.pluginBasicInfo[key].trim();
        if (!/^[a-zA-Z][a-zA-Z0-9_]*$/.test(name)) {
          this.pluginBasicInfo.nameErrorMsg = this.$t('插件名称，仅支持以字母开头，仅支持字母、下划线和数字。');
          this.pluginBasicInfo[empty] = true;
        } else if (name.length > 30) {
          this.pluginBasicInfo.nameErrorMsg = this.$t('输入超过30字符，禁止输入。');
          this.pluginBasicInfo[empty] = true;
        }
      } else {
        this.pluginBasicInfo[empty] = !this.pluginBasicInfo[key];
      }
      return !this.pluginBasicInfo[empty];
    },
    validateLabel() {
      this.pluginBasicInfo.noLabel = !this.pluginBasicInfo.label.value;
      return !this.pluginBasicInfo.noLabel;
    },
    /**
     * @description 验证是否上传了文件
     */
    validateUploadFile() {
      let hasCollectorJson = false;
      const collectorJson = this.pluginData.collector_json;

      for (const key in collectorJson) {
        if (Object.hasOwn(collectorJson, key) && collectorJson[key]) {
          hasCollectorJson = true;
        }
      }
      if (!hasCollectorJson) {
        const timer = setTimeout(() => {
          this.bkMessage('error', this.$t('上传文件') + this.pluginData.plugin_type);
          clearTimeout(timer);
        }, 300);
      }
      return hasCollectorJson;
    },
    /**
     * @description 验证exporter插件参数
     */
    validateExporterPlugin() {
      this.pluginBasicInfo.isPortLegal = !this.portRgx.test(this.pluginBasicInfo.port.trim());
      const hasCollectorJson = this.validateUploadFile();
      const hasHostPort = this.validateExporterParam();
      if (!hasHostPort) {
        this.bkMessage('error', this.$t('Exporter 类型插件参数默认值必须包含 ${host} 和 ${port} 变量模板'));
      }
      return ![hasCollectorJson, hasHostPort, !this.pluginBasicInfo.isPortLegal].includes(false);
    },
    /**
     * @description 验证exporter定义参数
     */
    validateExporterParam() {
      let hasHost = false;
      let hasPort = false;
      this.params.forEach(item => {
        if (typeof item.default === 'string' && item.default.includes('${host}')) {
          hasHost = true;
        }
        if (typeof item.default === 'string' && item.default.includes('${port}')) {
          hasPort = true;
        }
      });
      this.hasHostPort = hasHost && hasPort;
      return this.hasHostPort;
    },
    /**
     * @description 验证插件所有的必填参数
     */
    async validateAllOptions(pluginType) {
      const result = [];
      let isNameLagal = this.validateRequired('name', 'isNameLegal');
      const hasLabel = this.validateLabel();
      if ((this.data.type === 'create' || this.data.type === 'import') && !this.data.back) {
        isNameLagal = await this.checkPluginId();
      }
      if (['JMX', 'DataDog', 'Script'].includes(pluginType) && !this.pluginData.collector_json) {
        result.push(false);
      } else if (pluginType === 'Exporter') {
        result.push(this.validateExporterPlugin());
      }
      if (pluginType === 'DataDog' && !this.validateUploadFile()) {
        result.push(false);
      }
      if (pluginType === 'SNMP' && !this.pluginData.collector_json?.filename) {
        this.$bkMessage({ theme: 'error', message: this.$t('上传采集配置文件') });
        result.push(false);
      }
      result.push(isNameLagal, hasLabel);
      return !result.includes(false);
    },
    /**
     * @description 下一步
     */
    async handleNextStep() {
      this.pluginLoading = true;
      this.bkBtnIcon = 'loading';
      this.pluginData = this.generationPluginParams();
      const isPass = await this.validateAllOptions(this.pluginBasicInfo.type.value);
      if (!isPass) {
        this.bkBtnIcon = '';
        this.pluginLoading = false;
        return;
      }
      if (!this.pluginBasicInfo.logo) {
        this.pluginBasicInfo.logo = this.pluginBasicInfo.name.slice(0, 1);
      }
      const result = await this.createPlugin().catch(() => {
        this.pluginLoading = false;
      });
      if (result) {
        if (this.needRegister) {
          this.handleRegisterFlow(result);
        } else {
          this.$emit('update:data', this.pluginData);
          this.$bus.$emit('next');
        }
      }
      this.bkBtnIcon = '';
    },
    //  关闭插件变更说明dialog
    handleCancelDesc() {
      this.pluginChangeMsg.show = false;
    },
    handleFileChange(file) {
      this.pluginBasicInfo.snmpConfig.name = file.name;
      this.pluginBasicInfo.snmpConfig.content = file.fileContent;
    },
    // 根据链接的形式选择隐藏插件类型及新建插件时默认选择公共插件和操作系统类型
    // query: {
    //   notype: ['JMX', 'DataDog', 'Pushgateway']
    // }
    defaultCheckOptions() {
      const val = this.pluginBasicInfo.type.value;
      const noTypeList = this.$route.query.notype;
      if (Array.isArray(noTypeList)) {
        const index = noTypeList.indexOf(val);
        index > -1 && noTypeList.splice(index, 1);
        this.pluginBasicInfo.type.notShowType = noTypeList;
      }
      if (!this.data.isEdit && !this.pluginBasicInfo.label.value) {
        this.pluginBasicInfo.label.value = 'os';
      }
    },
    handleOsSwitcherChange(systemList) {
      const checkedList = systemList.filter(item => item.enable);
      this.pluginMonaco.selectedSystemList = checkedList.map(item => item.name);
    },
  },
};
</script>
<style lang="scss" scoped>
@import '../../../home/common/mixins';

.auth-disabled {
  cursor: pointer;
}

.step-plugin {
  padding: 40px 40px 20px;
  margin-bottom: 20px;
  font-size: 12px;
  color: #63656e;

  .next-step {
    :deep(.bk-button-icon-loading::before) {
      content: '';
    }

    .bk-button {
      padding: 0 21px;
      margin-right: 8px;
    }
  }

  &-item {
    display: flex;
    flex-direction: row;
    align-items: center;
    margin-bottom: 20px;

    .item-label {
      position: relative;
      flex: 0 0 68px;
      margin-right: 24px;
      text-align: right;

      &.item-required:after {
        position: absolute;
        top: 3px;
        right: -10px;
        color: red;
        content: '*';
      }

      &.param-label {
        margin-bottom: 5px;
      }
    }

    .item-container {
      position: relative;
      flex: 1;

      .item-input {
        display: inline-block;
        margin-right: 16px;
      }

      .plugin-logo {
        position: absolute;
        top: 0;
        right: 0;
      }

      .bk-select {
        width: 320px;
      }

      .bk-form-control {
        width: 320px;
      }

      .bk-button-group {
        .bk-button {
          width: 115px;
          font-size: 12px;
        }
      }

      &.plugin-id {
        :deep(.bk-form-checkbox) {
          position: absolute;
          top: 7px;
          left: 340px;

          .bk-checkbox-text {
            font-size: 12px;
          }
        }
      }

      &.editor-wrapper {
        max-width: calc(100% - 68px);
        overflow: hidden;
      }

      &.config-hint {
        font-size: 12px;
        color: #63656e;

        .icon-exclamation-circle {
          position: relative;
          top: 1px;
          color: #ff9c01;
        }
      }

      .exporter-tips {
        margin-top: 0;
        margin-bottom: 0;
        font-size: 12px;
        color: #979ba5;

        &.error {
          color: #f5f6fc;
        }
      }

      .remote-desc {
        margin-top: 8px;
        margin-bottom: 0;
        font-size: 12px;
        color: #ff9c01;
      }

      .prefix-name {
        height: 32px;
        padding: 0 13px;
        font-size: 14px;
        line-height: 32px;
        color: #63656e;
      }

      .item-param {
        position: relative;
        display: inline-block;
        height: 24px;
        margin: 0 8px 5px 0;
        font-size: 12px;
        line-height: 22px;
        text-align: center;
        vertical-align: top;
        border: 1px solid #c4c6cc;
        border-radius: 2px;

        .wrapper {
          position: relative;
          display: flex;
          justify-content: center;
          padding: 0 18px;

          .icon-close-circle-shape {
            position: absolute;
            top: -7px;
            right: -7px;
            z-index: 1;
            display: none;
            font-size: 14px;
            color: red;

            &::after {
              position: absolute;
              top: 0;
              left: 0;
              z-index: -1;
              display: inline-block;
              width: calc(100% - 2px);
              height: calc(100% - 2px);
              content: '';
              background: #fff;
              border-radius: 50%;
            }
          }

          .param-name {
            &.required {
              position: relative;

              &::after {
                position: absolute;
                top: -1px;
                right: -7px;
                color: red;
                content: '*';
              }
            }
          }
        }

        &:hover {
          color: #3a84ff;
          cursor: pointer;
          border-color: #3a84ff;

          .icon-close-circle-shape {
            display: block;
          }
        }
      }

      .run-port {
        display: inline-block;
        width: 320px;

        :deep(.tooltips-icon) {
          right: 4px;
        }
      }

      :deep(.step-verify-input) {
        .tooltips-icon {
          top: 8px;
        }
      }

      .upload-container {
        display: flex;
        flex-wrap: wrap;

        .upload-item {
          position: relative;
          width: calc(50% - 10px);
          min-width: 350px;
          margin-top: 8px;
          margin-left: 10px;

          :deep(.bk-upload) {
            .file-wrapper {
              height: 42px;
              font-size: 12px;
              line-height: 42px;
            }
          }
        }
      }

      .markdown-tpl {
        margin-top: 7px;
        font-size: 12px;

        .download {
          margin-left: 15px;
          color: #3a84ff;
          cursor: pointer;
        }
      }

      .item-markdown {
        height: 320px;
      }

      .snmp-yaml-import {
        display: flex;
        align-items: center;
        width: 684px;
        height: 32px;
        border: 1px dashed #c4c6cc;
      }
    }

    &.has-param {
      align-items: start;

      .item-label {
        margin-top: 3px;
      }
    }

    &.plugin-type {
      align-items: start;

      .item-label {
        margin-top: 7px;
      }

      .description {
        margin-top: 6px;
        line-height: 16px;
        color: #979ba5;

        .doc-link {
          color: #3a84ff;
          cursor: pointer;
        }

        .icon-mc-link {
          font-weight: 600;
          color: #3a84ff;
          cursor: pointer;
        }
      }
    }

    &.remote-collector {
      .item-container {
        display: flex;
        align-items: center;
      }

      .bk-switcher {
        margin-right: 10px;
      }

      .description {
        color: #979ba5;
      }
    }

    &.upload-package {
      margin-bottom: 10px;
    }

    &.label-bottom {
      align-items: start;

      .item-label {
        margin-top: 7px;
      }
    }

    .add-params-text {
      display: inline-block;
      margin-bottom: 5px;
      font-size: 12px;
      color: #3a84ff;
      cursor: pointer;
    }

    .icon-plus {
      display: inline-block;
      font-size: 22px;
      cursor: pointer;
      border: 1px solid #c4c6cc;
      border-radius: 2px;

      &:hover {
        color: #3a84ff;
        border-color: #a3c5fd;
      }
    }

    .mini-btn {
      min-width: 24px;
      padding: 0;

      :deep(.bk-icon) {
        margin-right: 0;
      }
    }

    &.plugin-exporter {
      margin-bottom: 0;
    }

    :deep(.bk-switcher.is-checked) {
      background-color: #3a84ff;
    }
  }

  .change-description {
    position: relative;
    padding-top: 16px;

    .title {
      position: absolute;
      top: -20px;
      font-size: 18px;
      color: #313238;
    }
  }

  :deep(.bk-dialog-header) {
    position: relative;
  }
}
</style>
