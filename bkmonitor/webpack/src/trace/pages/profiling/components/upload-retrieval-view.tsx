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
import { computed, defineComponent, PropType, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Exception, Select } from 'bkui-vue';
import { Upload as UploadIcon } from 'bkui-vue/lib/icon';
import { listProfileUploadRecord } from 'monitor-api/modules/apm_profile';

import { IQueryParams } from '../../../typings/trace';
import { ConditionType, DataTypeItem, RetrievalFormData } from '../typings';
import { EFileStatus, fileStatusMap } from '../typings/profiling-file';

import ProfilingFileUpload from './profiling-file-upload';
import ProfilingRetrievalView from './profiling-retrieval-view';

import './upload-retrieval-view.scss';

export default defineComponent({
  name: 'UploadRetrievalView',
  props: {
    formData: {
      type: Object as PropType<RetrievalFormData>,
      required: true
    },
    queryParams: {
      type: Object as PropType<IQueryParams>,
      required: true
    },
    dataTypeList: {
      type: Array as PropType<DataTypeItem[]>,
      default: () => []
    },
    dataType: {
      type: String,
      default: 'cpu'
    }
  },
  emits: ['showFileDetail', 'selectFile', 'dataTypeChange'],
  setup(props, { emit }) {
    const { t } = useI18n();

    const uploadDialogShow = ref(false);
    const active = ref<ConditionType>(ConditionType.Where);
    const selectFile = ref(null);

    /* 查询项 */
    const searchObj = reactive({
      selectFile: '',
      selectFileInfo: null,
      list: []
    });
    /* 对比项   暂时不做 */
    const compareObj = reactive({
      selectFile: '',
      list: []
    });
    const loading = ref(false);

    const isCompare = computed(() => {
      return false;
      // return !!props.formData.isComparison;
    });

    const selectToggle = ref(false);

    init();

    /**
     * @description 初始化
     */
    async function init() {
      await handleRefleshFiles();
    }

    function handleShowFileDetail(item) {
      emit('showFileDetail', item);
    }

    function handleUploadTypeChange(type: ConditionType) {
      active.value = type;
    }

    /**
     * @description 文件上传弹窗
     * @param v
     */
    function handleUploadShowChange(v: boolean) {
      uploadDialogShow.value = v;
    }

    /**
     * @description 选中文件
     * @param v
     */
    function handleSelectFile(v) {
      const fileInfo = searchObj.list.find(item => item.id === v);
      if (!!fileInfo && fileInfo?.status === EFileStatus.storeSucceed) {
        searchObj.selectFile = v;
        searchObj.selectFileInfo = fileInfo;
        emit('selectFile', fileInfo);
      }
    }

    async function handleRefleshFiles() {
      const data = await listProfileUploadRecord().catch(() => []);
      searchObj.list = data;
      if (searchObj.list.length && !searchObj.selectFile) {
        handleSelectFile(searchObj.list[0].id);
      }
    }

    function handleDataTypeChange(v: string) {
      emit('dataTypeChange', v);
    }

    /**
     * @description 下拉状态
     * @param v
     */
    function handleSelectFileToggle(v: boolean) {
      selectToggle.value = v;
    }

    function statusRender(status: EFileStatus, needName = true) {
      if ([EFileStatus.uploaded, EFileStatus.parsingSucceed, EFileStatus.storeSucceed].includes(status)) {
        return (
          <div class='status'>
            <div class='success circle'></div>
            {needName && <span class='label'>{fileStatusMap[status].name}</span>}
          </div>
        );
      }
      if ([EFileStatus.parsingFailed, EFileStatus.storeFailed].includes(status)) {
        return (
          <div class='status'>
            <div class='error circle'></div>
            {needName && <span class='label'>{fileStatusMap[status].name}</span>}
          </div>
        );
      }
      // if (status === 'running') {
      //   return (
      //     <div class='status'>
      //       <Spinner class='loading'></Spinner>
      //       <span class='label'>{t('解析中')}</span>
      //     </div>
      //   );
      // }
    }

    return {
      t,
      uploadDialogShow,
      active,
      selectFile,
      searchObj,
      compareObj,
      loading,
      isCompare,
      selectToggle,
      handleUploadTypeChange,
      handleUploadShowChange,
      statusRender,
      handleShowFileDetail,
      handleSelectFile,
      handleRefleshFiles,
      handleDataTypeChange,
      handleSelectFileToggle
    };
  },
  render() {
    return (
      <div class='upload-retrieval-view-component'>
        <div class='header-wrap'>
          <Button
            class='upload-btn'
            theme='primary'
            onClick={() => (this.uploadDialogShow = true)}
          >
            <UploadIcon class='upload-icon' />
            {this.t('上传文件')}
          </Button>

          <div class='file-select'>
            {this.isCompare && <div class='label where'>{this.t('查询项')}</div>}
            <Select
              modelValue={this.searchObj.selectFile}
              popoverOptions={{
                extCls: 'upload-select-popover',
                zIndex: 1
              }}
              clearable={false}
              onSelect={v => this.handleSelectFile(v)}
              onToggle={v => this.handleSelectFileToggle(v)}
            >
              {{
                trigger: () => (
                  <span class='select-trigger'>
                    <span class='left'>
                      {!!this.searchObj.selectFileInfo && (
                        <>
                          <span class='file-name'>{this.searchObj.selectFileInfo?.file_name || '--'}</span>
                          {this.statusRender(this.searchObj.selectFileInfo?.status, false)}
                        </>
                      )}
                    </span>
                    <span class='right'>
                      <span class={['icon-monitor icon-mc-triangle-down', { active: this.selectToggle }]}></span>
                    </span>
                  </span>
                ),
                default: () =>
                  this.searchObj.list.map(item => (
                    <Select.Option
                      id={item.id}
                      key={item.id}
                      name={item.file_name || '--'}
                      disabled={item.status !== EFileStatus.storeSucceed}
                    >
                      <div class='upload-select-item'>
                        <div class='left'>
                          {this.statusRender(item.status)}
                          <div class='divider'></div>
                          <div class='name'>{item.file_name || '--'}</div>
                          <div class='origin-name'>{`（${item.origin_file_name}）`}</div>
                        </div>
                        <i
                          class='icon-monitor icon-mc-detail'
                          onClick={e => {
                            e.stopPropagation();
                            this.handleShowFileDetail(item);
                          }}
                        ></i>
                      </div>
                    </Select.Option>
                  ))
              }}
            </Select>
          </div>
          {this.isCompare && (
            <div class='file-select'>
              {this.isCompare && <div class='label comparison'>{this.t('对比项')}</div>}
              <Select
                modelValue={this.compareObj.selectFile}
                popoverOptions={{
                  extCls: 'upload-select-popover'
                }}
              >
                {this.compareObj.list.map(item => (
                  <Select.Option
                    id={item.id}
                    name={item.file_name || '--'}
                    key={item.id}
                  >
                    <div class='upload-select-item'>
                      <div class='left'>
                        {this.statusRender(item.status)}
                        <div class='divider'></div>
                        <div class='name'>{item.file_name}</div>
                        <div class='origin-name'>{`（${item.origin_file_name}）`}</div>
                      </div>
                      <i class='icon-monitor icon-mc-detail'></i>
                    </div>
                  </Select.Option>
                ))}
              </Select>
            </div>
          )}
        </div>

        <div class='chart-wrap'>
          {this.loading || !this.searchObj.selectFile ? (
            <div class='exception-wrap'>
              <Exception
                class='loading-wrap'
                type='search-empty'
              >
                <div class='text'>
                  {!!this.searchObj.selectFile ? `${this.t('文件解析中')}...` : this.t('暂无数据')}
                </div>
                <div class='desc'>
                  {!!this.searchObj.selectFile
                    ? this.t('文件解析可能耗费较长时间，可先选择已解析文件查看')
                    : this.t('请上传文件后查看')}
                </div>
              </Exception>
            </div>
          ) : (
            <ProfilingRetrievalView
              dataType={this.dataType}
              queryParams={this.queryParams}
              onUpdate:dataType={this.handleDataTypeChange}
              dataTypeList={this.dataTypeList}
            ></ProfilingRetrievalView>
          )}
        </div>

        <ProfilingFileUpload
          show={this.uploadDialogShow}
          appName={this.formData.server.app_name}
          isCompare={this.isCompare}
          onShowChange={this.handleUploadShowChange}
          onRefleshFiles={this.handleRefleshFiles}
        ></ProfilingFileUpload>
      </div>
    );
  }
});
