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

import { defineComponent, ref, onMounted } from 'vue';

import { formatFileSize } from '@/common/util';
import useLocale from '@/hooks/use-locale';

import http from '@/api';

import './state-table.scss';

export default defineComponent({
  name: 'StateTable',
  props: {
    // 归档配置ID
    archiveConfigId: {
      type: Number,
      required: true,
    },
  },
  setup(props) {
    const { t } = useLocale(); // 获取国际化函数
    const scrollContainer = ref<any>(null); // 滚动容器引用

    const isTableLoading = ref(false); // 表格加载状态
    const throttle = ref(false); // 滚动节流
    const isPageOver = ref(false); // 是否加载完毕
    const dataList = ref<any[]>([]); // 数据列表
    const curPage = ref(0); // 当前页码
    const pageSize = 20; // 每页条数

    // 状态映射
    const stateMap = {
      SUCCESS: t('成功'),
      FAIL: t('失败'),
      PARTIAL: t('失败'),
      IN_PROGRESS: t('回溯中'),
    };

    // 获取文件大小
    const getFileSize = (size: number) => {
      return formatFileSize(size);
    };

    // 请求数据
    const requestData = async () => {
      try {
        const res = await http.request('archive/archiveConfig', {
          query: {
            page: curPage.value,
            pagesize: pageSize,
          },
          params: {
            archive_config_id: props.archiveConfigId,
          },
        });

        const { data } = res;
        isPageOver.value = data.indices.length < pageSize;

        if (data.indices.length) {
          const list = data.indices.map((item: any) => ({ ...item }));
          dataList.value.splice(dataList.value.length, 0, ...list);
        }
      } catch (err) {
        console.warn(err);
      } finally {
        isTableLoading.value = false;
      }
    };

    // 初始化
    const init = async () => {
      isTableLoading.value = true;
      await requestData();
    };

    // 加载更多数据
    const loadMore = async () => {
      curPage.value += 1;
      await requestData();
    };

    // 滚动处理
    const handleScroll = () => {
      if (throttle.value || isPageOver.value) {
        return;
      }
      throttle.value = true;
      setTimeout(() => {
        throttle.value = false;
        const el = scrollContainer.value;
        if (el && el.scrollHeight - el.offsetHeight - el.scrollTop < 60) {
          loadMore();
        }
      }, 200);
    };

    // 组件挂载时初始化
    onMounted(() => {
      init();
    });

    // 表头渲染函数
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    return () => (
      <section
        ref={scrollContainer}
        class='archive-state-list'
        onScroll={handleScroll}
      >
        <section>
          <bk-table
            class='state-table'
            v-bkloading={{ isLoading: isTableLoading.value }}
            data={dataList.value}
            outer-border={false}
          >
            <bk-table-column
              label={t('索引名')}
              min-width='300'
              renderHeader={renderHeader}
              scopedSlots={{ default: (newProps: any) => newProps.row.index_name }}
            />
            <bk-table-column
              label={t('数据起止时间')}
              min-width='200'
              renderHeader={renderHeader}
              scopedSlots={{ default: (newProps: any) => `${newProps.row.start_time} - ${newProps.row.end_time}` }}
            />
            <bk-table-column
              label={t('剩余')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (newProps: any) => newProps.row.expired_time }}
            />
            <bk-table-column
              label={t('大小')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (newProps: any) => getFileSize(newProps.row.store_size) }}
            />
            <bk-table-column
              scopedSlots={{
                default: (newProps: any) => (
                  <div class='restore-status'>
                    <span class={`status-icon is-${newProps.row.state}`} />
                    <span class='status-text'>{stateMap[newProps.row.state]}</span>
                  </div>
                ),
              }}
              label={t('归档状态')}
              renderHeader={renderHeader}
            />
            <bk-table-column
              width='200'
              label={t('是否已回溯')}
              renderHeader={renderHeader}
              scopedSlots={{ default: (newProps: any) => (newProps.row.is_stored ? t('是') : t('否')) }}
            />
          </bk-table>
          {dataList.value.length > 0 && (
            <div
              style='height: 40px'
              v-bkloading={{ isLoading: true }}
              v-show={!isPageOver.value}
            />
          )}
        </section>
      </section>
    );
  },
});
