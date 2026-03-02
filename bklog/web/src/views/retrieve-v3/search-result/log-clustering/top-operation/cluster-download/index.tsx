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

import { defineComponent, ref, computed } from 'vue';
import useLocale from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { blobDownload, formatDate } from '@/common/util';

import './index.scss';

export default defineComponent({
  name: 'ClusterDownload',
  props: {
    indexId: {
      type: String,
      require: true,
      default: '',
    },
    isClusterActive: {
      type: Boolean,
      default: false,
    },
    logTableRef: {
      type: Object,
      default: null,
    },
  },
  setup(props) {
    const { t } = useLocale();
    const store = useStore();
    const isDownloading = ref(false);

    // 计算下载按钮是否禁用
    const isDisabled = computed(() => {
      // 如果logTableRef不存在，禁用按钮
      if (!props.logTableRef?.value) {
        return true;
      }

      // 如果正在加载中，禁用按钮
      if (props.logTableRef.value.isLoading?.()) {
        return true;
      }

      // 如果没有数据，禁用按钮
      const rawData = props.logTableRef.value.getRawData?.() || [];
      return rawData.length === 0;
    });

    // 获取当前索引集信息
    const currentIndexItem = computed(() => {
      return store.state.indexItem.items?.find((item: { index_set_id: string }) => item.index_set_id === props.indexId);
    });

    // 生成文件名
    const generateFileName = (rawData: any[], displayMode: string) => {
      const indexSetName = currentIndexItem.value?.index_set_name || 'cluster';

      // 获取开始时间
      const { start_time } = store.state.indexItem;

      // 格式化时间为文件名格式（将冒号替换为横线以避免文件名非法字符）
      const startTimeStr = formatDate(start_time).replace(/:/g, '-');

      return `${indexSetName}_${displayMode}_${startTimeStr}.csv`;
    };

    /**
     * CSV字段值转义函数
     * 处理逗号、双引号、换行符等特殊字符
     */
    const escapeCSVField = (value: any): string => {
      // 处理null和undefined
      if (value === null || value === undefined) {
        return '';
      }

      // 转换为字符串
      let stringValue = String(value);

      // 检查是否包含需要转义的字符：逗号、双引号、换行符(\n)、回车符(\r)
      const needsEscape =        stringValue.includes(',')
        || stringValue.includes('"')
        || stringValue.includes('\n')
        || stringValue.includes('\r');

      if (needsEscape) {
        // 1. 先将字段内的双引号转义为两个双引号（CSV标准）
        stringValue = stringValue.replace(/"/g, '""');

        // 2. 用双引号包围整个字段
        return `"${stringValue}"`;
      }

      return stringValue;
    };

    // 将聚类数据转换为CSV格式
    const convertToCSV = (data: any[]) => {
      if (!data || data.length === 0) {
        return '';
      }

      // 从第一条数据中获取所有键名作为表头
      const firstItem = data[0];
      const headers = Object.keys(firstItem).filter(key => key !== 'id');

      // 处理数据行
      const rows = data.map((item) => {
        const row = [];

        // 遍历所有键，处理对应的值
        headers.forEach((key) => {
          let value = item[key];

          // 特殊处理某些字段的值格式
          if (key === 'owners' || key === 'group') {
            if (Array.isArray(value)) {
              value = value.join(';');
            } else {
              value = value || '';
            }
          } else if (key === 'remark') {
            if (Array.isArray(value)) {
              // 将 remark 对象数组转换为可读的字符串格式
              value = value
                .map((remark: { create_time: string; username: string; remark: string }) => {
                  return `[${formatDate(remark.create_time)}] ${remark.username}: ${remark.remark}`;
                })
                .join('\n');
            } else {
              value = value || '';
            }
          }

          // 使用CSV转义函数处理字段值
          row.push(escapeCSVField(value));
        });

        return row;
      });

      // 组合CSV内容
      const csvContent = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');

      // 添加UTF-8 BOM以解决中文乱码问题
      return `\uFEFF${csvContent}`;
    };

    const handleDownload = async () => {
      if (isDownloading.value || isDisabled.value) {
        return;
      }

      try {
        isDownloading.value = true;

        // 从logTableRef获取原始数据
        const rawData = props.logTableRef.value?.getRawData?.() || [];
        const displayMode = props.logTableRef.value?.getDisplayMode?.() || 'flatten';

        // 转换为CSV格式
        const csvContent = convertToCSV(rawData);

        // 生成文件名
        const fileName = generateFileName(rawData, displayMode);

        // 使用blobDownload进行下载
        blobDownload(csvContent, fileName);
      } catch (error) {
        console.error('Download error:', error);
      } finally {
        isDownloading.value = false;
      }
    };

    return () => (
      <div class='download-main'>
        <div
          class={{
            download: true,
            'is-disabled': isDisabled.value,
          }}
          on-click={handleDownload}
        >
          <log-icon
            type='download'
            common
            v-bk-tooltips={{
              content: isDisabled.value ? t('暂无数据') : t('聚类下载'),
              disabled: isDownloading.value,
            }}
            class={{ 'is-downloading': isDownloading.value }}
          />
        </div>
      </div>
    );
  },
});
