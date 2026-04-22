/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2017-2025 Tencent.  All rights reserved.
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
import { type PropType, defineComponent, reactive } from 'vue';

import { useI18n } from 'vue-i18n';

import EditableField from './editable-field';

import type { IRumAppConfig, IStorageInfo } from '../../typings/rum-app-config';

import './storage-status.scss';

/**
 * 存储状态组件
 * 展示存储信息，支持编辑存储配置
 */
export default defineComponent({
  name: 'StorageStatus',
  props: {
    detail: {
      type: Object as PropType<IRumAppConfig>,
      default: () => ({}),
    },
    /** ES集群列表 */
    clusterList: {
      type: Array as PropType<Array<{ id: number | string; name: string }>>,
      default: () => [],
    },
  },
  setup(_props) {
    const { t } = useI18n();

    // 存储配置数据
    const storageData = reactive<IStorageInfo>({
      es_number_of_replicas: 0,
      es_retention: 14,
      es_shards: 3,
      es_slice_size: 100,
      es_storage_cluster: '蓝鲸运维APM公共集群',
    });

    // 集群下拉选项
    const clusterOptions = [
      { label: '蓝鲸运维APM公共集群', value: '蓝鲸运维APM公共集群' },
      { label: 'es集群7', value: 'es集群7' },
    ];

    // 处理字段变更
    const handleFieldChange = (field: keyof IStorageInfo, value: number | string) => {
      storageData[field] = value as never;
      console.log(`Field ${field} changed to:`, value);
    };

    return {
      t,
      storageData,
      clusterOptions,
      handleFieldChange,
    };
  },
  render() {
    return (
      <div class='storage-status'>
        <div class='storage-status-title'>{this.t('存储信息')}</div>
        <div class='storage-status-content'>
          {/* 第一行：存储索引名 + 存储集群 */}
          <div class='storage-status-row'>
            <div class='storage-status-item'>
              <EditableField
                editable={false}
                label={this.t('存储索引名')}
                value={this.detail?.span_result_table_id || '--'}
              />
            </div>
            <div class='storage-status-item'>
              <EditableField
                label={this.t('存储集群')}
                options={this.clusterOptions}
                type='select'
                value={this.storageData.es_storage_cluster}
              />
            </div>
          </div>

          {/* 第二行：过期时间 + 副本数 */}
          <div class='storage-status-row'>
            <div class='storage-status-item'>
              <EditableField
                label={this.t('过期时间')}
                suffix={this.t('天')}
                value={this.storageData.es_retention}
              />
            </div>
            <div class='storage-status-item'>
              <EditableField
                label={this.t('副本数')}
                value={this.storageData.es_number_of_replicas}
              />
            </div>
          </div>

          {/* 第三行：分片数 + 索引切分大小 */}
          <div class='storage-status-row'>
            <div class='storage-status-item'>
              <EditableField
                label={this.t('分片数')}
                value={this.storageData.es_shards}
              />
            </div>
            <div class='storage-status-item'>
              <EditableField
                label={this.t('索引切分大小')}
                suffix='G'
                value={this.storageData.es_slice_size}
              />
            </div>
          </div>
        </div>
      </div>
    );
  },
});
