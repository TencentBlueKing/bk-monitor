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

import { Component, Prop, Emit, Mixins } from 'vue-property-decorator';

import { Button, Tab, TabPanel, Alert } from 'bk-magic-vue';

import $http from '../../api';
import MonacoEditor from '../../components/collection-access/components/step-add/monaco-editor.vue';
import classDragMixin from '../../mixins/class-drag-mixin';

import './masking-field-input.scss';

@Component
export default class MaskingFieldInput extends Mixins(classDragMixin) {
  /** 是否是采集项脱敏 */
  @Prop({ type: Boolean, default: true }) isIndexSetMasking: boolean;
  @Prop({ type: String, required: true }) operateType: string;
  @Prop({ required: true }) indexSetId: number | string;
  /** 当前活跃的采样日志下标 */
  activeTab = '0';
  /** 缓存的日志json列表 */
  catchJsonList = [];
  /** 是否钉住 */
  inputFix = false;
  /** 输入框最小高度 */
  collectMinHeight = 160;
  /** 输入框最大高度 */
  collectMaxHeight = 600;
  /** 当前容器的高度 */
  collectHeight = 160;
  /** 采样日志列表 */
  jsonValueList = [];
  /** 是否展示无法同步规则tips */
  isShowCannotCreateRuleTips = false;
  /** JSON格式错误tips */
  isJSONStrError = false;
  /** 日志查询loading */
  inputLoading = false;
  /** monaco输入框配置 */
  monacoConfig = {
    cursorBlinking: 'blink',
    acceptSuggestionOnEnter: 'off',
    acceptSuggestionOnCommitCharacter: false, // 是否提示输入
    overviewRulerBorder: false, // 是否应围绕概览标尺绘制边框
    selectOnLineNumbers: false, //
    renderLineHighlight: 'none', // 当前行高亮方式
    lineNumbers: 'off', // 左侧是否展示行
    // scrollBeyondLastLine: true,
    minimap: {
      enabled: false, // 是否启用预览图
    },
    scrollbar: {
      // 滚动条设置
      verticalScrollbarSize: 4, // 竖滚动条
      horizontalScrollbarSize: 4, // 横滚动条
      // useShadows: true, // 失焦阴影动画
    },
  };
  /** 是否是第一次添加采样 */
  isAddNewPanel = false;
  /** 当前活跃的采样日志的元素 */
  get activeJsonValue() {
    return this.jsonValueList[this.activeTab];
  }
  /** 获取所有输入框的json元素列表 */
  get getJsonParseList() {
    return this.jsonValueList.filter(item => this.isHaveValJSON(item.jsonStr)).map(item => JSON.parse(item.jsonStr));
  }
  /** 是否展示正在下发采集配置警告 */
  get isShowAlertTips() {
    return this.operateType === 'add' && !this.isAddNewPanel && !this.jsonValueList.length;
  }

  @Emit('change')
  hiddenSlider() {
    return false;
  }

  @Emit('blurInput')
  handleBlurInput(isPreview = true) {
    return { list: this.getJsonParseList, isPreview };
  }

  @Emit('createRule')
  emitCreateRule() {}

  mounted() {
    // 初始化采样日志输入框
    this.handleRefreshConfigStr(false);
  }

  /**
   * @desc: 刷新采样数据
   * @param {Boolean} isPreview 是否请求预览
   * @param {Boolean} isRefreshInput 是否是点击刷新按钮()
   */
  async handleRefreshConfigStr(isPreview = true, isRefreshInput = false) {
    try {
      this.inputLoading = true;
      const res = await $http.request('masking/getMaskingSearchStr', {
        params: { index_set_id: this.indexSetId },
      });
      if (res.data.list.length) {
        // 缓存当前的日志
        this.catchJsonList = res.data.list;
        if (!isRefreshInput) {
          // 有数据 且不是刷新按钮点击的 全都一次性展示出来
          this.addPanel(false);
          this.addPanel(false);
          this.addPanel(false);
        }
      }
      this.handleBlurConfigInput(isPreview);
    } catch (err) {
      return '';
    } finally {
      this.inputLoading = false;
    }
  }

  /**
   * @desc: 输入框失焦触发
   */
  async handleBlurConfigInput(isPreview = true) {
    // 与缓存的字符串一样 不更新
    if (this.activeJsonValue?.jsonStr === this.activeJsonValue?.catchJsonStr) return;
    this.activeJsonValue.catchJsonStr = this.activeJsonValue.jsonStr;

    this.handleBlurInput(isPreview);
  }

  /**
   * @desc: 一键生成规则
   */
  async handleCreateRule() {
    this.isShowCannotCreateRuleTips = !this.getJsonParseList.length;
    this.isJSONStrError = this.activeJsonValue.isJsonError;
    this.emitCreateRule();
  }

