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

import { defineComponent, ref, computed, onMounted } from 'vue';

import * as authorityMap from '@/common/authority-map';
import EmptyStatus from '@/components/empty-status/index.vue';
import useLocale from '@/hooks/use-locale';
import useRouter from '@/hooks/use-router';
import useStore from '@/hooks/use-store';
import { Message, InfoBox } from 'bk-magic-vue';

import http from '@/api';

import './link-list.scss';

export default defineComponent({
  name: 'ExtractLinkList',
  setup() {
    const store = useStore();
    const router = useRouter();
    const { t } = useLocale();

    const isLoading = ref(true); // 加载状态
    const extractLinkList = ref<any[]>([]); // 链路数据
    const isAllowedManage = ref<boolean | null>(null); // 是否有管理权限
    const isButtonLoading = ref(false); // 新增按钮 loading
    const emptyType = ref('empty'); // 空状态类型
    const linkNameMap = computed(() => ({
      // 链路类型映射
      common: t('内网链路'),
      qcloud_cos: t('腾讯云链路'),
      bk_repo: t('蓝鲸制品库'),
    }));
    const pagination = ref({
      // 分页配置
      count: 0,
      current: 1,
      limit: 10,
      limitList: [10, 20, 50, 100],
    });

    const spaceUid = computed(() => store.getters.spaceUid); // 空间UID

    // 权限校验，校验通过后拉取链路列表
    const checkManageAuth = async () => {
      try {
        const res = await store.dispatch('checkAllowed', {
          action_ids: [authorityMap.MANAGE_EXTRACT_AUTH],
          resources: [
            {
              type: 'space',
              id: spaceUid.value,
            },
          ],
        });
        isAllowedManage.value = res.isAllowed;
        if (res.isAllowed) {
          await initList();
        } else {
          isLoading.value = false;
        }
      } catch (err) {
        console.warn(err);
        isLoading.value = false;
        isAllowedManage.value = false;
      }
    };

    // 初始化链路列表
    const initList = async () => {
      try {
        isLoading.value = true;
        const res = await http.request('extractManage/getLogExtractLinks');
        // 分页处理
        const allList = res.data;
        pagination.value.count = allList.length;
        const start = (pagination.value.current - 1) * pagination.value.limit;
        const end = start + pagination.value.limit;
        extractLinkList.value = allList.slice(start, end);
      } catch (e) {
        console.warn(e);
        emptyType.value = '500';
      } finally {
        isLoading.value = false;
      }
    };

    // 处理分页变化
    const handlePageChange = (page: number) => {
      if (pagination.value.current !== page) {
        pagination.value.current = page;
        initList();
      }
    };

    // 处理每页数量变化
    const handleLimitChange = (limit: number) => {
      pagination.value.limit = limit;
      pagination.value.current = 1;
      initList();
    };

    // 新增链路
    const handleCreate = async () => {
      if (isAllowedManage.value) {
        router.push({
          name: 'extract-link-create',
          query: {
            spaceUid: spaceUid.value,
          },
        });
      } else {
        try {
          isButtonLoading.value = true;
          const res = await store.dispatch('getApplyData', {
            action_ids: [authorityMap.MANAGE_EXTRACT_AUTH],
            resources: [
              {
                type: 'space',
                id: spaceUid.value,
              },
            ],
          });
          store.commit('updateState', { authDialogData: res.data });
        } catch (err) {
          console.warn(err);
        } finally {
          isButtonLoading.value = false;
        }
      }
    };

    // 编辑链路
    const handleEditStrategy = (row: any) => {
      router.push({
        name: 'extract-link-edit',
        params: {
          linkId: row.link_id,
        },
        query: {
          spaceUid: spaceUid.value,
          editName: row.name,
        },
      });
    };

    // 删除链路
    const handleDeleteStrategy = (row: any) => {
      InfoBox({
        title: `${t('确定要删除')}【${row.name}】？`,
        confirmLoading: true,
        confirmFn: () => confirmDeleteStrategy(row.link_id),
      });
    };

    // 确认删除策略
    const confirmDeleteStrategy = async (id: number) => {
      try {
        isLoading.value = true;
        await http.request('extractManage/deleteLogExtractLink', {
          params: {
            link_id: id,
          },
        });
        Message({
          theme: 'success',
          message: t('删除成功'),
        });
        await initList();
      } catch (e) {
        console.warn(e);
        isLoading.value = false;
      }
    };

    // 空状态操作
    const handleOperation = (type: string) => {
      if (type === 'refresh') {
        emptyType.value = 'empty';
        pagination.value.current = 1;
        initList();
      }
    };

    // 表头渲染
    const renderHeader = (_: any, { column }: any) => <span>{column.label}</span>;

    onMounted(() => {
      checkManageAuth();
    });

    // 渲染函数
    return () => (
      <div
        class='extract-link-list-container'
        v-bkloading={{ isLoading: isLoading.value }}
        data-test-id='extractLinkList_div_extractLinkListBox'
      >
        {/* 新增按钮 */}
        <div>
          <bk-button
            style='width: 120px; margin: 20px 0'
            class='king-button'
            v-cursor={{ active: isAllowedManage.value === false }}
            data-test-id='extractLinkListBox_button_addNewLinkList'
            disabled={isAllowedManage.value === null || isLoading.value}
            loading={isButtonLoading.value}
            theme='primary'
            onClick={handleCreate}
          >
            {t('新增')}
          </bk-button>
        </div>
        {/* 链路表格 */}
        <bk-table
          class='king-table'
          scopedSlots={{
            empty: () => (
              <div>
                <EmptyStatus
                  empty-type={emptyType.value}
                  on-operation={handleOperation}
                />
              </div>
            ),
          }}
          data={extractLinkList.value}
          data-test-id='extractLinkListBox_table_LinkListTableBox'
          pagination={pagination.value}
          row-key='strategy_id'
          onPage-change={handlePageChange}
          onPage-limit-change={handleLimitChange}
        >
          <bk-table-column
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='table-ceil-container'>
                  <span v-bk-overflow-tips>{row.name}</span>
                </div>
              ),
            }}
            label={t('链路名称')}
            renderHeader={renderHeader}
          />
          <bk-table-column
            scopedSlots={{
              default: ({ row }: any) => <div>{linkNameMap.value[row.link_type]}</div>,
            }}
            label={t('链路类型')}
            prop='created_at'
            renderHeader={renderHeader}
          />
          <bk-table-column
            width='200'
            scopedSlots={{
              default: ({ row }: any) => (
                <div class='task-operation-container'>
                  <span
                    class='task-operation'
                    onClick={() => handleEditStrategy(row)}
                  >
                    {t('编辑')}
                  </span>
                  <span
                    class='task-operation'
                    onClick={() => handleDeleteStrategy(row)}
                  >
                    {t('删除')}
                  </span>
                </div>
              ),
            }}
            label={t('操作')}
            renderHeader={renderHeader}
          />
        </bk-table>
      </div>
    );
  },
});
