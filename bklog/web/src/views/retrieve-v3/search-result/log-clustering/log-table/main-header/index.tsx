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
  onBeforeUnmount,
  onMounted,
  ref,
  watch,
} from "vue";

import useLocale from "@/hooks/use-locale";

import FilterOperate from "./filter-operate";
// import useStore from "@/hooks/use-store";
import HeadColumn from "./head-column";
import SortOperate from "./sort-operate";
import $http from "@/api";

import "./index.scss";

export default defineComponent({
  name: "MainHeader",
  components: {
    SortOperate,
    FilterOperate,
    HeadColumn,
  },
  props: {
    tableColumnWidth: {
      type: Object,
      default: () => ({}),
    },
    requestData: {
      type: Object,
      require: true,
    },
    indexId: {
      type: String,
      require: true,
    },
    displayMode: {
      type: String,
      default: "group",
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();

    const headRowRef = ref<HTMLBaseElement>();
    const renderKey = ref(0);
    const tableHeaderWraperRef = ref<HTMLBaseElement>();
    const ownerList = ref([]);
    const sortColumnRefs = {
      count: ref(null),
      percentage: ref(null),
      year_on_year_count: ref(null),
      year_on_year_percentage: ref(null),
      owners: ref(null),
      remark: ref(null),
    };

    const showYOY = computed(() => props.requestData?.year_on_year_hour >= 1);
    const showGroupBy = computed(
      () =>
        props.requestData?.group_by.length > 0 && props.displayMode === "group",
    );
    const isFlattenMode = computed(
      () =>
        props.requestData?.group_by.length > 0 && props.displayMode !== "group",
    );

    const isExternal = window.IS_EXTERNAL === true;
    const ownerBaseList = [
      {
        id: "no_owner",
        name: t("未指定责任人"),
      },
    ];

    const remarkList = [
      {
        id: "remarked",
        name: t("已备注"),
      },
      {
        id: "no_remark",
        name: t("未备注"),
      },
    ];

    watch(
      () => props.requestData,
      () => {
        Object.values(sortColumnRefs).forEach((item: any) => {
          item.value?.reset();
        });
      },
      {
        deep: true,
      },
    );

    watch(
      () => [
        showGroupBy.value,
        showYOY.value,
        // isAiAssistanceActive.value,
        props.displayMode,
      ],
      () => {
        setTimeout(() => {
          initHeader();
        });
      },
      {
        immediate: true,
        deep: true,
      },
    );

    // 获取当前数据指纹所有的责任人
    const getUserList = () => {
      const cloneOwnerBase = structuredClone(ownerBaseList);
      $http
        .request("/logClustering/getOwnerList", {
          params: {
            index_set_id: props.indexId,
          },
        })
        .then((res) => {
          ownerList.value = res.data.reduce((acc, cur) => {
            acc.push({
              id: cur,
              name: cur,
            });
            return acc;
          }, cloneOwnerBase);
        });
    };

    const handleConfirmFilter = (value: any, field: string) => {
      emit("column-filter", field, value);
    };

    const handleSort = (type: string, field: string) => {
      Object.keys(sortColumnRefs).forEach((key) => {
        if (key !== field) {
          sortColumnRefs[key].value?.reset();
        }
      });
      emit("column-sort", field, type);
    };

    const handleResizeColumn = () => {
      emit("resize-column", tableHeaderWraperRef.value?.scrollWidth);
    };

    const initHeader = () => {
      renderKey.value += 1;
      setTimeout(() => {
        handleResizeColumn();
      });
    };

    getUserList();

    expose({
      scroll: (scrollLeft: number) => {
        tableHeaderWraperRef.value.scrollLeft = scrollLeft;
      },
      getColumnWidthList: () =>
        Array.from(headRowRef.value.querySelectorAll("th")).map(
          (item: HTMLElement) => [
            item.getAttribute("data-field-name"),
            item.getBoundingClientRect().width,
          ],
        ),
    });

    onMounted(() => {
      setTimeout(() => {
        handleResizeColumn();
      }, 1000);
      window.addEventListener("resize", initHeader);
    });

    onBeforeUnmount(() => {
      window.removeEventListener("resize", initHeader);
    });

    return () => (
      <div ref={tableHeaderWraperRef} class="log-table-header-main-wraper">
        <table key={renderKey.value} class="log-table-header-main">
          <thead>
            <tr ref={headRowRef}>
              {showGroupBy.value && <th style="width: 12px"></th>}
              <HeadColumn
                width={125}
                on-resize-width={handleResizeColumn}
                fieldName="signature"
              >
                {t("数据指纹")}
              </HeadColumn>
              <HeadColumn
                width={props.tableColumnWidth.number}
                on-click-column={() => sortColumnRefs.count.value?.update()}
                on-resize-width={handleResizeColumn}
                fieldName="number"
              >
                <div class="sort-column">
                  {t("数量")}
                  <sort-operate
                    ref={sortColumnRefs.count}
                    on-sort={(type) => handleSort(type, "count")}
                  />
                </div>
              </HeadColumn>
              <HeadColumn
                width={props.tableColumnWidth.percentage}
                on-click-column={() =>
                  sortColumnRefs.percentage.value?.update()
                }
                on-resize-width={handleResizeColumn}
                fieldName="percentage"
              >
                <div class="sort-column">
                  {t("占比")}
                  <sort-operate
                    ref={sortColumnRefs.percentage}
                    on-sort={(type) => handleSort(type, "percentage")}
                  />
                </div>
              </HeadColumn>
              {showYOY.value && (
                <HeadColumn
                  width={props.tableColumnWidth.year_on_year_count}
                  on-click-column={() =>
                    sortColumnRefs.year_on_year_count.value?.update()
                  }
                  on-resize-width={handleResizeColumn}
                  fieldName="year_on_year_count"
                >
                  <div class="sort-column">
                    {t("同比数量")}
                    <sort-operate
                      ref={sortColumnRefs.year_on_year_count}
                      on-sort={(type) => handleSort(type, "year_on_year_count")}
                    />
                  </div>
                </HeadColumn>
              )}
              {showYOY.value && (
                <HeadColumn
                  width={props.tableColumnWidth.year_on_year_percentage}
                  on-click-column={() =>
                    sortColumnRefs.year_on_year_percentage.value?.update()
                  }
                  on-resize-width={handleResizeColumn}
                  fieldName="year_on_year_percentage"
                >
                  <div class="sort-column">
                    {t("同比变化")}
                    <sort-operate
                      ref={sortColumnRefs.year_on_year_percentage}
                      on-sort={(type) =>
                        handleSort(type, "year_on_year_percentage")
                      }
                    />
                  </div>
                </HeadColumn>
              )}
              {isFlattenMode.value &&
                props.requestData.group_by.map((item) => (
                  <HeadColumn
                    width={100}
                    on-resize-width={handleResizeColumn}
                    fieldName={item}
                  >
                    {item}
                  </HeadColumn>
                ))}
              <HeadColumn
                minWidth={350}
                on-resize-width={handleResizeColumn}
                fieldName="pattern"
              >
                Pattern
              </HeadColumn>
              <HeadColumn
                width={200}
                customStyle={{ paddingLeft: "10px" }}
                on-resize-width={handleResizeColumn}
                fieldName="owners"
              >
                <div class="sort-column">
                  <span>{t("责任人")}</span>
                  <filter-operate
                    ref={sortColumnRefs.owners}
                    list={ownerList.value}
                    on-confirm={(value) => handleConfirmFilter(value, "owners")}
                  />
                </div>
              </HeadColumn>
              {!isExternal && (
                <HeadColumn
                  width={200}
                  on-resize-width={handleResizeColumn}
                  fieldName="alert_option"
                >
                  <div class="sort-column">
                    <span>{t("创建告警策略")}</span>
                    <span
                      class="tip-main"
                      v-bk-tooltips={{
                        content: t(
                          "勾选后，基于聚类结果为责任人创建关键字告警。持续监测您的异常问题。通过开关可控制告警策略启停。",
                        ),
                        placement: "top",
                      }}
                    >
                      <log-icon type="help" />
                    </span>
                  </div>
                </HeadColumn>
              )}
              <HeadColumn
                width={200}
                on-resize-width={handleResizeColumn}
                fieldName="remark"
              >
                <div class="sort-column">
                  <span>{t("备注")}</span>
                  <filter-operate
                    ref={sortColumnRefs.remark}
                    list={remarkList}
                    multiple={false}
                    searchable={false}
                    on-confirm={(value) => handleConfirmFilter(value, "remark")}
                  />
                </div>
              </HeadColumn>
              {/* {isAiAssistanceActive.value && (
                <HeadColumn
                  width={60}
                  on-resize-width={handleResizeColumn}
                ></HeadColumn>
              )} */}
              {showGroupBy.value && <th style="width: 12px"></th>}
            </tr>
          </thead>
          <div class="resize-guide-line"></div>
        </table>
      </div>
    );
  },
});
