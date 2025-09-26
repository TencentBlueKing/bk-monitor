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
import { defineComponent, onMounted, ref, computed, watch } from 'vue';
import TextHighlight from 'vue-text-highlight';

import FilterRule from '@/components/filter-rule';
import RuleConfigOperate from '@/components/rule-config-operate';
import RuleTable from '@/components/rule-table';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { bkNotify } from 'bk-magic-vue';

import RuleOperate from './rule-operate';
import $http from '@/api';

import type { ConfigInfo } from '@/services/log-clustering';
import type { IResponseData } from '@/services/type';

import './index.scss';

export default defineComponent({
  name: 'EditConfig',
  components: {
    RuleOperate,
    RuleTable,
    FilterRule,
    TextHighlight,
    RuleConfigOperate,
  },
  props: {
    indexId: {
      type: String,
      require: true,
    },
    totalFields: {
      type: Array,
      default: () => [],
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const ruleConfigOperateRef = ref<any>(null);
    const ruleOperateRef = ref<any>();
    const ruleTableRef = ref<any>(null);
    const filterRuleRef = ref(null);
    const formRef = ref<any>(null);
    const formData = ref({
      max_dist_list: '', // 敏感度
      predefined_varibles: '', //	预先定义的正则表达式
      max_log_length: 1, // 最大日志长度
      clustering_fields: '', // 聚类字段
      filter_rules: [] as any[], // 过滤规则
      signature_enable: false,
      regex_rule_type: 'customize',
      regex_template_id: 0,
    });
    const currentRuleType = ref('template'); // 规则类型
    const globalLoading = ref(false);
    const defaultData = ref({} as any);
    const clusterField = ref<
      {
        id: string;
        name: string;
      }[]
    >([]);
    const ruleList = ref<Record<string, string>[]>([]);

    const isRuleTableReadonly = computed(() => currentRuleType.value === 'template');
    const configId = computed(() => store.state.indexSetFieldConfig.clean_config?.extra.collector_config_id);
    const indexSetItem = computed(() => store.state.indexItem.items[0]);

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

    watch(
      () => props.totalFields,
      () => {
        clusterField.value = props.totalFields
          .filter((item: { is_analyzed: boolean }) => item.is_analyzed)
          .map(el => {
            const { field_name: id, field_alias: alias } = el as any;
            return { id, name: alias ? `${id}(${alias})` : id };
          });
      },
      {
        immediate: true,
      },
    );

    const handleRuleListChange = (list: Record<string, string>[]) => {
      ruleList.value = list;
    };

    // 数据指纹请求
    const requestCluster = async (isDefault = false) => {
      globalLoading.value = true;
      try {
        const params = {
          index_set_id: props.indexId,
        };
        const data = { collector_config_id: configId.value };
        const baseUrl = '/logClustering';
        const requestBehindUrl = isDefault ? '/getDefaultConfig' : '/getConfig';
        const requestUrl = `${baseUrl}${requestBehindUrl}`;
        const res = (await $http.request(requestUrl, !isDefault && { params, data })) as IResponseData<ConfigInfo>;
        const {
          max_dist_list,
          predefined_varibles,
          max_log_length,
          clustering_fields,
          filter_rules: filterRules,
          regex_rule_type,
          regex_template_id,
        } = res.data;
        const newFilterRules = filterRules.map(item => {
          const sameFieldItem: any =
            props.totalFields.find((tItem: any) => tItem.field_name === item.fields_name) || {};
          return {
            ...sameFieldItem,
            ...item,
            value: Array.isArray(item.value) ? [...item.value] : [item.value],
          };
        });
        // defaultVaribles.value = predefined_varibles;
        const assignObj = {
          max_dist_list,
          predefined_varibles,
          max_log_length,
          clustering_fields,
          filter_rules: newFilterRules || [],
          regex_rule_type,
          regex_template_id,
        };
        Object.assign(formData.value, assignObj);
        defaultData.value = structuredClone(assignObj);
        // 当前回填的字段如果在聚类字段列表里找不到则赋值为空需要用户重新赋值
        const isHaveFieldsItem = clusterField.value.find(item => item.id === res.data.clustering_fields);
        if (!isHaveFieldsItem) {
          formData.value.clustering_fields = '';
        }
      } catch (e) {
        console.warn(e);
      } finally {
        globalLoading.value = false;
      }
    };

    const handleSearchRuleList = (keyword: string) => {
      ruleTableRef.value.search(keyword);
    };

    const handleSubmit = () => {
      formRef.value
        .validate()
        .then(() => {
          formData.value.filter_rules = formData.value.filter_rules.map(item => ({
            ...item,
            fields_name: item.field_name,
          }));
          const { index_set_id, bk_biz_id } = indexSetItem.value;
          const { max_dist_list, max_log_length, clustering_fields, filter_rules } = formData.value;
          const ruleInfo = ruleOperateRef.value.getRuleInfo();
          const paramsData = {
            max_dist_list,
            predefined_varibles: ruleTableRef.value.getRuleListBase64(),
            max_log_length,
            clustering_fields,
            filter_rules: filter_rules.map(item => ({
              fields_name: item.fields_name,
              logic_operator: item.logic_operator,
              op: item.op,
              value: item.value,
            })),
            regex_rule_type: ruleInfo.type,
            regex_template_id: ruleInfo.id,
          };
          $http
            .request('retrieve/updateClusteringConfig', {
              params: {
                index_set_id,
              },
              data: {
                ...paramsData,
                signature_enable: true,
                collector_config_id: configId.value,
                index_set_id,
                bk_biz_id,
              },
            })
            .then(() => {
              bkNotify({
                title: t('保存待生效'),
                message: t('该保存需要10分钟生效, 请耐心等待'),
                limitLine: 3,
                offsetY: 80,
              });
              emit('close');
            })
            .finally(() => {
              ruleConfigOperateRef.value?.setSaveLoading(false);
            });
        })
        .catch(e => {
          console.error(e);
        });
    };

    const handleReset = () => {
      formData.value.clustering_fields = defaultData.value.clustering_fields;
      formData.value.max_log_length = defaultData.value.max_log_length;
      formData.value.filter_rules = structuredClone(defaultData.value.filter_rules);
      ruleOperateRef.value.reset();
      ruleTableRef.value.init();
    };

    onMounted(() => {
      requestCluster();
    });

    return () => (
      <div
        class='setting-log-cluster'
        v-bkloading={{ isLoading: globalLoading.value }}
      >
        <div class='setting-form-main'>
          <bk-form
            ref={formRef}
            class='setting-form'
            label-width={200}
            {...{
              props: {
                model: formData.value,
                rules,
              },
            }}
            form-type='vertical'
          >
            <bk-form-item
              label={t('聚类字段')}
              property='clustering_fields'
              required
            >
              <div class='setting-item'>
                <bk-select
                  style='width: 482px'
                  clearable={false}
                  value={formData.value.clustering_fields}
                  on-change={value => {
                    formData.value.clustering_fields = value;
                  }}
                >
                  {clusterField.value.map(item => (
                    <bk-option
                      id={item.id}
                      key={item.id}
                      name={item.name}
                    ></bk-option>
                  ))}
                </bk-select>
                <span class='set-tip-main'>
                  <log-icon
                    type='info'
                    common
                  />
                  <span class='tip'>{t('只能基于 1 个字段进行聚类，并且字段是为text的分词类型，默认为log字段')}</span>
                </span>
              </div>
            </bk-form-item>
            <div class='rule-container'>
              <bk-form-item
                label={t('最大字段长度')}
                property='max_log_length'
                required
              >
                <div class='setting-item'>
                  <bk-input
                    style='width: 94px'
                    max={2000000}
                    min={1}
                    precision={0}
                    type='number'
                    value={formData.value.max_log_length}
                    on-change={value => {
                      formData.value.max_log_length = Number(value);
                    }}
                  />
                  <span style='margin-left: 8px'>{t('字节')}</span>
                  <span class='set-tip-main'>
                    <log-icon
                      type='info'
                      common
                    />
                    <span class='tip'>
                      {t('聚类字段的最大长度，如果超过这个长度将直接丢弃，设置越大将消耗更多的资源')}
                    </span>
                  </span>
                </div>
              </bk-form-item>
              <div style='margin-bottom: 40px'>
                <p style='height: 24px; font-size: 12px'>{t('过滤规则')}</p>
                <filter-rule
                  ref={filterRuleRef}
                  data={formData.value.filter_rules}
                />
              </div>
              <p style='font-weight: 700;font-size: 12px'>{t('聚类规则')}</p>
              <RuleOperate
                ref={ruleOperateRef}
                style='margin-bottom: 8px'
                defaultValue={defaultData.value}
                ruleList={ruleList.value}
                on-rule-list-change={handleRuleListChange}
                on-rule-type-change={rule => {
                  currentRuleType.value = rule;
                }}
                on-search={handleSearchRuleList}
              />
              <RuleTable
                ref={ruleTableRef}
                readonly={isRuleTableReadonly.value}
                ruleList={ruleList.value}
                on-rule-list-change={list => {
                  ruleList.value = list;
                }}
              />
            </div>
          </bk-form>
        </div>

        <RuleConfigOperate
          ref={ruleConfigOperateRef}
          max_log_length={formData.value.max_log_length}
          ruleList={ruleList.value}
          on-reset={handleReset}
          on-submit={handleSubmit}
        />
      </div>
    );
  },
});
