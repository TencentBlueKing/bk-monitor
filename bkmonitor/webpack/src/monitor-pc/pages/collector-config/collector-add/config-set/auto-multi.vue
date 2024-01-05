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
  <div class="auto-multi-wrapper">
    <div
      class="auto-multi"
      v-for="(items, indexs) in souceDataInfo"
      :key="indexs"
    >
      <div
        class="del-icon"
        @click="delAuth(indexs)"
      >
        <bk-icon type="close" />
      </div>
      <template v-for="(item, index) in items">
        <template v-if="item.auth_priv">
          <verify-input
            v-if="
              item.auth_priv[curAuthPriv[indexs].curAuthPriv] && item.auth_priv[curAuthPriv[indexs].curAuthPriv].need
            "
            class="param-item"
            :key="index"
            :show-validate.sync="item.validate.isValidate"
            :validator="item.validate"
            position="right"
          >
            <auto-complete-input
              v-model.trim="item.default"
              class="reset-big-width fix-same-code"
              :tips-data="tipsData"
              :config="item"
              :type="item.type"
              @autoHandle="autoHandle"
              :cur-auth-priv="curAuthPriv[indexs].curAuthPriv"
            >
              <template slot="prepend">
                <bk-popover
                  placement="top"
                  :tippy-options="tippyOptions"
                >
                  <div class="prepend-text">
                    {{ item.description || item.name }}
                  </div>
                  <div
                    class="fix-same-code"
                    slot="content"
                  >
                    <div class="fix-same-code">
                      {{ $t('参数名称') }} : {{ item.name }}
                    </div>
                    <div class="fix-same-code">
                      {{ $t('参数类型') }} : {{ paramType[item.mode] }}
                    </div>
                    <div class="fix-same-code">
                      {{ $t('参数说明') }} : {{ item.description || '--' }}
                    </div>
                  </div>
                </bk-popover>
              </template>
            </auto-complete-input>
          </verify-input>
        </template>
        <template v-else>
          <verify-input
            class="param-item"
            :key="index"
            :show-validate.sync="item.validate.isValidate"
            :validator="item.validate"
            position="right"
          >
            <!-- 自动补全 -->
            <auto-complete-input
              v-model.trim="item.default"
              class="reset-big-width fix-same-code"
              :tips-data="tipsData"
              :config="item"
              :type="item.type"
              @curAuthPriv="handleAuthPriv(...arguments, indexs)"
              @autoHandle="autoHandle"
            >
              <template slot="prepend">
                <bk-popover
                  :tippy-options="tippyOptions"
                  placement="top"
                >
                  <div class="prepend-text fix-same-code">
                    {{ item.description ? item.description : item.name }}
                  </div>
                  <div slot="content">
                    <div class="fixed-same-code">
                      {{ $t('参数名称') }} : {{ item.name }}
                    </div>
                    <div>{{ $t('参数类型') }} : {{ paramType[item.mode] }}</div>
                    <div class="fix-same-coded">
                      {{ $t('参数说明') }} : {{ item.description || '--' }}
                    </div>
                  </div>
                </bk-popover>
              </template>
            </auto-complete-input>
          </verify-input>
        </template>
      </template>
    </div>
    <div
      class="auto-multi"
      v-if="allowAdd"
    >
      <div
        class="add-btn"
        @click="addAuth"
      >{{ $t('新增用户配置') }}</div>
    </div>
  </div>
</template>
<script>


import { deepClone } from '../../../../../monitor-common/utils/utils';
import VerifyInput from '../../../../components/verify-input/verify-input.vue';

import AutoCompleteInput from './auto-complete-input';
import * as snmp from './snmp';

export default {
  name: 'AutoMulti',
  components: {
    AutoCompleteInput,
    VerifyInput,
  },
  props: {
    templateData: {
      type: Array,
      default: () => []
    },
    souceData: {
      type: Array,
      default: []
    },
    tipsData: {
      type: Array,
      default: []
    },
    paramType: {
      type: Object,
      default: {}
    },
    allowAdd: {
      type: Boolean,
      default: true
    }
  },
  data() {
    return {
      tippyOptions: {
        distance: 0
      },
      curAuthPriv: [],
      souceDataInfo: [],
      templateDataInfo: [],
      isCanSave: false
    };
  },
  watch: {
    souceData: {
      handler: 'handleSouceData',
      immediate: true
    }
  },
  created() {
    this.souceData.forEach((item) => {
      item.forEach((value) => {
        if (value.key === 'security_level') {
          this.curAuthPriv.push({ curAuthPriv: value.default });
        }
      });
    });
    this.templateDataInfo = deepClone(this.templateData);
  },
  mounted() {
    this.trigger();
  },
  methods: {
    autoHandle() {
      this.trigger();
    },
    handleAuthPriv(v, index) {
      this.$set(this.curAuthPriv, index, { curAuthPriv: v });
      this.trigger();
    },
    handleSouceData(v) {
      this.souceDataInfo = deepClone(v);
    },
    addAuth() {
      this.curAuthPriv.push({ curAuthPriv: snmp.AuthPrivList[2] });
      this.souceDataInfo.push(deepClone(this.templateDataInfo));
      this.trigger();
    },
    delAuth(index) {
      if (this.souceDataInfo.length > 1) {
        this.curAuthPriv.splice(index, 1);
        this.souceDataInfo.splice(index, 1);
        this.trigger();
      }
    },
    trigger() {
      this.$emit('triggerData', this.souceDataInfo);
      this.isCanSave = this.authValidate();
      this.$emit('canSave', this.isCanSave);
    },
    authValidate() {
      let result = false;
      const { excludeValidateMap } = snmp;
      result = this.souceDataInfo.every((items, index) => items.every((item) => {
        if (!excludeValidateMap[this.curAuthPriv[index].curAuthPriv].includes(item.key)) {
          return item.type === 'file' ? item.default.value !== '' : item.default !== '';
        }
        return true;
      }));
      return result;
    }
  }
};
</script>
<style lang="scss">
.auto-multi-wrapper {
  .auto-multi {
    position: relative;
    padding: 10px 20px 10px 10px;
    margin-bottom: 10px;
    background: #fafbfd;
  }

  .reset-big-width {
    width: 490px;
  }

  .del-icon {
    position: absolute;
    top: 0;
    right: 0;
    font-size: 20px;
    cursor: pointer;
  }

  .add-btn {
    color: #3a84ff;
    cursor: pointer;
  }
}
</style>
