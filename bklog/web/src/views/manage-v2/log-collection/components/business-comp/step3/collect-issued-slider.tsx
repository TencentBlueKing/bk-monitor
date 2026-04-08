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

import { defineComponent, ref, computed, watch } from 'vue';

import useLocale from '@/hooks/use-locale';

import { showMessage } from '../../../utils';
import HostDetail from '../../common-comp/host-detail';
import $http from '@/api';

import './collect-issued-slider.scss';

/**
 * 主机状态类型
 */
type HostStatus = 'success' | 'failed' | 'running' | 'pending' | string;

/**
 * 主机项数据接口
 */
interface IHostItem {
  /** 主机IP地址 */
  ip: string;
  /** 云区域ID */
  bk_cloud_id: number | string;
  /** 实例ID */
  instance_id: string | number;
  /** 主机状态 */
  status: HostStatus;
  [key: string]: unknown;
}

/**
 * 集群项数据接口
 * 兼容 HostDetail 组件所需的 ILogItem 结构
 */
interface IClusterItem {
  /** 实例ID */
  bk_inst_id?: string | number;
  /** 对象ID（兼容 ILogItem） */
  bk_obj_id?: string;
  /** 对象名称 */
  bk_obj_name: string;
  /** 节点路径（兼容 ILogItem） */
  node_path?: string;
  /** 子项列表（主机列表） */
  child: IHostItem[];
  /** 是否折叠 */
  collapse?: boolean;
  [key: string]: unknown;
}

/**
 * 重试接口响应数据类型
 */
interface IRetryResponse {
  /** 响应数据（任务ID列表） */
  data?: (string | number)[];
  [key: string]: unknown;
}

/**
 * @description: 采集下发侧边栏组件
 * 用于展示采集下发状态，支持单条和批量重试功能
 */
