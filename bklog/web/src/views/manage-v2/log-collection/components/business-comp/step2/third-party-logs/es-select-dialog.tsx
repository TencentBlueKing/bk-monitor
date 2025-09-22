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

import { defineComponent, ref, computed } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';

import { useOperation } from '../../../../hook/useOperation';
import InfoTips from '../../../common-comp/info-tips';
import $http from '@/api';

import './es-select-dialog.scss';

export default defineComponent({
  name: 'EsSelectDialog',
  props: {
    isShowDialog: {
      type: Boolean,
      default: false,
    },
    configData: {
      type: Object,
      default: () => ({}),
    },
    scenarioId: {
      type: String,
      default: '',
    },
    timeIndex: {
      type: Object,
      default: () => ({}),
    },
  },

  emits: ['cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const indexName = ref('');
    const tableData = ref([]);
    const { handleMultipleSelected, tableLoading } = useOperation();
    // const tableLoading = ref(false);
    const confirmLoading = ref(false);
    const searchLoading = ref(false);
    const matchedTableIds = ref([]);
    const timeFields = ref([]);
    const bkBizId = computed(() => store.getters.bkBizId);

    const fetchList = async () => {
      try {
        const res = await $http.request('/resultTables/list', {
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId,
            storage_cluster_id: props.configData.storage_cluster_id,
            result_table_id: indexName.value,
          },
        });
        return res.data;
      } catch (e) {
        console.warn(e);
        // this.indexErrorText += e.message;
        // this.emptyType = '500';
        return [];
      }
    };

    const fetchInfo = () => {
      const param = {
        params: {
          result_table_id: indexName.value,
        },
        query: {
          scenario_id: props.scenarioId,
          bk_biz_id: bkBizId.value,
          storage_cluster_id: props.configData.storage_cluster_id,
        },
      };
      handleMultipleSelected(param, false, res => {
        const timeFields = res.data.fields.filter(item => item.field_type === 'date' || item.field_type === 'long');
        // 如果已经添加了索引，回填三个字段（禁止更改字段名）
        if (props.timeIndex) {
          const find = timeFields.find(item => item.field_name === props.timeIndex.time_field);
          if (find) {
            // Object.assign(this.formData, props.timeIndex);
          }
        }
        return timeFields;
      });
    };

    const handleSearch = async () => {
      searchLoading.value = true;
      tableLoading.value = true;
      const [idRes, fieldRes] = await Promise.all([fetchList(), fetchInfo()]);
      matchedTableIds.value = idRes;
      timeFields.value = fieldRes;
      searchLoading.value = false;
      tableLoading.value = false;
    };
    /**
     * 关闭新增索引弹窗
     */
    const handleCancel = () => {
      emit('cancel', false);
    };

    const handleConfirm = () => {};
    return () => (
      <bk-dialog
        width={680}
        ext-cls='es-select-dialog'
        header-position={'left'}
        mask-close={false}
        ok-text={t('添加')}
        theme='primary'
        title={t('新增索引')}
        value={props.isShowDialog}
        // on-cancel={handleCancel}
        // on-confirm={handleConfirm}
      >
        <bk-form label-width={80}>
          <bk-form-item
            label={t('索引')}
            property={'name'}
            required={true}
          >
            <bk-input
              class='input-box'
              placeholder='log_search_*'
              value={indexName.value}
              on-input={val => {
                indexName.value = val;
              }}
            />
            <bk-button
              disabled={!indexName.value}
              on-click={handleSearch}
            >
              {t('搜索')}
            </bk-button>
            <InfoTips tips={t('支持“ * ”匹配，不支持其他特殊符号')} />
          </bk-form-item>

          <bk-form-item class='mt-12'>
            <bk-table
              key={props.isShowDialog}
              height={320}
              v-bkloading={{ isLoading: tableLoading.value }}
              data={tableData.value}
            >
              <bk-table-column
                label={t('索引')}
                prop='field_name'
              />
            </bk-table>
          </bk-form-item>
          <bk-form-item
            label={t('时间字段')}
            property={'name'}
            required={true}
          >
            <bk-select
              // loading={basicLoading.value}
              value={indexName.value}
              searchable
              // on-selected={handleChoose}
            >
              {/* {(collectionList.value || []).map(item => (
                <bk-option
                  id={item.result_table_id}
                  key={item.result_table_id}
                  disabled={isSetDisabled(item.result_table_id)}
                  name={item.result_table_name_alias}
                />
              ))} */}
            </bk-select>
          </bk-form-item>
        </bk-form>
        <div slot='footer'>
          <bk-button
            class='mr-8'
            disabled={!indexName.value}
            loading={confirmLoading.value}
            theme='primary'
            on-click={handleConfirm}
          >
            {t('添加')}
          </bk-button>
          <bk-button on-click={handleCancel}>{t('取消')}</bk-button>
        </div>
      </bk-dialog>
    );
  },
});
