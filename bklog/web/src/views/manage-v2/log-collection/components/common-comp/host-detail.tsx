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

import { computed, defineComponent, ref, watch, nextTick, type PropType } from 'vue';

import { xssFilter } from '@/common/util';
import useLocale from '@/hooks/use-locale';

import { showMessage } from '../../utils';
import $http from '@/api';

import './host-detail.scss';

/**
 * 主机项状态类型
 */
type HostStatus = 'success' | 'failed' | 'running' | 'all';

/**
 * 主机项数据接口
 */
interface IHostItem {
  /** 主机ID */
  host_id: number;
  /** 实例ID */
  instance_id: string;
  /** 任务ID */
  task_id: string;
  /** IP地址 */
  ip: string;
  /** 状态：success-成功, failed-失败, running-运行中 */
  status: HostStatus | string;
}

/**
 * 日志分组项数据接口
 */
interface ILogItem {
  /** 对象ID */
  bk_obj_id: string;
  /** 对象名称 */
  bk_obj_name: string;
  /** 子项列表（主机列表） */
  child: IHostItem[];
  node_path: string;
}

/**
 * Tab项数据接口
 */
interface ITabItem {
  /** Tab键值 */
  key: HostStatus | string;
  /** Tab显示标签 */
  label: string;
  /** 数量 */
  count: number;
}

/**
 * 采集详情结果接口
 */
interface IDetailResult {
  /** 状态：SUCCESS-成功, FAILED-失败 */
  status?: 'SUCCESS' | 'FAILED';
}

/**
 * API响应数据接口
 */
interface IExecuteDetailsResponse {
  /** 日志详情（HTML字符串） */
  log_detail: string;
  /** 日志结果 */
  log_result: IDetailResult;
}

