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
import { computed, defineComponent, onMounted, provide, ref } from 'vue';

import { ResizeLayout } from 'bkui-vue';
import { incidentDetail, incidentOperations, incidentOperationTypes } from 'monitor-api/modules/incident';

import FailureContent from './failure-content/failure-content';
import FailureHeader from './failure-header/failure-header';
import FailureNav from './failure-nav/failure-nav';
import { replaceStr, typeTextMap } from './failure-process/process';
import FailureTags from './failure-tags/failure-tags';
import { type IIncident, type IFilterSearch } from './types';
import { type ITagInfoType } from './types';
import { useIncidentProvider } from './utils';

import './failure.scss';

export default defineComponent({
  props: {
    id: {
      type: String,
      default: '',
    },
  },
  setup(props) {
    useIncidentProvider(computed(() => props.id));
    const tagDomHeight = ref<number>(40);
    const collapseTagHandle = (val: boolean, height: number) => {
      tagDomHeight.value = height;
    };
    const operations = ref([]);
    const incidentDetailData = ref<IIncident>({});
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
    provide('incidentDetail', incidentDetailData);
    provide('operationsList', operations);
    provide('operationsLoading', operationsLoading);
    provide('operationTypeMap', operationTypeMap);
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
          getIncidentOperations();
          getIncidentOperationTypes();
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
      currentNode.value = item.related_entities || item;
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
    return {
      tagDomHeight,
      collapseTagHandle,
      incidentDetailData,
      getIncidentDetail,
      handleChooseTag,
      tagInfo,
      nodeClick,
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
      handleChangeSelectNode,
      topoNodeId,
    };
  },
  render() {
    return (
      <div class='failure-wrapper'>
        <FailureHeader onEditSuccess={this.getIncidentDetail} />
        <FailureTags
          onChooseNode={this.nodeClick}
          onChooseTag={this.handleChooseTag}
          onCollapse={this.collapseTagHandle}
        />
        <ResizeLayout
          style={{ height: `calc(100vh - ${160 + Number(this.tagDomHeight)}px)` }}
          class='failure-content-layout'
          v-slots={{
            aside: () => (
              <FailureNav
                ref='failureNavRef'
                tagInfo={this.tagInfo}
                topoNodeId={this.topoNodeId}
                onChooseOperation={this.chooseOperation}
                onFilterSearch={this.filterSearchHandle}
                onNodeClick={this.nodeClick}
                onNodeExpand={this.nodeExpand}
                onTreeScroll={this.treeScroll}
              ></FailureNav>
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
              ></FailureContent>
            ),
          }}
          auto-minimize={400}
          border={false}
          initial-divide={500}
          max={850}
          collapsible
        ></ResizeLayout>
      </div>
    );
  },
});
