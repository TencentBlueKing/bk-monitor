/*
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
 */

import { defineComponent, ref } from 'vue';
import useLocale from '@/hooks/use-locale';
// import useStore from '@/hooks/use-store';
import RuleOperate from './rule-operate';
import RuleTable from './rule-table';
// import $http from '@/api';

import './index.scss';

export default defineComponent({
  name: 'EditConfig',
  components: {
    RuleOperate,
    RuleTable,
  },
  props: {
    globalEditable: {
      type: Boolean,
      default: true,
    },
    indexId: {
      type: String,
      require: true,
    },
    totalFields: {
      type: Array,
      default: () => [],
    },
    // indexSetItem: {
    //   type: Object,
    //   require: true,
    // },
    // configData: {
    //   type: Object,
    //   require: true,
    // },
    // cleanConfig: {
    //   type: Object,
    //   require: true,
    // },
    // datePickerValue: {
    //   // 过滤条件字段可选值关系表
    //   type: Array,
    //   require: true,
    // },
    retrieveParams: {
      type: Object,
      default: () => ({}),
    },
  },
  setup(props) {
    const { t } = useLocale();
    // const store = useStore();

    const formRef = ref(null);
    // const ruleTableRef = ref(null);
    const formData = ref({
      max_dist_list: '', // 敏感度
      predefined_varibles: '', //	预先定义的正则表达式
      max_log_length: 1, // 最大日志长度
      clustering_fields: '', // 聚类字段
      filter_rules: [], // 过滤规则
      signature_enable: false,
      regex_rule_type: 'customize',
      regex_template_id: 0,
    });
    const globalLoading = ref(false);
    const isShowSubmitDialog = ref(false); // 是否展开保存弹窗
    const isHandle = ref(false); // 保存loading
    // const ruleType = ref('customize');
    // const defaultVaribles = ref('');
    // const defaultData = ref({});
    const clusterField = ref<
      {
        id: number;
        name: string;
      }[]
    >([]);
    const ruleList = ref([]);

    // const configID = computed(() => store.state.indexSetFieldConfig.clean_config?.extra.collector_config_id);

    const rules = {
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
    };

    const handleRuleListChange = list => {
      console.log(list);
      ruleList.value = list;
    };

    /**
     * @desc: 数据指纹请求
     * @param { Boolean } isDefault 是否请求默认值
     */
    // const requestCluster = async (isDefault = false, isInit = false) => {
    //   globalLoading.value = true;
    //   try {
    //     const params = {
    //       index_set_id: props.indexId,
    //     };
    //     const data = { collector_config_id: configID.value };
    //     const baseUrl = '/logClustering';
    //     const requestBehindUrl = isDefault ? '/getDefaultConfig' : '/getConfig';
    //     const requestUrl = `${baseUrl}${requestBehindUrl}`;
    //     const res = await $http.request(requestUrl, !isDefault && { params, data });
    //     const {
    //       max_dist_list,
    //       predefined_varibles,
    //       max_log_length,
    //       clustering_fields,
    //       filter_rules: filterRules,
    //       regex_rule_type,
    //       regex_template_id,
    //     } = res.data;
    //     const newFilterRules = filterRules.map(item => ({
    //       ...(props.totalFields.find(tItem => tItem.field_name === item.fields_name) ?? {}),
    //       ...item,
    //       value: Array.isArray(item.value) ? [...item.value] : [item.value],
    //     }));
    //     defaultVaribles.value = predefined_varibles;
    //     const assignObj = {
    //       max_dist_list,
    //       predefined_varibles,
    //       max_log_length,
    //       clustering_fields,
    //       filter_rules: newFilterRules || [],
    //       regex_rule_type,
    //       regex_template_id,
    //     };
    //     Object.assign(formData.value, assignObj);
    //     Object.assign(defaultData.value, assignObj);
    //     if (isInit) {
    //       ruleTableRef.value.initSelect(assignObj);
    //     }
    //     // 当前回填的字段如果在聚类字段列表里找不到则赋值为空需要用户重新赋值
    //     const isHaveFieldsItem = clusterField.value.find(item => item.id === res.data.clustering_fields);
    //     if (!isHaveFieldsItem) formData.value.clustering_fields = '';
    //   } catch (e) {
    //     console.warn(e);
    //   } finally {
    //     globalLoading.value = false;
    //   }
    // };

    return () => (
      <div
        class='setting-log-cluster'
        v-bkloading={{ isLoading: globalLoading.value }}
      >
        <bk-form
          ref={formRef}
          label-width={200}
          {...{
            props: {
              model: formData.value,
            },
          }}
          form-type='vertical'
        >
          <bk-form-item
            label={t('聚类字段')}
            property='clustering_fields'
            required
            rules={rules.clustering_fields}
          >
            <div class='setting-item'>
              <bk-select
                style='width: 482px'
                value={formData.value.clustering_fields}
                clearable={false}
                disabled={!props.globalEditable}
                data-test-id='LogCluster_div_selectField'
              >
                {clusterField.value.map(item => (
                  <bk-option
                    id={item.id}
                    key={item.id}
                    name={item.name}
                  ></bk-option>
                ))}
              </bk-select>
              <span>
                <span class='bk-icon icon-info'></span>
                <span>{t('只能基于 1 个字段进行聚类，并且字段是为text的分词类型，默认为log字段')}</span>
              </span>
            </div>
          </bk-form-item>
          <div class='rule-container'>
            <bk-form-item
              label={t('最大字段长度')}
              property='max_log_length'
              rules={rules.max_log_length}
              required
            >
              <div class='setting-item'>
                <bk-input
                  style='width: 94px'
                  value={formData.value.max_log_length}
                  disabled={!props.globalEditable}
                  max={2000000}
                  min={1}
                  precision={0}
                  data-test-id='LogCluster_input_fieldLength'
                  type='number'
                />
                <span style='margin-left: 8px'>{t('字节')}</span>
                <span>
                  <span class='bk-icon icon-info'></span>
                  <span>{t('聚类字段的最大长度，如果超过这个长度将直接丢弃，设置越大将消耗更多的资源')}</span>
                </span>
              </div>
            </bk-form-item>
            <div style='margin-bottom: 40px'>
              <p style='height: 24px; font-size: 12px'>{t('过滤规则')}</p>
              {/* <FilterRule
            ref="filterRuleRef"
            v-model="formData.filter_rules"
            date-picker-value="datePickerValue"
            retrieve-params="retrieveParams"
            total-fields="totalFields"
          ></FilterRule> */}
            </div>
            <p style='font-weight: 700;font-size: 12px'>{t('聚类规则')}</p>
            <rule-operate
              style='margin-bottom: 8px'
              on-rule-list-change={handleRuleListChange}
            />
            <rule-table ruleList={ruleList.value} />
            {/* <rule-table
          ref="ruleTableRef"
          v-on="$listeners"
          clean-config="cleanConfig"
          global-editable="globalEditable"
          submit-lading="isHandle"
          table-str="defaultData.predefined_varibles"
          max-log-length="formData.max_log_length"
          submit-rule="handleSubmitClusterChange"
        /> */}
          </div>
        </bk-form>
        <div class='submit-div'>
          <bk-button
            disabled={!props.globalEditable}
            loading={isHandle.value}
            data-test-id='LogCluster_button_submit'
            theme='primary'
            on-click='handleSubmit'
          >
            {t('保存')}
          </bk-button>
          <bk-button
            style='margin-left: 8px'
            disabled={!props.globalEditable}
            data-test-id='LogCluster_button_reset'
            on-click='resetPage'
          >
            {t('重置')}
          </bk-button>
        </div>
        <bk-dialog
          width='360'
          ext-cls='submit-dialog'
          value={isShowSubmitDialog.value}
          mask-close={false}
          show-footer={false}
          header-position='left'
        >
          <div class='submit-dialog-container'>
            <p class='submit-dialog-title'>{t('保存待生效')}</p>
            <p class='submit-dialog-text'>{t('该保存需要10分钟生效, 请耐心等待')}</p>
            <bk-button
              class='submit-dialog-btn'
              theme='primary'
              on-click='closeKnowDialog'
            >
              {t('我知道了')}
            </bk-button>
          </div>
        </bk-dialog>
      </div>
    );
  },
});
