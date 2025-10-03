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

import { computed, defineComponent, isRef, ref, type PropType } from "vue";
import TextHighlight from "vue-text-highlight";

import useLocale from "@/hooks/use-locale";
import useStore from "@/hooks/use-store";
import { BK_LOG_STORAGE } from "@/store/store.type";
import BkUserSelector from "@blueking/user-selector";
import { bkMessage } from "bk-magic-vue";
import tippy from "tippy.js";

import ClusterEventPopover from "./cluster-popover";
import RemarkEditTip from "./remark-edit-tip";
import { getConditionRouterParams } from "./utils";
import $http from "@/api";

import type { ITableItem } from "../index";
import type { LogPattern } from "@/services/log-clustering";

import RetrieveHelper from "@/views/retrieve-helper";
import "./index.scss";

export interface GroupListState {
  [key: string]: {
    isOpen: boolean;
  };
}

export interface IPagination {
  current: number;
  limit: number;

  // 当前可用于渲染总行数
  // 分组模式会计算为 groupCount + childCount
  // 平铺模式计算为 childCount
  count: number;

  // 分组数量
  groupCount: number;

  // 所有非分组数据行数
  // response.data.length
  childCount: number;

  // 可见行数据
  visibleCount: number;
}

export default defineComponent({
  name: "ContentTable",
  components: {
    TextHighlight,
    ClusterEventPopover,
    BkUserSelector,
    RemarkEditTip,
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
    tableList: {
      type: Array as PropType<ITableItem[]>,
      default: () => [],
    },
    indexId: {
      type: String,
      require: true,
    },

    widthList: {
      type: Object,
      default: () => {},
    },
    displayMode: {
      type: String,
      default: "group",
    },
    groupListState: {
      type: Object as PropType<GroupListState>,
      default: () => ({}),
    },
    pagination: {
      type: Object as PropType<IPagination>,
      default: () => ({
        current: 1,
        limit: 50,
        count: 0,
        groupCount: 0,
        childCount: 0,
      }),
    },
  },
  setup(props, { emit }) {
    const { t } = useLocale();
    const store = useStore();
    let activeMarkElement: HTMLElement | null = null;
    const isExternal = window.IS_EXTERNAL === true;

    const headRowRef = ref<HTMLElement>();
    const remarkTipsRef = ref<any>(null);
    const tableWraperRef = ref<HTMLElement>();
    const currentRowId = ref(0);
    const cacheExpandStr = ref<any[]>([]); // 展示pattern按钮数组

    const groupState = computed(() => props.groupListState);
    const showYOY = computed(() => props.requestData?.year_on_year_hour >= 1);
    const isLimitExpandView = computed(
      () => store.state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW],
    );

    /** 获取当前编辑操作的数据 */
    const currentRowValue = computed(() =>
      props.tableList.find((item) => item.data?.id === currentRowId.value),
    );
    const showGroupBy = computed(
      () =>
        props.requestData?.group_by.length > 0 && props.displayMode === "group",
    );
    const isFlattenMode = computed(
      () =>
        props.requestData?.group_by.length > 0 && props.displayMode !== "group",
    );
    const columnWidth = computed(() =>
      Object.assign({}, props.tableColumnWidth ?? {}, props.widthList ?? {}),
    );

    /**
     * 过滤所有可见行数据
     * 针对所有的数据
     */
    const visibleList = computed(() =>
      props.tableList.filter((d) => !d.hidden),
    );

    /**
     * 所有可见分组数据
     * 针对分组的展开收起
     */
    const visibleGroupData = computed(() =>
      visibleList.value.filter((d) => {
        if (showGroupBy.value) {
          // 如果是分组展示，则需要展示分组行和已经展开的分组行下的数据
          return d.isGroupRow || groupState.value[d.hashKey]?.isOpen;
        }

        return !d.isGroupRow;
      }),
    );

    /**
     * 获取当前页的数据
     */
    const tablePageData = computed(() => {
      const lastIndex = Math.min(
        props.pagination.current * props.pagination.limit,
        visibleGroupData.value.length,
      );
      const lastItem = visibleGroupData.value[lastIndex - 1];
      const lastItemIndex = visibleList.value.findIndex(
        (item) => item === lastItem,
      );
      return visibleList.value.slice(0, lastItemIndex + 1);
    });

    // 计算展示列数量
    const columnLength = computed(() => {
      // 固定列
      const staticColumnLen = 6;

      // 同比数量列 + 同比变化列
      const showYOYLen = showYOY.value ? 2 : 0;

      // groupBy 列数
      const groupByLen = isFlattenMode.value
        ? props.requestData.group_by?.length ?? 0
        : 0;

      // 创建告警策略列
      const externalLen = isExternal ? 0 : 1;

      return staticColumnLen + showYOYLen + groupByLen + externalLen;
    });

    let popoverInstance: any = null;
    let remarkPopoverTimer: any;

    /**
     * 更新编辑行数据
     * @param row
     * @param key
     * @param value
     */
    const updateTableRowData = (row: LogPattern, key: string, value: any) => {
      if (row) {
        if (isRef(row[key])) {
          row[key].value = value;
        } else {
          row[key] = value;
        }
      }
    };

    const getHeightLightList = (str: string) => str.match(/#.*?#/g) || [];

    const handleMenuBatchClick = (row, isLink = true) => {
      const additionList: any[] = [];
      const groupBy = props.requestData?.group_by;
      if (groupBy.length) {
        groupBy.forEach((el, index) => {
          additionList.push({
            field: el,
            operator: "is",
            value: row.group[index],
            isLink,
          });
        });
      }
      additionList.push({
        field: `__dist_${props.requestData?.pattern_level}`,
        operator: "is",
        value: row.signature.toString(),
        isLink,
      });

      // 聚类下钻只能使用ui模式
      store.commit("updateIndexItem", { search_mode: "ui" });
      // 新开页打开首页是原始日志，不需要传聚类参数，如果传了则会初始化为聚类
      store.commit("updateState", { key: "clusterParams", value: null });
      store
        .dispatch("setQueryCondition", additionList)
        .then(([newSearchList, searchMode, isNewSearchPage]) => {
          if (isLink) {
            const openUrl = getConditionRouterParams(
              newSearchList,
              searchMode,
              isNewSearchPage,
              { tab: "origin" },
            );
            window.open(openUrl, "_blank");
            // 新开页后当前页面回填聚类参数
            store.commit("updateState", {
              key: "clusterParams",
              value: props.requestData,
            });
            return;
          }
          emit("show-change", "origin");
        });
    };

    const handleMenuClick = (row, isLink = false) => {
      handleMenuBatchClick(row, isLink);
      emit("show-origin-log");
    };

    const getLimitState = (index: number) => {
      if (isLimitExpandView.value) return false;
      return !cacheExpandStr.value.includes(index);
    };

    /** 将分组的数组改成对像 */
    const getGroupsValue = (group) => {
      if (!props.requestData?.group_by.length) return {};
      return props.requestData.group_by.reduce((acc, cur, index) => {
        acc[cur] = group?.[index] ?? "";
        return acc;
      }, {});
    };

    // 设置负责人
    const handleChangePrincipal = (val: null | string[], row: LogPattern) => {
      currentRowId.value = row.id;
      // 当创建告警策略开启时，不允许删掉最后一个责任人
      if (row.strategy_enabled && !val.length) {
        bkMessage({
          theme: "error",
          message: t("删除失败，开启告警时，需要至少一个责任人"),
        });
        return;
      }
      $http
        .request("/logClustering/setOwner", {
          params: {
            index_set_id: props.indexId,
          },
          data: {
            signature: row.signature,
            owners: val ?? row.owners.value,
            origin_pattern: row.origin_pattern,
            groups: getGroupsValue(row.group),
          },
        })
        .then((res) => {
          if (res.result) {
            const { owners } = res.data;
            updateTableRowData(row, "owners", owners);
            bkMessage({
              theme: "success",
              message: t("操作成功"),
            });
          }
        });
    };

    const changeStrategy = (enabled: boolean, row: LogPattern) => {
      currentRowId.value = row.id;
      $http
        .request("/logClustering/updatePatternStrategy", {
          params: {
            index_set_id: props.indexId,
          },
          data: {
            signature: row.signature,
            origin_pattern: row.origin_pattern,
            strategy_enabled: enabled,
            groups: getGroupsValue(row.group),
          },
        })
        .then((res) => {
          if (res.result) {
            const { strategy_id } = res.data;
            bkMessage({
              theme: "success",
              message: t("操作成功"),
            });
            updateTableRowData(row, "strategy_id", strategy_id);
            updateTableRowData(row, "strategy_enabled", enabled);
          }
        });
    };

    const handleStrategyInfoClick = (row) => {
      currentRowId.value = row.id;
      window.open(
        `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/strategy-config/detail/${row.strategy_id}`,
        "_blank",
      );
    };

    const remarkContent = (remarkList) => {
      if (!remarkList.length) return "--";
      const maxTimestamp = remarkList.reduce((pre, cur) => {
        return cur.create_time > pre.create_time ? cur : pre;
      }, remarkList[0]);
      return maxTimestamp.remark;
    };

    const handleHideRemarkTip = () => {
      popoverInstance?.hide();
    };

    const handleHoverRemarkIcon = (e: Event, row: LogPattern) => {
      currentRowId.value = row.id;
      clearTimeout(remarkPopoverTimer);
      activeMarkElement = e.target as HTMLElement;
      remarkPopoverTimer = setTimeout(() => {
        if (!popoverInstance) {
          popoverInstance = tippy(activeMarkElement, {
            appendTo: () => document.body,
            content: remarkTipsRef.value.tipRef,
            allowHTML: true,
            arrow: true,
            theme: "light remark-edit-tip-popover",
            sticky: true,
            maxWidth: 340,
            // duration: [500, 0],
            offset: [0, 5],
            interactive: true,
            placement: "top",
            onHidden: () => {
              popoverInstance?.destroy();
              popoverInstance = null;
            },
          });
        }
        popoverInstance.show();
      }, 500);
    };

    const handleUpdateRemark = (remark: LogPattern["remark"]) => {
      updateTableRowData(currentRowValue.value.data, "remark", remark);
      activeMarkElement.textContent = remarkContent(remark);
    };

    const handleAddSearch = (e: Event, row: ITableItem) => {
      e.stopPropagation();
      const addConditions = props.requestData?.group_by.map((item, index) => ({
        field: item,
        operator: "=",
        value: [row.group[index]],
        from: "cluster",
      }));
      store.dispatch("setQueryCondition", addConditions);
      RetrieveHelper.searchValueChange("cluster", addConditions);
    };

    /**
     * 点击分组功能
     * @param row
     */
    const handleGroupClick = (row: ITableItem) => {
      emit("group-state-change", row);
    };

    /**
     * 渲染分组行功能
     * @param row
     * @returns
     */
    const renderGroupItem = (row: ITableItem) => {
      if (showGroupBy.value) {
        return (
          <div
            class="collpase-main"
            on-click={() => {
              handleGroupClick(row);
            }}
          >
            <div
              class={{
                "collapse-icon": true,
                "is-open": groupState.value[row.hashKey]?.isOpen ?? false,
              }}
            >
              <log-icon type="arrow-down-filled-2" />
            </div>
            <div
              class="group-value-display"
              v-bk-overflow-tips={{
                content: row.groupKey,
              }}
            >
              <div class="value-item">{row.groupKey}</div>
            </div>
            <div
              class="add-search"
              v-bk-tooltips={t("添加为检索条件")}
              on-click={(e) => handleAddSearch(e, row)}
            >
              <log-icon type="sousuo-" />
            </div>
            <div class="count-display">
              （{t("共有 {0} 条数据", [row.childCount])}）
            </div>
          </div>
        );
      }

      return (
        <div class="list-count-main">
          <i18n path="共有 {0} 条数据">
            <span style="font-weight:700">{props.pagination.childCount}</span>
          </i18n>
        </div>
      );
    };

    /**
     * 渲染分组行
     * @param row
     * @returns
     */
    const renderGroupRow = (row: ITableItem) => {
      // 平铺模式
      if (
        (isFlattenMode.value || props.requestData?.group_by.length === 0) &&
        row.index === 1
      ) {
        return (
          <tr class="is-row-group is-flatten-count">
            <td colspan={columnLength.value}>{renderGroupItem(row)}</td>
          </tr>
        );
      }

      // 分组模式
      if (showGroupBy.value) {
        return (
          <tr class="is-row-group">
            <td colspan={columnLength.value}>{renderGroupItem(row)}</td>
          </tr>
        );
      }

      return null;
    };

    /**
     * 渲染数据行
     * @param row
     * @returns
     */
    const renderDataRow = (row: ITableItem) => {
      return (
        <tr>
          <td>
            <div class="signature-box">
              <div class="signature" v-bk-overflow-tips>
                {row.data?.signature}
              </div>
              <div class="new-finger" v-show={row.data?.is_new_class}>
                New
              </div>
            </div>
          </td>
          <td>
            <bk-button
              style="padding: 0px"
              size="small"
              theme="primary"
              text
              on-click={() => handleMenuBatchClick(row)}
            >
              {row.data?.count}
            </bk-button>
          </td>
          <td>
            <bk-button
              style="padding: 0px"
              size="small"
              theme="primary"
              text
              on-click={() => handleMenuBatchClick(row)}
            >
              {`${row.data?.percentage.toFixed(2)}%`}
            </bk-button>
          </td>
          {showYOY.value && (
            <td>
              <span style="padding-left:6px">
                {row.data?.year_on_year_count}
              </span>
            </td>
          )}
          {showYOY.value && (
            <td>
              <div
                style={{
                  color:
                    row.data?.year_on_year_percentage < 0
                      ? "#2CAF5E"
                      : row.data?.year_on_year_percentage === 0
                        ? "#313238"
                        : "#E71818",
                }}
                class="compared-change"
              >
                <span>{`${Math.abs(Number(row.data?.year_on_year_percentage.toFixed(2)))}%`}</span>
                {row.data?.year_on_year_percentage !== 0 ? (
                  <log-icon
                    style="font-size: 16px;"
                    type={
                      row.data?.year_on_year_percentage < 0 ? "down-4" : "up-2"
                    }
                  />
                ) : (
                  <log-icon style="font-size: 16px;" type="--2" />
                )}
              </div>
            </td>
          )}
          {isFlattenMode.value &&
            row.data?.group.map((item) => (
              <td>
                <div class="dynamic-column" v-bk-overflow-tips>
                  {item}
                </div>
              </td>
            ))}
          <td>
            <div
              class={[
                "pattern-content",
                { "is-limit": getLimitState(row.index) },
              ]}
            >
              <ClusterEventPopover
                indexId={props.indexId}
                rowData={row.data}
                on-event-click={(isLink) => handleMenuClick(row.data, isLink)}
                on-open-cluster-config={() => emit("open-cluster-config")}
              >
                <text-highlight
                  style=""
                  class="monospace-text"
                  queries={getHeightLightList(row.data?.pattern)}
                >
                  {row.data?.pattern ? row.data?.pattern : t("未匹配")}
                </text-highlight>
              </ClusterEventPopover>
              {/* {!isLimitExpandView.value && (
            <div>
              {!cacheExpandStr.value.includes(rowIndex) ? (
                <p
                  class='show-whole-btn'
                  on-click={() => handleShowWhole(rowIndex)}
                >
                  {t('展开全部')}
                </p>
              ) : (
                <p
                  class='hide-whole-btn'
                  on-click={() => handleHideWhole(rowIndex)}
                >
                  {t('收起')}
                </p>
              )}
            </div>
          )} */}
            </div>
          </td>
          <td style="padding-left: 0px">
            <div
              // 组件样式有问题，暂时这样处理
              style={{ padding: isExternal && "5px 0" }}
              class="principal-main"
              v-bk-tooltips={{
                placement: "top",
                content: row.data?.owners.value.join(", "),
                delay: 300,
                disabled: !row.data?.owners.value.length,
              }}
            >
              {!isExternal ? (
                <bk-user-selector
                  class="principal-input"
                  api={window.BK_LOGIN_URL}
                  empty-text={t("无匹配人员")}
                  placeholder="--"
                  value={row.data?.owners.value}
                  multiple
                  on-change={(val) => handleChangePrincipal(val, row.data)}
                />
              ) : (
                <bk-tag-input
                  style="width: 100%"
                  class="principal-tag-input"
                  clearable={false}
                  placeholder="--"
                  value={row.data?.owners.value}
                  allow-create
                  has-delete-icon
                  on-blur={() => handleChangePrincipal(null, row.data)}
                  on-change={(value) => {
                    row.data.owners.value = value;
                  }}
                />
              )}
            </div>
          </td>
          {!isExternal && (
            <td>
              <div class="create-strategy-main">
                {row.data?.owners.value.length > 0 ? (
                  <div class="is-able">
                    <bk-switcher
                      theme="primary"
                      value={row.data?.strategy_enabled}
                      on-change={(val) => changeStrategy(val, row.data)}
                    />
                    {row.data?.strategy_id > 0 && (
                      <span on-click={() => handleStrategyInfoClick(row.data)}>
                        <log-icon style="font-size: 16px" type="audit" />
                      </span>
                    )}
                  </div>
                ) : (
                  <bk-switcher
                    v-bk-tooltips={t("暂无配置责任人，无法自动创建告警策略")}
                    theme="primary"
                    value={row.data?.strategy_enabled}
                    disabled
                  />
                )}
              </div>
            </td>
          )}
          <td style="padding-right: 8px;">
            <div
              class="remark-column"
              on-mouseenter={(e) => handleHoverRemarkIcon(e, row.data)}
              on-mouseleave={() => clearTimeout(remarkPopoverTimer)}
            >
              {remarkContent(row.data?.remark)}
            </div>
          </td>
        </tr>
      );
    };

    /**
     * 渲染表格行
     * @param row
     * @returns
     */
    const renderTableRow = (row: ITableItem) => {
      if (row.isGroupRow) {
        return renderGroupRow(row);
      }

      if (showGroupBy.value) {
        if (groupState.value[row.hashKey].isOpen ?? false) {
          return renderDataRow(row);
        }

        return null;
      }

      if (!showGroupBy.value) {
        return renderDataRow(row);
      }

      return null;
    };

    return () => (
      <div
        style={{
          borderLeft: showGroupBy.value ? "1px solid #dcdee5" : "none",
          borderRight: showGroupBy.value ? "1px solid #dcdee5" : "none",
        }}
        class="log-content-table-main"
        v-show={props.tableList.length > 0}
      >
        <div ref={tableWraperRef} class="log-content-table-wraper">
          <table class="log-content-table">
            <thead class="hide-header">
              <tr ref={headRowRef}>
                <th
                  style={{ width: `${columnWidth.value.signature ?? 125}px` }}
                >
                  数据指纹
                </th>
                <th style={{ width: `${columnWidth.value.number}px` }}>数量</th>
                <th style={{ width: `${columnWidth.value.percentage}px` }}>
                  占比
                </th>
                {showYOY.value && (
                  <th
                    style={{
                      width: `${columnWidth.value.year_on_year_count}px`,
                    }}
                  >
                    同比数量
                  </th>
                )}
                {showYOY.value && (
                  <th
                    style={{
                      width: `${columnWidth.value.year_on_year_percentage}px`,
                    }}
                  >
                    同比变化
                  </th>
                )}
                {isFlattenMode.value &&
                  props.requestData.group_by.map((item) => (
                    <th
                      style={{ width: `${columnWidth.value[item] ?? 100}px` }}
                    >
                      {item}
                    </th>
                  ))}
                <th style={{ width: `${columnWidth.value.pattern ?? 350}px` }}>
                  Pattern
                </th>
                <th style={{ width: `${columnWidth.value.owners ?? 200}px` }}>
                  责任人
                </th>
                {!isExternal && (
                  <th
                    style={{
                      width: `${columnWidth.value.alert_option ?? 200}px`,
                    }}
                  >
                    创建告警策略
                  </th>
                )}
                <th style={{ width: `${columnWidth.value.remark ?? 200}px` }}>
                  备注
                </th>
                {/* {isAiAssistanceActive.value && <th style="width:60px">ai</th>} */}
              </tr>
            </thead>
            <tbody>{(tablePageData.value ?? []).map(renderTableRow)}</tbody>
          </table>
        </div>
        <RemarkEditTip
          ref={remarkTipsRef}
          indexId={props.indexId}
          requestData={props.requestData}
          rowData={currentRowValue.value?.data ?? {}}
          on-hide-self={handleHideRemarkTip}
          on-update={handleUpdateRemark}
        />
      </div>
    );
  },
});
