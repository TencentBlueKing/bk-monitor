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

import { blobDownload, readBlobRespToJson } from '@/common/util';
import { axiosInstance } from '@/api';
import { Message } from 'bk-magic-vue';
import { t } from '@/hooks/use-locale';
import useStore from '@/hooks/use-store';
import { BK_LOG_STORAGE } from '@/store/store.type';
import * as authorityMap from '../../../../common/authority-map';

/**
 * 从 Content-Disposition 响应头中解析文件名
 * 优先取 RFC 5987 编码格式（filename*=UTF-8''xxx），其次取普通格式（filename="xxx"）
 * @param contentDisposition Content-Disposition 响应头
 * @returns 解析出的文件名，解析失败时返回空字符串
 */
const parseFileNameFromHeader = (contentDisposition?: string): string => {
  if (!contentDisposition) return '';

  const encodedMatch = /filename\*\s*=\s*[^']*''([^;]+)/i.exec(contentDisposition);
  if (encodedMatch?.[1]) {
    try {
      return decodeURIComponent(encodedMatch[1].trim());
    } catch {
      // 编码不合法时忽略，继续尝试普通格式
    }
  }

  const match = /filename\s*=\s*("([^"]*)"|([^;]+))/i.exec(contentDisposition);
  if (!match) return '';

  return (match[2] ?? match[3] ?? '').trim();
};

/** 下载参数 */
interface DownloadFileOptions {
  /** 是否优先使用响应头 Content-Disposition 中的文件名，默认 false（使用入参 fileName） */
  useResponseFileName?: boolean;
}

/**
 * 文件下载 Hook
 * 用于统一处理表格中的文件下载逻辑（含权限校验）
 */
export const useDownloadFile = () => {
  const store = useStore();

  /**
   * 请求单个文件并触发浏览器保存；错误提示保持原有逻辑
   * @param fileName 文件名
   * @param bkBizId 业务ID
   * @param options 下载参数
   */
  const requestFileDownload = async (fileName: string, bkBizId: number | string, options: DownloadFileOptions = {}) => {
    try {
      const res = await axiosInstance.get('/tgpa/task/download_file/', {
        params: {
          bk_biz_id: bkBizId,
          file_name: fileName,
        },
        responseType: 'blob',
      });
      const contentType = res.headers?.['content-type'] || '';
      if (!contentType.includes('application/zip')) {
        try {
          const jsonData = await readBlobRespToJson(res.data);
          if (jsonData?.code !== 0) {
            Message({
              theme: 'error',
              message: jsonData?.message || t('文件不存在'),
            });
            return;
          }
        } catch {
          Message({
            theme: 'error',
            message: t('文件不存在'),
          });
          return;
        }
      }
      // 仅按需取响应头文件名（后端会按 openid/任务ID/创建人/创建时间生成），未开启或解析失败时使用入参文件名
      const responseFileName = options.useResponseFileName
        ? parseFileNameFromHeader(res.headers?.['content-disposition'])
        : '';
      blobDownload(res.data, responseFileName || fileName);
    } catch (error) {
      console.error('下载失败:', error);
    }
  };

  /** 无下载权限时弹出权限申请 */
  const requestApplyPermission = async () => {
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
  };

  /**
   * 下载文件
   * @param fileName 文件名
   * @param isAllowedDownload 是否有下载权限
   * @param options 下载参数
   */
  const downloadFile = async (fileName: string, isAllowedDownload: boolean, options: DownloadFileOptions = {}) => {
    if (isAllowedDownload) {
      requestFileDownload(fileName, store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID], options);
    } else {
      await requestApplyPermission();
    }
  };

  /**
   * 按文件名去重后按首次出现顺序串行下载，单个失败不影响后续文件；无权限时仅申请一次
   * @param fileNames 文件名列表
   * @param isAllowedDownload 是否有下载权限
   * @param options 下载参数
   */
  const downloadFiles = async (fileNames: string[], isAllowedDownload: boolean, options: DownloadFileOptions = {}) => {
    const uniqueFileNames = [...new Set(fileNames.filter(Boolean))];
    if (!uniqueFileNames.length) return;
    if (!isAllowedDownload) {
      await requestApplyPermission();
      return;
    }
    const bkBizId = store.state.storage[BK_LOG_STORAGE.BK_BIZ_ID];
    for (const fileName of uniqueFileNames) {
      await requestFileDownload(fileName, bkBizId, options);
    }
  };

  return {
    downloadFile,
    downloadFiles,
  };
};
