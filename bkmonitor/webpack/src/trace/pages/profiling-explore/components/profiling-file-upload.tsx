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
import { computed, defineComponent, watch } from 'vue';

import { Button, Dialog, Progress, Upload } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { useProfileUpload } from '../composables/use-profile-upload';
import { useAppStore } from '@/store/modules/app';
import { transformByte } from '@/utils';

import type { ProfileFile } from '../types/file';
import type { UploadFile } from 'bkui-vue/lib/upload/upload.type';

export default defineComponent({
  name: 'ProfilingExploreFileUpload',
  props: { show: Boolean },
  emits: { close: () => true, uploaded: (_file: ProfileFile) => true },
  setup(props, { emit }) {
    const { t } = useI18n();
    const app = useAppStore();
    const upload = useProfileUpload({
      bizId: computed(() => Number(app.bizId)),
      onUploaded: file => emit('uploaded', file),
      onComplete: () => emit('close'),
    });
    watch(
      () => props.show,
      show => {
        if (!show) upload.reset();
      }
    );
    const uploading = computed(() => upload.items.value.some(item => item.status === 'uploading'));
    return { t, upload, uploading, transformByte };
  },
  render() {
    return (
      <Dialog
        width={640}
        isShow={this.show}
        quickClose={!this.uploading}
        title={this.t('上传 Profiling 文件')}
        onClosed={() => this.$emit('close')}
      >
        {{
          default: () =>
            this.show && (
              <div class='profiling-file-upload'>
                <Upload
                  beforeUpload={this.upload.beforeUpload}
                  customRequest={this.upload.request}
                  handleResCode={() => true}
                  size={50}
                  multiple
                >
                  {{
                    default: () => (
                      <div class='profiling-file-dropzone'>
                        <i
                          class='icon-monitor icon-upload-cloud'
                          aria-hidden='true'
                        />
                        <div class='profiling-file-dropzone-action'>
                          {this.t('将文件拖到此处，或')}
                          <span>{this.t('点击上传')}</span>
                        </div>
                        <div class='profiling-file-dropzone-description'>
                          <span>{this.t('支持 pprof、perf_script 格式')}</span>
                          <span>{this.t('单个文件不超过 50 MB，支持批量上传')}</span>
                        </div>
                      </div>
                    ),
                    file: ({ file }: { file: UploadFile }) => {
                      const item = this.upload.items.value.find(item => item.id === file.uid);
                      if (!item)
                        return (
                          <div class='profiling-upload-item'>
                            <i
                              class='icon-monitor icon-mc-file profiling-upload-file-icon'
                              aria-hidden='true'
                            />
                            <div class='profiling-upload-item-content'>
                              <div class='profiling-upload-item-heading'>
                                <span title={file.name}>{file.name}</span>
                              </div>
                              <div
                                class='profiling-upload-error'
                                role='alert'
                              >
                                {file.statusText}
                              </div>
                            </div>
                          </div>
                        );
                      return (
                        <div class='profiling-upload-item'>
                          <i
                            class='icon-monitor icon-mc-file profiling-upload-file-icon'
                            aria-hidden='true'
                          />
                          <div class='profiling-upload-item-content'>
                            <div class='profiling-upload-item-heading'>
                              <span title={item.file.name}>{item.file.name}</span>
                              {item.status === 'uploading' ? (
                                <Button
                                  theme='primary'
                                  text
                                  onClick={() => this.upload.cancel(item.id)}
                                >
                                  {this.t('取消上传')}
                                </Button>
                              ) : (
                                ['error', 'canceled'].includes(item.status) && (
                                  <Button
                                    theme='primary'
                                    text
                                    onClick={() => this.upload.retry(item)}
                                  >
                                    {this.t('重新上传')}
                                  </Button>
                                )
                              )}
                            </div>
                            <div class='profiling-upload-item-meta'>
                              <span>{this.transformByte(item.file.size)}</span>
                              <span
                                class={['profiling-upload-status', item.status]}
                                aria-live='polite'
                              >
                                {this.t(
                                  item.status === 'uploading'
                                    ? item.progress >= 99
                                      ? '等待上传结果'
                                      : '上传中'
                                    : item.status === 'success'
                                      ? '上传成功'
                                      : item.status === 'canceled'
                                        ? '已取消'
                                        : '上传失败'
                                )}
                              </span>
                            </div>
                            {item.status === 'uploading' && (
                              <Progress
                                percent={item.progress}
                                size='small'
                              />
                            )}
                            {item.error && (
                              <div
                                class='profiling-upload-error'
                                role='alert'
                              >
                                {item.error}
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    },
                  }}
                </Upload>
                {this.upload.validationError.value && (
                  <div
                    class='profiling-upload-error'
                    role='alert'
                  >
                    {this.upload.validationError.value}
                  </div>
                )}
                <div class='profiling-upload-hint'>
                  <i
                    class='icon-monitor icon-inform-circle'
                    aria-hidden='true'
                  />
                  <span>{this.t('上传完成后自动关闭窗口，解析进度可在文件列表中查看。')}</span>
                </div>
              </div>
            ),
          footer: () => (
            <div class='profiling-upload-footer'>
              {this.uploading && <span>{this.t('关闭窗口将取消未完成的上传')}</span>}
              <Button onClick={() => this.$emit('close')}>{this.t(this.uploading ? '取消上传并关闭' : '关闭')}</Button>
            </div>
          ),
        }}
      </Dialog>
    );
  },
});
