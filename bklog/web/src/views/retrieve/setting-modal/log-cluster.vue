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
  <!-- 设置-日志聚类 -->
  <div
    class="setting-log-cluster"
    v-bkloading="{ isLoading: globalLoading }"
  >
    <bk-form
      ref="validateForm"
      :label-width="200"
      :model="formData"
      form-type="vertical"
    >
      <!-- 聚类字段 -->
      <bk-form-item
        :label="$t('聚类字段')"
        :property="'clustering_fields'"
        :required="true"
        :rules="rules.clustering_fields"
      >
        <div class="setting-item">
          <bk-select
            style="width: 482px"
            v-model="formData.clustering_fields"
            :clearable="false"
            :disabled="!globalEditable"
            data-test-id="LogCluster_div_selectField"
          >
            <bk-option
              v-for="option in clusterField"
              :id="option.id"
              :key="option.id"
              :name="option.name"
            >
            </bk-option>
          </bk-select>
          <span
            v-bk-tooltips="{
              content: $t('只能基于一个字段进行聚类，并且字段是为text的分词类型，默认为log字段'),
              placements: ['right'],
              delay: 300,
            }"
          >
            <span class="bk-icon icon-info"></span>
          </span>
        </div>
      </bk-form-item>
      <bk-form-item :label="$t('是否启用')">
        <div class="setting-item">
          <div @click="handleChangeFinger">
            <span
              class="top-middle"
              v-bk-tooltips="$t('暂时未开放聚类关闭功能，如有关闭需求，可联系平台管理员')"
              :disabled="!isShowFingerTips"
            >
              <bk-switcher
                class="left-word"
                v-model="fingerSwitch"
                :disabled="!globalEditable || fingerSwitch"
                :pre-check="() => false"
                data-test-id="LogCluster_div_isOpenSignature"
                size="large"
                theme="primary"
              >
              </bk-switcher>
            </span>
          </div>
        </div>
      </bk-form-item>

      <!-- 字段长度 -->
      <div class="rule-container">
        <bk-form-item
          :label="$t('最大字段长度')"
          :property="'max_log_length'"
          :rules="rules.max_log_length"
          required
        >
          <div class="setting-item">
            <bk-input
              style="width: 94px"
              v-model="formData.max_log_length"
              :disabled="!globalEditable"
              :max="2000000"
              :min="1"
              :precision="0"
              data-test-id="LogCluster_input_fieldLength"
              type="number"
            ></bk-input>
            <span style="margin-left: 8px">{{ $t('字节') }}</span>
            <span
              v-bk-tooltips="{
                content: $t('聚类字段的最大长度，如果超过这个长度将直接丢弃，设置越大将消耗更多的资源'),
                placements: ['right'],
                delay: 300,
              }"
            >
              <span class="bk-icon icon-info"></span>
            </span>
          </div>
        </bk-form-item>
        <!-- 过滤规则 -->
        <div style="margin-bottom: 40px">
          <p style="height: 24px; font-size: 12px">{{ $t('过滤规则') }}</p>
          <FilterRule
            ref="filterRuleRef"
            v-model="formData.filter_rules"
            :total-fields="totalFields"
            :date-picker-value="datePickerValue"
            :retrieve-params="retrieveParams"
          ></FilterRule>
        </div>
        <!-- 聚类规则 -->
        <rule-table
          ref="ruleTableRef"
          v-on="$listeners"
          :clean-config="cleanConfig"
          :global-editable="globalEditable"
          :table-str="defaultData.predefined_varibles"
          :submit-lading="isHandle"
          @submit-rule="handleSubmitClusterChange"
        />
      </div>
    </bk-form>
    <div class="submit-div">
      <bk-button
        :disabled="!globalEditable"
        :loading="isHandle"
        :title="$t('保存')"
        data-test-id="LogCluster_button_submit"
        theme="primary"
        @click.stop.prevent="handleSubmit"
      >
        {{ $t('保存') }}
      </bk-button>
      <bk-button
        style="margin-left: 8px"
        :disabled="!globalEditable"
        :title="$t('重置')"
        data-test-id="LogCluster_button_reset"
        @click="resetPage"
      >
        {{ $t('重置') }}
      </bk-button>
    </div>
    <!-- 保存dialog -->
    <bk-dialog
      width="360"
      ext-cls="submit-dialog"
      v-model="isShowSubmitDialog"
      :mask-close="false"
      :show-footer="false"
      header-position="left"
    >
      <div class="submit-dialog-container">
        <p class="submit-dialog-title">{{ $t('保存待生效') }}</p>
        <p class="submit-dialog-text">{{ $t('该保存需要10分钟生效, 请耐心等待') }}</p>
        <bk-button
          class="submit-dialog-btn"
          theme="primary"
          @click="closeKnowDialog"
        >
          {{ $t('我知道了') }}</bk-button
        >
      </div>
    </bk-dialog>
  </div>
