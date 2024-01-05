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
import { computed, defineComponent, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Alert, Button, Dialog, Upload } from 'bkui-vue';
import { TextFill as UploadTextFill, Upload as UploadIcon } from 'bkui-vue/lib/icon';

import { ConditionType } from '../typings/profiling-retrieval';

import './profiling-file-upload.scss';

const uploadTypeList = [
  { id: ConditionType.Where, name: window.i18n.t('查询项') },
  { id: ConditionType.Comparison, name: window.i18n.t('对比项') }
];

interface IFileStatus {
  name: string;
  uid: number;
  progress: number;
  isCancel: boolean;
}

export default defineComponent({
  name: 'ProfilingFileUpload',
  props: {
    show: {
      type: Boolean,
      default: false
    },
    isCompare: {
      type: Boolean,
      default: false
    }
  },
  emits: ['showChange'],
  setup(_props, { emit }) {
    const { t } = useI18n();
    const uploadType = ref<ConditionType>(ConditionType.Where);

    /* 查询项 */
    const searchObj = reactive({
      files: [],
      isRunning: false
    });
    /* 对比详情 */
    const compareObj = reactive({
      files: [],
      isRunning: false
    });

    const isRunning = computed(() => {
      if (uploadType.value === ConditionType.Where) {
        return searchObj.isRunning;
      }
      return compareObj.isRunning;
    });

    const filesStatus = ref<IFileStatus[]>([]);

    function showChange(v: Boolean) {
      emit('showChange', v);
    }

    /**
     * @description 切换类型
     * @param v
     */
    function handleUploadTypeChange(v: ConditionType) {
      uploadType.value = v;
    }

    /**
     * @description 上传的文件
     * @param options
     */
    function handleUploadProgress(options) {
      console.log(options);
      if (uploadType.value === ConditionType.Where) {
        searchObj.files.push(options.file);
        setTimeout(() => {
          searchObj.isRunning = true;
          filesStatus.value = searchObj.files.map(item => ({
            name: item.name,
            uid: item.uid,
            progress: 0.5,
            isCancel: false
          }));
        }, 300);
      } else {
        compareObj.files.push(options.file);
        setTimeout(() => {
          compareObj.isRunning = true;
          filesStatus.value = searchObj.files.map(item => ({
            name: item.name,
            uid: item.uid,
            progress: 0.5,
            isCancel: false
          }));
        }, 50);
      }
    }

    return {
      uploadType,
      searchObj,
      compareObj,
      isRunning,
      filesStatus,
      showChange,
      handleUploadTypeChange,
      handleUploadProgress,
      t
    };
  },
  render() {
    return (
      <Dialog
        isShow={this.show}
        extCls={'profiling-file-upload-component'}
        title={this.t('上传文件')}
        dialogType={this.isCompare ? 'operation' : 'show'}
        width={640}
        onClosed={() => this.showChange(false)}
        onConfirm={() => this.showChange(false)}
      >
        {{
          default: () => (
            <div class='upload-file-wrap'>
              {this.isCompare && (
                <Button.ButtonGroup class='upload-type-group'>
                  {uploadTypeList.map(item => (
                    <Button
                      key={item.id}
                      selected={this.uploadType === item.id}
                      onClick={() => this.handleUploadTypeChange(item.id)}
                    >
                      {item.name}
                    </Button>
                  ))}
                </Button.ButtonGroup>
              )}
              {!this.isRunning ? (
                <Upload customRequest={this.handleUploadProgress as any}>
                  <div class='upload-content'>
                    <UploadIcon class='upload-icon' />
                    <span class='title'>{this.t('点击上传或将文件拖到此处')}</span>
                    <span class='desc'>{this.t('支持 pprof, json 等文件格式')}</span>
                    <Button
                      theme='primary'
                      class='upload-btn'
                    >
                      {this.t('上传')}
                    </Button>
                  </div>
                </Upload>
              ) : (
                <div class='upload-running-wrap'>
                  <div class='file-list'>
                    {this.filesStatus.map(item => (
                      <div
                        class='file-list-item'
                        key={item.uid}
                      >
                        <div class='file-logo'>
                          <UploadTextFill
                            width={22}
                            height={28}
                            fill={'#A3C5FD'}
                          ></UploadTextFill>
                        </div>
                        <div class='file-status'>
                          <div class='file-name'>
                            <span class='name'>{item.name}</span>
                            <span class='cancel-btn'>{this.t('取消上传')}</span>
                          </div>
                          <div class='status-progress'>
                            <div
                              class='progress-line'
                              style={{
                                width: `${item.progress * 100}%`
                              }}
                            ></div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                  <div class='tips-wrap'>
                    <Alert
                      theme='info'
                      title={'上传成功后会自动关闭当前上传窗口，并进行文件解析;'}
                    ></Alert>
                  </div>
                </div>
              )}
            </div>
          )
        }}
      </Dialog>
    );
  }
});
