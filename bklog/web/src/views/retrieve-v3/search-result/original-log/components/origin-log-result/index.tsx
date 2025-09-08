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
import { debounce } from "lodash-es";
import {
  defineComponent,
  ref,
  watch,
  computed,
  onMounted,
  onBeforeUnmount,
} from "vue";
import { parseTableRowData } from "@/common/util";
import SearchBar from "@/views/retrieve-v2/search-bar/index.vue";
import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import { axiosInstance } from "@/api";
import JsonFormatter from "@/global/json-formatter.vue";
import RenderJsonCell from "./render-json-cell";
import DOMPurify from "dompurify";
import {
  readBlobRespToJson,
  parseBigNumberList,
  bigNumberToString,
  formatDate,
} from "@/common/util";

import "./index.scss";

export default defineComponent({
  name: "LogResult",
  props: {
    indexSetId: {
      type: Number,
      default: 0,
    },
    logIndex: {
      type: Number,
      default: 0,
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();

    const searchBarRef = ref<any>();
    const contentMainRef = ref<HTMLElement>();
    const tableRef = ref<HTMLElement>();
    const logList = ref<any[]>([]);
    const choosedIndex = ref(props.logIndex);
    const listLoading = ref(false);

    const visibleFields = computed(() => store.state.visibleFields);

    const requestOtherparams = {
      interval: "auto",
      keyword: "*",
      search_mode: "ui",
      addition: [] as any[],
    };
    // 隐藏掉tippy弹出框中的非必要按钮
    const styleContent = `
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(1),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(2),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(5) {
        display: none !important;
      }
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(3),
      .tippy-box[data-theme~="segment-light"] .tippy-content .segment-event-box:nth-child(4) {
        .segment-new-link {
          display: none !important;
        }
      }
    `;

    let styleElement: any = null;
    let isInit = false;
    let begin = 0;
    let size = 50;

    watch(
      () => props.logIndex,
      () => {
        choosedIndex.value = props.logIndex;
      },
      {
        immediate: true,
      }
    );

    const requestLogList = () => {
      listLoading.value = true;
      const baseUrl =
        process.env.NODE_ENV === "development"
          ? "api/v1"
          : window.AJAX_URL_PREFIX;
      const searchUrl = `/search/index_set/${props.indexSetId}/search/`;
      const { start_time, end_time } = store.state.indexItem;
      size = isInit ? 50 : props.logIndex > 50 ? props.logIndex + 20 : 50;
      const requestData = {
        bk_biz_id: store.state.bkBizId,
        size,
        begin,
        start_time,
        end_time,
        sort_list: [],
        ...requestOtherparams,
      };
      const params: any = {
        method: "post",
        url: searchUrl,
        withCredentials: true,
        baseURL: baseUrl,
        responseType: "blob",
        data: requestData,
        headers: {},
      };
      if (store.state.isExternal) {
        params.headers = {
          "X-Bk-Space-Uid": store.state.spaceUid,
        };
      }
      axiosInstance(params)
        .then((resp: any) => {
          if (resp.data && !resp.message) {
            readBlobRespToJson(resp.data).then(
              ({ code, data, result, message }) => {
                if (result) {
                  const list = parseBigNumberList(data.list);
                  logList.value.push(...list);
                  const total = bigNumberToString(data.total);
                  if (!isInit) {
                    setTimeout(() => {
                      contentMainRef.value!.scrollTop = 58;
                      // 自动定位到选中行
                      const isChoosedRow = Array.from(
                        tableRef.value.querySelectorAll(".is-choosed")
                      )[0];
                      const positionInfo = isChoosedRow.getBoundingClientRect();
                      if (positionInfo.top > window.innerHeight) {
                        isChoosedRow.scrollIntoView();
                      }
                    });
                    isInit = true;
                  }
                }
              }
            );
          }
        })
        .finally(() => {
          listLoading.value = false;
        });
    };

    const getAdditionMappingOperator = (
      operator: string,
      field: string,
      value: string[],
      depth: number
    ) => {
      let mappingKey = {
        // is is not 值映射
        is: "=",
        "is not": "!=",
      };

      /** text类型字段类型的下钻映射 */
      const textMappingKey = {
        is: "contains match phrase",
        "is not": "not contains match phrase",
      };

      /** keyword 类型字段类型的下钻映射 */
      const keywordMappingKey = {
        is: "contains",
        "is not": "not contains",
      };

      const boolMapping = {
        is: `is ${value[0]}`,
        "is not": `is ${/true/i.test(value[0]) ? "false" : "true"}`,
      };

      const targetField = store.state.visibleFields?.find(
        (item) => item.field_name === field
      );

      const textType = targetField?.field_type ?? "";
      const isVirtualObjNode = targetField?.is_virtual_obj_node ?? false;

      if (isVirtualObjNode && textType === "object") {
        mappingKey = textMappingKey;
      }

      if (textType === "text") {
        mappingKey = textMappingKey;
      }

      if (textType === "boolean") {
        mappingKey = boolMapping;
        if (value.length) {
          value.splice(0, value.length);
        }
      }

      if (depth > 1 && textType === "keyword") {
        mappingKey = keywordMappingKey;
      }
      return mappingKey[operator] ?? operator; // is is not 值映射
    };

    const formatJsonString = (formatResult: string) => {
      if (typeof formatResult === "string") {
        return DOMPurify.sanitize(formatResult);
      }

      return formatResult;
    };

    const getSqlAdditionMappingOperator = (
      operator: string,
      field: string,
      fieldType: string,
      value: string
    ) => {
      const formatValue = (value: string | string[]) => {
        let formatResult = value;
        if (["text", "string", "keyword"].includes(fieldType)) {
          if (Array.isArray(formatResult)) {
            formatResult = formatResult.map(formatJsonString);
          } else {
            formatResult = formatJsonString(formatResult);
          }
        }

        return formatResult;
      };

      let mappingKey = {
        // is is not 值映射
        is: `${field}: "${formatValue(value)}"`,
        "is not": `NOT ${field}: "${formatValue(value)}"`,
      };

      return mappingKey[operator] ?? operator; // is is not 值映射
    };

    const getValidUISearchValue = (searchValue: any[]) =>
      searchValue.reduce((addtions, item) => {
        if (!item.disabled) {
          addtions.push({
            field: item.field,
            operator: item.operator,
            value:
              item.hidden_values?.length > 0
                ? item.value.filter(
                    (value) => !item.hidden_values.includes(value)
                  )
                : item.value,
          });
        }
        return addtions;
      }, []);

    const handleMenuClick = (data: {
      option: {
        depth: number;
        fieldName: string;
        fieldType: string;
        operation: string;
        value: string;
      };
      isLink: boolean;
    }) => {
      let isNeedRefresh = false;
      if (requestOtherparams.search_mode === "ui") {
        const operator = getAdditionMappingOperator(
          data.option.operation,
          data.option.fieldName,
          [data.option.value],
          data.option.depth
        );
        const searchItem = {
          disabled: false,
          field: data.option.fieldName,
          field_type: data.option.fieldType,
          operator,
          value: [data.option.value],
          relation: "OR",
          showAll: true,
        };
        isNeedRefresh = searchBarRef.value.addValue(searchItem);
        const searchValue = searchBarRef.value.getValue();
        requestOtherparams.addition = getValidUISearchValue(searchValue);
        requestOtherparams.keyword = "*";
      } else {
        const searchItem = getSqlAdditionMappingOperator(
          data.option.operation,
          data.option.fieldName,
          data.option.fieldType,
          data.option.value
        );
        isNeedRefresh = searchBarRef.value.addValue(searchItem);
        const searchValue = searchBarRef.value.getValue();
        requestOtherparams.addition = [];
        requestOtherparams.keyword = searchValue;
      }
      if (isNeedRefresh) {
        handleReset();
        requestLogList();
      }
    };

    const handleSearch = (mode: string) => {
      handleModeChange(mode);
    };

    const handleModeChange = (mode: string) => {
      requestOtherparams.search_mode = mode;
      const searchValue = searchBarRef.value.getValue();
      if (mode === "ui") {
        requestOtherparams.addition = getValidUISearchValue(searchValue);
        requestOtherparams.keyword = "*";
      } else {
        requestOtherparams.addition = [];
        requestOtherparams.keyword = !searchValue ? "*" : searchValue;
      }
      handleReset();
      requestLogList();
    };

    const handleChooseRow = (index: number) => {
      if (choosedIndex.value === index) {
        return;
      }

      choosedIndex.value = index;
      const rowInfo = logList.value[index];
      const contextFields =
        store.state.indexSetOperatorConfig.contextAndRealtime.extra
          ?.context_fields;
      const timeField = store.state.indexFieldInfo.time_field;
      const dialogNewParams = {};
      Object.assign(dialogNewParams, {
        dtEventTimeStamp: rowInfo.dtEventTimeStamp,
      });
      if (Array.isArray(contextFields) && contextFields.length) {
        // 传参配置指定字段
        contextFields.push(timeField);
        contextFields.forEach((field) => {
          if (field === "bk_host_id") {
            if (rowInfo[field]) {
              dialogNewParams[field] = rowInfo[field];
            }
          } else {
            dialogNewParams[field] = parseTableRowData(
              rowInfo,
              field,
              "",
              store.state.isFormatDate,
              ""
            );
          }
        });
      } else {
        Object.assign(dialogNewParams, rowInfo);
      }
      emit("choose-row", dialogNewParams);
    };

    const handleScrollContent = debounce((e: any) => {
      const { scrollTop, scrollHeight, clientHeight } = e.target;
      if (scrollHeight - scrollTop - clientHeight <= 1) {
        if (size !== 50) {
          // 从50条以上进来的
          begin = size;
          size = 50;
        } else {
          begin += size;
        }

        requestLogList();
      }
    }, 500);

    const handleReset = () => {
      logList.value = [];
      begin = 0;
    };

    // 添加样式函数
    const addSegmentLightStyle = () => {
      if (!styleElement) {
        styleElement = document.createElement("style");
        styleElement.id = "dynamic-segment-light-style";
        styleElement.innerHTML = styleContent;
        document.head.appendChild(styleElement);
      }
    };

    // 移除样式函数
    const removeSegmentLightStyle = () => {
      if (styleElement) {
        document.head.removeChild(styleElement);
        styleElement = null;
      }
    };

    onMounted(() => {
      addSegmentLightStyle();
    });

    onBeforeUnmount(() => {
      removeSegmentLightStyle();
    });

    expose({
      init: () => handleModeChange(requestOtherparams.search_mode),
      reset: handleReset,
    });

    return () => (
      <div class="log-result-main">
        <div class="title-main">
          <div class="title">{t("原始日志检索结果")}</div>
          <div class="split-line"></div>
          <div class="desc">{t("可切换原始日志，查看该日志的上下文")}</div>
        </div>
        <div
          class="content-main"
          ref={contentMainRef}
          on-scroll={handleScrollContent}
        >
          <div class="search-main">
            <SearchBar
              ref={searchBarRef}
              showCopy={false}
              showClear={false}
              showQuerySetting={false}
              showFavorites={false}
              usageType="local"
              on-search={handleSearch}
              on-mode-change={handleModeChange}
            />
          </div>
          <table class="log-result-table" ref={tableRef}>
            <thead>
              <tr class="table-header">
                <th style="width:90px;padding-left:42px">{t("行号")}</th>
                <th style="width:140px">{t("时间")}</th>
                <th style="min-width:300px">{t("原始日志")}</th>
              </tr>
            </thead>
            <tbody v-bkloading={{ isLoading: listLoading.value, opacity: 0.6 }}>
              {logList.value.length > 0 &&
                logList.value.map((row, index) => (
                  <tr
                    key={index}
                    class={{ "is-choosed": choosedIndex.value === index }}
                    on-click={() => handleChooseRow(index)}
                  >
                    <td>
                      <div class="index-column">
                        <span>{index + 1}</span>
                        <div class="choosed-bgd">
                          <div class="check-icon-main">
                            <span class="bk-icon bklog-icon bklog-correct"></span>
                          </div>
                        </div>
                      </div>
                    </td>
                    <td>{formatDate(Number(row.time))}</td>
                    <td style="padding:4px 0">
                      <RenderJsonCell>
                        <JsonFormatter
                          class="bklog-column-wrapper"
                          fields={visibleFields.value}
                          jsonValue={row}
                          limitRow={null}
                          onMenu-click={handleMenuClick}
                        ></JsonFormatter>
                      </RenderJsonCell>
                    </td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  },
});
