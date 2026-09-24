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
import { type PropType, computed, defineComponent, onScopeDispose, shallowRef, watch } from 'vue';

import { Button, Input, Message, Popover } from 'bkui-vue';
import { useI18n } from 'vue-i18n';

import { getApplicationToken } from '../services/profiling';
import { useDocumentLink } from '@/hooks/documentLink';

import type { Application } from '../types';

import './profiling-service-select.scss';

export default defineComponent({
  name: 'ProfilingServiceSelect',
  props: {
    applications: { type: Array as PropType<Application[]>, default: () => [] },
    value: { type: Array as PropType<string[]>, required: true },
    loading: Boolean,
  },
  emits: { change: (_value: string[]) => true },
  setup(props, { emit }) {
    const { t } = useI18n();
    const { handleGotoLink } = useDocumentLink();
    const opened = shallowRef(false);
    const keyword = shallowRef('');
    // 仅记录菜单中正在浏览的应用，点击服务后才向页面提交，查看无数据应用不改变查询。
    const activeApp = shallowRef('');
    const inputText = computed(() => (props.value.length === 2 ? props.value.join(' / ') : ''));
    const application = computed(() => props.applications.find(item => item.app_name === activeApp.value));
    const token = shallowRef('');
    const tokenLoading = shallowRef(false);
    let tokenRequest: AbortController;
    function clearToken() {
      tokenRequest?.abort();
      token.value = '';
      tokenLoading.value = false;
    }
    // 同步清除敏感值并取消请求，避免切换应用/关闭菜单后旧响应回填到新面板。
    watch([activeApp, opened], clearToken, { flush: 'sync' });
    onScopeDispose(clearToken);
    async function viewToken() {
      if (tokenLoading.value || !application.value?.application_id) return;
      const request = new AbortController();
      tokenRequest = request;
      tokenLoading.value = true;
      try {
        const value = await getApplicationToken(application.value.application_id, request.signal);
        if (!request.signal.aborted) token.value = value;
      } catch {
        if (!request.signal.aborted) Message({ theme: 'error', message: t('数据加载失败，请重试') });
      } finally {
        if (!request.signal.aborted) tokenLoading.value = false;
      }
    }
    function goToApplication(create = false) {
      const url = new URL(window.location.href);
      url.hash = create
        ? '/apm/home?is_enabled_profiling=false'
        : `/apm/home?queryString=${encodeURIComponent(application.value.app_name)}`;
      // 跨微应用须完整导航，避免当前子路由将 APM 的 hash 重定向到 Trace 首页。
      window.location.href = url.href;
      window.location.reload();
    }
    const hasData = (item: Application) => item.has_data ?? !!item.services.length;
    // 搜索只过滤左侧应用；命中服务名时右侧仍展示该应用的完整服务列表。
    const filtered = computed(() => {
      const search = keyword.value.trim().toLowerCase();
      return props.applications.filter(
        item =>
          !search ||
          item.app_name.toLowerCase().includes(search) ||
          item.app_alias?.toLowerCase().includes(search) ||
          (hasData(item) && item.services.some(service => service.name.toLowerCase().includes(search)))
      );
    });
    function open() {
      opened.value = true;
      keyword.value = '';
      activeApp.value = props.value[0] || '';
    }
    function selectService(name: string) {
      opened.value = false;
      emit('change', [activeApp.value, name]);
    }
    return {
      t,
      opened,
      keyword,
      activeApp,
      application,
      inputText,
      filtered,
      hasData,
      open,
      selectService,
      token,
      tokenLoading,
      viewToken,
      handleGotoLink,
      goToApplication,
    };
  },
  render() {
    const app = this.application;
    return (
      <div class='profiling-service-selector'>
        <Popover
          extCls='profiling-service-popover'
          arrow={false}
          isShow={this.opened}
          padding={0}
          placement='bottom-start'
          theme='light profiling-service-popover'
          trigger='click'
          onAfterHidden={() => {
            this.opened = false;
          }}
          onAfterShow={this.open}
        >
          {{
            default: () => (
              <div class={['profiling-service-trigger', { active: this.opened }]}>
                <span class='select-label'>{this.t('应用服务')}:</span>
                <Input
                  v-slots={{ suffix: () => <i class='icon-monitor icon-arrow-down' /> }}
                  modelValue={this.inputText}
                  placeholder={this.t('请选择应用服务')}
                  readonly
                />
                <kbd>{/mac/i.test(navigator.platform) ? 'cmd' : 'ctrl'}+o</kbd>
              </div>
            ),
            content: () => (
              <div class='profiling-service-menu'>
                <Input
                  class='profiling-service-search'
                  v-slots={{ prefix: () => <i class='icon-monitor icon-mc-search' /> }}
                  modelValue={this.keyword}
                  placeholder={this.t('请输入 关键字')}
                  clearable
                  onUpdate:modelValue={value => {
                    this.keyword = String(value);
                  }}
                />
                <div class='profiling-service-columns'>
                  {this.loading ? (
                    <div class='profiling-service-empty'>{this.t('应用加载中，请耐心等候…')}</div>
                  ) : !this.filtered.length ? (
                    <div class='profiling-service-empty'>{this.t('暂无搜索结果')}</div>
                  ) : (
                    <>
                      <div class='profiling-application-menu'>
                        {this.filtered.map(item => (
                          <Button
                            key={item.app_name}
                            class={['profiling-service-option', { selected: this.activeApp === item.app_name }]}
                            onClick={() => {
                              this.activeApp = item.app_name;
                            }}
                          >
                            {this.hasData(item) ? (
                              <i class='icon-monitor icon-mc-menu-apm' />
                            ) : (
                              <i class='profiling-no-data-dot' />
                            )}
                            <span
                              class='option-name'
                              title={`${item.app_name}${item.app_alias ? ` (${item.app_alias})` : ''}`}
                            >
                              {item.app_name}
                              {item.app_alias && <span class='option-alias'>({item.app_alias})</span>}
                            </span>
                            {this.hasData(item) && <i class='icon-monitor icon-arrow-right' />}
                          </Button>
                        ))}
                      </div>
                      <div class='profiling-child-menu'>
                        {!app ? (
                          <div class='profiling-service-empty'>{this.t('请先在左侧选择应用')}</div>
                        ) : this.hasData(app) ? (
                          <div class='profiling-service-list'>
                            {app.services.map(service => (
                              <Button
                                key={service.name}
                                class={[
                                  'profiling-service-option',
                                  { selected: app.app_name === this.value[0] && service.name === this.value[1] },
                                ]}
                                onClick={() => this.selectService(service.name)}
                              >
                                <i class='icon-monitor icon-mokuai' />
                                <span
                                  class='option-name'
                                  title={service.name}
                                >
                                  {service.name}
                                </span>
                              </Button>
                            ))}
                          </div>
                        ) : (
                          <div class='profiling-application-info'>
                            <dl>
                              <dt>{this.t('应用名')}</dt>
                              <dd>{app.app_name}</dd>
                              <dt>{this.t('应用别名')}</dt>
                              <dd>{app.app_alias}</dd>
                              <dt>{this.t('描述')}</dt>
                              <dd>{app.description}</dd>
                              <dt>Token</dt>
                              <dd class='profiling-application-token'>
                                <span>{this.token || '●●●●●●●●●●'}</span>
                                {!this.token && (
                                  <Button
                                    disabled={this.tokenLoading}
                                    theme='primary'
                                    text
                                    onClick={this.viewToken}
                                  >
                                    {this.tokenLoading ? this.t('加载中...') : this.t('点击查看')}
                                  </Button>
                                )}
                              </dd>
                            </dl>
                            <Button
                              class='profiling-application-link'
                              onClick={() => this.handleGotoLink('profiling_docs')}
                            >
                              {this.t('Profile 接入指引')}
                              <i class='icon-monitor icon-fenxiang' />
                            </Button>
                            <Button
                              class='profiling-application-link'
                              onClick={() => this.goToApplication()}
                            >
                              {this.t('查看应用')}
                              <i class='icon-monitor icon-fenxiang' />
                            </Button>
                          </div>
                        )}
                      </div>
                    </>
                  )}
                </div>
                <Button
                  class='profiling-service-footer'
                  onClick={() => this.goToApplication(true)}
                >
                  <i class='icon-monitor icon-jia' />
                  {this.t('新增接入')}
                </Button>
              </div>
            ),
          }}
        </Popover>
      </div>
    );
  },
});
