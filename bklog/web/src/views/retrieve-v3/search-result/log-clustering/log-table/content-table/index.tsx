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
  type PropType,
  shallowRef,
  onMounted,
  onBeforeUnmount,
} from 'vue';
import TextHighlight from 'vue-text-highlight';

import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import { RetrieveUrlResolver } from '@/store/url-resolver';
import BkUserSelector from '@blueking/user-selector';
import { bkMessage } from 'bk-magic-vue';
import { orderBy } from 'lodash-es';
import tippy from 'tippy.js';
import { useRoute, useRouter } from 'vue-router/composables';

import ClusterEventPopover from './cluster-popover';
import RemarkEditTip from './remark-edit-tip';
import { getConditionRouterParams } from './utils';
import $http from '@/api';

// import aiImageUrl from "@/images/rowAiNew.svg";
import type { TableInfo } from '../index';
import type { LogPattern } from '@/services/log-clustering';

import './index.scss';

export default defineComponent({
  name: 'ContentTable',
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
    tableInfo: {
      type: Object as PropType<TableInfo>,
      default: () => {},
    },
    index: {
      type: Number,
      default: 0,
    },
    indexId: {
      type: String,
      require: true,
    },
    filterSortMap: {
      type: Object as PropType<{
        sort: Record<string, string>;
        filter: Record<string, string[]>;
      }>,
      default: () => ({}),
    },
    widthList: {
      type: Array<string>,
      default: () => [],
    },
    displayMode: {
      type: String,
      default: 'group',
    },
  },
  setup(props, { emit, expose }) {
    const { t } = useLocale();
    const store = useStore();
    const route = useRoute();
    const router = useRouter();

    const headRowRef = ref<HTMLElement>();
    const remarkTipsRef = ref<any>(null);
    const tableWraperRef = ref<HTMLElement>();
    const currentRowId = ref(0);
    const cacheExpandStr = ref<any[]>([]); // 展示pattern按钮数组
    const isOpen = ref(props.index === 0); // 是否展开
    const tableData = ref<LogPattern[]>([]);

    const localTableData = shallowRef<LogPattern[]>([]);

    const showTableList = computed(() => isOpen.value || isFlattenMode.value || !props.requestData?.group_by.length);

    const showYOY = computed(() => props.requestData?.year_on_year_hour >= 1);
    const isLimitExpandView = computed(() => store.state.storage[BK_LOG_STORAGE.IS_LIMIT_EXPAND_VIEW]);
    /** 获取当前编辑操作的数据 */
    const currentRowValue = computed(() => tableData.value.find(item => item.id === currentRowId.value));
    const showGounpBy = computed(() => props.requestData?.group_by.length > 0 && props.displayMode === 'group');
    const isFlattenMode = computed(() => props.requestData?.group_by.length > 0 && props.displayMode !== 'group');
    const groupValueList = computed(() => {
      if (props.requestData?.group_by.length && props.tableInfo?.group.length) {
        return props.requestData.group_by.map((item, index) => `${item}=${props.tableInfo.group[index]}`);
      }
      return [];
    });
    // const isAiAssistanceActive = computed(
    //   () => store.getters.isAiAssistantActive
    // );

    let outerSCrollLeft = 0;
    let popoverInstance: any = null;
    let remarkPopoverTimer: NodeJS.Timeout;
    const pageSize = 100;
    let offset = 0;

    const isExternal = window.IS_EXTERNAL === true;

    watch(
      () => props.widthList,
      () => {
        if (props.widthList.length) {
          let widthList: string[] = [];
          if (!props.requestData?.group_by.length || isFlattenMode.value) {
            widthList = props.widthList;
          } else {
            widthList = props.widthList.slice(1, props.widthList.length - 1);
          }
          const columns = Array.from(headRowRef.value?.querySelectorAll('th') || []);
          if (columns.length) {
            columns.forEach((item: any, index) => {
              item.style.width = widthList[index];
            });
          }
        }
      },
      {
        immediate: true,
      },
    );

    watch(
      () => props.tableInfo?.dataList,
      () => {
        localTableData.value = structuredClone(props.tableInfo.dataList);
        if (localTableData.value.length > pageSize) {
          // 分页
          tableData.value = props.tableInfo.dataList.slice(0, pageSize);
          return;
        }

        tableData.value = props.tableInfo.dataList;
      },
      {
        immediate: true,
      },
    );

    watch(
      () => [props.filterSortMap, isOpen.value],
      () => {
        if (!isOpen.value) {
          return;
        }

        const sortObj = Object.entries(props.filterSortMap.sort).find(item => !!item[1]);
        let dataList = structuredClone(localTableData.value);
        if (sortObj) {
          // 排序
          const [field, order] = sortObj;
          if (order !== 'none') {
            dataList = orderBy(dataList, [field], order as any);
          }
        }
        const owners = props.filterSortMap.filter.owners;
        if (owners.length) {
          // 过滤责任人
          if (owners.length === 1 && owners[0] === 'no_owner') {
            dataList = dataList.filter(item => !!item.owners.length);
          } else {
            const ownersMap = owners.reduce<Record<string, boolean>>(
              (map, item) => Object.assign(map, { [item]: true }),
              {},
            );
            dataList = dataList.filter(item => item.owners.some(item => !!ownersMap[item]));
          }
        }
        const remark = props.filterSortMap.filter.remark;
        if (remark.length) {
          // 过滤备注
          const isRemarked = remark[0] === 'remarked';
          dataList = dataList.filter(item => (isRemarked ? item.remark.length > 0 : !item.remark.length));
        }
        tableData.value = dataList;
      },
      {
        deep: true,
      },
    );

    watch(
      () => [showGounpBy.value, isFlattenMode.value],
      () => {
        offset = 0;
      },
    );

    watch(isOpen, () => {
      if (isOpen.value) {
        setTimeout(() => {
          tableWraperRef.value.scrollLeft = outerSCrollLeft;
        });
      }
    });

    const updateTableRowData = (id: number, key: string, value: any) => {
      const row = tableData.value.find(item => item.id === id);
      if (row) {
        row[key] = value;
      }
      const localRow = localTableData.value.find(item => item.id === id);
      if (localRow) {
        localRow[key] = value;
      }
    };

    const getHeightLightList = (str: string) => str.match(/#.*?#/g) || [];

    const handleShowWhole = (index: number) => {
      cacheExpandStr.value.push(index);
    };

    const handleHideWhole = (index: number) => {
      cacheExpandStr.value = cacheExpandStr.value.map(item => item !== index);
    };

    const handleMenuBatchClick = (row, isLink = true) => {
      const additionList: any[] = [];
      const groupBy = props.requestData?.group_by;
      if (groupBy.length) {
        groupBy.forEach((el, index) => {
          additionList.push({
            field: el,
            operator: 'is',
            value: row.group[index],
            isLink,
          });
        });
      }
      additionList.push({
        field: `__dist_${props.requestData?.pattern_level}`,
        operator: 'is',
        value: row.signature.toString(),
        isLink,
      });

      // 聚类下钻只能使用ui模式
      store.commit('updateIndexItem', { search_mode: 'ui' });
      // 新开页打开首页是原始日志，不需要传聚类参数，如果传了则会初始化为聚类
      store.commit('updateClusterParams', null);
      store.dispatch('setQueryCondition', additionList).then(([newSearchList, searchMode, isNewSearchPage]) => {
        if (isLink) {
          const openUrl = getConditionRouterParams(newSearchList, searchMode, isNewSearchPage, { tab: 'origin' });
          window.open(openUrl, '_blank');
          // 新开页后当前页面回填聚类参数
          store.commit('updateClusterParams', props.requestData);
          return;
        } else {
          emit('show-change', 'origin');
        }

        const query = { ...route.query };

        const resolver = new RetrieveUrlResolver({
          clusterParams: store.state.clusterParams,
          addition: additionList,
          searchMode,
        });

        Object.assign(query, resolver.resolveParamsToUrl());

        router.push({
          params: { ...route.params },
          query: { ...query, tab: 'origin', clusterParams: undefined },
        });

        // 触发索引集查询
        nextTick(() => {
          store.dispatch('requestIndexSetQuery');
        });
      });
    };

    const handleMenuClick = (row, isLink = false) => {
      handleMenuBatchClick(row, isLink);
      emit('show-origin-log');
    };

    const getLimitState = (index: number) => {
      if (isLimitExpandView.value) return false;
      return !cacheExpandStr.value.includes(index);
    };

    /** 将分组的数组改成对像 */
    const getGroupsValue = group => {
      if (!props.requestData?.group_by.length) return {};
      return props.requestData.group_by.reduce((acc, cur, index) => {
        acc[cur] = group?.[index] ?? '';
        return acc;
      }, {});
    };

    // 设置负责人
    const handleChangePrincipal = (val: null | string[], row: LogPattern) => {
      currentRowId.value = row.id;
      // 当创建告警策略开启时，不允许删掉最后一个责任人
      if (row.strategy_enabled && !val.length) {
        bkMessage({
          theme: 'error',
          message: t('删除失败，开启告警时，需要至少一个责任人'),
        });
        return;
      }
      $http
        .request('/logClustering/setOwner', {
          params: {
            index_set_id: props.indexId,
          },
          data: {
            signature: currentRowValue.value?.signature,
            owners: val ?? row.owners,
            origin_pattern: currentRowValue.value?.origin_pattern,
            groups: getGroupsValue(row.group),
          },
        })
        .then(res => {
          if (res.result) {
            const { owners } = res.data;
            updateTableRowData(row.id, 'owners', owners);
            bkMessage({
              theme: 'success',
              message: t('操作成功'),
            });
          }
        });
    };

    const changeStrategy = (enabled: boolean, row: LogPattern) => {
      currentRowId.value = row.id;
      $http
        .request('/logClustering/updatePatternStrategy', {
          params: {
            index_set_id: props.indexId,
          },
          data: {
            signature: currentRowValue.value?.signature,
            origin_pattern: currentRowValue.value?.origin_pattern,
            strategy_enabled: enabled,
            groups: getGroupsValue(row.group),
          },
        })
        .then(res => {
          if (res.result) {
            const { strategy_id } = res.data;
            bkMessage({
              theme: 'success',
              message: t('操作成功'),
            });
            updateTableRowData(row.id, 'strategy_id', strategy_id);
            updateTableRowData(row.id, 'strategy_enabled', enabled);
          }
        });
    };

    const handleStrategyInfoClick = row => {
      currentRowId.value = row.id;
      window.open(
        `${window.MONITOR_URL}/?bizId=${store.state.bkBizId}#/strategy-config/detail/${row.strategy_id}`,
        '_blank',
      );
    };

    const remarkContent = remarkList => {
      if (!remarkList.length) return '--';
      const maxTimestamp = remarkList.reduce((pre, cur) => {
        return cur.create_time > pre.create_time ? cur : pre;
      }, remarkList[0]);
      return maxTimestamp.remark;
    };

    const handleHideRemarkTip = () => {
      popoverInstance?.hide();
    };

    const handleHoverRemarkIcon = (e: any, row: LogPattern) => {
      currentRowId.value = row.id;
      clearTimeout(remarkPopoverTimer);
      remarkPopoverTimer = setTimeout(() => {
        if (!popoverInstance) {
          popoverInstance = tippy(e.target, {
            appendTo: () => document.body,
            content: remarkTipsRef.value.tipRef,
            allowHTML: true,
            arrow: true,
            theme: 'light remark-edit-tip-popover',
            sticky: true,
            maxWidth: 340,
            // duration: [500, 0],
            offset: [0, 5],
            interactive: true,
            placement: 'top',
            onHidden: () => {
              popoverInstance?.destroy();
              popoverInstance = null;
            },
          });
        }
        popoverInstance.show();
      }, 500);
    };

    const handleUpdateRemark = (remark: LogPattern['remark']) => {
      updateTableRowData(currentRowValue.value.id, 'remark', remark);
    };

    const handleAddSearch = (e: Event) => {
      e.stopPropagation();
      const addConditions = props.requestData?.group_by.map((item, index) => ({
        field: item,
        operator: '=',
        value: [props.tableInfo.group[index]],
      }));
      store.dispatch('setQueryCondition', addConditions);
    };

    const handleBottomAppendList = () => {
      offset += pageSize;
      tableData.value.push(...localTableData.value.slice(offset, offset + pageSize));
    };

    const handleGlobalwheel = (e: any) => {
      e.preventDefault();
      if (
        tableWraperRef.value.clientHeight + tableWraperRef.value.scrollTop < tableWraperRef.value.scrollHeight &&
        tableWraperRef.value.scrollTop > 0
      ) {
        e.stopPropagation();
      }

      if (!showGounpBy.value) {
        return;
      }

      if (e.deltaY !== 0) {
        tableWraperRef.value.scrollTop += e.deltaY;
      }
    };

    const handleGlobalScroll = (e: any) => {
      if (!showGounpBy.value) {
        return;
      }
      const { scrollHeight, clientHeight, scrollTop } = e.target;
      if (scrollHeight === clientHeight) {
        return;
      }

      if (clientHeight + scrollTop === scrollHeight) {
        handleBottomAppendList();
      }
    };

    onMounted(() => {
      tableWraperRef.value.addEventListener('wheel', handleGlobalwheel, {
        passive: false,
      });
      tableWraperRef.value.addEventListener('scroll', handleGlobalScroll);
    });

    onBeforeUnmount(() => {
      tableWraperRef.value.removeEventListener('wheel', handleGlobalwheel);
      tableWraperRef.value.removeEventListener('scroll', handleGlobalScroll);
    });

    expose({
      scroll: (scrollLeft: number) => {
        outerSCrollLeft = scrollLeft;
        tableWraperRef.value.scrollLeft = scrollLeft;
      },
      bottomAppendList: () => {
        if (showGounpBy.value && !isFlattenMode.value) {
          return;
        }

        if (offset > localTableData.value.length) {
          return;
        }

        handleBottomAppendList();
      },
    });

    return () => (
      <div
        style={{
          borderLeft: showGounpBy.value ? '1px solid #dcdee5' : 'none',
          borderRight: showGounpBy.value ? '1px solid #dcdee5' : 'none',
        }}
        class='log-content-table-main'
        v-show={tableData.value.length > 0}
      >
        {showGounpBy.value && (
          <div
            class='collpase-main'
            on-click={() => {
              isOpen.value = !isOpen.value;
            }}
          >
            <div class={{ 'collapse-icon': true, 'is-open': isOpen.value }}>
              <log-icon type='arrow-down-filled-2' />
            </div>
            <div
              class='group-value-display'
              v-bk-overflow-tips={{
                content: groupValueList.value.join(' , '),
              }}
            >
              {groupValueList.value.map((value, index) => (
                <div class='value-item'>
                  <span>{value}</span>
                  {groupValueList.value.length > 1 && index < groupValueList.value.length - 1 && (
                    <div class='split-line'></div>
                  )}
                </div>
              ))}
            </div>
            <div
              class='add-search'
              v-bk-tooltips={t('添加为检索条件')}
              on-click={handleAddSearch}
            >
              <log-icon type='sousuo-' />
            </div>
            <div class='count-display'>（{t('共有 {0} 条数据', [localTableData.value.length])}）</div>
          </div>
        )}
        {!showGounpBy.value && (
          <div class='list-count-main'>
            <i18n path='共有 {0} 条数据'>
              <span style='font-weight:700'>{localTableData.value.length}</span>
            </i18n>
          </div>
        )}
        <div
          ref={tableWraperRef}
          style={{
            display: isOpen.value || showTableList.value ? 'block' : 'none',
          }}
          class={{
            'log-content-table-wraper': true,
            'is-scroll-mode': showGounpBy.value,
          }}
        >
          <table class='log-content-table'>
            <thead class='hide-header'>
              <tr ref={headRowRef}>
                <th style='width: 125px'>数据指纹</th>
                <th style={{ width: `${props.tableColumnWidth.number}px` }}>数量</th>
                <th style={{ width: `${props.tableColumnWidth.percentage}px` }}>占比</th>
                {showYOY.value && (
                  <th
                    style={{
                      width: `${props.tableColumnWidth.year_on_year_count}px`,
                    }}
                  >
                    同比数量
                  </th>
                )}
                {showYOY.value && (
                  <th
                    style={{
                      width: `${props.tableColumnWidth.year_on_year_percentage}px`,
                    }}
                  >
                    同比变化
                  </th>
                )}
                {isFlattenMode.value && props.requestData.group_by.map(item => <th style='width:100px'>{item}</th>)}
                <th style='minWidth:350px'>Pattern</th>
                <th style='width:200px'>责任人</th>
                {!isExternal && <th style='width:200px'>创建告警策略</th>}
                <th style='width:200px'>备注</th>
                {/* {isAiAssistanceActive.value && <th style="width:60px">ai</th>} */}
              </tr>
            </thead>
            <tbody>
              {showTableList.value &&
                tableData.value.map((row, rowIndex) => (
                  <tr>
                    <td>
                      <div class='signature-box'>
                        <div
                          class='signature'
                          v-bk-overflow-tips
                        >
                          {row.signature}
                        </div>
                        <div
                          class='new-finger'
                          v-show={row.is_new_class}
                        >
                          New
                        </div>
                      </div>
                    </td>
                    <td>
                      <bk-button
                        style='padding: 0px'
                        size='small'
                        theme='primary'
                        text
                        on-click={() => handleMenuBatchClick(row)}
                      >
                        {row.count}
                      </bk-button>
                    </td>
                    <td>
                      <bk-button
                        style='padding: 0px'
                        size='small'
                        theme='primary'
                        text
                        on-click={() => handleMenuBatchClick(row)}
                      >
                        {`${row.percentage.toFixed(2)}%`}
                      </bk-button>
                    </td>
                    {showYOY.value && (
                      <td>
                        <span style='padding-left:6px'>{row.year_on_year_count}</span>
                      </td>
                    )}
                    {showYOY.value && (
                      <td>
                        <div
                          style={{
                            color:
                              row.year_on_year_percentage < 0
                                ? '#2CAF5E'
                                : row.year_on_year_percentage === 0
                                  ? '#313238'
                                  : '#E71818',
                          }}
                          class='compared-change'
                        >
                          <span>{`${Math.abs(Number(row.year_on_year_percentage.toFixed(2)))}%`}</span>
                          {row.year_on_year_percentage !== 0 ? (
                            <log-icon
                              style='font-size: 16px;'
                              type={row.year_on_year_percentage < 0 ? 'down-4' : 'up-2'}
                            />
                          ) : (
                            <log-icon
                              style='font-size: 16px;'
                              type='--2'
                            />
                          )}
                        </div>
                      </td>
                    )}
                    {isFlattenMode.value &&
                      row.group.map(item => (
                        <td>
                          <div
                            class='dynamic-column'
                            v-bk-overflow-tips
                          >
                            {item}
                          </div>
                        </td>
                      ))}
                    <td>
                      <div class={['pattern-content', { 'is-limit': getLimitState(rowIndex) }]}>
                        <ClusterEventPopover
                          indexId={props.indexId}
                          rowData={row}
                          on-event-click={isLink => handleMenuClick(row, isLink)}
                          on-open-cluster-config={() => emit('open-cluster-config')}
                        >
                          <text-highlight
                            style=''
                            class='monospace-text'
                            queries={getHeightLightList(row.pattern)}
                          >
                            {row.pattern ? row.pattern : t('未匹配')}
                          </text-highlight>
                        </ClusterEventPopover>
                        {!isLimitExpandView.value && (
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
                        )}
                      </div>
                    </td>
                    <td style='padding-left: 0px'>
                      <div
                        // 组件样式有问题，暂时这样处理
                        style={{ padding: isExternal && '5px 0' }}
                        class='principal-main'
                        v-bk-tooltips={{
                          placement: 'top',
                          content: row.owners.join(', '),
                          delay: 300,
                          disabled: !row.owners.length,
                        }}
                      >
                        {!isExternal ? (
                          <bk-user-selector
                            class='principal-input'
                            api={window.BK_LOGIN_URL}
                            empty-text={t('无匹配人员')}
                            placeholder='--'
                            value={row.owners}
                            multiple
                            on-change={val => handleChangePrincipal(val, row)}
                          />
                        ) : (
                          <bk-tag-input
                            style='width: 100%'
                            class='principal-tag-input'
                            clearable={false}
                            placeholder='--'
                            value={row.owners}
                            allow-create
                            has-delete-icon
                            on-blur={() => handleChangePrincipal(null, row)}
                            on-change={value => {
                              row.owners = value;
                            }}
                          />
                        )}
                      </div>
                    </td>
                    {!isExternal && (
                      <td>
                        <div class='create-strategy-main'>
                          {row.owners.length > 0 ? (
                            <div class='is-able'>
                              <bk-switcher
                                theme='primary'
                                value={row.strategy_enabled}
                                on-change={val => changeStrategy(val, row)}
                              />
                              {row.strategy_id > 0 && (
                                <span on-click={() => handleStrategyInfoClick(row)}>
                                  <log-icon
                                    style='font-size: 16px'
                                    type='audit'
                                  />
                                </span>
                              )}
                            </div>
                          ) : (
                            <bk-switcher
                              v-bk-tooltips={t('暂无配置责任人，无法自动创建告警策略')}
                              theme='primary'
                              value={row.strategy_enabled}
                              disabled
                            />
                          )}
                        </div>
                      </td>
                    )}
                    <td style='padding-right: 8px;'>
                      <div
                        class='remark-column'
                        on-mouseenter={e => handleHoverRemarkIcon(e, row)}
                        on-mouseleave={() => clearTimeout(remarkPopoverTimer)}
                      >
                        {remarkContent(row.remark)}
                      </div>
                    </td>
                    {/* {isAiAssistanceActive.value && (
                      <td>
                        <div class="ai-assist-column">
                          <span on-click={() => emit("open-ai", row, rowIndex)}>
                            <log-icon class="ai-icon" type="ai-mofabang" />
                            <img class="ai-icon-active" src={aiImageUrl} />
                          </span>
                        </div>
                      </td>
                    )} */}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
        <RemarkEditTip
          ref={remarkTipsRef}
          indexId={props.indexId}
          requestData={props.requestData}
          rowData={currentRowValue.value}
          on-hide-self={handleHideRemarkTip}
          on-update={handleUpdateRemark}
        />
      </div>
    );
  },
});
