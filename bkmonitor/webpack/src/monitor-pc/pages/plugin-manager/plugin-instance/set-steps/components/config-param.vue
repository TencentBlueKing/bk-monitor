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
  <bk-dialog
    :mask-close="false"
    :show-footer="!disabledEditConfig"
    :title="disabledEditConfig ? $t('参数配置') : $t('定义参数')"
    :value="show"
    :width="480"
    header-position="left"
    theme="primary"
    @after-leave="handleCancel"
  >
    <div
      v-if="disabledEditConfig"
      class="readonly-param"
    >
      <div
        v-for="(item, index) in readonlyParam"
        :key="index"
        class="item"
      >
        <div class="label">{{ item.label }} ：</div>
        <div class="value">
          {{ item.value || '--' }}
        </div>
      </div>
    </div>
    <div
      v-else
      class="param-html"
    >
      <div class="item-param param-type">
        <span class="item-required"> {{ $t('参数类型') }} </span>
        <bk-select
          v-model="config.types.type"
          :clearable="false"
          @change="handleTypeChange"
        >
          <bk-option
            v-for="(type, index) in paramType"
            v-show="type.id !== 'collector'"
            :id="type.id"
            :key="index"
            :name="type.name"
          />
        </bk-select>
      </div>
      <span class="type-des">{{ typeDes[config.types.type] }}</span>
      <div class="item-param">
        <span class="item-required"> {{ $t('参数名称') }} </span>
        <verify-input
          :show-validate.sync="rules.name.error"
          :validator="{ content: rules.name.message }"
        >
          <bk-input
            v-model="config.paramName"
            :clearable="true"
            :disabled="config.types.type === 'dms_insert'"
          />
        </verify-input>
      </div>
      <div class="item-param">
        <span> {{ $t('参数别名') }} </span>
        <bk-input
          v-model="config.alias"
          :clearable="true"
        />
      </div>
      <div class="item-param">
        <span> {{ $t('默认值') }} </span>
        <i
          v-show="config.types.type === 'dms_insert'"
          v-bk-tooltips="{
            content: defaultTipContentByDefaultType(config.default.type),
          }"
          class="bk-icon icon-info"
        />
        <verify-input
          :show-validate="dmsInsertError"
          :validator="{ content: rules.dmsInsert.message }"
        >
          <div class="default-value">
            <div :class="['value-type', { 'is-input': ['text', 'password', 'file'].includes(config.default.type) }]">
              <bk-select
                v-model="config.default.type"
                :clearable="false"
                @selected="handleDefaultTypeChange"
              >
                <bk-option
                  v-for="item in defaultTypeList"
                  :id="item.id"
                  :key="item.id"
                  :name="item.name"
                />
              </bk-select>
            </div>
            <div class="value">
              <bk-input
                v-if="config.default.type === 'text'"
                v-model="config.default.value"
              />
              <bk-input
                v-else-if="['password', 'encrypt'].includes(config.default.type)"
                v-model="config.default.value"
                ext-cls="value-password"
                type="password"
              />
              <bk-switcher
                v-else-if="config.default.type === 'switch'"
                v-model="config.default.value"
                class="value-switch"
                false-value="false"
                true-value="true"
              />
              <div
                v-else-if="config.default.type === 'file'"
                class="file-input-wrap"
              >
                <import-file
                  :file-content="config.default.fileBase64"
                  :file-name="config.default.value"
                  @change="handleFileChange"
                  @error-message="handleImportError"
                />
                <div
                  v-if="fileErrorMsg"
                  class="error-msg"
                >
                  {{ fileErrorMsg }}
                </div>
              </div>
              <bk-tag-input
                v-else-if="['host', 'service', 'custom'].includes(config.default.type)"
                v-model="config.default.value"
                allow-create
                has-delete-icon
                @change="validInsertValue"
              />
            </div>
          </div>
        </verify-input>
      </div>
      <div class="item-param">
        <span> {{ $t('参数说明') }} </span>
        <bk-input
          v-model="config.description"
          :disabled="config.types.type === 'dms_insert'"
        />
      </div>
      <div class="item-param">
        <bk-checkbox v-model="config.required">{{ $t('必填') }}</bk-checkbox>
      </div>
    </div>
    <div slot="footer">
      <bk-button
        class="mr-5"
        :disabled="disabledEditConfig"
        :title="$t('提交')"
        theme="primary"
        @click="handleConfirm"
        @keyup.enter="handleConfirm"
      >
        {{ $t('提交') }}
      </bk-button>
      <bk-button
        :title="$t('取消')"
        theme="default"
        @click="handleCancel"
      >
        {{ $t('取消') }}
      </bk-button>
    </div>
  </bk-dialog>
