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
import { computed, defineComponent, onMounted, provide, ref, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';

import { ResizeLayout } from 'bkui-vue';
import dayjs from 'dayjs';
import { alertTopN, listAlertTags } from 'monitor-api/modules/alert';
import { incidentDetail, incidentOperationTypes, incidentOperations } from 'monitor-api/modules/incident';
import { LANGUAGE_COOKIE_KEY, docCookies } from 'monitor-common/utils';

import FailureContent from './failure-content/failure-content';
import FailureHeader from './failure-header/failure-header';
import FailureNav from './failure-nav/failure-nav';
import { replaceStr, typeTextMap } from './failure-process/process';
import FailureTags from './failure-tags/failure-tags';
import { useIncidentProvider } from './utils';

import type { AnlyzeField, ICommonItem } from '../../../../fta-solutions/typings/event';
import type { IFilterSearch, IIncident } from './types';
import type { ITagInfoType } from './types';

const isEn = docCookies.getItem(LANGUAGE_COOKIE_KEY) === 'en';
import './failure.scss';
export const commonAlertFieldMap = {
  status: [
    {
      id: isEn ? 'ABNORMAL' : '未恢复',
      name: window.i18n.tc('未恢复'),
    },
    {
      id: isEn ? 'RECOVERED' : '已恢复',
      name: window.i18n.tc('已恢复'),
    },
    {
      id: isEn ? 'CLOSED' : '已失效',
      name: window.i18n.tc('已失效'),
    },
  ],
  severity: [
    {
      id: isEn ? 1 : '致命',
      name: window.i18n.tc('致命'),
    },
    {
      id: isEn ? 2 : '预警',
      name: window.i18n.tc('预警'),
    },
    {
      id: isEn ? 3 : '提醒',
      name: window.i18n.tc('提醒'),
    },
  ],
};
export default defineComponent({
  props: {
    id: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    useIncidentProvider(computed(() => props.id));
    const operations = ref([]);
    const bkzIds = ref([]);
    const { t } = useI18n();
    const incidentDetailData = ref<IIncident>({});
    const valueMap = ref<Record<Partial<AnlyzeField>, ICommonItem[]>>({});
    const analyzeTagList = ref([]);
    const tagInfo = ref<ITagInfoType>({});
    const currentNode = ref([] as string[]);
    const filterSearch = ref<IFilterSearch>({});
    const alertAggregateData = ref([]);
    const operationsLoading = ref(false);
    const scrollTopNum = ref(0);
    const operationTypeMap = ref({});
    const playLoading = ref(false);
    const operationTypes = ref([]);
    const refContent = ref<HTMLDivElement>();
    const failureNavRef = ref<HTMLDivElement>();
    const topoNodeId = ref<string>();
    provide('playLoading', playLoading);
    provide('bkzIds', bkzIds);
    provide('incidentDetail', incidentDetailData);
    provide('valueMap', valueMap);
    provide('operationsList', operations);
    provide('operationsLoading', operationsLoading);
    provide('operationTypeMap', operationTypeMap);
    /**
     * @description: 获取告警分析TopN数据
     * @param {*}
     * @return {*}
     */
    const handleGetSearchTopNList = async () => {
      await handleGetAlertTagList();
      const tagList = analyzeTagList.value || [];
      const allAnlyzeFieldList = [
        'alert_name',
        'metric',
        'duration',
        'ip',
        'bk_cloud_id',
        'strategy_id',
        'strategy_name',
        'assignee',
        'bk_service_instance_id',
        'appointee',
        'labels',
        'plugin_id',
        'ipv6',
      ];
      const allFieldList = bkzIds.value.length > 1 ? ['bk_biz_id', ...allAnlyzeFieldList] : allAnlyzeFieldList;
      const topNFieldList = ['alert_name', 'metric', 'bk_biz_id', 'duration', 'ip', 'ipv6', 'bk_cloud_id'];
      const setTopnDataFn = async (fieldList, count) => {
        valueMap.value = {};
        const list = [];
        (fieldList || []).forEach(item => {
          valueMap.value[item.field] =
            item.buckets.map(set => {
              if (tagList.some(tag => tag.id === item.field)) {
                return { id: set.id, name: `"${set.name}"` };
              }
              return { id: set.id, name: item.field === 'strategy_id' ? set.id : `"${set.name}"` };
            }) || [];
          if (topNFieldList.includes(item.field)) {
            list.push({
              ...item,
              buckets: (item.buckets || []).map(set => ({
                ...set,
                name: set.name,
                percent: count ? Number((set.count / count).toFixed(4)) : 0,
              })),
            });
          }
        });
        // 特殊添加一个空选项给 通知人 ，注意：仅仅加个 空 值还不够，之后查询之前还要执行一次 replaceSpecialCondition
        // 去替换这里添加的 空值 ，使之最后替换成这样 'NOT 通知人 : *'
        if (valueMap.value.assignee) {
          valueMap.value.assignee.unshift({
            id: '""',
            name: t('- 空 -'),
          });
        }
        if (tagList?.length) {
          valueMap.value.tags = tagList.map(item => ({ id: item.name, name: item.name }));
        }
        const mergeFieldMap = commonAlertFieldMap;
        valueMap.value = { ...valueMap.value, ...mergeFieldMap };
      };

      const topNParams = {
        query_string: '',
        bk_biz_ids: bkzIds.value || [],
        conditions: [],
        end_time: dayjs().unix(),
        start_time: incidentDetailData.value?.begin_time,
        status: [],
        fields: [...allFieldList, ...(tagList || []).map(item => item.id)],
        size: 10,
      };
      let fieldList = [];
      let count = 0;
      const { fields, doc_count } = await alertTopN(
        {
          ...topNParams,
          fields: [...allFieldList],
        },
        { needCancel: true }
      ).catch(() => ({ doc_count: 0, fields: [] }));
      fieldList = fields;
      count = doc_count;
      await alertTopN(
        {
          ...topNParams,
          fields: [...(tagList || []).map(item => item.id)].slice(0, 20),
        },
        { needCancel: true }
      )
        .then(({ fields, doc_count }) => {
          fieldList = [...fieldList, ...fields];
          count = doc_count;
          setTopnDataFn(fieldList, count);
        })
        .catch(err => console.error(err));
    };
    /**
     * @description: 获取告警分析告警tag列表数据
     * @param {*}
     * @return {*}
     */
    const handleGetAlertTagList = async () => {
      const list = await listAlertTags({
        query_string: '',
        bk_biz_ids: bkzIds.value || [],
        conditions: [],
        end_time: dayjs().unix(),
        start_time: incidentDetailData.value?.begin_time,
        status: [],
      }).catch(() => []);
      analyzeTagList.value = list;
    };
    const getIncidentOperationTypes = () => {
      incidentOperationTypes({
        incident_id: incidentDetailData.value?.incident_id,
      })
        .then(res => {
          res.forEach(item => {
            item.id = item.operation_class;
            item.name = item.operation_class_alias;
            item.operation_types.forEach(type => {
              type.id = type.operation_type;
              type.name = type.operation_type_alias;
              operationTypeMap.value[type.id] = type.name;
            });
            const isAddLineIndex = item.operation_types.findIndex(type => type.id.startsWith('alert'));
            isAddLineIndex > 0 && (item.operation_types[isAddLineIndex - 1].isAddLine = true);
          });
          operationTypes.value = res;
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {});
    };
    /** 获取故障流转列表 */
    const getIncidentOperations = () => {
      operationsLoading.value = true;
      incidentOperations({
        incident_id: incidentDetailData.value?.incident_id,
      })
        .then(res => {
          res.forEach(item => {
            const { operation_type, extra_info } = item;
            item.str = replaceStr(typeTextMap[operation_type], extra_info);
          });
          operations.value = res;
          operationsLoading.value = false;
        })
        .catch(err => {
          console.log(err);
          operationsLoading.value = false;
        });
    };
    /** 获取故障详情 */
    const getIncidentDetail = () => {
      incidentDetail({
        id: props.id,
      })
        .then(res => {
          incidentDetailData.value = res;
          bkzIds.value = incidentDetailData.value?.current_snapshot?.bk_biz_ids?.map(item => item.bk_biz_id) || [];
          getIncidentOperations();
          getIncidentOperationTypes();
          handleGetSearchTopNList();
        })
        .catch(err => {
          console.log(err);
        });
    };
    const handleChooseTag = (tag: ITagInfoType, isCheck: boolean) => {
      tagInfo.value = Object.assign({ isCheck }, tag);
    };
    const treeDataList = computed(() => {
      return alertAggregateData.value;
    });
    onMounted(() => {
      getIncidentDetail();
    });
    const nodeClick = item => {
      currentNode.value = [];
      nextTick(() => {
        currentNode.value = item.related_entities || item;
      });
    };
    const filterSearchHandle = data => {
      filterSearch.value = data;
    };

    const nodeExpand = data => {
      alertAggregateData.value = data;
    };
    const treeScroll = scrollTop => {
      scrollTopNum.value = scrollTop;
    };
    const refresh = () => {
      getIncidentOperations();
      failureNavRef.value.handleRefNavRefresh();
    };
    const chooseOperation = (id, data) => {
      refContent.value.goFailureTiming(id, data);
    };
    const handleChangeSelectNode = (nodeId: string) => {
      topoNodeId.value = nodeId;
    };
    const handleChangeSpace = (space: string[]) => {
      bkzIds.value = space;
    };
    const changeTab = () => {
      refContent.value?.handleChangeActive('FailureView');
    };
    return {
      incidentDetailData,
      getIncidentDetail,
      handleChooseTag,
      tagInfo,
      nodeClick,
      valueMap,
      currentNode,
      filterSearch,
      filterSearchHandle,
      nodeExpand,
      alertAggregateData,
      treeDataList,
      treeScroll,
      scrollTopNum,
      refresh,
      chooseOperation,
      refContent,
      failureNavRef,
      handleChangeSpace,
      handleChangeSelectNode,
      topoNodeId,
      changeTab,
    };
  },
  render() {
    return (
      <div
        class='failure-wrapper'
        tabindex='0'
      >
        <FailureHeader onEditSuccess={this.getIncidentDetail} />
        <FailureTags
          onChooseNode={this.nodeClick}
          onChooseTag={this.handleChooseTag}
        />
        <ResizeLayout
          class='failure-content-layout'
          v-slots={{
            aside: () => (
              <FailureNav
                ref='failureNavRef'
                tagInfo={this.tagInfo}
                topoNodeId={this.topoNodeId}
                onChangeSpace={this.handleChangeSpace}
                onChangeTab={this.changeTab}
                onChooseOperation={this.chooseOperation}
                onFilterSearch={this.filterSearchHandle}
                onNodeClick={this.nodeClick}
                onNodeExpand={this.nodeExpand}
                onTreeScroll={this.treeScroll}
              />
            ),
            main: () => (
              <FailureContent
                ref='refContent'
                alertAggregateData={this.treeDataList}
                currentNode={this.currentNode}
                filterSearch={this.filterSearch}
                incidentDetail={this.incidentDetailData}
                scrollTop={this.scrollTopNum}
                onChangeSelectNode={this.handleChangeSelectNode}
                onRefresh={this.refresh}
              />
            ),
          }}
          auto-minimize={400}
          border={false}
          initial-divide={500}
          max={850}
          collapsible
        />
      </div>
    );
  },
});
