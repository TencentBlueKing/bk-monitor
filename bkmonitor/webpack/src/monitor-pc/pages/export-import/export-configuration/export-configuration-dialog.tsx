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

import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './export-configuration-dialog.scss';

type StateType = 'FAILURE' | 'MAKE_PACKAGE' | 'PENDING' | 'PREPARE_FILE';

interface ExportConfigurationDialogProps {
  state?: StateType;
  packageNum?: any;
  show?: boolean;
  message?: string;
}

@Component
export default class ExportConfigurationDialog extends tsc<ExportConfigurationDialogProps> {
  @Prop({ default: 'PREPARE_FILE' }) state: StateType;
  @Prop({ default: () => ({}) }) packageNum: any;
  @Prop({ default: false }) show: boolean;
  @Prop({ default: '' }) message: string;

  get isMakePackage() {
    return this.state === 'MAKE_PACKAGE' && Object.keys(this.packageNum).length;
  }

  // 导出失败取消按钮事件
  handleCloseDialog() {
    this.$emit('update:show', false);
  }
  // 重试操作事件
  handlerRetry() {
    this.$emit('retry');
  }

  render() {
    return (
      <bk-dialog
        width='450'
        ext-cls='export-configuration-dialog'
        v-model={this.show}
        close-icon={false}
        show-footer={false}
      >
        <div class='export-configuration-dialog-wrap'>
          {this.state !== 'FAILURE' ? (
            <div>
              {/* 导出正常 */}
              <div class='dialog-header'>
                <img
                  alt=''
                  // eslint-disable-next-line @typescript-eslint/no-require-imports
                  src={require('../../../static/images/svg/spinner.svg')}
                />
                {(this.state === 'PENDING' || this.state === 'PREPARE_FILE') && <span> {this.$t('准备中...')} </span>}
                {this.state === 'MAKE_PACKAGE' && <span> {this.$t('打包中...')} </span>}
              </div>
              <div class='dialog-tips'>{this.$t('所含内容文件')}</div>
              <div class='dialog-content'>
                <div class='column'>
                  <div>
                    {this.$t('采集配置文件')}
                    <span
                      class='gray'
                      v-show={this.isMakePackage}
                    >
                      （
                      <span class={{ blue: this.packageNum.collect_config_file > 0 }}>
                        {this.$t(' {num} 个', { num: this.packageNum.collect_config_file })}
                      </span>
                      ）
                    </span>
                  </div>
                  <div>
                    {this.$t('自动关联采集配置文件')}
                    <span
                      class='gray'
                      v-show={this.isMakePackage}
                    >
                      （
                      <span class={{ blue: this.packageNum.associated_collect_config > 0 }}>
                        {this.$t(' {num} 个', { num: this.packageNum.associated_collect_config })}
                      </span>{' '}
                      ）
                    </span>
                  </div>
                </div>
                <div class='column'>
                  <div>
                    {this.$t('策略配置文件')}
                    <span
                      class='gray'
                      v-show={this.isMakePackage}
                    >
                      （
                      <span class={{ blue: this.packageNum.strategy_config_file > 0 }}>
                        {this.$t(' {num} 个', { num: this.packageNum.strategy_config_file })}
                      </span>
                      ）
                    </span>
                  </div>
                  <div>
                    {this.$t('自动关联插件文件')}
                    <span
                      class='gray'
                      v-show={this.isMakePackage}
                    >
                      （
                      <span class={{ blue: this.packageNum.associated_plugin > 0 }}>
                        {this.$t(' {num} 个', { num: this.packageNum.associated_plugin })}
                      </span>
                      ）
                    </span>
                  </div>
                </div>
                <div>
                  {this.$t('仪表盘')}
                  <span
                    class='gray'
                    v-show='isMakePackage'
                  >
                    （
                    <span class={{ blue: this.packageNum.view_config_file > 0 }}>
                      {this.$t(' {num} 个', { num: this.packageNum.view_config_file })}
                    </span>
                    ）
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div>
              {/* 导出失败 */}
              <div class='dialog-header'>
                <i class='icon-monitor icon-remind' />
                <span> {this.$t('导出失败，请重试！')} </span>
              </div>
              <div class={{ 'dialog-tips': true, 'tips-err': this.state === 'FAILURE' }}>{this.$t('失败原因')}</div>
              <div class='dialog-content dialog-content-err'>
                <div class='column'>{this.message}</div>
                <div class='btn'>
                  <span
                    style='margin-right: 16px'
                    onClick={this.handlerRetry}
                  >
                    {' '}
                    {this.$t('点击重试')}{' '}
                  </span>
                  <span onClick={this.handleCloseDialog}> {this.$t('取消')} </span>
                </div>
              </div>
            </div>
          )}
        </div>
      </bk-dialog>
    );
  }
}