</template>
<script>
import VerifyInput from '../../../../../components/verify-input/verify-input';
import importFile from './import-file';

const CONFIG_DEFAULT_DYNAMIC_ID_LIST = ['host', 'service', 'custom'];
export default {
  name: 'ConfigParam',
  components: {
    VerifyInput,
    importFile,
  },
  props: {
    show: Boolean,
    param: {
      type: Object,
      default: () => ({}),
    },
    paramList: {
      type: Array,
      default: () => [],
    },
    pluginType: {
      type: String,
      default: 'Script',
    },
  },
  data() {
    return {
      labels: {
        mode: this.$t('参数类型'),
        name: this.$t('参数名称'),
        alias: this.$t('参数别名'),
        default: this.$t('默认值'),
        description: this.$t('参数说明'),
      },
      types: {
        text: this.$t('文本'),
        file: this.$t('文件'),
        password: this.$t('密码'),
        switch: this.$t('开关'),
        service: this.$t('服务实例标签'),
        host: this.$t('主机字段'),
        custom: this.$t('自定义'),
      },
      typeDes: {
        opt_cmd: this.$t('最常用的参数使用方式。如 --port 3306'),
        env: this.$t("在程序中直接获取环境变量中的变量如 os.getenv('PYTHONPATH')"),
        pos_cmd: this.$t('基于参数传递的顺序进行变量的获取,由添加参数的顺序决定,如Shell中常见的echo $1'),
        dms_insert: this.$t('注入的维度信息将追加进采集的指标数据中，基于配置平台的服务实例自定义标签及主机字段获取'),
      },
      config: {
        types: {
          list: [
            {
              id: 'opt_cmd',
              name: this.$t('命令行参数'),
            },
            {
              id: 'env',
              name: this.$t('环境变量'),
            },
            {
              id: 'pos_cmd',
              name: this.$t('位置参数'),
            },
            {
              id: 'collector',
              name: this.$t('采集器参数'),
            },
            {
              id: 'dms_insert',
              name: this.$t('维度注入'),
            },
          ],
          type: 'opt_cmd',
        },
        default: {
          list: [
            {
              name: this.$t('文本'),
              id: 'text',
            },
            {
              name: this.$t('强密码'),
              id: 'encrypt',
            },
            {
              name: this.$t('密码'),
              id: 'password',
            },
            {
              name: this.$t('文件'),
              id: 'file',
            },
            {
              name: this.$t('开关'),
              id: 'switch',
            },
            {
              name: this.$t('服务实例标签'),
              id: 'service',
            },
            {
              name: this.$t('主机字段'),
              id: 'host',
            },
            {
              name: this.$t('自定义'),
              id: 'custom',
            },
          ],
          type: 'text',
          value: '',
        },
        paramName: '',
        alias: '',
        description: '',
        required: false,
      },
      rules: {
        name: {
          error: false,
          message: this.$t('输入参数名'),
        },
        dmsInsert: {
          typeError: false,
          valueError: false,
          message: this.$t('已添加该默认值'),
        },
      },
      fileErrorMsg: '',
    };
  },
  computed: {
    paramType() {
      if (this.pluginType === 'Pushgateway') return [this.config.types.list.find(item => item.id === 'dms_insert')];
      return this.config.types.list;
    },
    // 禁止编辑
    disabledEditConfig() {
      return this.param.disabled;
    },
    // 只读参数
    readonlyParam() {
      const param = this.param || {};
      const result = [];
      Object.keys(this.labels).forEach(key => {
        result.push({
          label: this.labels[key],
          value:
            key === 'default'
              ? `${param[key]}`.length
                ? `${this.types[param.type]}=${param[key]}`
                : this.types[param.type]
              : param[key],
        });
      });
      return result;
    },
    defaultTypeList() {
      let defaultList = [];
      let configDefaultList = this.config.default.list;
      if (this.config.types.type === 'dms_insert') {
        return configDefaultList.filter(item => CONFIG_DEFAULT_DYNAMIC_ID_LIST.includes(item.id));
      }

      configDefaultList = configDefaultList.filter(item => !CONFIG_DEFAULT_DYNAMIC_ID_LIST.includes(item.id));
      if (this.pluginType !== 'Exporter') {
        defaultList = configDefaultList.filter(item => item.id !== 'encrypt');
      } else {
        defaultList = configDefaultList;
      }
      if (this.config.types.type === 'opt_cmd') {
        return defaultList;
      }
      return defaultList.filter(item => item.id !== 'switch');
    },
    dmsInsertError() {
      return this.rules.dmsInsert.typeError || this.rules.dmsInsert.valueError;
    },
  },
  watch: {
    show(val) {
      if (val) {
        /**
         * @description 如果有值，则回填
         */
        if (Object.keys(this.param).length) this.backfillConfig();
        else this.initProps();
      } else {
        this.rules.name.error = false;
        this.rules.dmsInsert.typeError = false;
        this.rules.dmsInsert.valueError = false;
      }
    },
  },
  methods: {
    handleConfirm() {
      const name = this.config.paramName.trim();
      const alias = this.config.alias.trim();
      this.rules.name.error = !name;
      if (this.rules.name.error) {
        this.rules.name.message = this.$t('输入参数名');
        return;
      }
      if (this.dmsInsertError) return;
      if (this.config.default.type === 'file' && this.fileErrorMsg) return;
      const param = {
        name,
        alias,
        mode: this.config.types.type,
        type: this.config.default.type,
        default: ['text', 'password'].includes(this.config.default.type)
          ? this.config.default.value.trim()
          : this.config.default.value,
        description: this.config.description.trim(),
        required: this.config.required || false,
      };
      if (this.config.types.type === 'dms_insert') {
        // ['a:1','b:2'] -----> { a: '1', b: '2' }
        const arr = param.default.map(item => (item.split(':').length === 2 ? item.split(':') : item.split('：')));
        param.default = Object.fromEntries(arr);
      }
      this.config.default.type === 'file' && (param.file_base64 = this.config.default.fileBase64);
      this.$emit('confirm', param);
      this.$emit('update:show', false);
    },
    handleCancel() {
      this.$emit('update:show', false);
    },
    /**
     * @description 初始化表单属性
     */
    initProps() {
      this.config.paramName = '';
      this.config.description = '';
      this.config.alias = '';
      this.config.types.type = this.paramType[0]?.id || 'opt_cmd';
      this.config.default.type = this.defaultTypeList[0]?.id || 'text';
      this.config.required = false;
      this.handleDefaultTypeChange(this.config.default.type);
    },
    /**
     * @description 回填编辑数据
     */
    backfillConfig() {
      const { param } = this;
      this.config.paramName = param.name;
      this.config.alias = param.alias || '';
      this.config.types.type = param.mode;
      this.config.default.type = param.type;
      this.config.required = param.required || false;
      if (param.mode === 'dms_insert') {
        // { a:1, b:2 } ----->  ['a:1','b:2']
        this.config.default.value = Object.entries(param.default).map(item => `${item[0]}:${item[1]}`);
      } else {
        this.config.default.value = param.default;
      }
      this.config.description = param.description;
      param.type === 'file' && (this.config.default.fileBase64 = param.file_base64);
    },
    handleDefaultTypeChange(type) {
      const typeMap = {
        text: () => (this.config.default.value = ''),
        password: () => (this.config.default.value = ''),
        file: () => {
          this.config.default.value = '';
          this.$set(this.config.default, 'fileBase64', '');
        },
        switch: () => (this.config.default.value = this.config.default.value || 'false'),
        encrypt: () => (this.config.default.value = ''),
        service: () => {
          this.config.default.value = [];
          this.config.description = this.$t('可以从配置平台获取相应服务实例的标签追加到采集的数据里当成维度');
          this.config.paramName = this.$t('服务实例维度注入');
          this.validInsertType();
        },
        host: () => {
          this.config.default.value = [];
          this.config.description = this.$t('可以从配置平台获取相应主机的字段追加到采集的数据里当成维度');
          this.config.paramName = this.$t('主机维度注入');
          this.validInsertType();
        },
        custom: () => {
          this.config.default.value = [];
          this.config.description = this.$t('指定需要注入维度的值');
          this.config.paramName = this.$t('自定义维度注入');
          this.validInsertType();
        },
      };
      this.fileErrorMsg = '';
      typeMap[type]?.();
    },
    /**
     * @description 校验维度注入-默认值类型是否只添加一个
     */
    validInsertType() {
      const paramList = this.paramList.filter(item => item !== this.param);
      const res = paramList.find(item => item.type === this.config.default.type);
      if (res) {
        this.rules.dmsInsert.message = this.$t('每种默认值类型只能添加一个');
        this.rules.dmsInsert.typeError = true;
        return;
      }
      this.rules.dmsInsert.typeError = false;
    },
    /**
     * @description 校验维度注入-标签值格式和key值的唯一性
     */
    validInsertValue(tags) {
      const len = tags.length;
      const keys = [];
      for (let i = 0; i < len; i++) {
        tags[i] = tags[i].replace('：', ':');
        const [key, value] = tags[i].split(':');
        if (key && value) {
          keys.push(key);
        } else {
          this.rules.dmsInsert.message = this.$t('标签格式应为key:value');
          this.rules.dmsInsert.valueError = true;
          return;
        }
      }
      if (keys.length !== new Set(keys).size) {
        this.rules.dmsInsert.message = this.$t('标签key值应该保持唯一性');
        this.rules.dmsInsert.valueError = true;
        return;
      }
      this.rules.dmsInsert.valueError = false;
    },
    handleTypeChange(nv, ov) {
      /**
       * 这里有个坑, 因为弹窗关闭时，组件并没有卸载，所以如果打开与上一次参数类型不同的弹窗，会触发这个函数
       * 并且函数执行时机在show监听器后，也就代表在这里做初始化时，会覆盖show监听器所回填的数据
       */

      if (Object.keys(this.param).length && this.param.mode === nv) {
        this.backfillConfig();
      }

      if (nv === 'dms_insert' && nv !== this.param.mode) {
        this.config.default.type = 'service';
        this.config.paramName = this.$t('服务实例维度注入');
        this.config.description = this.$t('可以从配置平台获取相应服务实例的标签追加到采集的数据里当成维度');
        this.config.default.value = [];
        this.validInsertType();
        return;
      }

      if (ov === 'dms_insert') {
        if (nv !== this.param.mode) {
          this.config.default.type = 'text';
          this.config.paramName = '';
          this.config.description = '';
          this.config.default.value = '';
        }
        this.rules.dmsInsert.typeError = false;
        this.rules.dmsInsert.valueError = false;
        return;
      }

      if (ov === 'opt_cmd' && this.config.default.type === 'switch') {
        this.config.default.type = 'text';
        this.config.default.value = '';
      }
    },
    handleFileChange(fileInfo) {
      this.config.default.value = fileInfo.name;
      this.config.default.fileBase64 = fileInfo.fileContent;
    },
    handleImportError(msg) {
      this.fileErrorMsg = msg;
    },
    defaultTipContentByDefaultType(type) {
      switch (type) {
        case 'service':
          return this.$t('维度名:实例标签名，如cluster_name:cluster_name');
        case 'custom':
          return this.$t('维度名:维度值，如tag: host');
        default:
          return this.$t('维度名:主机字段名，如host_ip:bk_host_innerip');
      }
    },
  },
};
</script>
<style lang="scss" scoped>
.param-html {
  .item-param {
    margin-bottom: 17px;

    .item-required::after {
      position: relative;
      top: -1px;
      left: 3px;
      color: red;
      content: '*';
    }

    &:last-child {
      margin-bottom: 0;
    }
  }

  .param-type {
    margin-bottom: 0;
  }

  .type-des {
    font-size: 12px;
  }

  .default-value {
    display: flex;
    flex: 1;

    .value-type {
      flex: 0 0 94px;
    }

    .is-input {
      :deep(.bk-select) {
        border-right: 0;
        border-radius: 2px 0 0 2px;
        box-shadow: none;
      }
    }

    .value {
      display: flex;
      flex: 1;
      align-items: center;

      :deep(.bk-form-input) {
        border-radius: 0 2px 2px 0;
      }

      :deep(.value-password) {
        .control-icon {
          display: none;
        }
      }

      .value-switch {
        margin-left: 20px;
      }
    }

    .file-input-wrap {
      flex: 1;
      height: 32px;

      .monitor-import {
        display: flex;
        align-items: center;
        margin: 0;
        vertical-align: middle;
      }

      .error-msg {
        padding-top: 6px;
        font-size: 12px;
        color: #f56c6c;
      }
    }

    .bk-tag-selector {
      flex: 1;
    }
  }
}

.readonly-param {
  .item {
    display: flex;
    margin-bottom: 20px;

    .label {
      flex: 0 0 170px;
      margin-right: 10px;
      font-size: 14px;
      color: #979ba5;
      text-align: right;
    }

    .value {
      flex: 1;
      word-break: break-all;
    }

    &:last-child {
      margin-bottom: 0;
    }
  }
}

.mr-5 {
  margin-right: 5px;
}
</style>
