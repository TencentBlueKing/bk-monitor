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

import { defineComponent, ref, watch } from 'vue';
import { t } from '@/hooks/use-locale';
import http from '@/api';
import { BK_LOG_STORAGE } from '@/store/store.type';
import useStore from '@/hooks/use-store';

import './batch-upload.scss';

export default defineComponent({
  name: 'BatchUpload',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
  },
  emits: ['cancel', 'confirm'],
  setup(props, { emit }) {
    const store = useStore();
    const formRef = ref(null);

    // 表单数据
    const formData = ref({
      fileNameList: [],
      openidList: [],
    });

    // 表单验证规则
    const rules = {
      fileNameList: [
        {
          required: true,
          trigger: 'blur',
        },
      ],
      openidList: [
        {
          required: true,
          trigger: 'blur',
        },
      ],
    };

    // 工厂函数：创建分页选择器的状态和方法
    const createPaginationSelect = (apiMethod: string) => {
      const options = ref<Array<{ id: string; name: string }>>([]);
      const isLoading = ref(false);
      const scrollLoading = ref({ size: 'mini', isLoading: false });
      const searchKeyword = ref('');
      const pagination = ref({ page: 1, pagesize: 10, hasMore: true });
      let searchTimer = null;

      const fetchList = async (isLoadMore = false, keyword = '') => {
        if (!isLoadMore) {
          isLoading.value = true;
          pagination.value.page = 1;
        } else {
          scrollLoading.value.isLoading = true;
        }

        try {
          const params = {
            query: {
              bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
              page: pagination.value.page,
              pagesize: pagination.value.pagesize,
              ...(keyword && { keyword }),
            },
          };
          const response = await http.request(apiMethod, params);
          const newData = (response.data || [])
            .filter((item: any) => item !== '')
            .map((item: any) => ({
              id: item,
              name: item,
            }));

          if (isLoadMore) {
            options.value.push(...newData);
          } else {
            options.value = newData;
          }

          // 判断是否还有更多数据
          pagination.value.hasMore = newData.length === pagination.value.pagesize;

          if (pagination.value.hasMore) {
            pagination.value.page += 1;
          }
        } catch (error) {
          console.error(`获取${apiMethod}数据失败:`, error);
        } finally {
          if (!isLoadMore) {
            isLoading.value = false;
          } else {
            scrollLoading.value.isLoading = false;
          }
        }
      };

      const handleScrollToBottom = () => {
        if (pagination.value.hasMore && !scrollLoading.value.isLoading) {
          fetchList(true, searchKeyword.value);
        }
      };

      const handleRemoteSearch = (keyword: string): Promise<void> => {
        return new Promise((resolve) => {
          if (searchTimer) {
            clearTimeout(searchTimer);
          }
          searchTimer = setTimeout(async () => {
            searchKeyword.value = keyword;
            await fetchList(false, keyword);
            resolve();
          }, 300);
        });
      };

      const reset = () => {
        options.value = [];
        isLoading.value = false;
        scrollLoading.value = { size: 'mini', isLoading: false };
        pagination.value = { page: 1, pagesize: 10, hasMore: true };
        searchKeyword.value = '';
        if (searchTimer) {
          clearTimeout(searchTimer);
          searchTimer = null;
        }
      };

      return {
        options,
        isLoading,
        scrollLoading,
        searchKeyword,
        fetchList,
        handleScrollToBottom,
        handleRemoteSearch,
        reset,
      };
    };

    // 创建文件名和openid的选择器实例
    const fileNameSelect = createPaginationSelect('collect/getFileNameList');
    const openidSelect = createPaginationSelect('collect/getOpenidList');

    // 关闭弹窗
    const handleClose = () => {
      emit('cancel');
    };

    const handleDialogValueChange = (value: boolean) => {
      if (!value) {
        handleClose();
        // 重置表单
        formData.value = {
          fileNameList: [],
          openidList: [],
        };
        // 重置选择器状态
        fileNameSelect.reset();
        openidSelect.reset();
        formRef?.value?.clearError();
      }
    };

    const handleConfirm = async () => {
      if (!formRef.value) return;

      try {
        await formRef.value.validate();
        // 表单验证通过，触发确认事件
        emit('confirm', {
          file_name_list: [...formData.value.fileNameList],
          openid_list: [...formData.value.openidList],
        });
        handleClose();
      } catch (error) {
        console.warn('表单验证失败:', error);
      }
    };

    // 监听弹窗显示状态，当弹窗显示时获取数据
    watch(
      () => props.show,
      (newShow) => {
        if (newShow) {
          // 弹窗显示时获取数据
          fileNameSelect.fetchList();
          openidSelect.fetchList();
        }
      },
      { immediate: true },
    );

    return () => (
      <bk-dialog
        value={props.show}
        title={t('批量上传')}
        width={480}
        mask-close={false}
        header-position='left'
        on-value-change={handleDialogValueChange}
        transfer
      >
        <div class='batch-upload-form'>
          <bk-form
            ref={formRef}
            form-type='vertical'
            {...{
              props: {
                model: formData.value,
                rules,
              },
            }}
          >
            <bk-form-item
              label={t('文件名称')}
              required
              property='fileNameList'
            >
              <bk-select
                multiple
                searchable
                enable-scroll-load
                loading={fileNameSelect.isLoading.value}
                scroll-loading={fileNameSelect.scrollLoading.value}
                value={formData.value.fileNameList}
                remote-method={fileNameSelect.handleRemoteSearch}
                on-change={(value: string[]) => (formData.value.fileNameList = value)}
                on-scroll-end={fileNameSelect.handleScrollToBottom}
              >
                {fileNameSelect.options.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            </bk-form-item>
            <bk-form-item
              label='openid'
              required
              property='openidList'
              style='margin-top: 24px;'
            >
              <bk-select
                multiple
                searchable
                enable-scroll-load
                loading={openidSelect.isLoading.value}
                scroll-loading={openidSelect.scrollLoading.value}
                value={formData.value.openidList}
                remote-method={openidSelect.handleRemoteSearch}
                on-change={(value: string[]) => (formData.value.openidList = value)}
                on-scroll-end={openidSelect.handleScrollToBottom}
              >
                {openidSelect.options.value.map(option => (
                  <bk-option
                    id={option.id}
                    key={option.id}
                    name={option.name}
                  />
                ))}
              </bk-select>
            </bk-form-item>
          </bk-form>
        </div>
        <div slot='footer'>
          <bk-button
            theme='primary'
            on-click={handleConfirm}
          >
            {t('上传')}
          </bk-button>
          <bk-button
            style='margin-left: 8px;'
            on-click={handleClose}
          >
            {t('取消')}
          </bk-button>
        </div>
      </bk-dialog>
    );
  },
});
