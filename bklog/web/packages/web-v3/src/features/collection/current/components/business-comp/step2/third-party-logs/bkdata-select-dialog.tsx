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

import { Button as TButton } from 'tdesign-vue-next';
import { ServicesInstance } from '@/platform/services';

import { defineComponent, ref, onMounted, computed, watch } from 'vue';

import useLocale from '@/shared/composables/use-locale';
import useStore from '@/shared/composables/use-store';

import { useOperation } from '../../../../hook/useOperation';

import TableComponent from '../../../common-comp/table-component';
import './bkdata-select-dialog.scss';

export default defineComponent({
  name: 'BkdataSelectDialog',
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
  },

  emits: ['selected', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const indexName = ref('');
    const tableData = ref([]);
    const basicLoading = ref(false);
    const collectionList = ref([]);
    const confirmLoading = ref(false);
    const bkBizId = computed(() => store.getters.bkBizId);
    const { handleMultipleSelected, tableLoading } = useOperation();
    onMounted(() => {
      fetchCollectionList();
    });

    watch(
      () => props.isShowDialog,
      (val: boolean) => {
        if (val) {
          indexName.value = '';
          tableData.value = [];
        }
      },
    );

    /**
     * 获取索引列表
     */
    const fetchCollectionList = async () => {
      try {
        basicLoading.value = true;
        const res = await ServicesInstance.resultTables.list({
          query: {
            scenario_id: props.scenarioId,
            bk_biz_id: bkBizId.value,
          },
        });
        collectionList.value = res.data.map((item: { bk_biz_id: any; }) => {
          // 后端要求传这个值，虽然不太合理
          item.bk_biz_id = bkBizId.value;
          return item;
        });
      } catch (e) {
        console.log(e);
      } finally {
        basicLoading.value = false;
      }
    };
    /**
     * 索引是否可选
     */
    const isSetDisabled = (id: unknown) => props.configData.indexes.some((item: { result_table_id: any; }) => item.result_table_id === id);

    // 选择采集项获取字段列表
    const handleSelected = async (id: number) => {
      const param = {
        params: {
          result_table_id: id,
        },
        query: {
          scenario_id: props.scenarioId,
          bk_biz_id: bkBizId.value,
        },
      };
      tableData.value = await handleMultipleSelected(param);
    };
    /**
     * 选择索引
     */
    const handleChoose = (value: string|number) => {
      indexName.value = value;
      handleSelected(value);
    };
    /**
     * 关闭新增索引弹窗
     */
    const handleCancel = () => {
      emit('cancel', false);
    };
    /**
     * 确认添加索引
     */
    const handleConfirm = async () => {
      try {
        confirmLoading.value = true;
        const data = {
          scenario_id: props.scenarioId,
          bk_biz_id: bkBizId.value,
          basic_indices: props.configData.indexes.map((item: { result_table_id: any; }) => ({
            index: item.result_table_id,
          })),
          append_index: {
            index: indexName.value,
          },
        };
        await ServicesInstance.resultTables.adapt({ data });
        const info = collectionList.value.find(item => item.result_table_id === indexName.value);
        const currentIndex = { ...info, ...{ scenarioId: props.scenarioId } };
        emit('selected', currentIndex);
        handleCancel();
      } catch (e) {
        console.log(e);
      } finally {
        confirmLoading.value = false;
      }
    };
    return () => (
      <bk-dialog
        v-slots={{
          footer: () => (
            <div>
              <TButton
                class='mr-8'
                disabled={!indexName.value}
                loading={confirmLoading.value}
                theme='primary'
                onClick={handleConfirm}
              >
                {t('添加')}
              </TButton>
              <TButton onClick={handleCancel}>{t('取消')}</TButton>
            </div>
          ),
        }}
        width={680}
        ext-cls='bk-data-index-dialog'
        header-position={'left'}
        mask-close={false}
        ok-text={t('添加')}
        theme='primary'
        title={t('新增数据源')}
        value={props.isShowDialog}
        onCancel={handleCancel}
      >
        <bk-form label-width={60}>
          <bk-form-item
            label={t('索引')}
            property={'name'}
            required={true}
          >
            <bk-select
              loading={basicLoading.value}
              value={indexName.value}
              searchable
              onSelected={handleChoose}
            >
              {(collectionList.value || []).map(item => (
                <bk-option
                  id={item.result_table_id}
                  key={item.result_table_id}
                  disabled={isSetDisabled(item.result_table_id)}
                  name={item.result_table_name_alias}
                />
              ))}
            </bk-select>
          </bk-form-item>
          <bk-form-item>
            <TableComponent
              key={props.isShowDialog}
              height={320}
              loading={tableLoading.value}
              data={tableData.value}
              skeletonConfig={{
                columns: 2,
                rows: 4,
                widths: ['50%', '50%'],
              }}
              columns={[
                {
                  title: t('字段'),
                  colKey: 'field_name',
                  ellipsis: true,
                },
                {
                  title: t('类型'),
                  colKey: 'field_type',
                  ellipsis: true,
                },
              ]}
            />
          </bk-form-item>
        </bk-form>
      </bk-dialog>
    );
  },
});
