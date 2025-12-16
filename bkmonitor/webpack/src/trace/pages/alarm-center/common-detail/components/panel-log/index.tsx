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
import { type PropType, computed, defineComponent, watch } from 'vue';
import { shallowRef } from 'vue';

import { Button, Message } from 'bkui-vue';
import { request } from 'monitor-api/base';
import { copyText, random } from 'monitor-common/utils';
import { type IWhereItem, EMode } from 'trace/components/retrieval-filter/typing';
import { useI18n } from 'vue-i18n';

import RetrievalFilter from '../../../../../components/retrieval-filter/retrieval-filter';
import { useAlarmLog } from '../../../composables/use-alarm-log';
import IndexSetSelector from './index-set-selector/index-set-selector';
import LogTableNew from './log-table/log-table-new';

import type { AlarmDetail } from '../../../typings/detail';
export const getLogIndexSetSearch = request(
  'POST' as any,
  'apm_log_forward/bklog/api/v1/search/index_set/{pk}/search/'
);
export const getLogFieldsData = request('GET' as any, 'apm_log_forward/bklog/api/v1/search/index_set/{pk}/fields/');

export const updateUserFiledTableConfig = request(
  'POST' as any,
  'apm_log_forward/bklog/api/v1/search/index_set/user_custom_config/'
);

import TableFieldSetting from './log-table/table-field-setting';
import { type TClickMenuOpt, EClickMenuType } from './log-table/typing';
import { formatHierarchy } from './log-table/utils/fields';

import type { TdPrimaryTableProps } from '@blueking/tdesign-ui';

import './index.scss';

