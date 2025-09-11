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
import {
  computed,
  defineComponent,
  ref,
  nextTick,
  watch,
  onMounted,
  onBeforeUnmount,
} from "vue";
import ClusteringLoader from "@/skeleton/clustering-loader.vue";
import useStore from "@/hooks/use-store";
import useFieldNameHook from "@/hooks/use-field-name";
import { useRoute, useRouter } from "vue-router/composables";
import $http from "@/api";
import { RetrieveUrlResolver } from "@/store/url-resolver";
import TopOperation from "./top-operation";
import QuickOpenCluster from "./quick-open-cluster";
import ClusterStartFail from "./cluster-start-fail";
import { type IResponseData } from "@/services/type";
import { type ClusteringConfigStatus } from "@/services/retrieve";
import EmptyCluster from "./empty-cluster";
import LogTable from "./log-table";

import "./index.scss";

export default defineComponent({
  name: "LogClustering",
  components: {
    ClusteringLoader,
    QuickOpenCluster,
    ClusterStartFail,
    EmptyCluster,
    LogTable,
  },
  setup(props) {
    let statusTimer: NodeJS.Timeout | null;
    const loadingWidthList = {
      global: [""],
      notCompared: [150, 90, 90, ""],
      compared: [150, 90, 90, 100, 100, ""],
    };

    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const topOperationRef = ref<any>(null);
    const logTableRef = ref<any>(null);
    const stepRef = ref<any>(null);
    const isFieldInit = ref(false);
    const isClusterActive = ref(true);
    const isShowClusterStep = ref(true);
    const clusterStepData = ref({} as ClusteringConfigStatus);
    const clusterStepDataLoading = ref(false);
    const isInitPage = ref(true); // 是否是第一次进入数据指纹
    const fingerOperateData = ref({
      patternSize: 0, // slider当前值
      sliderMaxVal: 0, // pattern最大值
      comparedList: [], // 同比List
      patternList: [], // pattern敏感度List
      isShowCustomize: true, // 是否显示自定义
      dimensionList: [], // 维度字段列表
      selectGroupList: [], // 选中的字段分组列表
      yearSwitch: false, // 同比开关
      yearOnYearHour: 0, // 同比的值
      groupList: [] as {
        id: string;
        name: string;
      }[], // 所有的字段分组列表
      alarmObj: {}, // 是否需要告警对象
    });
    const requestData = ref({
      // 数据请求
      pattern_level: "05",
      year_on_year_hour: 0,
      show_new_pattern: false,
      group_by: [],
      size: 10000,
      remark_config: "all",
      owner_config: "all",
      owners: [],
    });

    const indexFieldInfo = computed(() => store.state.indexFieldInfo);
    const indexSetFieldConfig = computed(() => store.state.indexSetFieldConfig);
    const totalFields = computed(
      () => (indexFieldInfo.value.fields || []) as Array<any>
    );
    const globalLoading = computed(
      () => indexFieldInfo.value.is_loading || isFieldInit.value
    );
    const clusteringConfig = computed(
      () => indexSetFieldConfig.value.clustering_config
    );
    const clusterSwitch = computed(
      () => clusteringConfig.value?.is_active || false
    );
    // 无字段提取或者聚类开关没开时直接不显示聚类nav和table，来源如果是数据平台并且日志聚类开关有打开则进入text判断，有text则提示去开启日志聚类, 无则显示跳转计算平台
    const exhibitAll = computed(() =>
      totalFields.value.some((el) => el.field_type === "text")
    );
    const isShowTopNav = computed(
      () => exhibitAll.value && clusterSwitch.value && !isShowClusterStep.value
    );
    const indexSetId = computed(() =>
      window.__IS_MONITOR_COMPONENT__
        ? (route.query.indexId as string)
        : route.params.indexId
    );
    const clusterParams = computed(() => store.state.clusterParams);
    const collectorConfigId = computed(
      () => indexSetFieldConfig.value.clean_config.extra?.collector_config_id
    );

    watch(indexSetId, () => {
      isShowClusterStep.value = true;
      confirmClusterStepStatus();
    });

    watch(isShowClusterStep, () => {
      store.commit('updateState', { 'storeIsShowClusterStep': isShowClusterStep.value});
    });
    const stopPolling = () => {
      // 清除定时器
      if (statusTimer) {
        clearInterval(statusTimer);
        statusTimer = null;
      }
    };

    const startPolling = (pollingTime = 10000) => {
      stopPolling();
      statusTimer = setInterval(clusterPolling, pollingTime);
    };

    const fieldsChangeQuery = async () => {
      if (totalFields.value.length && !isFieldInit.value) {
        isFieldInit.value = true;
        startPolling();
        await clusterPolling();
        isFieldInit.value = false;
      }
    };

    const getClusterConfigStatus = () => {
      return $http.request(
        "retrieve/getClusteringConfigStatus",
        {
          params: {
            index_set_id: indexSetId.value,
          },
        },
        {
          catchIsShowMessage: false,
        }
      ) as Promise<IResponseData<ClusteringConfigStatus>>;
    };

    // 获取分组状态
    const getInitGroupFields = async () => {
      try {
        if (clusterSwitch.value) {
          const params = { index_set_id: indexSetId.value };
          const data = { collector_config_id: collectorConfigId.value };
          const res = await $http.request("/logClustering/getConfig", {
            params,
            data,
          });
          return res.data.group_fields;
        }
        return [];
      } catch (err) {
        console.warn(err);
        return [];
      }
    };

    const initTableOperator = async () => {
      const {
        log_clustering_level_year_on_year: yearOnYearList,
        log_clustering_level: clusterLevel,
      } = store.state.globals.globalsData;
      let patternLevel;
      if (clusterLevel && clusterLevel.length > 0) {
        // 判断奇偶数来取pattern中间值
        if (clusterLevel.length % 2 === 1) {
          patternLevel = (clusterLevel.length + 1) / 2;
        } else {
          patternLevel = clusterLevel.length / 2;
        }
      }
      const patternList = clusterLevel.sort((a, b) => Number(b) - Number(a));
      // clusterLevel[patternLevel - 1]
      const queryRequestData = {
        pattern_level: "05",
        group_by: [],
        remark_config: "all",
        owner_config: "all",
        owners: [],
        year_on_year_hour: 0,
      };
      // 通过路由返回的值 初始化数据指纹的操作参数 url是否有缓存的值
      if (isInitPage.value && !!clusterParams.value) {
        const paramData = structuredClone(clusterParams.value);
        const findIndex = clusterLevel.findIndex(
          (item) => item === String(paramData.pattern_level)
        );
        if (findIndex >= 0) patternLevel = findIndex + 1;
        Object.assign(queryRequestData, paramData, {
          pattern_level: paramData.pattern_level
            ? paramData.pattern_level
            : clusterLevel[patternLevel - 1],
        });
      }
      const { year_on_year_hour: yearOnYearHour } = queryRequestData;
      Object.assign(fingerOperateData.value, {
        patternSize: patternLevel - 1,
        sliderMaxVal: clusterLevel.length - 1,
        patternList,
        comparedList: yearOnYearList.filter((item) => item.id !== 0),
        yearOnYearHour: yearOnYearHour > 0 ? yearOnYearHour : 1,
        yearSwitch: yearOnYearHour > 0,
        dimensionList: [],
        selectGroupList: queryRequestData.group_by || [], // 未请求维度时 默认是所有字段的分组
      });
      // 这里判断是否有保存过所有人都显示一样的分组 如果有则直接显示相应的分组
      const groupFields = await getInitGroupFields();
      if (groupFields?.length) {
        const selectGroupList = fingerOperateData.value.selectGroupList.filter(
          (item) => !groupFields.includes(item)
        );
        // 如果初始化时有默认维度的字段 将维度和分组分开来处理
        Object.assign(queryRequestData, {
          group_by: [...groupFields, ...selectGroupList],
        });
        Object.assign(fingerOperateData.value, {
          dimensionList: groupFields,
          selectGroupList,
        });
      }
      Object.assign(requestData.value, queryRequestData);
      store.commit('updateState', { 'clusterParams': requestData.value});
      setRouteParams();
      isInitPage.value = false;
    };

    const clusterPolling = async () => {
      const isActiveCluster = await confirmClusterStepStatus();
      if (isActiveCluster) {
        filterGroupList();
        await initTableOperator(); // 初始化分组下拉列表
        stopPolling();
      }
    };

    // 数据指纹操作
    const handleFingerOperate = (
      operateType: string,
      val: any = {},
      isQuery = false
    ) => {
      switch (operateType) {
        case "requestData": // 数据指纹的请求参数
          Object.assign(requestData.value, val);
          // 数据指纹对请求参数修改过的操作将数据回填到url上
          store.commit('updateState', { 'clusterParams': requestData.value});
          setRouteParams();
          break;
        case "fingerOperateData": // 数据指纹操作的参数
          Object.assign(fingerOperateData.value, val);
          break;
        default:
          break;
      }
      if (isQuery) {
        logTableRef.value.refreshTable();
      }
    };

    // 初始化分组select数组
    const filterGroupList = () => {
      const { getConcatenatedFieldName } = useFieldNameHook({ store });
      const filterList = totalFields.value
        .filter((el) => el.es_doc_values && !/^__dist_/.test(el.field_name)) // 过滤__dist字段
        .map((item) => {
          return getConcatenatedFieldName(item);
        });
      fingerOperateData.value.groupList = filterList;
    };

    const setRouteParams = () => {
      const query = { ...route.query };
      const resolver = new RetrieveUrlResolver({
        clusterParams: store.state.clusterParams,
      });
      Object.assign(query, resolver.resolveParamsToUrl());
      router.replace({ query });
    };

    const confirmClusterStepStatus = async () => {
      if (!isShowClusterStep.value) {
        return;
      }
      try {
        clusterStepDataLoading.value = true;
        const res = await getClusterConfigStatus();
        if (res.code === 0) {
          // 未完成，展示step步骤
          if (!res.data.access_finished) clusterStepData.value = res.data;
          isShowClusterStep.value = !res.data.access_finished;
          return res.data.access_finished;
        }
      } catch {
        // 报错就证明没开日志聚类
        isShowClusterStep.value = false;
        stopPolling();
        return false;
      } finally {
        // 如果有报错信息，也直接停止轮询
        nextTick(() => {
          // 记得放开注释
          if (stepRef.value?.errorMessage) {
            stopPolling();
          }
        });
        clusterStepDataLoading.value = false;
      }
    };

    const handleCloseGroupTag = () => {
      Object.assign(fingerOperateData.value, { selectGroupList: [] });
      handleFingerOperate(
        "requestData",
        { group_by: fingerOperateData.value.dimensionList },
        true
      );
    };
    const handleCloseYearTag = () => {
      Object.assign(fingerOperateData.value, { yearSwitch: false });
      handleFingerOperate("requestData", { year_on_year_hour: 0 }, true);
    };

    const handleClusterCreate = () => {
      isShowClusterStep.value = true;
      startPolling();
      clusterPolling();
    };

    const handleOpenClusterConfig = () => {
      topOperationRef.value.openClusterConfig();
    };

    // 特殊情况，watch必须放这里
    watch(
      totalFields,
      (newVal, oldVal) => {
        if (newVal === oldVal) {
          return;
        }
        // 无字段提取或者聚类开关没开时直接不显示聚类nav和table，来源如果是数据平台并且日志聚类大开关有打开则进入text判断，有text则提示去开启日志聚类 无则显示跳转计算平台
        fieldsChangeQuery();
      },
      {
        immediate: true,
        deep: true,
      }
    );

    onMounted(async () => {
      if (!isClusterActive.value) {
        isClusterActive.value = true;
        await confirmClusterStepStatus();
        // if (isClickSearch.value && !isInitPage.value) {
        //   requestFinger();
        // }
        if (!isInitPage.value) {
          store.commit('updateState', { 'clusterParams': requestData.value});
          setRouteParams();
        }
      }
    });

    onBeforeUnmount(() => {
      if (isClusterActive.value) {
        isClusterActive.value = false;
        store.commit('updateState', { 'clusterParams': null});
        setRouteParams();
        stopPolling(); // 停止状态轮询
      }
    });

    return () => (
      <div class="log-cluster-table-container-main">
        {globalLoading.value ? (
          <clustering-loader width-list={loadingWidthList.global} is-loading />
        ) : (
          <div class="log-cluster-table-container">
            {isShowTopNav.value && (
              // 顶部工具栏
              <TopOperation
                ref={topOperationRef}
                indexId={indexSetId.value}
                isShowClusterStep={isShowClusterStep.value}
                cluster-switch={clusterSwitch.value}
                is-cluster-active={isClusterActive.value}
                finger-operate-data={fingerOperateData.value}
                request-data={requestData.value}
                total-fields={totalFields.value}
                on-handle-finger-operate={handleFingerOperate}
                on-close-group-tag={handleCloseGroupTag}
                on-close-year-tag={handleCloseYearTag}
              />
            )}
            {exhibitAll.value ? (
              (() => {
                if (isShowClusterStep.value) {
                  // 聚类启动失败
                  return (
                    <cluster-start-fail
                      ref={stepRef}
                      cluster-step-data={clusterStepData.value}
                    />
                  );
                } else if (!clusterSwitch.value) {
                  // 快速开启日志聚类
                  return (
                    <QuickOpenCluster
                      indexSetId={indexSetId.value}
                      totalFields={totalFields.value}
                      on-create-cluster={handleClusterCreate}
                    />
                  );
                } else {
                  return (
                    <log-table
                      ref={logTableRef}
                      indexId={indexSetId.value}
                      isShowClusterStep={isShowClusterStep.value}
                      cluster-switch={clusterSwitch.value}
                      is-cluster-active={isClusterActive.value}
                      finger-operate-data={fingerOperateData.value}
                      request-data={requestData.value}
                      total-fields={totalFields.value}
                      on-open-cluster-config={handleOpenClusterConfig}
                    />
                  );
                }
              })()
            ) : (
              // 无text的空聚类
              <empty-cluster clusterSwitch={clusterSwitch.value} />
            )}
          </div>
        )}
      </div>
    );
  },
});
