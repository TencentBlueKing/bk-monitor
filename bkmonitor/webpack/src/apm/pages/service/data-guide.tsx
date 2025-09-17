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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { listApplication, metaConfigInfo, metaInstrumentGuides, pushUrl } from 'monitor-api/modules/apm_meta';
import { Debounce } from 'monitor-common/utils';
import MarkdownViewer from 'monitor-ui/markdown-editor/viewer';

import SelectCardItem from '../application/app-add/select-card-item';

import type { ICardItem } from '../application/app-add/utils';

import './data-guide.scss';
interface IProps {
  defaultAppName: string; // 应用名
}
@Component
export default class ServiceApply extends tsc<
  IProps,
  {
    onUpdateGuideUrl: string;
  }
> {
  @Prop({ type: String, default: '' }) defaultAppName: IProps['defaultAppName'];
  loading = false;
  /** 应用 */
  appName = '';
  appLoading = false;
  appList = [];
  /** 服务名称 */
  formData = {
    serviceName: '',
  };
  formRules = {
    serviceName: [{ required: true, message: '请输入服务名', trigger: 'blur' }],
  };
  /** 语言列表 */
  languageList: ICardItem[] = [];
  languageLoading = false;
  /** 报表url列表 */
  reportUrlList = [];
  reportUrl = '';
  reportLoading = false;

  markdownMap = new Map<string, string>();
  markdownStr = '';
  markdownLoading = false;

  guideUrl = '';

  get markdownParams() {
    if (!this.appName || !this.reportUrl) return undefined;
    const lang = this.languageList.find(item => item.checked)?.id;
    if (!lang) return undefined;
    return {
      app_name: this.appName,
      languages: [lang],
      base_endpoint: this.reportUrl,
    };
  }
  created() {
    this.markdownLoading = true;
    this.getAppList();
    this.getReportUrlList();
    this.getLanguageData();
  }

  @Watch('defaultAppName', { immediate: true })
  handleAppNameChange(val: string) {
    if (val) {
      this.appName = val;
    }
  }

  @Watch('markdownParams', { immediate: true })
  @Debounce(500)
  async fetchMarkdown() {
    const params = this.markdownParams;
    if (!params) {
      this.markdownStr = '';
      return;
    }
    const key = JSON.stringify(params || {});
    if (this.markdownMap.has(JSON.stringify(params))) {
      this.markdownStr = this.getMarkdownStr(key);
      return;
    }
    this.markdownLoading = true;
    const data = await metaInstrumentGuides({ ...params }).catch(() => false);
    if (data?.length) {
      this.markdownMap.set(key, data[0].content);
      this.markdownStr = this.getMarkdownStr(key);
    }
    this.markdownLoading = false;
  }

  getMarkdownStr(markKey?: string) {
    let key = markKey;
    if (!markKey) {
      key = JSON.stringify(this.markdownParams || {});
    }
    const rawMarkdownStr = this.markdownMap.get(key) || '';

    return rawMarkdownStr.replace(/{{service_name}}/gim, this.formData.serviceName);
  }
  /** 获取应用列表 */
  async getAppList() {
    this.appLoading = true;
    const data = await listApplication().catch(() => ({
      data: [],
    }));
    let hasApp = false;
    this.appList = data.data.map(item => {
      if (item.app_name === this.appName) {
        hasApp = true;
      }
      return {
        id: item.app_name,
        name: item.app_alias,
        app_id: item.application_id,
      };
    });
    if (!hasApp) {
      this.appName = '';
    }
    this.appLoading = false;
  }

  /** 获取环境 语言 md文档等信息 */
  async getLanguageData() {
    this.languageLoading = true;
    const data = await metaConfigInfo()
      .then(data => {
        this.guideUrl = data?.setup?.guide_url?.access_url || '';
        this.$emit('updateGuideUrl', this.guideUrl);
        return data;
      })
      .catch(() => {
        this.guideUrl = '';
        return {
          languages: [],
        };
      });
    this.languageList = (data.languages || []).map((item, index) => ({
      id: item.id,
      title: item.name,
      img: item.icon,
      checked: index === 0,
    }));
    this.languageLoading = false;
  }

  /** 获取push url数据 */
  async getReportUrlList() {
    this.reportLoading = true;
    this.reportUrlList = await pushUrl({
      format_type: 'simple',
    })
      .then(list => {
        return (list || []).map(item => ({
          id: item.push_url,
          name: `${item.bk_cloud_alias || this.$t('管控区域')} ${item.push_url}`,
        }));
      })
      .catch(() => []);
    this.reportUrl = this.reportUrlList[0]?.id || '';
    this.reportLoading = false;
  }

  @Debounce(300)
  handleServiceNameChange(v: string) {
    this.formData.serviceName = v?.trim();
    this.markdownStr = this.getMarkdownStr();
  }
  handleLanguageChange(language: ICardItem, val: boolean) {
    if (language.checked && !val) {
      return;
    }
    const checkLang = this.languageList.find(item => item.checked);
    if (checkLang) {
      checkLang.checked = false;
    }
    language.checked = val;
  }

  handleJumpToService() {
    const { href } = this.$router.resolve({
      name: 'service',
      query: {
        'filter-app_name': this.appName,
        'filter-service_name': this.formData.serviceName,
      },
    });
    window.open(`/?bizId=${this.$store.getters.bizId}${href}`, '_blank');
  }
  createIndexIcon(index: number) {
    return <span class='service-index-icon'>{index}</span>;
  }
  createInfoIcon() {
    return (
      <span class='service-add-info'>
        <i class='icon-monitor icon-hint' />
        {this.$t('将根据「服务名」自动生成上报示例代码，你可以直接运行')}
      </span>
    );
  }
  render() {
    const rowContent = (name: any, index: number, content?: any, showInfo = false) => [
      !!name && (
        <div class={['row-title']}>
          {this.createIndexIcon(index)}
          {name}
          {showInfo && this.createInfoIcon()}
        </div>
      ),
      <div
        key={'row-content'}
        class='row-content'
      >
        {content}
      </div>,
    ];
    return (
      <div
        class='data-guide-wrap is-service'
        v-bkloading={{ isLoading: this.loading }}
      >
        <div class='row-content-wrap'>
          {rowContent(
            this.$tc('上报Demo'),
            1,
            <div class='select-config-wrap'>
              <bk-form
                label-width={114}
                rules={this.formRules}
                {...{
                  props: {
                    model: this.formData,
                  },
                }}
              >
                <bk-form-item
                  class='service-name-form'
                  label={this.$tc('服务名')}
                  property='serviceName'
                  required
                >
                  <bk-input
                    style='width:394px;'
                    placeholder={this.$t('请输入服务名')}
                    value={this.formData.serviceName}
                    onChange={this.handleServiceNameChange}
                  />
                </bk-form-item>
                <bk-form-item label={this.$tc('所属应用')}>
                  <bk-select
                    style='width:394px;'
                    clearable={false}
                    loading={this.appLoading}
                    searchable={true}
                    value={this.appName}
                    onChange={this.handleAppNameChange}
                  >
                    {this.appList.map(item => {
                      return (
                        <bk-option
                          id={item.id}
                          key={item.id}
                          name={item.name}
                        />
                      );
                    })}
                  </bk-select>
                </bk-form-item>
                <bk-form-item label={this.$tc('选择语言')}>
                  <bk-input style='display: none' />
                  {!this.languageLoading ? (
                    this.languageList.map(item => {
                      return (
                        <SelectCardItem
                          key={item.id}
                          class='system-select-list-item'
                          checked={item.checked}
                          img={item.img}
                          mode='small'
                          title={item.title}
                          onClick={() => this.handleLanguageChange(item, !item.checked)}
                        />
                      );
                    })
                  ) : (
                    <div style='display: flex'>
                      {Array.of(1, 2, 3, 4).map((_, index) => (
                        <div
                          key={index}
                          style='width: 120px;height: 40px;margin-right: 16px;'
                          class='skeleton-element'
                        />
                      ))}
                    </div>
                  )}
                </bk-form-item>
                <bk-form-item label={this.$tc('默认上报地址')}>
                  <bk-select
                    style='width:580px;'
                    clearable={false}
                    loading={this.reportLoading}
                    searchable={true}
                    value={this.reportUrl}
                    onChange={v => {
                      this.reportUrl = v;
                    }}
                  >
                    {this.reportUrlList.map(item => {
                      return (
                        <bk-option
                          id={item.id}
                          key={item.id}
                          name={item.name}
                        />
                      );
                    })}
                  </bk-select>
                </bk-form-item>
              </bk-form>
            </div>,
            true
          )}
        </div>
        {this.formData.serviceName && (
          <div
            style='flex: 1'
            class='row-content-wrap is-markdown'
          >
            {rowContent(
              this.$tc('上报示例'),
              2,
              this.markdownLoading ? (
                <div class='markdown-skeleton'>
                  {Array.of(35, 65, 55, 85, 75, 45, 95).map(w => (
                    <div
                      key={w}
                      style={{
                        width: `${w}%`,
                      }}
                      class='skeleton-element markdown-skeleton-item'
                    />
                  ))}
                </div>
              ) : this.markdownStr ? (
                <div class='view-main'>
                  <MarkdownViewer
                    flowchartStyle={false}
                    value={this.markdownStr}
                  />
                </div>
              ) : (
                <bk-exception
                  scene='part'
                  type='empty'
                >
                  {this.$t('暂无数据')}
                </bk-exception>
              )
            )}
          </div>
        )}
        {!this.markdownLoading && this.formData.serviceName && (
          <div
            style='padding-bottom: 0'
            class='row-content-wrap'
          >
            {rowContent(
              <i18n path='稍等几分钟后，前往 {0} 查看相关数据'>
                <bk-button
                  text
                  onClick={this.handleJumpToService}
                >
                  「服务详情」
                </bk-button>
              </i18n>,
              3,
              undefined
            )}
          </div>
        )}
      </div>
    );
  }
}
