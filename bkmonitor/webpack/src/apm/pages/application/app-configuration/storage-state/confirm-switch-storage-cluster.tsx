import type Vue from 'vue';

import './confirm-switch-storage-cluster.scss';

export interface ISwitchStorageClusterConfirm {
  currentName: string;
  targetName: string;
  /** 弹窗展示的保留天数，由调用方决定取值 */
  retentionDays: number | string;
}

/**
 * 调用链与日志共用的存储集群切换确认弹窗，只负责确认，不提交保存。
 */
export function confirmSwitchStorageCluster(vm: Vue, options: ISwitchStorageClusterConfirm): Promise<boolean> {
  const h = vm.$createElement;
  const { currentName, targetName, retentionDays } = options;
  return new Promise(resolve => {
    vm.$bkInfo({
      title: vm.$t('确认切换存储集群？'),
      width: 600,
      okText: vm.$t('确认切换'),
      cancelText: vm.$t('取消'),
      subHeader: h('div', { class: 'cluster-switch-dialog-body' }, [
        h('div', { class: 'cluster-switch-row' }, [
          h('span', { class: 'cluster-switch-label' }, `${vm.$t('当前集群')}：`),
          h('span', { class: 'cluster-switch-value' }, currentName),
          h('span', { class: 'cluster-switch-arrow' }, '\u2192'),
          h('span', { class: 'cluster-switch-label' }, `${vm.$t('目标集群')}：`),
          h('span', { class: 'cluster-switch-value cluster-switch-value-target' }, targetName),
        ]),
        h(
          'div',
          { class: 'cluster-switch-retention' },
          `${vm.$t('切换后保留天数：{days} 天', { days: retentionDays })}`,
        ),
        h(
          'div',
          { class: 'cluster-switch-desc' },
          `${vm.$t('切换生效后，新增数据将写入目标集群。历史数据仍可查询，并按切换后生效的保留时长自动清理。')}`,
        ),
      ]),
      confirmFn: () => resolve(true),
      cancelFn: () => resolve(false),
    });
  });
}
