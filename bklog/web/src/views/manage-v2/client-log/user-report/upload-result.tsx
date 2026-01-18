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

import { defineComponent } from 'vue';

import { t } from '@/hooks/use-locale';
import { UploadStatus } from './types';

import './upload-result.scss';

export default defineComponent({
  name: 'UploadResult',
  props: {
    show: {
      type: Boolean,
      default: false,
    },
    status: {
      type: String as () => UploadStatus,
      default: UploadStatus.RUNNING,
    },
  },
  emits: ['close', 'retry', 'go-search', 'back-list'],
  setup(props, { emit }) {
    // 关闭弹窗
    const handleClose = () => {
      emit('close');
    };

    // 重试
    const handleRetry = () => {
      emit('retry');
    };

    // 去首页查询
    const handleGoSearch = () => {
      emit('go-search');
    };

    // 返回列表
    const handleBackList = () => {
      emit('back-list');
    };

    // 渲染上传中状态
    const renderRunning = () => (
      <div class='upload-result-content'>
        <div
          class='upload-icon running'
          key='running'
        >
          <bk-spin size='normal'></bk-spin>
        </div>
        <div class='upload-title'>{t('日志上传中...')}</div>
        <div class='upload-desc'>{t('预计等待2-3分钟，窗口关闭后不会影响任务执行')}</div>
        <div class='upload-actions'>
          <bk-button on-click={handleClose}>{t('关闭')}</bk-button>
        </div>
      </div>
    );

    // 渲染上传成功状态
    const renderSuccess = () => (
      <div class='upload-result-content'>
        <div
          class='upload-icon success'
          key='success'
        >
          <i class='bk-icon icon-check-1'></i>
        </div>
        <div class='upload-title'>{t('日志上传成功')}</div>
        <div class='upload-actions'>
          <bk-button
            theme='primary'
            on-click={handleGoSearch}
          >
            {t('去首页查询')}
          </bk-button>
          <bk-button on-click={handleBackList}>{t('返回列表')}</bk-button>
        </div>
      </div>
    );

    // 渲染上传失败状态
    const renderFailed = () => (
      <div class='upload-result-content'>
        <div
          class='upload-icon failed'
          key='failed'
        >
          <i class='bk-icon icon-close'></i>
        </div>
        <div class='upload-title'>{t('日志上传失败')}</div>
        <div class='upload-actions'>
          <bk-button
            theme='primary'
            on-click={handleRetry}
          >
            {t('重试')}
          </bk-button>
        </div>
      </div>
    );

    const handleDialogValueChange = (value: boolean) => {
      if (!value) {
        handleClose();
      }
    };

    // 根据状态渲染内容
    const renderContent = () => {
      switch (props.status) {
        case UploadStatus.RUNNING:
          return renderRunning();
        case UploadStatus.SUCCESS:
          return renderSuccess();
        case UploadStatus.FAILED:
          return renderFailed();
        default:
          return renderRunning();
      }
    };

    return () => (
      <bk-dialog
        value={props.show}
        width={400}
        show-footer={false}
        on-closed={handleClose}
        on-value-change={handleDialogValueChange}
        transfer
      >
        {renderContent()}
      </bk-dialog>
    );
  },
});
