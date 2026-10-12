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
import { type PropType, defineComponent } from 'vue';

import { Button, Sideslider } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { fileStatusLabels } from '../utils/file';
import { useDocumentLink } from '@/hooks';
import { transformByte } from '@/utils';

import type { ProfileFile } from '../types/file';

export default defineComponent({
  name: 'ProfilingExploreFileDetail',
  props: { file: { type: Object as PropType<ProfileFile>, default: null } },
  emits: { close: () => true },
  setup() {
    const { t } = useI18n();
    const { handleGotoLink } = useDocumentLink();
    return { t, handleGotoLink };
  },
  render() {
    const file = this.file;
    return (
      <Sideslider
        width={560}
        isShow={!!file}
        title={this.t('文件详情')}
        quickClose
        onClosed={() => this.$emit('close')}
      >
        {file && (
          <>
            <div class='profiling-file-guide'>
              <Button
                theme='primary'
                text
                onClick={() => this.handleGotoLink('profiling_docs')}
              >
                {this.t('Profile 接入指引')}
              </Button>
            </div>
            <dl class='profiling-service-detail'>
              {[
                ['文件名称', file.file_name],
                ['原文件名', file.origin_file_name],
                ['文件大小', transformByte(file.file_size)],
                ['协议类型', file.file_type],
                ['解析状态', this.t(fileStatusLabels[file.status] || file.status)],
                ['文件md5', file.file_md5],
                ['上传人', file.operator],
                ['上传时间', file.uploaded_time],
                ['pprof文件时间', file.data_time],
                ...(['parsing_failed', 'store_failed'].includes(file.status) ? [['错误信息', file.content]] : []),
              ].map(([label, value]) => (
                <>
                  <dt key={`${label}-label`}>{this.t(label)}</dt>
                  <dd key={label}>{value || '--'}</dd>
                </>
              ))}
            </dl>
          </>
        )}
      </Sideslider>
    );
  },
});
