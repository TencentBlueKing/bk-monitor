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

import { blobDownload } from '@/common/util';
import { axiosInstance } from '@/api';
import { Message } from 'bk-magic-vue';
import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import * as authorityMap from '../../../../common/authority-map';

/**
 * 文件下载 Hook
 * 用于统一处理表格中的文件下载逻辑（含权限校验）
 */
export const useDownloadFile = () => {
  const store = useStore();

  /**
   * 下载文件
   * @param fileName 文件名
   * @param isAllowedDownload 是否有下载权限
   */
  const downloadFile = async (fileName: string, isAllowedDownload: boolean) => {
    if (isAllowedDownload) {
      axiosInstance
        .get('/tgpa/task/download_file/', {
          params: {
            bk_biz_id: store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID],
            file_name: fileName,
          },
          responseType: 'blob',
        })
        .then((res) => {
          const contentType = res.headers?.['content-type'] || '';
          if (!contentType.includes('application/zip')) {
            Message({
              theme: 'error',
              message: t('文件不存在'),
            });
            return;
          }
          blobDownload(res.data, fileName);
        })
        .catch((error) => {
          console.error('下载失败:', error);
        });
    } else {
      const paramData = {
        action_ids: [authorityMap.DOWNLOAD_FILE_AUTH],
        resources: [
          {
            type: 'space',
            id: store.state.spaceUid,
          },
        ],
      };
      const res = await store.dispatch('getApplyData', paramData);
      store.commit('updateState', { authDialogData: res.data });
    }
  };

  return {
    downloadFile,
  };
};