</template>

<script>
  import RuleTable from './rule-table';
  import FilterRule from '../result-table-panel/log-clustering/components/quick-open-cluster-step/filter-rule';

  export default {
    components: {
      RuleTable,
      FilterRule,
    },
    props: {
      globalEditable: {
        type: Boolean,
        default: true,
      },
      totalFields: {
        type: Array,
        default: () => [],
      },
      indexSetItem: {
        type: Object,
        require: true,
      },
      configData: {
        type: Object,
        require: true,
      },
      cleanConfig: {
        type: Object,
        require: true,
      },
      datePickerValue: {
        // 过滤条件字段可选值关系表
        type: Array,
        required: true,
      },
      retrieveParams: {
        type: Object,
        default: () => ({}),
      },
    },
    data() {
      return {
        clusterField: [], // 聚类字段
        globalLoading: false,
        fingerSwitch: false, // 数据指纹
        isShowAddFilterIcon: true, // 是否显示过滤规则增加按钮
        isShowSubmitDialog: false, // 是否展开保存弹窗
        isHandle: false, // 保存loading
        isCloseSelect: false, // 过滤规则下拉框隐藏
        defaultData: {},
        defaultVaribles: '',
        rules: {
          clustering_fields: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
          max_log_length: [
            {
              required: true,
              trigger: 'blur',
            },
          ],
        },
        formData: {
          max_dist_list: '', // 敏感度
          predefined_varibles: '', //	预先定义的正则表达式
          max_log_length: 1, // 最大日志长度
          clustering_fields: '', // 聚类字段
          filter_rules: [], // 过滤规则
          signature_enable: false,
          regex_rule_type: 'customize',
          regex_template_id: 0,
        },
        isShowFingerTips: false,
        isActive: false,
      };
    },
    mounted() {
      this.initList();
    },
    methods: {
      /**
       * @desc: 数据指纹请求
       * @param { Boolean } isDefault 是否请求默认值
       */
      async requestCluster(isDefault = false, isInit = false) {
        this.globalLoading = true;
        try {
          const params = { index_set_id: this.$route.params.indexId };
          const data = { collector_config_id: this.configID };
          const baseUrl = '/logClustering';
          const requestBehindUrl = isDefault ? '/getDefaultConfig' : '/getConfig';
          const requestUrl = `${baseUrl}${requestBehindUrl}`;
          const res = await this.$http.request(requestUrl, !isDefault && { params, data });
          const {
            max_dist_list,
            predefined_varibles,
            max_log_length,
            clustering_fields,
            filter_rules: filterRules,
            regex_rule_type,
            regex_template_id,
          } = res.data;
          const newFilterRules = filterRules.map(item => ({
            ...(this.totalFields.find(tItem => tItem.field_name === item.fields_name) ?? {}),
            ...item,
            value: [item.value],
          }));
          this.defaultVaribles = predefined_varibles;
          const assignObj = {
            max_dist_list,
            predefined_varibles,
            max_log_length,
            clustering_fields,
            filter_rules: newFilterRules || [],
            regex_rule_type,
            regex_template_id,
          };
          Object.assign(this.formData, assignObj);
          Object.assign(this.defaultData, assignObj);
          if (isInit) this.$refs.ruleTableRef.initSelect(assignObj);
          // 当前回填的字段如果在聚类字段列表里找不到则赋值为空需要用户重新赋值
          const isHaveFieldsItem = this.clusterField.find(item => item.id === res.data.clustering_fields);
          if (!isHaveFieldsItem) this.formData.clustering_fields = '';
        } catch (e) {
          console.warn(e);
        } finally {
          this.globalLoading = false;
        }
      },
      initList() {
        this.fingerSwitch = true;
        this.isShowFingerTips = true;
        this.isActive = this.configData.is_active;
        this.configID = this.$store.state.indexSetFieldConfig.clean_config?.extra.collector_config_id;
        this.formData.clustering_fields = this.configData?.extra.clustering_fields;
        this.clusterField = this.totalFields
          .filter(item => item.is_analyzed)
          .map(el => {
            const { field_name: id, field_alias: alias } = el;
            return { id, name: alias ? `${id}(${alias})` : id };
          });
        // 日志聚类且数据指纹同时打开则不请求默认值
        this.requestCluster(false, true);
      },
      /**
       * @desc: 数据指纹开关
       */
      handleChangeFinger() {
        if (!this.globalEditable) return;

        if (this.fingerSwitch) {
          this.fingerSwitch = false;
          // this.$bkInfo({
          //   title: this.$t('是否关闭数据指纹'),
          //   confirmFn: () => {
          //     this.fingerSwitch = false;
          //   },
          // });
        } else {
          // 当前如果是计算平台则直接请求 计算平台无configID
          if (this.indexSetItem.scenario_id === 'bkdata') {
            this.fingerSwitch = true;
            this.requestCluster(true);
            return;
          }
          if (!this.configID) {
            this.$bkInfo({
              title: this.$t('当前索引集为非采集项,无法设置数据指纹'),
              confirmFn: () => {},
            });
            return;
          }
          this.fingerSwitch = true;
          this.requestCluster(true);
        }
      },
      getIsChangeRule() {
        return this.$refs.ruleTableRef.ruleArrToBase64() !== this.defaultVaribles;
      },
      async handleSubmit() {
        const isRulePass = await this.$refs.filterRuleRef.handleCheckRuleValidate();
        if (!isRulePass) return;
        this.$refs.validateForm.validate().then(
          () => {
            const newPredefinedVaribles = this.$refs.ruleTableRef.ruleArrToBase64();
            if (newPredefinedVaribles !== this.defaultVaribles) {
              this.$refs.ruleTableRef.isClickAlertIcon = true;
              this.$refs.ruleTableRef.isChangeRule = true;
              this.$refs.ruleTableRef.effectOriginal = '';
              this.$refs.ruleTableRef.getLogOriginal();
              return;
            }
            this.handleSubmitClusterChange();
          },
          () => {},
        );
      },
      handleSubmitClusterChange() {
        this.isHandle = true;
        const { index_set_id, bk_biz_id } = this.indexSetItem;
        const {
          max_dist_list,
          predefined_varibles,
          delimeter,
          max_log_length,
          is_case_sensitive,
          clustering_fields,
          filter_rules,
          regex_rule_type,
          regex_template_id,
        } = this.formData;
        const paramsData = {
          max_dist_list,
          predefined_varibles,
          delimeter,
          max_log_length,
          is_case_sensitive,
          clustering_fields,
          filter_rules,
          regex_rule_type,
          regex_template_id,
        };
        // 获取子组件传来的聚类规则数组base64字符串
        paramsData.predefined_varibles = this.$refs.ruleTableRef.ruleArrToBase64();
        paramsData.regex_rule_type = this.$refs.ruleTableRef.getRuleType();
        paramsData.regex_template_id = this.$refs.ruleTableRef.getTemplateID();
        // 过滤规则数组形式转成字符串形式传参
        paramsData.filter_rules = paramsData.filter_rules
          .filter(item => item.value.length)
          .map(item => ({
            fields_name: item.fields_name,
            logic_operator: item.logic_operator,
            op: item.op,
            value: item.value[0],
          }));
        this.$http
          .request('retrieve/updateClusteringConfig', {
            params: {
              index_set_id,
            },
            data: {
              ...paramsData,
              signature_enable: this.fingerSwitch,
              collector_config_id: this.configID,
              index_set_id,
              bk_biz_id,
            },
          })
          .then(() => {
            this.isShowSubmitDialog = true;
          })
          .finally(() => {
            this.isHandle = false;
          });
      },
      resetPage() {
        this.defaultData.predefined_varibles = '';
        this.requestCluster(false);
      },
      closeKnowDialog() {
        this.isShowSubmitDialog = false;
        this.$emit('update-log-fields');
      },
    },
  };
</script>

<style lang="scss" scoped>
  .setting-log-cluster {
    position: relative;
    padding: 0 20px;

    .rule-container {
      margin-top: 16px;
    }

    .setting-item {
      display: flex;
      align-items: center;
      margin-bottom: 25px;

      .bk-icon {
        margin-left: 8px;
        font-size: 18px;
        color: #979ba5;
      }
    }

    .submit-div {
      position: sticky;
      bottom: 40px;
      padding: 10px 0;
      background: #fff;
    }
  }

  .submit-dialog {
    :deep(.bk-dialog-tool) {
      display: none;
    }

    .submit-dialog-container {
      :deep(.bk-button) {
        margin-left: 100px;
      }

      .submit-dialog-title {
        margin-bottom: 7px;
        font-size: 16px;
        font-weight: 700;
      }

      .submit-dialog-text {
        margin-bottom: 22px;
      }

      :deep(.submit-dialog-btn) {
        margin-left: 224px;
      }
    }
  }
</style>
