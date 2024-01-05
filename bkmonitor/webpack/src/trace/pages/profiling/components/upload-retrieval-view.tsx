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
import { defineComponent, PropType, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { Button, Dialog, Exception, Select, Upload } from 'bkui-vue';
import { Spinner, Upload as UploadIcon } from 'bkui-vue/lib/icon';

import { ConditionType, RetrievalFormData } from '../typings';

import './upload-retrieval-view.scss';

const mockList = [
  {
    id: '1',
    name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
    status: 'loading'
  },
  {
    id: '2',
    name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
    status: 'success'
  },
  {
    id: '3',
    name: 'Profile-2023-11-22-06-02-27.json （原文件名）',
    status: 'error'
  }
];

export default defineComponent({
  name: 'UploadRetrievalView',
  props: {
    formData: {
      type: Object as PropType<RetrievalFormData>,
      required: true
    }
  },
  emits: ['showFileDetail'],
  setup(props, { emit }) {
    const { t } = useI18n();
    function handleShowFileDetail(item) {
      emit('showFileDetail', item);
    }

    const uploadDialogShow = ref(false);
    const active = ref<ConditionType>(ConditionType.Where);
    const selectFile = ref(null);

    function handleUploadTypeChange(type: ConditionType) {
      active.value = type;
    }
    function handleUploadConfirm() {
      uploadDialogShow.value = false;
    }

    return {
      t,
      uploadDialogShow,
      active,
      selectFile,
      handleUploadTypeChange,
      handleUploadConfirm,
      handleShowFileDetail
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
            {this.formData.isComparison && <div class='label where'>{this.t('查询项')}</div>}
            <Select
              v-model={this.selectFile}
              popoverOptions={{
                extCls: 'upload-select-popover'
              }}
            >
              {mockList.map(item => (
                <Select.Option
                  id={item.id}
                  name={item.name}
                >
                  <div class='upload-select-item'>
                    <div class='left'>
                      <div class='status'>
                        {item.status === 'loading' && [
                          <Spinner class='loading'></Spinner>,
                          <span class='label'>{this.t('解析中')}</span>
                        ]}
                        {item.status === 'success' && [
                          <div class='success circle'></div>,
                          <span class='label'>{this.t('解析成功')}</span>
                        ]}
                        {item.status === 'error' && [
                          <div class='error circle'></div>,
                          <span class='label'>{this.t('解析失败')}</span>
                        ]}
                      </div>
                      <div class='divider'></div>
                      <div class='name'>{item.name}</div>
                    </div>
                    <i
                      class='icon-monitor icon-mc-detail'
                      onClick={() => this.handleShowFileDetail(item)}
                    ></i>
                  </div>
                </Select.Option>
              ))}
            </Select>
          </div>
          {this.formData.isComparison && (
            <div class='file-select'>
              {this.formData.isComparison && <div class='label comparison'>{this.t('对比项')}</div>}
              <Select></Select>
            </div>
          )}
        </div>

        <div class='chart-wrap'>
          <Exception
            class='loading-wrap'
            type='search-empty'
          >
            <div class='text'>{this.t('文件解析中')}</div>
            <div class='desc'>{this.t('文件解析可能耗费较长时间，可先选择已解析文件查看')}</div>
          </Exception>
        </div>

        <Dialog
          class={['upload-popover', this.formData.isComparison ? 'show-footer' : '']}
          is-show={this.uploadDialogShow}
          title={this.t('上传文件')}
          show-mask={false}
          width={640}
          onClosed={() => (this.uploadDialogShow = false)}
        >
          {{
            default: () => (
              <div class='upload-popover-wrap'>
                {this.formData.isComparison && (
                  <Button.ButtonGroup class='upload-type-group'>
                    <Button
                      selected={this.active === ConditionType.Where}
                      onClick={() => this.handleUploadTypeChange(ConditionType.Where)}
                    >
                      {this.t('查询项')}
                    </Button>
                    <Button
                      selected={this.active === ConditionType.Comparison}
                      onClick={() => this.handleUploadTypeChange(ConditionType.Comparison)}
                    >
                      {this.t('查询项')}
                    </Button>
                  </Button.ButtonGroup>
                )}

                <Upload>
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
              </div>
            ),
            footer: () => (
              <div class='upload-popover-footer'>
                <Button
                  theme='primary'
                  disabled
                  onClick={this.handleUploadConfirm}
                >
                  {this.t('确定')}
                </Button>
                <Button onClick={() => (this.uploadDialogShow = false)}>{this.t('取消')}</Button>
              </div>
            )
          }}
        </Dialog>
      </div>
    );
  }
});
