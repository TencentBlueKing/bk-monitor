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
import { Component, Prop, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import type { CodeRedefineItem } from 'monitor-ui/chart-plugins/plugins/apm-service-caller-callee/type';
import { uploadJsonFile } from 'monitor-pc/pages/view-detail/utils';
import Redefine from './components/redefine';
import Remark from './components/remark';

import './index.scss';
interface ReturnCodeProps {
  appName: string;
}

@Component
export default class ReturnCode extends tsc<ReturnCodeProps> {
  @Prop({ default: '' }) appName: string;

  @Ref('fileRef') fileRef!: HTMLInputElement;
  @Ref('tabContentRef') tabContentRef: any;

  tabList = [
    {
      id: 'redefine',
      name: this.$t('返回码重定义'),
    },
    {
      id: 'remark',
      name: this.$t('返回码备注'),
    },
  ];
  activeTab = 'redefine';
  isBatchEdit = false;
  currentEditRowId = '';
  isBatchEditLoading = false;
  tableMaxHeight = window.innerHeight - 350;

  get isRedefineTab() {
    return this.activeTab === 'redefine';
  }

  handleTabClick(id: string) {
    this.handleCancelBatchEdit();
    this.activeTab = id;
    const { query } = this.$route;
    this.$router.replace({
      query: {
        ...query,
        type: id,
      },
      params: {
        appName: this.appName,
      },
    });
  }

  handleBatchEdit() {
    this.isBatchEdit = true;
    this.tabContentRef?.handleBatchEdit();
  }

  handleCancelBatchEdit() {
    this.isBatchEdit = false;
    this.tabContentRef?.handleCancelBatchEdit();
  }

  handleBatchEditSave() {
    this.isBatchEditLoading = true;
    this.tabContentRef?.handleBatchSave();
  }

  handleAddRow() {
    this.tabContentRef?.addRow();
  }

  handleWindowResize() {
    this.tableMaxHeight = window.innerHeight - 350;
  }

  mounted() {
    const { query } = this.$route;
    if (query.type) {
      this.activeTab = query.type as string;
    }
    window.addEventListener('resize', this.handleWindowResize);
  }

  beforeDestroy() {
    window.removeEventListener('resize', this.handleWindowResize);
  }

  async fileChange(e) {
    // 读取导入的 json 文件
    const files = e.target.files;
    const data = await uploadJsonFile<CodeRedefineItem[]>(files[0]).catch(() => []);
    const isDataValid = this.isRedefineTab ? data.every(item => !item.code) : data.every(item => item.code);
    if (!data || !Array.isArray(data) || !isDataValid) {
      this.$bkMessage({
        theme: 'error',
        message: this.$t('文件格式不正确'),
      });
      return;
    }

    this.tabContentRef?.handleImport(data);

    this.$nextTick(() => {
      this.handleBatchEdit();
    });
  }

  handleImport() {
    // 触发隐藏文件选择框
    if (this.fileRef) {
      this.fileRef.value = '';
      this.fileRef.click();
    }
  }

  handleExport() {
    this.tabContentRef?.handleExport();
  }

  handleCurrentEditRowIdChange(id: string) {
    this.currentEditRowId = id;
  }

  handleBatchSaveSuccess() {
    this.isBatchEdit = false;
    this.isBatchEditLoading = false;
  }

  handleBatchSaveFailed() {
    this.isBatchEditLoading = false;
  }

  render() {
    const Component = this.isRedefineTab ? Redefine : Remark;
    return (
      <div class='return-code-page-main'>
        <div class='tab-list'>
          {this.tabList.map(item => {
            return (
              <div
                key={item.id}
                class={['tab-item', { 'is-active': this.activeTab === item.id }]}
                onClick={() => this.handleTabClick(item.id)}
              >
                <span class='tab-item-name'>{item.name}</span>
              </div>
            );
          })}
        </div>
        <div class='top-btns'>
          <span
            v-bk-tooltips={{
              content: this.$t('当前已有配置正在编辑，请先保存或取消'),
              disabled: this.currentEditRowId === '',
            }}
          >
            <bk-button
              icon='plus'
              disabled={this.currentEditRowId !== ''}
              theme='primary'
              on-click={this.handleAddRow}
            >
              {this.$t('新增')}
            </bk-button>
          </span>
          {!this.isBatchEdit ? (
            <bk-button on-click={this.handleBatchEdit}>
              <i class='icon-monitor icon-mc-wholesale-editor' />
              {this.$t('批量编辑')}
            </bk-button>
          ) : (
            <div class='batch-group'>
              <bk-button
                outline
                theme='primary'
                disabled={this.isBatchEditLoading}
                loading={this.isBatchEditLoading}
                on-click={this.handleBatchEditSave}
              >
                <div class='save-btn'>
                  <i class='bk-icon icon-save' />
                  {this.$t('保存')}
                </div>
              </bk-button>
              <bk-button
                icon='close'
                on-click={this.handleCancelBatchEdit}
              >
                {this.$t('取消')}
              </bk-button>
            </div>
          )}
          <div class='explore-btns'>
            <input
              ref='fileRef'
              class='hidden-file-input'
              accept='application/json'
              type='file'
              onChange={this.fileChange}
            />
            <bk-button
              class='btn'
              theme='primary'
              text
              onClick={this.handleImport}
            >
              {this.$t('导入')}
            </bk-button>
            <bk-button
              class='btn'
              theme='primary'
              text
              onClick={this.handleExport}
            >
              {this.$t('导出')}
            </bk-button>
          </div>
        </div>

        <Component
          ref='tabContentRef'
          isBatchEdit={this.isBatchEdit}
          appName={this.appName}
          tableMaxHeight={this.tableMaxHeight}
          onCurrentEditRowIdChange={this.handleCurrentEditRowIdChange}
          onBatchSaveSuccess={this.handleBatchSaveSuccess}
          onBatchSaveFailed={this.handleBatchSaveFailed}
        />
      </div>
    );
  }
}
