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
import axios from 'axios';
import { Alert, Button, Dialog, Upload } from 'bkui-vue';
import { TextFill as UploadTextFill, Upload as UploadIcon } from 'bkui-vue/lib/icon';
import { upload } from 'monitor-api/modules/apm_profile';

import { FILES_TYPE_NAME } from '../typings/profiling-file';
import { ConditionType } from '../typings/profiling-retrieval';

import './profiling-file-upload.scss';

// function getFileType(fileName: string) {
//   const regex = /(?:\.([^.]+))?$/;
//   const extension = regex.exec(fileName)[1];
//   const type = extension.toLocaleLowerCase();
//   if (type === 'prof') {
//     return 'pprof';
//   }
//   return type;
// }

function valueFlash(set, val, limit) {
  let v = 0; // 初始值
  const interval = 10; // 每次执行的间隔毫秒数
  const step = val / (limit / interval); // 每次累加的步长
  const timer = setInterval(function () {
    // 定义一个计时器
    v += step; // 累加
    if (v >= val || v >= 0.99) {
      // 如果达到或超过目标值
      set(val); // 显示目标值
      clearInterval(timer); // 清除计时器
    } else {
      // 否则
      set(v.toFixed(2)); // 显示目标值
    }
  }, interval); // 每隔interval毫秒执行一次
  return timer;
}

const uploadTypeList = [
  { id: ConditionType.Where, name: window.i18n.t('查询项') },
  { id: ConditionType.Comparison, name: window.i18n.t('对比项') }
];

enum EFileStatus {
  failure = 'failure',
  running = 'running',
  success = 'success'
}
interface IFileStatus {
  name: string;
  uid: number;
  progress: number;
  status: EFileStatus;
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
    },
    appName: {
      type: String,
      default: ''
    }
  },
  emits: ['showChange', 'refleshFiles'],
  setup(_props, { emit }) {
    const { t } = useI18n();
    const uploadType = ref<ConditionType>(ConditionType.Where);

    /* 查询项 */
    const searchObj = reactive<{
      files: IFileStatus[];
      isRunning: boolean;
    }>({
      files: [],
      isRunning: false
    });
    /* 对比详情 */
    const compareObj = reactive({
      files: [],
      isRunning: false
    });

    const cancelObj = reactive<{
      [uid: number]: any;
    }>({});

    const timerObj = reactive<{
      [uid: number]: any;
    }>({});

    const isRunning = computed(() => {
      if (uploadType.value === ConditionType.Where) {
        return searchObj.isRunning;
      }
      return compareObj.isRunning;
    });

    const filesStatus = ref<IFileStatus[]>([]);

    function showChange(v: Boolean) {
      if (!v) {
        searchObj.files.forEach(item => {
          cancelObj?.[item.uid]?.cancel?.();
        });
        searchObj.files = [];
        searchObj.isRunning = false;
        filesStatus.value = [...searchObj.files];
      }
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
      if (uploadType.value === ConditionType.Where) {
        const fileOption = {
          name: options.file.name,
          uid: options.file.uid,
          progress: 0,
          status: EFileStatus.running
        };
        searchObj.files.push(fileOption);
        filesStatus.value.push(fileOption);
        searchObj.isRunning = true;
        uploadFiles(options.file);
      } else {
        // compareObj.files.push(options.file);
        // compareObj.isRunning = true;
        // filesStatus.value.push({
        //   name: options.file.name,
        //   uid: options.file.uid,
        //   progress: 0,
        //   isCancel: false
        // });
      }
    }
    /**
     * @description 上传文件接口
     * @param file
     */
    function uploadFiles(file: any) {
      const params = {
        // 暂时默认传pprof
        file_type: 'pprof',
        file,
        global_query: 1
      };
      const cancelTokenSource = axios.CancelToken.source();
      cancelObj[file.uid] = cancelTokenSource;
      const fileObj = searchObj.files.find(item => item.uid === file.uid);
      const curFileObj = filesStatus.value.find(item => item.uid === file.uid);
      if (fileObj && curFileObj) {
        timerObj[file.uid] = valueFlash(
          val => {
            fileObj.progress = val;
            curFileObj.progress = val;
          },
          0.99,
          3000
        );
        upload(params, { cancelToken: cancelObj[file.uid].token })
          .then(data => {
            console.log(data);
            window.clearInterval(timerObj[file.uid]);
            fileObj.progress = 1;
            fileObj.status = EFileStatus.success;
            if (searchObj.files.every(f => f.status === EFileStatus.success)) {
              showChange(false);
              emit('refleshFiles');
            }
          })
          .catch(() => {
            window.clearInterval(timerObj[file.uid]);
            fileObj.progress = 0;
            fileObj.status = EFileStatus.failure;
          });
      }
    }

    /**
     * @description 取消上传
     * @param uid
     */
    function cancelUpload(uid: number) {
      cancelObj?.[uid]?.cancel?.();
      window.clearInterval(timerObj[uid]);
      const fileObj = searchObj.files.find(item => item.uid === uid);
      fileObj.progress = 0;
      fileObj.status = EFileStatus.failure;
      filesStatus.value = [...searchObj.files];
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
      t,
      cancelUpload
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
              <div
                style={{
                  display: this.isRunning ? 'none' : undefined
                }}
              >
                <Upload
                  customRequest={this.handleUploadProgress as any}
                  // accept={FILES_TYPE.map(f => `.${f}`).join(',')}
                >
                  {{
                    default: () => (
                      <div class='upload-content'>
                        <UploadIcon class='upload-icon' />
                        <span class='title'>{this.t('点击上传或将文件拖到此处')}</span>
                        <span class='desc'>{this.t('支持{0}等文件格式', [FILES_TYPE_NAME])}</span>
                        <Button
                          theme='primary'
                          class='upload-btn'
                        >
                          {this.t('上传')}
                        </Button>
                      </div>
                    )
                  }}
                </Upload>
              </div>
              <div
                class='upload-running-wrap'
                style={{
                  display: !this.isRunning ? 'none' : undefined
                }}
              >
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
                          {(() => {
                            if (item.status === EFileStatus.running) {
                              return (
                                <span
                                  class='cancel-btn running'
                                  onClick={() => this.cancelUpload(item.uid)}
                                >
                                  {this.t('取消上传')}
                                </span>
                              );
                            }
                            if (item.status === EFileStatus.success) {
                              return <span class='cancel-btn success'>{this.t('上传成功')}</span>;
                            }
                            if (item.status === EFileStatus.failure) {
                              return <span class='cancel-btn failure'>{this.t('上传失败')}</span>;
                            }
                          })()}
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
            </div>
          )
        }}
      </Dialog>
    );
  }
});
