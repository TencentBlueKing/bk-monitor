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

import { computed, defineComponent, ref, watch, type PropType } from 'vue';

import { formatFileSize } from '@/common/util';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { useRouter } from 'vue-router/composables';
import TableComponent from '../../common-comp/table-component';

import './cluster-table.scss';

// ==================== 类型定义 ====================

/**
 * 集群配置接口
 */
interface ISetupConfig {
  /** 最大副本数 */
  number_of_replicas_max: number;
  /** 最大保留天数 */
  retention_days_max: number;
  /** 最大分片数 */
  es_shards_max?: number;
  [key: string]: unknown;
}

/**
 * 集群项接口
 */
interface IClusterItem {
  /** 存储集群ID */
  storage_cluster_id: number;
  /** 存储集群名称 */
  storage_display_name: string;
  /** 存储总量（字节） */
  storage_total: number;
  /** 存储使用率（百分比，0-100） */
  storage_usage: number;
  /** 索引数量 */
  index_count?: number;
  /** 业务数量 */
  biz_count?: number;
  /** 集群描述 */
  description?: string;
  /** 是否启用冷热数据 */
  enable_hot_warm?: boolean;
  /** 是否启用日志归档 */
  enable_archive?: boolean;
  /** 集群配置 */
  setup_config?: ISetupConfig;
  [key: string]: unknown;
}

/**
 * 集群描述项接口
 */
interface IClusterDescItem {
  /** 标签 */
  label: string;
  /** 值 */
  value: string;
}

/**
 * 集群选择表格组件
 * 功能：
 * 1. 显示集群列表，支持选择
 * 2. 显示集群详细信息（副本数量、过期时间、冷热数据、日志归档、集群备注）
 * 3. 支持空状态显示和创建新集群
 */