  /** 切换采样 */
  tabChange(val) {
    this.activeTab = val;
  }
  /** 添加采样 */
  addPanel(isQuery = true) {
    const id = this.jsonValueList.length;
    const catchStrValue = JSON.stringify(this.catchJsonList[id] ?? {}, null, 4);
    this.jsonValueList.push({
      id,
      jsonStr: catchStrValue === '{}' ? '' : catchStrValue,
      catchJsonStr: '',
      name: String(id),
      isJsonError: false,
      label: `${this.$t('采样日志')}${id + 1}`,
    });
    if (isQuery) {
      this.activeTab = String(id);
      this.handleBlurInput();
    }
    this.isAddNewPanel = true;
  }
  /** 删除采样 */
  closePanel(index: number) {
    const actIndex = Number(this.activeTab);
    // 当删除的下标和展示的下标相同时 直接展示第一个采样日志
    if (actIndex === index) this.activeTab = '0';
    // 当删除的下标小于展示的下标时 当前活跃的下标要 -1
    if (actIndex - index >= 1) this.activeTab = String(actIndex - 1);
    this.jsonValueList.splice(index, 1);
    // 更新采样日志名
    this.jsonValueList.forEach((item, index) => {
      item.id = index;
      item.name = String(index);
      item.label = `${this.$t('采样日志')}${index + 1}`;
    });
    if (!this.jsonValueList.length) {
      this.isShowCannotCreateRuleTips = false;
      this.isJSONStrError = false;
    }
    this.handleBlurInput();
  }

  /**
   * @desc: 判断当前字符串是否是json格式并且有值
   * @param {String} str 字符串
   * @returns {Boolean}
   */
  isHaveValJSON(str: string): boolean {
    try {
      JSON.parse(str);
      return JSON.parse(str) instanceof Object && str !== '{}';
    } catch (error) {
      return false;
    }
  }

  render() {
    return (
      <div
        class={[
          'item-container field-input',
          {
            'input-fix': this.inputFix,
            'other-color': !this.isIndexSetMasking,
          },
        ]}
      >
        {this.isShowAlertTips && (
          <Alert
            style='margin-bottom: 16px;'
            show-icon={false}
            type='warning'
            closable
          >
            <div slot='title'>
              <i class='bklog-icon bklog-log-loading'></i>
              <span>{this.$t('正在下发采集配置，需要3-5分钟来生成采集日志，请稍后配置脱敏规则…')}</span>
            </div>
          </Alert>
        )}
        <div class='item-title'>
          <div class='left'>
            <span class='title'>{this.$t('采样日志')}</span>
            <span class='alert'>
              {this.$t(
                '日志脱敏会结合您的采样预览日志自动匹配并选用规则，无采样预览日志无法展示预览结果。您也可以新增采样，手动构造日志'
              )}
            </span>
          </div>
          <div
            class='right-fix'
            onClick={() => (this.inputFix = !this.inputFix)}
          >
            <i class={['bklog-icon', this.inputFix ? 'bklog-fix-shape' : 'bklog-fix-line']}></i>
            <span class='text'>{this.inputFix ? this.$t('取消钉住') : this.$t('钉住')}</span>
          </div>
        </div>
        <Tab
          class={{ 'hidden-input is-not-log': !this.jsonValueList.length }}
          active={this.activeTab}
          type='border-card'
          closable
          on-close-panel={this.closePanel}
          on-tab-change={this.tabChange}
        >
          <div
            class='text-btn'
            slot='setting'
            // eslint-disable-next-line @typescript-eslint/no-misused-promises
            onClick={() => this.handleRefreshConfigStr(true, true)}
          >
            <i class='icon bk-icon icon-right-turn-line'></i>
            <span class='text'>{this.$t('刷新')}</span>
          </div>
          <div
            slot='add'
            onClick={() => this.addPanel()}
          >
            <div
              style='margin-left: 10px;'
              class='text-btn'
            >
              <i class='icon bk-icon icon-plus push'></i>
              <span class='text'>{this.$t('新增采样')}</span>
            </div>
          </div>
          {this.jsonValueList.map((panel, index) => (
            <TabPanel
              {...{ props: panel }}
              key={index}
            />
          ))}
          {!!this.jsonValueList.length ? (
            <div>
              <div
                class='json-editor'
                v-bkloading={{ isLoading: this.inputLoading }}
              >
                <MonacoEditor
                  height={this.collectHeight}
                  v-model={this.activeJsonValue.jsonStr}
                  font-size={14}
                  is-show-problem-drag={false}
                  is-show-top-label={false}
                  language='json'
                  monaco-config={this.monacoConfig}
                  placeholder={this.$t('请输入 JSON 格式日志')}
                  theme='vs'
                  on-blur={() => this.handleBlurConfigInput()}
                  on-get-problem-state={(err: boolean) => (this.activeJsonValue.isJsonError = err)}
                ></MonacoEditor>
              </div>
              <div
                class={['drag-bottom', { 'drag-ing': this.isChanging }]}
                onMousedown={e => this.dragBegin(e, 'dragY')}
              ></div>
            </div>
          ) : (
            <div class='no-data-tips'>
              <span>{this.$t('暂无采样日志')}</span>
            </div>
          )}
        </Tab>
        <div class='sync-rule-box'>
          <Button
            disabled={!this.jsonValueList.length}
            size='small'
            theme='primary'
            outline
            onClick={() => this.handleCreateRule()}
          >
            {this.$t('自动匹配脱敏规则')}
          </Button>
          {this.isShowCannotCreateRuleTips && <span>{this.$t('未检测到采样日志内容，无法同步规则')}</span>}
          {this.isJSONStrError && <span>{this.$t('当前日志不符合JSON格式，请确认后重试')}</span>}
        </div>
        {this.$slots.default}
      </div>
    );
  }
}
