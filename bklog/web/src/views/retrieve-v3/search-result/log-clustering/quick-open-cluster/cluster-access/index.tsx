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
import _ from 'lodash';
import { computed, defineComponent, ref, watch, PropType } from 'vue';
import useLocale from '@/hooks/use-locale';
import { useRoute, useRouter } from 'vue-router/composables';
import useStore from '@/hooks/use-store';
import $http from '@/api';
import { bkPopover } from 'bk-magic-vue';
import clusterImg from '@/images/cluster-img/cluster.png';
import FilterRule from './filter-rule-new';
import PreviewResult from './preview-result';

import './index.scss';

export default defineComponent({
  name: 'QuickOpenCluster',
  components: {
    FilterRule,
    PreviewResult,
  },
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    indexId: {
      type: String,
      default: '',
    },
    totalFields: {
      type: Array<any>,
      required: true,
    },
    retrieveParams: {
      type: Object as PropType<Record<string, any>>,
      required: true,
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();

    const quickClusterFromRef = ref();
    const filterRuleRef = ref();
    const isShowDialog = ref(false);
    const confirmLading = ref(false);
    const formData = ref({
      clustering_fields: '',
      filter_rules: [],
    });

    const clusterField = computed(() =>
      props.totalFields
        .filter(item => item.is_analyzed)
        .map(el => {
          const { field_name: id, field_alias: alias } = el;
          return { id, name: alias ? `${id}(${alias})` : id };
        }),
    );

    let cloneFormData = null;

    const formRules = {
      clustering_fields: [
        {
          required: true,
          trigger: 'blur',
        },
      ],
    };

    watch(
      () => props.isShow,
      () => {
        isShowDialog.value = props.isShow;
      },
      {
        immediate: true,
      },
    );

    watch(
      () => formData.value.clustering_fields,
      fieldName => {
        handleClusteringFields(fieldName);
      },
    );

    const handleClusteringFields = (fieldName: string) => {
      if (formData.value.filter_rules.length) {
        formData.value.filter_rules.forEach(rule => {
          const targetField = props.totalFields.find(f => f.field_name === fieldName);
          Object.assign(rule, { ...targetField, field_name: targetField.field_name });
        });
      }
    };

    const handleConfirmSubmit = async () => {
      // const isRulePass = await filterRuleRef.value.handleCheckRuleValidate();
      // if (!isRulePass) return;
      quickClusterFromRef.value.validate().then(async () => {
        // confirmLading.value = true;
        try {
          console.log('???', formData.value.filter_rules);
          // const data = {
          //   bk_biz_id: bkBizId.value,
          //   clustering_fields: formData.value.clustering_fields,
          //   filter_rules: formData.value.filter_rules
          //     .filter(item => item.value.length)
          //     .map(item => ({
          //       fields_name: item.field_name,
          //       logic_operator: item.logic_operator,
          //       op: item.op,
          //       value: item.value,
          //     })),
          // };
          // const result = await $http.request('retrieve/createClusteringConfig', {
          //   params: {
          //     index_set_id: props.indexId,
          //   },
          //   data,
          // });
          // if (result.code === 0) {
          //   // 若是从未弹窗过的话，打开更多聚类的弹窗
          //   const clusterPopoverState = localStorage.getItem('CLUSTER_MORE_POPOVER');
          //   if (!Boolean(clusterPopoverState)) {
          //     const dom = document.querySelector('#more-operator');
          //     dom?.addEventListener('popoverShowEvent', operatorTargetEvent);
          //     dom?.dispatchEvent(new Event('popoverShowEvent'));
          //     localStorage.setItem('CLUSTER_MORE_POPOVER', 'true');
          //   }
          //   isShowDialog.value = false;
          //   handleCreateCluster();
          // }
        } catch (error) {
          console.warn(error);
        } finally {
          confirmLading.value = false;
        }
      });
    };

    const handleOpenDialog = (isOpen: boolean) => {
      if (isOpen) {
        cloneFormData = _.cloneDeep(formData.value);
        if (clusterField.value[0]?.id) {
          formData.value.clustering_fields = clusterField.value[0]?.id || '';
          const targetField = props.totalFields.find(f => f.field_name === clusterField.value[0]?.id);
          formData.value.filter_rules.push({
            ...targetField,
            op: 'LIKE',
            value: ['%ERROR%'],
            field_name: targetField.field_name,
          });
        }
      } else {
        formData.value = cloneFormData;
      }
    };

    return () => (
      <bk-sideslider
        width={1028}
        ext-cls='cluster-access-slider-main'
        is-show={isShowDialog.value}
        mask-close={false}
        theme='primary'
        title={t('日志聚类接入')}
        on-shown={() => handleOpenDialog(true)}
        on-hidden={() => handleOpenDialog(false)}
      >
        <div slot='content'>
          <bk-alert
            type='info'
            title={t('大量的日志会导致聚类结果过多，建议使用过滤规则将重要日志进行聚类；如：仅聚类 warn 日志')}
          />
          <bk-form
            ref={quickClusterFromRef}
            form-type='vertical'
            {...{
              props: {
                model: formData.value,
                rules: formRules,
              },
            }}
          >
            <bk-form-item
              label={t('聚类字段')}
              property='clustering_fields'
              required
            >
              <div class='setting-item'>
                <bk-select
                  style='width: 482px'
                  value={formData.value.clustering_fields}
                  clearable={false}
                  on-change={value => (formData.value.clustering_fields = value)}
                >
                  {clusterField.value.map(option => (
                    <bk-option
                      id={option.id}
                      name={option.name}
                    ></bk-option>
                  ))}
                </bk-select>
                <span>
                  <span class='bk-icon icon-info'></span>
                </span>
              </div>
            </bk-form-item>
            <bk-form-item
              label={t('过滤规则')}
              property='filter_rules'
            >
              <filter-rule
                ref={filterRuleRef}
                data={formData.value.filter_rules}
                retrieve-params={props.retrieveParams}
                total-fields={props.totalFields}
              />
            </bk-form-item>
          </bk-form>
          <PreviewResult style='margin-top: 32px;margin-bottom: 24px' />
          <div class='bottom-operate'>
            <bk-button
              theme='primary'
              style='width: 88px'
              loading={confirmLading.value}
              on-click={handleConfirmSubmit}
            >
              {t('提交')}
            </bk-button>
            <bk-button
              style='width: 88px'
              on-click={() => (isShowDialog.value = false)}
            >
              {t('取消')}
            </bk-button>
          </div>
        </div>
      </bk-sideslider>
    );
  },
});
