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
import { computed, defineComponent, inject, nextTick, onMounted, Ref, ref, watch } from 'vue';

import { Exception, Input, Loading, Popover, Tree } from 'bkui-vue';
import { CogShape } from 'bkui-vue/lib/icon';
import dayjs from 'dayjs';
import { useIncidentInject } from '../utils';
import { incidentOperationTypes } from '../../../../monitor-api/modules/incident';
import { IIncident } from '../types';
import { renderMap } from './process';

import './failure-process.scss';

export default defineComponent({
  name: 'FailureProcess',
  props: {
    steps: {
      type: Array,
      default: () => [],
    },
  },
  emits: ['choose-operation'],
  setup(props, { emit }) {
    const failureProcessListRef = ref<HTMLDivElement>();
    const renderStep = () => {};
    const handleSetting = () => {};
    const queryString = ref<string>('');
    const hidePopover = ref<boolean>(false);
    // const operations = ref([]);
    const operations = inject<Ref>('operationsList');
    const incidentDetail = inject<Ref<IIncident>>('incidentDetail');
    const operationTypes = ref([]);
    const operationTypeMap = ref({});
    const checkedNodes = ref([]);
    const tableLoading = ref<boolean>(false);
    const operationId = ref<string>('');
    const incidentId = useIncidentInject();
    /** 时间过滤 */
    const formatterTime = (time: number | string): string => {
      if (!time) return '--';
      if (typeof time !== 'number') return time;
      if (time.toString().length < 13) return dayjs(time * 1000).format('YYYY-MM-DD HH:mm:ss');
      return dayjs(time).format('YYYY-MM-DD HH:mm:ss');
    };
    const handleHide = () => {
      hidePopover.value = true;
    };

    const handleChecked = (select, filterSelect) => {
      const result = select.filter(item => !filterSelect.find(filter => filter.id === item.id));
      checkedNodes.value = result.map(item => item.id);
    };
    /** 前端搜索 */
    const searchOperations = computed(() => {
      let result = operations.value;
      if (checkedNodes.value.length > 0) {
        result = operations.value.filter(operation => checkedNodes.value.includes(operation.operation_type));
      }
      if (queryString.value !== '') {
        result = operations.value.filter(
          operation => operation.str.toUpperCase().indexOf(queryString.value.toUpperCase()) > -1
        );
      }
      return result;
    });

    // const getIncidentOperations = () => {
    //   incidentOperations({
    //     incident_id: incidentDetailData.value?.incident_id
    //   })
    //     .then(res => {
    //       res.forEach(item => {
    //         const { operation_type, extra_info } = item;
    //         item.str = replaceStr(typeTextMap[operation_type], extra_info);
    //       });
    //       operations.value = res;
    //       // console.log(res);
    //     })
    //     .catch(err => {
    //       console.log(err);
    //     });
    // };
    const getIncidentOperationTypes = () => {
      tableLoading.value = true;
      incidentOperationTypes({
        incident_id: incidentDetail.value?.incident_id,
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
        .finally(() => (tableLoading.value = false));
    };
    const handleClearSearch = () => {
      queryString.value = '';
      checkedNodes.value = [];
    };
    const handleOperationId = (e, operation) => {
      e.stopPropagation();
      operations.value.filter(item => Object.assign(item, { isActive: item.id === operation.id }));
      operationId.value = operation.id;
      emit('choose-operation', operation.id, operation);
    };
    watch(
      () => searchOperations.value,
      val => {
        nextTick(() => {
          const ind = val.findIndex(item => item.isActive);
          if (ind !== -1) {
            const element = failureProcessListRef.value.children[ind];
            failureProcessListRef.value.scrollTo({
              top: element.offsetTop - 55,
              behavior: 'smooth',
            });
          }
        });
      },
      { immediate: true, deep: true }
    );

    onMounted(() => {
      getIncidentOperationTypes();
      // getIncidentOperations();
    });
    return {
      queryString,
      operationTypeMap,
      tableLoading,
      checkedNodes,
      searchOperations,
      operations,
      operationTypes,
      renderStep,
      handleHide,
      handleClearSearch,
      formatterTime,
      handleChecked,
      handleSetting,
      operationId,
      handleOperationId,
      failureProcessListRef,
      incidentId,
      incidentDetail,
    };
  },
  render() {
    return (
      <div class='failure-process'>
        <div class='failure-process-search'>
          <Input
            v-model={this.queryString}
            placeholder={this.$t('搜索 流转记录')}
          ></Input>

          <Popover
            width='242'
            extCls='failure-process-search-setting-popover'
            arrow={false}
            placement='bottom-center'
            theme='light'
            trigger='click'
            onAfterHidden={this.handleHide}
          >
            {{
              default: (
                <span
                  class='failure-process-search-setting'
                  v-bk-tooltips={{ content: this.$t('设置展示类型') }}
                  onClick={this.handleSetting}
                >
                  <CogShape></CogShape>
                </span>
              ),
              content: (
                <div class='failure-process-search-setting-tree'>
                  <Tree
                    children='operation_types'
                    data={this.operationTypes}
                    expand-all={true}
                    indent={24}
                    label='name'
                    node-key='id'
                    prefix-icon={true}
                    selectable={false}
                    selected={this.checkedNodes}
                    show-checkbox={true}
                    showNodeTypeIcon={false}
                    onNodeChecked={this.handleChecked}
                  >
                    {{
                      default: ({ data, attributes }) => {
                        return (
                          <span class='failure-process-search-setting-tree-node'>
                            {attributes.parent && (
                              <i
                                class={[
                                  'icon-monitor',
                                  data.id.startsWith('alert') ? 'icon-gaojing1' : 'icon-mc-fault',
                                ]}
                              ></i>
                            )}
                            {data.name}
                            {data.isAddLine ? <span class='node-line'></span> : ''}
                          </span>
                        );
                      },
                    }}
                  </Tree>
                </div>
              ),
            }}
          </Popover>
        </div>
        <Loading loading={this.tableLoading}>
          {this.searchOperations.length ? (
            <ul
              ref='failureProcessListRef'
              class='failure-process-list'
            >
              {this.searchOperations.map((operation, index) => {
                return (
                  <li
                    key={`${operation.operation_type}_${index}`}
                    class={['failure-process-item', { active: operation?.isActive }]}
                    onClick={(e) => this.handleOperationId(e, operation)}
                  >
                    <div class='failure-process-item-avatar'>
                      {index !== this.searchOperations.length - 1 && <span class='failure-process-list-line'></span>}
                      <i
                        class={[
                          'icon-monitor item-icon',
                          operation.operation_class !== 'system'
                            ? operation.operation_type.startsWith('alert')
                              ? 'icon-gaojing1'
                              : 'icon-mc-fault'
                            : 'icon-mc-user-one',
                        ]}
                      ></i>
                    </div>
                    <div class='failure-process-item-content'>
                      <p>
                        <span class='failure-process-item-time'>{this.formatterTime(operation.create_time)}</span>
                        <span class='failure-process-item-title'>
                          {this.operationTypeMap[operation.operation_type] || '--'}
                        </span>
                      </p>
                      <p class='failure-process-item-flex'>
                        {renderMap[operation.operation_type]?.(operation, this.incidentId, this.incidentDetail.bk_biz_id) || '--'}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          ) : (
            <Exception
              description={
                this.checkedNodes.length || this.queryString !== '' ? this.$t('搜索数据为空') : this.$t('暂无数据')
              }
              scene='part'
              type='empty'
            >
              {this.checkedNodes.length || this.queryString !== '' ? (
                <span
                  class='link cursor'
                  onClick={this.handleClearSearch}
                >
                  {this.$t('清空筛选条件')}
                </span>
              ) : (
                ''
              )}
            </Exception>
          )}
        </Loading>
      </div>
    );
  },
});
