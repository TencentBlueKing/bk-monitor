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

import { computed, defineComponent, ref, watch } from 'vue';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRoute } from 'vue-router/composables';

import $http from '@/api';

import './index-config-import-dialog.scss';
/**
 * 行首正则调试弹窗
 */

export default defineComponent({
  name: 'IndexConfigImportDialog',
  props: {
    showDialog: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['update', 'cancel'],

  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const syncTypeList = [
      { name: t('同步源日志信息'), id: 'source_log_info' },
      { name: t('同步字段清洗配置'), id: 'field_clear_config' },
      { name: t('同步存储配置'), id: 'storage_config' },
      { name: t('同步采集目标'), id: 'acquisition_target' },
    ];

    const syncType = ref(['source_log_info']);
    const pagination = ref({
      current: 1,
      count: 0,
      limit: 10,
      'show-limit': false,
    });
    const isTableLoading = ref(false);
    const submitLoading = ref(false);
    const collectList = ref([]);
    const emptyType = ref('empty');
    const keyword = ref('');
    const searchKeyword = ref('');
    const currentCheckImportID = ref(null);

    const getCheckedStatus = row => {
      return row.collector_config_id === currentCheckImportID.value;
    };

    const changePagination = (page: { current?: number; count?: number; limit?: number }) => {
      pagination.value = {
        ...pagination.value,
        ...page,
      };
    };
    const etlConfigList = computed(() => store.getters['globals/globalsData']?.etl_config || []);

    const collectShowList = computed(() => {
      let collect = collectList.value;
      if (keyword.value) {
        collect = collect.filter(item =>
          item.collector_config_name.toString().toLowerCase().includes(keyword.value.toLowerCase()),
        );
      }
      emptyType.value = keyword.value ? 'search-empty' : 'empty';
      changePagination({ count: collect.length });
      const { current, limit } = pagination.value;

      const startIndex = (current - 1) * limit;
      const endIndex = current * limit;
      return collect.slice(startIndex, endIndex);
    });
    const handleCollectPageChange = (current: number) => {
      changePagination({ current });
    };
    const handleRowCheckChange = row => {
      if (currentCheckImportID.value === row.collector_config_id) {
        currentCheckImportID.value = null;
        return;
      }
      currentCheckImportID.value = row.collector_config_id;
    };
    const handleSave = () => {};
    const handleValueChange = v => {
      if (!v) {
        syncType.value = ['source_log_info'];
        currentCheckImportID.value = null;
        emptyType.value = 'empty';
        keyword.value = '';
        searchKeyword.value = '';
      }
    };
    const handleCancel = () => {
      emit('cancel', !props.showDialog);
    };
    const pythonDictString = (pythonString: string) => {
      return pythonString
        .replace(/'/g, '"') // 将单引号替换为双引号
        .replace(/None/g, 'null') // 将 None 替换为 null
        .replace(/True/g, 'true') // 将 True 替换为 true
        .replace(/False/g, 'false'); // 将 False 替换为 false
    };
    const getLinkList = () => {
      isTableLoading.value = true;
      const ids = route.query.ids as string; // 根据id来检索
      const collectorIdList = ids ? decodeURIComponent(ids) : [];
      collectList.value.length = 0;
      collectList.value = [];
      $http
        .request('collect/getAllCollectors', {
          query: {
            bk_biz_id: store.state.bkBizId,
            collector_id_list: collectorIdList,
            have_data_id: 1,
            not_custom: 1,
          },
        })
        .then(res => {
          const { data } = res;
          if (data?.length) {
            collectList.value = data.map(item => {
              const {
                collector_config_id,
                collector_config_name,
                storage_cluster_name,
                etl_config,
                retention,
                params,
                bk_data_id,
              } = item;
              let paths: string[] = [];
              try {
                const value = JSON.parse(pythonDictString(params));
                paths = value?.paths ?? [];
              } catch (e) {
                console.error(e);
              }
              return {
                bk_data_id,
                collector_config_id,
                collector_config_name: collector_config_name || '--',
                storage_cluster_name: storage_cluster_name || '--',
                retention: retention ? `${retention}${t('天')}` : '--',
                paths: paths?.join('; ') ?? '',
                etl_config: etlConfigList.value.find(newItem => newItem.id === etl_config)?.name ?? '--',
              };
            });
          }
        })
        .catch(() => {
          emptyType.value = '500';
        })
        .finally(() => {
          isTableLoading.value = false;
        });
    };

    watch(
      () => props.showDialog,
      (val: boolean) => {
        val && getLinkList();
      },
    );

    const search = () => {
      keyword.value = searchKeyword.value;
      emptyType.value = keyword.value ? 'search-empty' : 'empty';
    };

    const spanSlot = {
      default: ({ row, column }) => (
        <div
          class='title-overflow'
          v-bk-overflow-tips
        >
          <span>{row[column.property] || '--'}</span>
        </div>
      ),
    };
    const checkBoxSlot = {
      default: ({ row }) => (
        <div class='import-check-box'>
          <bk-checkbox
            class='group-check-box'
            checked={getCheckedStatus(row)}
          />
        </div>
      ),
    };

    return () => (
      <bk-dialog
        width={1200}
        class='index-config-import-dialog'
        header-position='left'
        mask-close={false}
        position={{ top: 100 }}
        title={t('索引配置导入')}
        value={props.showDialog}
        on-cancel={handleCancel}
        on-confirm={handleSave}
        on-value-change={handleValueChange}
      >
        <div class='index-config-import-dialog-content'>
          <div class='content-top'>
            <bk-checkbox-group
              value={syncType.value}
              on-change={(val: string[]) => {
                syncType.value = val;
              }}
            >
              {syncTypeList.map(item => (
                <bk-checkbox
                  value={item.id}
                  key={item.id}
                >
                  {item.name}
                </bk-checkbox>
              ))}
            </bk-checkbox-group>
            <bk-input
              placeholder={t('搜索名称')}
              right-icon='bk-icon icon-search'
              value={searchKeyword.value}
              on-change={(val: string) => {
                searchKeyword.value = val;
                if (val === '') {
                  changePagination({ current: 1 });
                  keyword.value = '';
                }
              }}
              on-enter={search}
            />
          </div>
          <div class='content-bot'>
            <div class='content-bot-title'>{t('请选择目标索引集')}</div>
            <bk-table
              v-bkloading={{ isLoading: isTableLoading.value }}
              data={collectShowList.value}
              pagination={pagination.value}
              on-page-change={handleCollectPageChange}
              on-row-click={handleRowCheckChange}
            >
              <bk-table-column
                width='60'
                label=''
                prop=''
                scopedSlots={checkBoxSlot}
              />
              <bk-table-column
                label={t('索引集')}
                scopedSlots={spanSlot}
                prop='collector_config_name'
              />
              <bk-table-column
                label={t('采集路径')}
                prop='paths'
                scopedSlots={spanSlot}
              />
              <bk-table-column
                label={t('采集模式')}
                prop='etl_config'
              />
              <bk-table-column
                label={t('存储集群')}
                prop='storage_cluster_name'
                scopedSlots={spanSlot}
              />
              <bk-table-column
                label={t('存储时长')}
                prop='retention'
              />
            </bk-table>
          </div>
        </div>
      </bk-dialog>
    );
  },
});