export default defineComponent({
  name: 'PanelLog',
  props: {
    detail: {
      type: Object as PropType<AlarmDetail>,
      default: () => null,
    },
    headerAffixedTop: {
      type: Object as PropType<TdPrimaryTableProps['headerAffixedTop']>,
      default: () => null,
    },
  },
  setup(props) {
    const { t } = useI18n();
    const { getIndexSetList } = useAlarmLog(props.detail);
    const selectLoading = shallowRef(false);
    /** 索引集列表 */
    const indexSetList = shallowRef([]);
    const relatedBkBizId = shallowRef(-1);
    /** 选中的索引集ID */
    const selectIndexSet = shallowRef<number | string>('');
    const keyword = shallowRef('');
    const filterMode = shallowRef<EMode>(EMode.ui);
    const where = shallowRef<IWhereItem[]>([]);
    const tableRefreshKey = shallowRef(null);

    const tableColumnsSetting = shallowRef([]);

    watch(
      () => props.detail,
      val => {
        if (val) {
          init();
        }
      },
      { immediate: true }
    );

    async function init() {
      selectLoading.value = true;
      const data = await getIndexSetList();
      relatedBkBizId.value = data?.relatedBkBizId || -1;
      indexSetList.value = data?.relatedIndexSetList || [];
      selectIndexSet.value = indexSetList.value[0]?.index_set_id || '';
      selectLoading.value = false;
      tableRefreshKey.value = random(6);
    }

    /**
     * 获取日志列表
     * @param params
     */
    async function getTableData(
      params = {
        size: 50,
        offset: 0,
        sortList: [],
      }
    ) {
      // const data = await updateTableData({
      //   index_set_id: selectIndexSet.value,
      //   keyword: keyword.value,
      //   limit: params.limit,
      //   offset: params.offset,
      // });
      const data = await getLogIndexSetSearch(selectIndexSet.value, {
        bk_biz_id: props.detail?.bk_biz_id || window.bk_biz_id,
        size: params.size,
        start_time: props.detail?.begin_time,
        end_time: props.detail.latest_time,
        addition: where.value.map(item => ({
          field: item.key,
          operator: item.method,
          value: item.value,
        })),
        begin: params.offset,
        ip_chooser: {},
        host_scopes: {},
        interval: 'auto',
        search_mode: filterMode.value === EMode.ui ? 'ui' : 'sql',
        sort_list: params?.sortList || [],
        keyword: keyword.value,
      })
        .then(res => {
          return res;
        })
        .catch(() => null);
      return data;
    }

    const fieldsData = shallowRef(null);
    const getFieldsData = async () => {
      if (fieldsData.value) {
        return fieldsData.value;
      }
      const data = await getLogFieldsData(selectIndexSet.value, {
        is_realtime: 'True',
        start_time: props.detail?.begin_time,
        end_time: props.detail.latest_time,
      })
        .then(res => res)
        .catch(() => null);
      fieldsData.value = data;
      tableColumnsSetting.value = formatHierarchy(fieldsData.value?.fields || []).map(item => {
        return {
          id: item.field_name,
          name: item.query_alias || item.field_name,
          type: item.field_type,
        };
      });
      /** 优先使用user_custom_config配置，如果没有再使用display_fields配置 */
      displayColumnFields.value = data?.user_custom_config?.displayFields || data?.display_fields || [];
      return data;
    };

    /** 需要展示的表格字段 */
    const displayColumnFields = shallowRef([]);

    const retrievalFields = computed(() => {
      const excludesFields = ['__ext', '__module__', ' __set__', '__ipv6__'];
      const filterFn = field => field.field_type !== '__virtual__' && !excludesFields.includes(field.field_name);
      const tempFields = fieldsData.value?.fields?.filter(filterFn) || [];
      return [
        {
          alias: t('全文'),
          name: '*',
          isEnableOptions: false,
          type: 'all',
          methods: [
            {
              alias: t('包含'),
              value: 'contains match phrase',
              placeholder: t('请输入搜索内容'),
            },
            {
              alias: t('不包含'),
              value: 'not contains match phrase',
              placeholder: t('请输入搜索内容'),
            },
          ],
        },
        ...tempFields.map(item => ({
          alias: item.query_alias || item.field_name,
          name: item.field_name,
          isEnableOptions: true,
          type: item.field_type,
          methods: item?.field_operator?.map(o => ({
            alias: o.label,
            value: o.operator,
            placeholder: o.placeholder,
          })),
        })),
      ];
    });

    const handleDisplayColumnFieldsChange = (val: string[]) => {
      updateUserFiledTableConfig({
        index_set_config: {
          displayFields: val,
          fieldsWidth: {},
          filterAddition: [],
          filterSetting: [],
          fixedFilterAddition: false,
          sortList: [],
        },
        index_set_id: String(selectIndexSet.value),
        index_set_type: 'single',
      }).then(() => {
        fieldsData.value = null;
        tableRefreshKey.value = random(6);
      });
    };

    const customColumns = shallowRef([
      {
        width: '32px',
        minWidth: '32px',
        fixed: 'right',
        align: 'center',
        resizable: false,
        className: ({ type }) => {
          if (type === 'th') {
            return 'col-th-field-setting';
          } else {
            return 'col-td-field-setting';
          }
        },
        thClassName: '__table-custom-setting-col__',
        colKey: '__col_setting__',
        title: () => {
          return (
            <TableFieldSetting
              class='table-field-setting'
              sourceList={tableColumnsSetting.value}
              targetList={displayColumnFields.value}
              onConfirm={handleDisplayColumnFieldsChange}
            />
          );
        },
        cell: () => undefined,
      },
    ]);

    /**
     * 切换索引集
     * @param indexSetId 索引集ID
     */
    function handleChangeIndexSet(indexSetId: number | string) {
      selectIndexSet.value = indexSetId;
      tableRefreshKey.value = random(8);
    }

    /**
     * 跳转日志搜索页
     */
    function handleGoLog() {
      const url = `${window.bk_log_search_url}#/retrieve/${selectIndexSet.value}?bizId=${props.detail?.bk_biz_id || (relatedBkBizId.value === -1 ? window.cc_biz_id : relatedBkBizId.value)}`;
      window.open(url, '_blank');
    }

    /**
     * 日志搜索
     */
    function handleSearch() {
      tableRefreshKey.value = random(8);
    }

    /**
     * 日志搜索关键词改变
     * @param queryString 关键词
     */
    function handleQueryStringChange(queryString: string) {
      keyword.value = queryString;
    }

    /**
     * 日志搜索模式改变
     * @param mode 模式
     */
    function handleModeChange(mode: EMode) {
      filterMode.value = mode;
      if (mode === EMode.ui) {
        keyword.value = '';
      }
      handleSearch();
    }

    const handleWhereChange = (val: IWhereItem[]) => {
      where.value = val;
      handleSearch();
    };

    const handleClickMenu = (opt: TClickMenuOpt) => {
      if (opt.type === EClickMenuType.Link) {
        return;
      }
      if (opt.type === EClickMenuType.Copy) {
        copyText(opt.value, msg => {
          Message({
            message: msg,
            theme: 'error',
          });
          return;
        });
        Message({
          message: t('复制成功'),
          theme: 'success',
        });
        return;
      }
      let whereItem = null;
      const methodMap = {
        default: {
          [EClickMenuType.Exclude]: '!=',
          [EClickMenuType.Include]: '=',
        },
        boolean: {
          [EClickMenuType.Exclude]: 'is false',
          [EClickMenuType.Include]: 'is true',
        },
        all: {
          [EClickMenuType.Exclude]: 'not contains match phrase',
          [EClickMenuType.Include]: 'contains match phrase',
        },
      };
      for (const item of retrievalFields.value) {
        if (item.name === opt.field.field_name) {
          const method = methodMap[item.type]?.[opt.type] || methodMap.default[opt.type];
          whereItem = {
            key: item.name,
            method,
            value: [opt.value],
            condition: 'and',
          };
          break;
        }
      }
      if (!whereItem) {
        whereItem = {
          key: '*',
          method: methodMap.all[opt.type],
          value: [opt.value],
          condition: 'and',
        };
      }
      where.value = [...where.value, whereItem];
      tableRefreshKey.value = random(8);
    };

    const handleRemoveField = (fieldName: string) => {
      displayColumnFields.value = displayColumnFields.value.filter(item => item !== fieldName);
    };

    const handleAddField = (fieldName: string) => {
      if (displayColumnFields.value.includes(fieldName)) {
        return;
      }
      displayColumnFields.value = [...displayColumnFields.value, fieldName];
    };

    return {
      indexSetList,
      tableRefreshKey,
      selectIndexSet,
      selectLoading,
      keyword,
      filterMode,
      customColumns,
      displayColumnFields,
      retrievalFields,
      fieldsData,
      where,
      handleChangeIndexSet,
      t,
      handleGoLog,
      handleSearch,
      handleQueryStringChange,
      handleModeChange,
      getTableData,
      getFieldsData,
      handleWhereChange,
      handleClickMenu,
      handleRemoveField,
      handleAddField,
    };
  },
  render() {
    return (
      <div class='alarm-center-detail-panel-alarm-log'>
        <div class='panel-log-header'>
          {this.selectLoading ? (
            <div class='skeleton-element select-loading' />
          ) : (
            <IndexSetSelector
              indexSetList={this.indexSetList}
              value={this.selectIndexSet}
              onChange={this.handleChangeIndexSet}
            />
          )}
          <Button
            class='ml-16'
            theme='primary'
            text
            onClick={this.handleGoLog}
          >
            <span>{this.t('更多日志')}</span>
            <span class='icon-monitor icon-fenxiang ml-5' />
          </Button>
        </div>
        <div class='panel-log-filter'>
          <RetrievalFilter
            fields={this.retrievalFields}
            filterMode={this.filterMode}
            queryString={this.keyword}
            where={this.where}
            zIndex={4000}
            onModeChange={this.handleModeChange}
            onQueryStringChange={this.handleQueryStringChange}
            onSearch={this.handleSearch}
            onWhereChange={this.handleWhereChange}
          />
        </div>
        <LogTableNew
          customColumns={this.customColumns}
          displayFields={this.displayColumnFields}
          getFieldsData={this.getFieldsData}
          getTableData={this.getTableData}
          headerAffixedTop={this.headerAffixedTop}
          refreshKey={this.tableRefreshKey}
          onAddField={this.handleAddField}
          onClickMenu={this.handleClickMenu}
          onRemoveField={this.handleRemoveField}
        />
      </div>
    );
  },
});