export default defineComponent({
  name: 'CollectIssuedSlider',
  props: {
    isShow: {
      type: Boolean,
      default: false,
    },
    isStopCollection: {
      type: Boolean,
      default: false,
    },
    status: {
      type: String,
      default: '',
    },
    config: {
      type: Object,
      default: () => {},
    },
    collectorConfigId: {
      type: Number,
      default: undefined,
    },
  },

  emits: ['change', 'refresh'],

  setup(props, { emit }) {
    const { t } = useLocale();
    // const store = useStore();

    const loading = ref<boolean>(false);
    // const curCollect = computed(() => store.getters['collect/curCollect']);
    /** 当前任务ID列表 */
    const curTaskIdList = ref<(string | number)[]>([]);
    /** 错误数量 */
    const errorNum = ref<number>(0);
    /** 节点管理是否准备就绪 */
    const notReady = ref<boolean>(false);
    /** 轮询计时器编号（用于防止并发轮询） */
    const timerNum = ref<number>(0);
    /** 所有集群列表数据 */
    const tableListAll = ref<IClusterItem[]>([]);
    /** 轮询定时器 */
    const timer = ref<ReturnType<typeof setTimeout> | null>(null);
    /** 是否离开页面 */
    const isLeavePage = ref<boolean>(false);
    /** 是否存在运行中的任务 */
    const hasRunning = ref<boolean>(false);
    const tabList = ref([
      {
        key: 'all',
        label: t('全部'),
        count: 0,
      },
      {
        key: 'success',
        label: t('成功'),
        count: 0,
      },
      {
        key: 'failed',
        label: t('失败'),
        count: 0,
      },
      {
        key: 'running',
        label: t('执行中'),
        count: 0,
      },
    ]);
    const isHandle = ref(false);

    const collectionName = computed(() => props.config.name);
    const isRunning = computed(() => tabList.value.find(item => item.key === 'running').count > 0);

    const calcTabNum = () => {
      const num = {
        all: 0,
        success: 0,
        failed: 0,
        running: 0,
      };

      // 遍历所有集群，计算各状态数量
      for (const cluster of tableListAll.value) {
        // 累加总数量（所有主机）
        num.all += cluster.child.length;

        // 遍历当前集群下的主机，按状态累加
        for (const row of cluster.child) {
          num[row.status] += 1;
        }
      }

      // 更新标签页数量
      for (const tab of tabList.value) {
        tab.count = num[tab.key];
      }
      errorNum.value = num.failed;
      // 根据running状态更新hasRunning，用于控制轮询
      hasRunning.value = num.running > 0;
    };

    const stopStatusPolling = () => {
      clearTimeout(timer.value);
    };

    const startStatusPolling = () => {
      timerNum.value = timerNum.value + 1;
      stopStatusPolling();
      timer.value = setTimeout(() => {
        if (isLeavePage.value) {
          stopStatusPolling();
          return;
        }
        requestIssuedClusterList('polling');
      }, 3000);
    };

    /**
     *  集群list，与轮询共用
     */
    const requestIssuedClusterList = async (isPolling = '') => {
      if (!isPolling) {
        loading.value = true;
      }

      const params = {
        collector_config_id: props.collectorConfigId,
      };
      const cacheTimeNum = timerNum.value;

      try {
        const res = await $http.request('collect/getIssuedClusterList', {
          params,
          query: { task_id_list: curTaskIdList.value },
        });

        const data = res.data.contents || [];
        notReady.value = res.data.task_ready === false;

        const processData = (data: IClusterItem[]) => {
          let collapseCount = 0;
          // 遍历集群列表
          for (const cluster of data) {
            cluster.collapse = cluster.child.length && collapseCount < 5;
            if (cluster.child.length) {
              collapseCount = collapseCount + 1;
            }
            // 遍历集群下的主机列表
            for (const host of cluster.child) {
              host.status = host.status === 'PENDING' ? 'running' : host.status.toLowerCase();
            }
          }
          tableListAll.value = [...data];
        };

        if (isPolling === 'polling') {
          // 轮询模式下始终更新数据，以便正确判断状态
          if (cacheTimeNum === timerNum.value) {
            processData(data);
          }
          calcTabNum();
          // 只有当存在running状态时才继续轮询，否则停止轮询
          hasRunning.value ? startStatusPolling() : stopStatusPolling();
        } else {
          processData(data);
          calcTabNum();
          // 首次加载时，如果存在running状态，启动轮询
          if (hasRunning.value) {
            startStatusPolling();
          }
        }
      } catch (err) {
        showMessage(err.message, 'error');
      } finally {
        setTimeout(() => {
          loading.value = false;
        }, 500);
      }
    };
    /**
     * 停用
     */
    const handleStop = () => {
      isHandle.value = true;
      $http
        .request('collect/stopCollect', {
          params: {
            collector_config_id: props.collectorConfigId,
          },
        })
        .then(res => {
          if (res.result) {
            emit('refresh');
          }
        })
        .catch(() => {
          showMessage(t('停用失败'), 'error');
        })
        .finally(() => {
          isHandle.value = false;
        });
    };

    watch(
      () => props.isShow,
      (val: boolean) => {
        if (val) {
          for (const id of props.config?.task_id_list ?? []) {
            curTaskIdList.value.push(id);
          }
          requestIssuedClusterList();
        } else {
          // 侧边栏关闭时停止轮询
          stopStatusPolling();
        }
      },
      {
        immediate: true,
        deep: true,
      },
    );
    /**
     * 更新主机状态为运行中
     * @param host - 主机项数据
     */
    const updateHostStatusToRunning = (host: IHostItem): void => {
      host.status = 'running';
    };

    /**
     * 单条重试：更新指定主机的状态并收集实例ID
     * @param row - 要重试的主机项
     * @param cluster - 主机所属的集群项
     * @returns 实例ID列表
     */
    const handleSingleRetry = (row: IHostItem, cluster: IClusterItem): (string | number)[] => {
      // 更新传入的行状态
      updateHostStatusToRunning(row);

      // 在表格数据中查找并更新对应主机的状态
      const targetCluster = tableListAll.value.find(
        item => item.bk_inst_id === cluster.bk_inst_id && item.bk_obj_name === cluster.bk_obj_name,
      );

      if (targetCluster?.child) {
        const targetHost = targetCluster.child.find(host => host.ip === row.ip && host.bk_cloud_id === row.bk_cloud_id);
        if (targetHost) {
          updateHostStatusToRunning(targetHost);
        }
      }

      return [row.instance_id];
    };

    /**
     * 批量重试：更新所有失败主机的状态并收集实例ID列表
     * @returns 实例ID列表
     */
    const handleBatchRetry = (): (string | number)[] => {
      const instanceIDList: (string | number)[] = [];

      // 遍历所有集群，查找失败的主机并更新状态
      for (const cluster of tableListAll.value) {
        if (!cluster.child) continue;

        for (const host of cluster.child) {
          if (host.status === 'failed') {
            updateHostStatusToRunning(host);
            instanceIDList.push(host.instance_id);
          }
        }
      }

      return instanceIDList;
    };

    /**
     * 处理重试操作
     * 支持单条重试和批量重试两种模式
     * @param row - 要重试的主机项（批量重试时可为 null 或 undefined）
     * @param cluster - 主机所属的集群项（批量重试时可为 null 或 undefined）
     */
    const handleRestart = (row?: IHostItem | null, cluster?: IClusterItem | null): void => {
      // 根据是否传入 cluster 参数判断是单条重试还是批量重试
      const instanceIDList: (string | number)[] = cluster && row ? handleSingleRetry(row, cluster) : handleBatchRetry();

      // 如果没有需要重试的实例，直接返回
      if (instanceIDList.length === 0) {
        showMessage(t('没有需要重试的实例'), 'warning');
        return;
      }

      // 更新标签页数量统计
      calcTabNum();

      // 调用重试接口
      $http
        .request('collect/retry', {
          params: { collector_config_id: props.collectorConfigId },
          data: {
            instance_id_list: instanceIDList,
          },
        })
        .then((res: IRetryResponse) => {
          if (res.data?.length) {
            // 将返回的任务ID添加到任务列表
            res.data.forEach((taskId: string | number) => {
              curTaskIdList.value.push(taskId);
            });
            // 启动状态轮询，监控重试结果
            startStatusPolling();
          }
        })
        .catch((err: Error) => {
          const errorMessage = err?.message || t('重试失败');
          showMessage(errorMessage, 'error');
          // 重试失败时，恢复主机状态为失败
          if (cluster && row) {
            // 单条重试失败，恢复单条状态
            row.status = 'failed';
            const targetCluster = tableListAll.value.find(
              item => item.bk_inst_id === cluster.bk_inst_id && item.bk_obj_name === cluster.bk_obj_name,
            );
            const targetHost = targetCluster?.child?.find(
              host => host.ip === row.ip && host.bk_cloud_id === row.bk_cloud_id,
            );
            if (targetHost) {
              targetHost.status = 'failed';
            }
          } else {
            // 批量重试失败，恢复所有失败状态
            for (const clusterItem of tableListAll.value) {
              if (!clusterItem.child) continue;
              for (const host of clusterItem.child) {
                if (host.status === 'running' && instanceIDList.includes(host.instance_id)) {
                  host.status = 'failed';
                }
              }
            }
          }
          // 重新计算标签页数量
          calcTabNum();
        });
    };

    const renderHeader = () => (
      <div>
        {props.isStopCollection ? (
          <div class='collect-link'>
            {t('编辑采集项')}
            <span class='link-name'>
              <span class='bk-icon bklog-icon bklog-position' />
              {collectionName.value}
            </span>
          </div>
        ) : (
          <span>{t('采集下发')}</span>
        )}
      </div>
    );

    const renderContent = () => (
      <div class='collect-issued-slider-content'>
        {errorNum.value > 0 && (
          <div class='collect-issued-slider-alert'>
            <i class='bklog-icon bklog-alert alert-icon' />
            {t('采集下发存在失败，请点击')}
            <span
              class='restart'
              on-click={handleRestart}
            >
              {t('重试')}
            </span>
            {t('如再次失败请 联系助手。')}
          </div>
        )}
        <div
          class='content-host'
          style={{ height: props.isStopCollection ? 'calc(100% - 90px)' : 'calc(100% - 44px)' }}
        >
          <HostDetail
            list={tableListAll.value as IClusterItem[]}
            loading={loading.value}
            tabList={tabList.value}
            collectorConfigId={props.collectorConfigId}
            on-retry={(row: IHostItem, item: IClusterItem) => handleRestart(row, item)}
          />
        </div>
        {props.isStopCollection && !loading.value && (
          <div class='content-footer'>
            <bk-button
              theme='primary'
              class='mr-12'
              disabled={isRunning.value}
              on-click={handleStop}
              loading={isHandle.value}
            >
              {t('停用')}
            </bk-button>
            <bk-button
              on-click={() => {
                emit('change', false);
              }}
            >
              {t('取消')}
            </bk-button>
          </div>
        )}
      </div>
    );

    return () => (
      <bk-sideslider
        width={960}
        ext-cls='collect-issued-slider-main'
        before-close={() => {
          emit('change', false);
        }}
        scopedSlots={{
          header: renderHeader,
          content: renderContent,
        }}
        is-show={props.isShow}
        quick-close
        transfer
      />
    );
  },
});