export default defineComponent({
  name: 'ClusterTable',
  props: {
    /** 集群列表 */
    clusterList: {
      type: Array as PropType<IClusterItem[]>,
      default: () => [],
    },
    /** 是否显示业务数列 */
    showBizCount: {
      type: Boolean,
      default: true,
    },
    /** 当前选中的集群ID */
    clusterSelect: {
      type: Number,
      default: undefined,
    },
    /** 组件名称（用于空状态显示） */
    name: {
      type: String,
      default: '',
    },
    /** 加载状态 */
    loading: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['choose'],

  setup(props, { emit }) {
    // ==================== 基础依赖 ====================
    const { t } = useLocale();
    const router = useRouter();
    const store = useStore();

    // ==================== 常量定义 ====================
    /** 百分比基数 */
    const PERCENT_BASE = 100;

    // ==================== 响应式状态 ====================
    /** 当前选中的集群行数据 */
    const currentRow = ref<IClusterItem | null>(null);
    /** 当前选中集群的配置信息 */
    const setupConfig = ref<ISetupConfig | null>(null);
    const columns = computed(() => {
      const baseColumns = [
        {
          title: t('采集名'),
          colKey: 'storage_display_name',
          cell: (h, { row }: { row: IClusterItem }) => (
            <bk-radio checked={isSelected(row)}>
              <div
                class='overflow-tips'
                v-bk-overflow-tips
              >
                <span class='cluster-name'>{row.storage_display_name}</span>
              </div>
            </bk-radio>
          ),
          width: 200,
          ellipsis: true,
        },
        {
          title: t('总量'),
          colKey: 'storage_total',
          width: 90,
          cell: (h, { row }: { row: IClusterItem }) => <span>{formatFileSize(row.storage_total)}</span>,
        },
        {
          title: t('空闲率'),
          colKey: 'storage_usage',
          width: 150,
          cell: (h, { row }: { row: IClusterItem }) => (
            <div class='percent'>
              <div class='percent-progress'>
                <bk-progress
                  percent={getPercent(row)}
                  show-text={false}
                  theme='success'
                />
              </div>
              <span class='percent-count'>{`${100 - row.storage_usage}%`}</span>
            </div>
          ),
        },
        {
          title: t('索引数'),
          colKey: 'index_count',
          width: 80,
        },
      ];
      const bizCountColumns = [
        {
          title: t('业务数'),
          colKey: 'biz_count',
          width: 80,
        },
      ];
      return props.showBizCount ? [...baseColumns, ...bizCountColumns] : baseColumns;
    });

    // ==================== 计算属性 ====================

    /**
     * 计算空闲率百分比
     * @param row - 集群项数据
     * @returns 空闲率（0-1之间的小数）
     */
    const getPercent = (row: IClusterItem): number => {
      return (PERCENT_BASE - row.storage_usage) / PERCENT_BASE;
    };

    /**
     * 判断集群是否被选中
     * @param item - 集群项
     * @returns 是否选中
     */
    const isSelected = (item: IClusterItem): boolean => {
      return props.clusterSelect === item.storage_cluster_id;
    };

    /**
     * 是否显示集群说明
     * 当有选中的集群且该集群存在于列表中时显示
     */
    const isShowDesc = computed(() => {
      if (!props.clusterSelect) {
        return false;
      }
      return props.clusterList.some(item => isSelected(item));
    });

    /**
     * 集群描述信息列表
     * 包含：副本数量、过期时间、冷热数据、日志归档、集群备注
     */
    const clusterDesc = computed<IClusterDescItem[]>(() => {
      if (!setupConfig.value || !currentRow.value) {
        return [];
      }

      const { number_of_replicas_max: replicasMax, retention_days_max: daysMax } = setupConfig.value;
      const { description, enable_hot_warm: hotWarm, enable_archive: archive } = currentRow.value;

      return [
        {
          label: t('副本数量'),
          value: t('最大 {num} 个', { num: replicasMax }),
        },
        {
          label: t('过期时间'),
          value: t('最大 {num} 天', { num: daysMax }),
        },
        {
          label: t('冷热数据'),
          value: hotWarm ? t('支持') : t('不支持'),
        },
        {
          label: t('日志归档'),
          value: archive ? t('支持') : t('不支持'),
        },
        {
          label: t('集群备注'),
          value: description || '--',
        },
      ];
    });

    // ==================== 事件处理函数 ====================

    /**
     * 处理集群选择事件
     * @param row - 选中的集群数据
     */
    const handleSelectCluster = (row: IClusterItem): void => {
      setupConfig.value = row.setup_config || null;
      currentRow.value = row;
      emit('choose', row);
    };

    /**
     * 处理创建集群操作
     * 在新窗口打开集群管理页面
     */
    const handleCreateCluster = (): void => {
      const newUrl = router.resolve({
        name: 'es-cluster-manage',
        query: {
          spaceUid: store.state.spaceUid,
        },
      });
      window.open(newUrl.href, '_blank');
    };

    // ==================== 监听器 ====================

    /**
     * 监听集群列表变化，自动选中指定的集群
     * 当集群列表更新且存在指定的选中集群时，自动触发选择
     */
    watch(
      () => props.clusterList,
      (val: IClusterItem[]) => {
        if (!props.clusterSelect) {
          return;
        }
        const targetCluster = val.find(item => item.storage_cluster_id === props.clusterSelect);
        if (targetCluster) {
          handleSelectCluster(targetCluster);
        }
      },
      { deep: true },
    );
    // ==================== 渲染函数 ====================

    /**
     * 渲染集群表格
     * 显示集群列表，包含：集群名、总量、空闲率、索引数、业务数（可选）
     * @returns JSX元素
     */
    const renderClusterTable = () => (
      <div
        style={{ width: isShowDesc.value ? '58%' : '100%' }}
        class='cluster-content-table'
      >
        <TableComponent
          class='cluster-table'
          loading={props.loading}
          data={props.clusterList}
          columns={columns.value}
          on-cell-click={handleSelectCluster}
        />
      </div>
    );

    /**
     * 渲染空状态
     * 当集群列表为空时显示，提供创建集群的入口
     * @returns JSX元素
     */
    const renderEmpty = () => (
      <bk-exception
        class='cluster-content-empty'
        scene='part'
        type='empty'
      >
        <span>
          {t('暂无')}
          {props.name ? t(props.name) : ''}
        </span>
        <div
          class='text-wrap text-part'
          on-click={handleCreateCluster}
        >
          <span class='text-btn'>{t('创建集群')}</span>
        </div>
      </bk-exception>
    );

    /**
     * 渲染集群说明
     * 显示选中集群的详细信息：副本数量、过期时间、冷热数据、日志归档、集群备注
     * @returns JSX元素
     */
    const renderClusterDesc = () => (
      <div class='cluster-content-desc'>
        <div class='desc-title'>{t('集群说明')}</div>
        <div class='desc-content'>
          {clusterDesc.value.map(item => (
            <div
              key={`${item.label}-${item.value}`}
              class='desc-content-item'
            >
              <span class='item-title'>{item.label}：</span>
              <span class='item-desc'>{item.value}</span>
            </div>
          ))}
        </div>
      </div>
    );

    // ==================== 渲染 ====================

    return () => (
      <div class='cluster-table-box'>
        {(props.clusterList || []).length === 0
          ? renderEmpty()
          : [renderClusterTable(), isShowDesc.value && renderClusterDesc()]}
      </div>
    );
  },
});
