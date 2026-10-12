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
import { type Ref, onScopeDispose, shallowRef, watch } from 'vue';

import { useI18n } from 'vue-i18n';

import { uploadProfileFile } from '../services/files';

import type { ProfileFile, ProfileUploadItem } from '../types/file';
import type { UploadRawFile, UploadRequestOptions } from 'bkui-vue/lib/upload/upload.type';

export function useProfileUpload({
  bizId,
  onUploaded,
  onComplete,
}: {
  bizId: Ref<number>;
  onComplete: () => void;
  onUploaded: (file: ProfileFile) => void;
}) {
  const { t } = useI18n();
  const items = shallowRef<ProfileUploadItem[]>([]);
  const validationError = shallowRef('');
  const controllers = new Map<number, AbortController>();

  function update(id: number, value: Partial<ProfileUploadItem>) {
    items.value = items.value.map(item => (item.id === id ? { ...item, ...value } : item));
  }

  function beforeUpload(file: File) {
    validationError.value = file.size > 50 * 1024 * 1024 ? t('文件大小不能超过 50 MB') : '';
    return !validationError.value;
  }

  async function request({ file }: Pick<UploadRequestOptions, 'file'>) {
    const id = (file as UploadRawFile).uid;
    const controller = new AbortController();
    controllers.get(id)?.abort();
    controllers.set(id, controller);
    const item: ProfileUploadItem = { id, file, progress: 0, status: 'uploading', error: '' };
    items.value = [...items.value.filter(item => item.id !== id), item];
    try {
      const result = await uploadProfileFile(bizId.value, file, controller.signal, progress => {
        if (!controller.signal.aborted) update(id, { progress });
      });
      if (controller.signal.aborted) return;
      update(id, { progress: 100, status: 'success' });
      onUploaded(result);
      if (items.value.every(item => item.status === 'success')) onComplete();
      return result;
    } catch (e) {
      if (!controller.signal.aborted) {
        update(id, { status: 'error', error: (e as Error)?.message || t('上传失败，请重试') });
      }
      throw e;
    } finally {
      if (controllers.get(id) === controller) controllers.delete(id);
    }
  }

  function cancel(id: number) {
    controllers.get(id)?.abort();
    controllers.delete(id);
    update(id, { status: 'canceled' });
  }

  function retry(item: ProfileUploadItem) {
    request({ file: item.file }).catch(() => {});
  }

  function reset() {
    controllers.forEach(controller => controller.abort());
    controllers.clear();
    items.value = [];
    validationError.value = '';
  }

  watch(bizId, reset);
  onScopeDispose(reset);
  return { items, validationError, beforeUpload, request, cancel, retry, reset };
}