export default defineComponent({
  name: 'HostDetail',
  props: {
    /** 是否加载中 */
    loading: {
      type: Boolean,
      default: false,
    },
    /** 主机列表数据 */
    list: {
      type: Array as PropType<ILogItem[]>,
      default: () => [],
    },
    /** Tab列表数据 */
    tabList: {
      type: Array as PropType<ITabItem[]>,
      default: () => [],
    },
    collectorConfigId: {
      type: Number,
      default: 0,
    },
  },
  emits: ['retry'],

  setup(props, { emit }) {
    const { t } = useLocale();

    /** 当前激活的Tab键值 */
    const activeKey = ref<HostStatus | string>('all');
    /** 当前选中的主机项 */
    const currentItem = ref<IHostItem | null>(null);
    /** 详情加载状态 */
    const itemLoading = ref(false);
    /** 日志详情内容（HTML字符串） */
    const log = ref<string>('');
    /** 采集详情结果 */
    const detail = ref<IDetailResult>({});
    /** 日志内容容器的引用 */
    const logContentRef = ref<HTMLDivElement | null>(null);
    const activeName = ref([]);

    /**
     * 根据当前激活的Tab筛选显示列表
     * 当activeKey为'all'时返回全部，否则只返回匹配状态的主机项
     */
    const showList = computed<ILogItem[]>(() => {
      const { list } = props;
      if (activeKey.value === 'all') {
        return list;
      }
      // 筛选出包含匹配状态主机的分组，并更新分组中的child列表
      return list
        .map(item => {
          const childList = item.child.filter(child => child.status === activeKey.value);
          // 只返回包含匹配项的分组
          return childList.length > 0 ? { ...item, child: childList } : null;
        })
        .filter((item): item is ILogItem => item !== null);
    });

    /**
     * 切换tab时默认选中第一个item
     * 如果列表为空或第一个分组没有子项，则不执行任何操作
     */
    const setDefaultItem = (): void => {
      if (showList.value.length === 0) {
        return;
      }
      const firstGroup = showList.value[0];
      if (!firstGroup?.child || firstGroup.child.length === 0) {
        return;
      }
      const firstItem = firstGroup.child[0];
      if (firstItem) {
        handleItemClick(firstItem);
      }
    };

    /**
     * 切换Tab
     * @param item - Tab项数据
     */
    const handleTabClick = (item: ITabItem): void => {
      // 只有当Tab有数据时才允许切换
      if (item.count !== 0) {
        log.value = '';
        detail.value = {};
        activeKey.value = item.key;
      }
    };

    /**
     * 获取选中主机的采集详情
     * @param item - 主机项数据
     */
    const getItemDetail = (item: IHostItem): void => {
      // 校验必要参数
      if (!item?.instance_id || !item?.task_id) {
        showMessage(t('缺少必要参数'), 'error');
        return;
      }

      // 校验采集配置ID
      if (!props.collectorConfigId) {
        showMessage(t('采集配置ID不存在'), 'error');
        return;
      }

      itemLoading.value = true;
      $http
        .request('collect/executDetails', {
          params: {
            collector_id: props.collectorConfigId,
          },
          query: {
            instance_id: item.instance_id,
            task_id: item.task_id,
          },
        })
        .then((res: { result: boolean; data: IExecuteDetailsResponse }) => {
          if (res.result && res.data) {
            log.value = res.data.log_detail || '';
            detail.value = res.data.log_result || {};
            // log值变化会触发watch自动更新DOM
          } else {
            showMessage(t('获取详情失败'), 'error');
          }
        })
        .catch(err => {
          const errorMessage = err?.message || err || t('获取详情失败');
          showMessage(errorMessage, 'error');
        })
        .finally(() => {
          itemLoading.value = false;
        });
    };

    /**
     * 选择某个主机项
     * @param item - 主机项数据
     */
    const handleItemClick = (item: IHostItem): void => {
      if (!item) {
        return;
      }
      currentItem.value = item;
      getItemDetail(item);
    };

    /**
     * 根据状态渲染状态图标
     * @returns JSX元素或null
     */
    const renderIcon = (): JSX.Element | null => {
      const statusIconMap: Record<string, string> = {
        SUCCESS: 'bklog-circle-correct-filled',
        FAILED: 'bklog-circle-alert-filled',
      };
      const status = detail.value?.status;
      if (!status) {
        return null;
      }
      const iconClass = statusIconMap[status];
      return iconClass ? <i class={`bklog-icon ${iconClass} status-icon ${status}`} /> : null;
    };

    // 监听log内容变化，同步更新DOM
    watch(
      () => log.value,
      (newValue: string) => {
        nextTick(() => {
          if (logContentRef.value) {
            logContentRef.value.innerHTML = xssFilter(newValue || '');
          }
        });
      },
      { immediate: true },
    );

    // 监听loading状态，当加载完成时自动选中第一个item
    watch(
      () => props.loading,
      (val: boolean) => {
        if (!val) {
          setDefaultItem();
          const keys = showList.value.map(item => item.bk_obj_id);
          activeName.value = keys;
        }
      },
    );

    // 监听activeKey变化，切换Tab时自动选中第一个item
    watch(
      () => activeKey.value,
      (val: string) => {
        setDefaultItem();
        /**
         * 1. 【全部】Tab，默认展开第一个，其他都收起
         * 2. 【其他状态】Tab，默认都展开
         */
        const keys = showList.value.map(item => item.bk_obj_id);
        if (keys.length > 0) {
          activeName.value = val === 'all' ? keys : [keys[0]];
        }
      },
      {
        immediate: true,
      },
    );

    return () => (
      <div class='host-detail-main'>
        {/* Tab切换区域 */}
        <span class='host-detail-tab'>
          {props.tabList.map(item => (
            <span
              key={item.key}
              class={{
                'host-detail-tab-item': true,
                active: activeKey.value === item.key,
                disabled: item.count === 0,
              }}
              on-click={() => handleTabClick(item)}
            >
              {/* 成功/失败状态显示圆形标识 */}
              {['success', 'failed'].includes(item.key) && <span class={`item-circle ${item.key}`} />}
              {/* 运行中状态显示加载动画 */}
              {item.key === 'running' && <i class='running' />}
              {item.label} （{item.count}）
            </span>
          ))}
        </span>

        {/* 主内容区域 */}
        <div
          v-bkloading={{ isLoading: props.loading }}
          class='host-detail-main'
        >
          {showList.value.length === 0 ? (
            // 空状态展示
            <bk-exception
              class='host-detail-main-empty'
              scene='part'
              type='empty'
            />
          ) : (
            <div class='host-detail-content'>
              {/* 左侧主机列表 */}
              <div class='content-left'>
                <bk-collapse value={activeName.value}>
                  {showList.value.map(logItem => (
                    <bk-collapse-item
                      name={logItem.bk_obj_id}
                      key={logItem.bk_obj_id}
                      class='detail-content-item'
                    >
                      {logItem.node_path}
                      <div
                        slot='content'
                        class='left-list'
                      >
                        {logItem.child.map(item => (
                          <div
                            key={item.host_id}
                            class={{
                              'left-item': true,
                              active: currentItem.value?.host_id === item.host_id,
                            }}
                            on-click={() => handleItemClick(item)}
                          >
                            {item.status === 'running' ? (
                              <i class='running' />
                            ) : (
                              <span class={`item-circle ${item.status}`} />
                            )}
                            <span
                              class='item-name'
                              title={item.ip}
                            >
                              {item.ip}
                            </span>
                            {item.status === 'failed' && (
                              <span
                                class='retry'
                                on-click={() => {
                                  emit('retry', item, logItem);
                                }}
                              >
                                {t('重试')}
                              </span>
                            )}
                          </div>
                        ))}
                      </div>
                    </bk-collapse-item>
                  ))}
                </bk-collapse>
              </div>

              {/* 右侧详情展示 */}
              <div class='content-right'>
                <div class='content-right-title'>
                  {renderIcon()}
                  {t('采集详情 ')}
                  {/* 刷新按钮 */}
                  <i
                    class='bklog-icon bklog-refresh2 refresh-icon'
                    on-click={() => {
                      if (currentItem.value) {
                        getItemDetail(currentItem.value);
                      }
                    }}
                  />
                </div>
                <div
                  class='content-right-detail'
                  v-bkloading={{ isLoading: itemLoading.value, color: '#2E2E2E', zIndex: 10 }}
                >
                  <div
                    ref={logContentRef}
                    class='content-box'
                  />
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    );
  },
});
