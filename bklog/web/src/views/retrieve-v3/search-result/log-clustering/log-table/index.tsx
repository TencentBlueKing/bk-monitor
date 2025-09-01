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
  watch,
  onMounted,
  onBeforeUnmount,
} from "vue";
import { cloneDeep } from "lodash-es";
import useStore from "@/hooks/use-store";
import useLocale from "@/hooks/use-locale";
import MainHeader from "./main-header";
import $http from "@/api";
import ClusteringLoader from "@/skeleton/clustering-loader.vue";
import AiAssitant from "@/global/ai-assitant.tsx";
import ContentTable from "./content-table";
import { type LogPattern } from "@/services/log-clustering";
import { type IResponseData } from "@/services/type";

import "./index.scss";

export interface TableInfo {
  group: string[];
  dataList: LogPattern[];
}

export default defineComponent({
  name: "LogTable",
  components: {
    MainHeader,
    ClusteringLoader,
    ContentTable,
    AiAssitant,
  },
  props: {
    retrieveParams: {
      type: Object,
      required: true,
    },
    clusterSwitch: {
      type: Boolean,
      default: false,
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    requestData: {
      type: Object,
      require: true,
    },
    indexId: {
      type: String,
      require: true,
    },
  },
  setup(props, { expose, emit }) {
    const store = useStore();
    const { t } = useLocale();

    const initFilterSortMap = () => ({
      filter: {
        owners: [],
        remark: [],
      },
      sort: {
        count: "",
        percentage: "",
        year_on_year_count: "",
        year_on_year_percentage: "",
      },
    });

    const logTableRef = ref<HTMLElement>();
    const tablesRef = ref<any[]>([]);
    const globalScrollbarWraperRef = ref<HTMLElement>();
    const globalScrollbarRef = ref<HTMLElement>();
    const mainHeaderRef = ref<any>();
    const aiAssitantRef = ref<any>(null);
    const tableLoading = ref(false);
    const tablesInfoList = ref<TableInfo[]>([]);
    const widthList = ref<string[]>([]);
    const filterSortMap = ref(initFilterSortMap());
    const displayType = ref("group");

    const showGroupBy = computed(
      () =>
        props.requestData?.group_by.length > 0 && displayType.value === "group"
    );
    const isFlattenMode = computed(
      () =>
        props.requestData?.group_by.length > 0 && displayType.value !== "group"
    );
    const smallLoaderWidthList = computed(() => {
      return props.requestData?.year_on_year_hour > 0
        ? loadingWidthList.compared
        : loadingWidthList.notCompared;
    });

    const tableColumnWidth = computed(() =>
      store.getters.isEnLanguage ? enTableWidth : cnTableWidth
    );

    const loadingWidthList = {
      // loading表头宽度列表
      global: [""],
      notCompared: [150, 90, 90, ""],
      compared: [150, 90, 90, 100, 100, ""],
    };

    const enTableWidth = {
      number: "110",
      percentage: "116",
      year_on_year_count: "171",
      year_on_year_percentage: "171",
    };
    const cnTableWidth = {
      number: "91",
      percentage: "96",
      year_on_year_count: "101",
      year_on_year_percentage: "101",
    };

    let localTotalList: LogPattern[] = [];
    let localTablesInfoList: TableInfo[] = [];

    watch(
      () => props.requestData,
      () => {
        filterSortMap.value = initFilterSortMap();
      },
      {
        deep: true,
      }
    );

    watch(
      () => props.retrieveParams,
      () => {
        refreshTable();
      },
      { deep: true }
    );

    const refreshTable = () => {
      // loading中，或者没有开启数据指纹功能，或当前页面初始化或者切换索引集时不允许起请求
      if (
        tableLoading.value ||
        !props.clusterSwitch ||
        !props.isClusterActive
      ) {
        return;
      }
      const {
        start_time,
        end_time,
        addition,
        size,
        keyword = "*",
        ip_chooser,
        host_scopes,
        interval,
        timezone,
      } = props.retrieveParams;
      tableLoading.value = true;
      (
        $http.request(
          "/logClustering/clusterSearch",
          {
            params: {
              index_set_id: props.indexId,
            },
            data: {
              addition,
              size,
              keyword,
              ip_chooser,
              host_scopes,
              interval,
              timezone,
              start_time,
              end_time,
              ...props.requestData,
            },
          },
          { cancelWhenRouteChange: false }
        ) as Promise<IResponseData<LogPattern[]>>
      ) // 由于回填指纹的数据导致路由变化，故路由变化时不取消请求
        .then((res) => {
          localTotalList = res.data;
          const keyValueSetList: Array<Set<string>> = [];
          props.requestData?.group_by.forEach((_, index) => {
            keyValueSetList[index] = new Set();
          });
          res.data.forEach((item, index) => {
            Object.assign(item, { id: index });
            item.group.forEach((_, index) => {
              keyValueSetList[index].add(item.group[index]);
            });
          });
          const keyValueList = keyValueSetList.map((item) =>
            Array.from(item).sort()
          );
          let valueList: any[] = [];
          keyValueList.forEach((values) => {
            let tmpValueList: any[] = [];
            values.forEach((value) => {
              if (valueList.length) {
                valueList.forEach((existValue) => {
                  const arr = [...existValue, value];
                  tmpValueList.push(arr);
                });
              } else {
                tmpValueList.push([value]);
              }
            });
            valueList = tmpValueList;
          });
          valueList.sort((a, b) => a[0] - b[0]);
          tablesInfoList.value = [];
          valueList.forEach((values: string[]) => {
            const tableInfo: TableInfo = {
              group: values,
              dataList: [],
            };
            res.data.forEach((item) => {
              if (item.group.join(",") === values.join(",")) {
                tableInfo.dataList.push(item);
              }
            });
            if (tableInfo.dataList.length) {
              tablesInfoList.value.push(tableInfo);
            }
          });
          if (!tablesInfoList.value.length) {
            tablesInfoList.value.push({ group: [], dataList: res.data });
          }

          localTablesInfoList = cloneDeep(tablesInfoList.value);
        })
        .finally(() => {
          tableLoading.value = false;
        });
    };

    const handleColumnFilter = (field: string, value: any) => {
      filterSortMap.value.filter[field] = value;
    };

    const handleColumnSort = (field: string, order: string) => {
      Object.keys(filterSortMap.value.sort).forEach((key) => {
        if (key !== field) {
          filterSortMap.value.sort[key] = "";
        }
      });
      filterSortMap.value.sort[field] = order;
    };

    const handleOpenAi = (row: LogPattern, index: number) => {
      aiAssitantRef.value.open(true, {
        space_uid: store.getters.spaceUid,
        index_set_id: store.getters.indexId,
        log_data: row,
        index,
      });
    };

    const handleHeaderResizeColumn = (scrollWidth: number) => {
      globalScrollbarRef.value!.style.width = `${scrollWidth}px`;
      widthList.value = mainHeaderRef.value.getColumnWidthList();
    };

    const handleGlobalScrollbarScroll = (e: Event) => {
      const { scrollLeft } = e.target as HTMLDivElement;
      mainHeaderRef.value.scroll(scrollLeft);
      tablesRef.value.forEach((item) => item?.scroll(scrollLeft));
    };

    const setTableItemRef = (index: number) => (el: HTMLElement | null) => {
      tablesRef.value[index] = el;
    };

    const handleGlobalScroll = (e: any) => {
      e.preventDefault();
      if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        if (
          globalScrollbarWraperRef.value!.scrollWidth ===
          globalScrollbarWraperRef.value!.clientWidth
        ) {
          return;
        }

        if (e.deltaX < 0) {
          globalScrollbarWraperRef.value!.scrollLeft -= 5;
        } else {
          globalScrollbarWraperRef.value!.scrollLeft += 5;
        }
        return;
      }

      if (e.deltaY < 0) {
        logTableRef.value!.scrollTop -= 20;
      } else {
        logTableRef.value!.scrollTop += 20;
      }
    };

    const handleDisplayTypeChange = (value: string) => {
      displayType.value = value;
      if (value === "flatten") {
        tablesInfoList.value = [{ group: [], dataList: localTotalList }];
      } else {
        tablesInfoList.value = localTablesInfoList;
      }
    };

    onMounted(() => {
      refreshTable();
      logTableRef.value!.addEventListener("wheel", handleGlobalScroll, {
        passive: false,
      });
    });

    onBeforeUnmount(() => {
      logTableRef.value!.removeEventListener("wheel", handleGlobalScroll);
    });

    expose({
      refreshTable,
    });
    return () => (
      <div
        class="log-table-main"
        style={{
          height:
            showGroupBy.value || isFlattenMode.value
              ? "calc(100% - 90px)"
              : "calc(100% - 60px)",
        }}
      >
        {props.requestData?.group_by.length > 0 && (
          <bk-radio-group
            class="display-type-main"
            value={displayType.value}
            on-change={handleDisplayTypeChange}
          >
            <bk-radio value="flatten">{t("平铺模式")}</bk-radio>
            <bk-radio value="group">{t("分组模式")}</bk-radio>
          </bk-radio-group>
        )}
        <main-header
          ref={mainHeaderRef}
          requestData={props.requestData}
          tableColumnWidth={tableColumnWidth.value}
          indexId={props.indexId}
          displayMode={displayType.value}
          on-column-filter={handleColumnFilter}
          on-column-sort={handleColumnSort}
          on-resize-column={handleHeaderResizeColumn}
        />
        <div
          ref={logTableRef}
          class="table-list-content"
          style={{ padding: showGroupBy.value ? "0 12px" : "0px" }}
          v-bkloading={{ isLoading: tableLoading.value }}
        >
          {tableLoading.value ? (
            <clustering-loader
              width-list={smallLoaderWidthList.value}
              is-loading
            />
          ) : tablesInfoList.value.length > 0 &&
            tablesInfoList.value.every((item) => item.dataList.length > 0) ? (
            tablesInfoList.value.map((info, index) => (
              <ContentTable
                ref={setTableItemRef(index)}
                tableInfo={info}
                widthList={widthList.value}
                displayMode={displayType.value}
                index={index}
                filterSortMap={filterSortMap.value}
                requestData={props.requestData}
                tableColumnWidth={tableColumnWidth.value}
                indexId={props.indexId}
                on-open-ai={handleOpenAi}
                on-open-cluster-config={() => emit("open-cluster-config")}
              />
            ))
          ) : (
            <bk-exception type="empty" scene="part" style="margin-top: 80px">
              <span>
                {props.retrieveParams.addition.length > 0
                  ? t("搜索结果为空")
                  : t("暂无数据")}
              </span>
            </bk-exception>
          )}
        </div>
        <AiAssitant ref={aiAssitantRef} on-close="handleAiClose" />
        <div
          class="global-scrollbar-wraper"
          ref={globalScrollbarWraperRef}
          on-scroll={handleGlobalScrollbarScroll}
        >
          <div class="global-scrollbar" ref={globalScrollbarRef}></div>
        </div>
      </div>
    );
  },
});
