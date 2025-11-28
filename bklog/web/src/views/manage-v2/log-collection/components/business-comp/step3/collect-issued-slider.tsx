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
import useStore from '@/hooks/use-store';

import { showMessage } from '../../../utils';
import HostDetail from '../../common-comp/host-detail';
import $http from '@/api';

import './collect-issued-slider.scss';
/**
 * @description: 采集才发侧边栏
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
    },
  },

  emits: ['change', 'refresh'],

  setup(props, { emit }) {
    const { t } = useLocale();
    // const store = useStore();

    const loading = ref(false);
    // const curCollect = computed(() => store.getters['collect/curCollect']);
    const curTaskIdList = ref([]);
    const errorNum = ref(0);
    // 节点管理准备好了吗
    const notReady = ref(false);
    const timerNum = ref(0);
    const tableListAll = ref([]);
    const tableList = ref([]);
    const timer = ref();
    const isLeavePage = ref(false);
    const hasRunning = ref(false);
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
    const stopStatusPolling = () => {
      clearTimeout(timer.value);
    };
    const collectionName = computed(() => props.config.name);

    // onMounted(() => {});
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

    const startStatusPolling = () => {
      timerNum.value += 1;
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

        const processData = data => {
          let collapseCount = 0;
          // 遍历集群列表
          for (const cluster of data) {
            cluster.collapse = cluster.child.length && collapseCount < 5;
            if (cluster.child.length) {
              collapseCount++;
            }
            // 遍历集群下的主机列表
            for (const host of cluster.child) {
              host.status = host.status === 'PENDING' ? 'running' : host.status.toLowerCase();
            }
          }
          tableListAll.value = [...data];
          tableList.value = [...data];
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
      val => {
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
            {t('采集下发存在失败，请点击 重试，如再次失败请 联系助手。')}
          </div>
        )}
        <div
          class='content-host'
          style={{ height: props.isStopCollection ? 'calc(100% - 90px)' : 'calc(100% - 44px)' }}
        >
          <HostDetail
            list={tableListAll.value}
            loading={loading.value}
            tabList={tabList.value}
            collectorConfigId={props.collectorConfigId}
          />
        </div>
        {props.isStopCollection && (
          <div class='content-footer'>
            <bk-button
              theme='primary'
              class='mr-12'
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
