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
  defineComponent,
  nextTick,
  onMounted,
  inject,
  onUnmounted,
  provide,
  ref as deepRef,
  watch,
  type Ref,
} from 'vue';
import { useI18n } from 'vue-i18n';

import { Checkbox, Exception, Loading, PopConfirm, Tree } from 'bkui-vue';
import { BkCheckboxGroup } from 'bkui-vue/lib/checkbox';
import { incidentAlertAggregate } from 'monitor-api/modules/incident';

import { useIncidentInject } from '../utils';
import FilterSearchMain from './filter-search-main';

import type { IAggregationRoot, ITagInfoType, IUserName } from '../types';

import './handle-search.scss';

export default defineComponent({
  name: 'HandleSearch',
  props: {
    username: {
      type: Object as () => IUserName,
      default: () => ({}),
    },
    tagInfo: {
      type: Object as () => ITagInfoType,
      default: () => ({}),
    },
    topoNodeId: {
      type: String,
      default: '',
    },
  },
  emits: ['nodeClick', 'filterSearch', 'nodeExpand', 'treeScroll', 'changeSpace'],
  setup(props, { emit }) {
    const { t } = useI18n();
    const bkzIds = inject<Ref<string[]>>('bkzIds');
    const alertAggregateData = deepRef<IAggregationRoot[]>([]);
    const listLoading = deepRef(false);
    const isShowDropdown = deepRef(false);
    const cacheAggregateData = deepRef<string[]>([]);
    const bkBizIds = deepRef<number[]>([]);
    const queryString = deepRef('');
    const treeRef = deepRef(null);
    provide('alertAggregateDataList', alertAggregateData);
    const aggregateBysList = [
      {
        name: t('节点层级'),
        key: 'node_level',
      },
      {
        name: t('节点类型'),
        key: 'node_type',
      },
      {
        name: t('告警名称'),
        key: 'alert_name',
      },
      {
        name: t('节点名称'),
        key: 'node_name',
      },
      {
        name: t('监控数据项'),
        key: 'metric_name',
      },
    ];
    const aggregateBys = deepRef(['alert_name', 'node_name']);
    const incidentId = useIncidentInject();
    const filterListHandle = (key: string) => {
      if (aggregateBys.value.includes(key)) {
        aggregateBys.value = aggregateBys.value.filter(item => item !== key);
      } else {
        aggregateBys.value.push(key);
      }
    };
    const treeStatus = deepRef(true);
    watch(
      () => props.topoNodeId,
      () => {
        treeStatus.value = false;
        setTimeout(() => {
          treeStatus.value = true;
        }, 1);
      }
    );
    watch(
      () => props.username,
      () => {
        getIncidentAlertAggregate();
      }
    );
    const searchHeadFn = () => (
      <div class='handle-search-top'>
        <FilterSearchMain
          tagInfo={props.tagInfo}
          onChangeSpace={(val: number[], isErr: boolean) => {
            bkBizIds.value = val;
            !isErr && getIncidentAlertAggregate();
            emit('changeSpace', bkBizIds.value);
          }}
          onSearch={(val: string, validate: boolean) => {
            queryString.value = val;
            validate && getIncidentAlertAggregate();
          }}
        />
      </div>
    );
    const handleIsRoot = data => {
      return data.map(item => {
        item.isOpen = item.is_root || item.is_feedback_root;
        if (item.children) {
          handleIsRoot(item.children);
        }
        return item;
      });
    };
    const getIncidentAlertAggregate = () => {
      listLoading.value = true;
      const params = {
        id: incidentId.value,
        aggregate_bys: aggregateBys.value,
        bk_biz_ids: bkzIds.value,
        query_string: queryString.value,
      };
      props.username.id !== 'all' && Object.assign(params, { username: props.username.id });
      incidentAlertAggregate(params)
        .then(res => {
          const list: IAggregationRoot[] = Object.values(res);
          alertAggregateData.value = list.filter(item => item.count !== 0);
          const isHasRoot = alertAggregateData.value.findIndex(item => item.is_root || item.is_feedback_root) !== -1;
          const isHasChildInd = alertAggregateData.value.findIndex(item => item.children?.length);
          if (alertAggregateData.value.length !== 0) {
            isHasRoot
              ? handleIsRoot(alertAggregateData.value)
              : (alertAggregateData.value[isHasChildInd].isOpen = true);
          }
          emit('filterSearch', params);
          emit('nodeExpand', alertAggregateData.value);
        })
        .catch(err => {
          console.log(err);
        })
        .finally(() => {
          listLoading.value = false;
        });
    };
    /** 节点icon映射 */
    const treeShowIcon = {
      /** 状态icon列表 */
      status: {
        ABNORMAL: 'mind-fill',
        RECOVERED: 'mc-check-fill',
        CLOSED: 'mc-expired',
      },
      /** 节点层级icon列表 */
      node_level: {
        service: 'default',
        host_platform: 'menu-performance',
        data_center: 'mc-data-center',
      },
      /** 告警名称icon列表 */
      alert_name: {},
      /** 节点名称icon列表 */
      node_name: {},
      /** 节点类型icon列表 */
      node_type: {},
      /** 监控数据项icon列表 */
      metricName: {},
    };

    /** 节点树icon展示 */
    const getPrefixIcon = (item, renderType) => {
      const { level_name, id } = item;
      const {
        __attr__: { isOpen, hasChild },
      } = item;
      if (renderType === 'node_action') {
        /** 有根因存在的节点icon标红 */
        if ((item.is_root || item.is_feedback_root) && hasChild) {
          const icon = isOpen ? 'down' : 'right';
          return (
            <span class={['custom-node', { 'open-node': isOpen }]}>
              <i class={`icon-monitor icon-mc-arrow-${icon} ${item.is_root ? 'root' : 'feed'}`} />
            </span>
          );
        }
        return 'default';
      }
      let showIcon = 'Pod';
      /** 告警名称icon */
      if (level_name === 'alert_name') {
        showIcon = 'gaojing1';
      }
      if (['status', 'node_level'].includes(level_name)) {
        showIcon = treeShowIcon[level_name][id];
      }
      return <i class={`icon-monitor icon-${showIcon} tree-icon ${level_name} ${id}`} />;
    };
    const handleFilter = () => {
      getIncidentAlertAggregate();
      cacheAggregateData.value = JSON.parse(JSON.stringify(aggregateBys.value));
    };
    const cancelFilter = () => {
      aggregateBys.value = cacheAggregateData.value;
    };
    const nodeClick = item => {
      if (item.level_name !== 'status') {
        // selectedNode.value = item;
        emit('nodeClick', item);
      }
    };
    const nodeCollapse = item => {
      const handleData = scopedData => {
        scopedData.map(ele => {
          if (ele.isOpen) {
            ele.isOpen = false;
            ele.children?.length > 0 && handleData(ele.children);
          }
        });
      };
      if (item.level_name === 'status' && item.children.length > 0) {
        handleData(item.children);
      }
      item.isOpen = false;
      handleData(item.children);
      /** 如果都收起的情况下，默认展开第一个 */
      // const isAllExpand = alertAggregateData.value.findIndex(item => item.isOpen) === -1;
      // if (isAllExpand) {
      //   const isHasChildInd = alertAggregateData.value.findIndex(item => item.children?.length);
      //   alertAggregateData.value[isHasChildInd].isOpen = true;
      // }
      emit('nodeExpand', alertAggregateData.value);
    };
    const nodeExpand = item => {
      item.isOpen = true;
      emit('nodeExpand', alertAggregateData.value);
    };
    const treeFn = () => {
      if (alertAggregateData.value.length === 0) {
        return (
          <Exception
            class='tree-empty'
            type='search-empty'
          >
            <span class='text-tips'>{t('搜索结果为空')}</span>
            <div class='text-wrap'>
              <span class='text-row'>{t('请调整筛选条件')}</span>
            </div>
          </Exception>
        );
      }
      return (
        <Tree
          class='search-tree-list'
          v-slots={{
            node: (data: any) => {
              const { level_name, name } = data;
              let title = '';
              if (level_name !== 'status') {
                const curNode = aggregateBysList.filter(item => item.key === level_name);
                title = `${curNode[0]?.name}: ${name}`;
              }
              return <span title={title}>{name}</span>;
            },
            nodeAppend: (node: any) => {
              const {
                __attr__: { isOpen, hasChild },
                is_root,
                is_feedback_root,
                count,
              } = node;
              const isShow = !isOpen || (!hasChild && isOpen);
              const hasRoot = is_root || is_feedback_root;
              return (
                <span class='node-append-main'>
                  {hasRoot && isShow && <span class={is_root ? 'node-root' : 'node-root-feed'}>{t('根因')}</span>}
                  <span class='node-append'>{count}</span>
                </span>
              );
            },
          }}
          auto-open-parent-node={false}
          data={alertAggregateData.value}
          label='name'
          level-line='solid 1px #DCDEE5'
          nodeKey={'id'}
          prefix-icon={getPrefixIcon}
          virtual-render
          onNodeClick={nodeClick}
          onNodeCollapse={nodeCollapse}
          onNodeExpand={nodeExpand}
        />
      );
    };
    const showName = () => {
      if (['all', window.user_name, window.username].includes(props.username.id)) {
        return `${props.username.name}${t('的告警')}`;
      }
      return `${props.username.name}${t('处理的告警')}`;
    };
    const scrollChange = e => {
      const scrollTop = e.target?.scrollTop;
      emit('treeScroll', scrollTop);
    };
    watch(
      () => bkzIds.value,
      val => {
        val.length > 0 && getIncidentAlertAggregate();
      },
      { immediate: true }
    );
    onMounted(() => {
      // getIncidentAlertAggregate();
      cacheAggregateData.value = JSON.parse(JSON.stringify(aggregateBys.value));
      nextTick(() => {
        treeRef.value?.addEventListener('scroll', scrollChange, true);
      });
    });
    onUnmounted(() => {
      treeRef.value?.removeEventListener('scroll', scrollChange, true);
    });
    return {
      t,
      searchHeadFn,
      filterListHandle,
      isShowDropdown,
      listLoading,
      treeFn,
      aggregateBysList,
      aggregateBys,
      handleFilter,
      cancelFilter,
      showName,
      treeRef,
      treeStatus,
    };
  },
  render() {
    return (
      <div class='handle-search'>
        {this.searchHeadFn()}
        <div class='handle-search-list'>
          <div class='search-head'>
            {this.showName()}
            <PopConfirm
              width='148'
              v-slots={{
                content: () => (
                  <div class='drop-main'>
                    <div class='drop-main-title'>{this.t('设置聚合维度')}</div>
                    <BkCheckboxGroup
                      class='drop-main-list'
                      v-model={this.aggregateBys}
                    >
                      {this.aggregateBysList.map(item => (
                        <Checkbox
                          key={item.key}
                          class='drop-item drop-item-checkbox'
                          disabled={this.aggregateBys.length === 1 && this.aggregateBys.includes(item.key)}
                          label={item.key}
                          size={'small'}
                        >
                          {item.name}
                        </Checkbox>
                      ))}
                    </BkCheckboxGroup>
                  </div>
                ),
              }}
              placement={'bottom-start'}
              trigger='click'
              onCancel={this.cancelFilter}
              onConfirm={this.handleFilter}
            >
              <i class='icon-monitor icon-shezhi1 search-head-icon' />
            </PopConfirm>
          </div>
          <Loading
            class='search-tree-loading'
            loading={this.listLoading}
          >
            <div
              ref='treeRef'
              class='search-tree'
            >
              {this.treeStatus && this.treeFn()}
            </div>
          </Loading>
        </div>
      </div>
    );
  },
});
