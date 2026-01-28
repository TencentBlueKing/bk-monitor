import { Component, Prop, Watch, InjectReactive, Inject } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';
import type { IListItem } from '../../../result-preview';
import type { RequestHandlerMap } from '../../../../../../../../../../type';

@Component({
  name: 'RegexOperation',
})
export default class RegexOperation extends tsc<any> {
  /** 列表项数据 */
  @Prop({ default: () => {} }) data: IListItem;

  @InjectReactive('timeSeriesGroupId') readonly timeSeriesGroupId: number;
  @InjectReactive('requestHandlerMap') readonly requestHandlerMap: RequestHandlerMap;
  @InjectReactive('isAPM') readonly isAPM: boolean;
  @InjectReactive('appName') readonly appName: string;
  @InjectReactive('serviceName') readonly serviceName: string;

  /** 正则表达式的值 */
  regexValue = '';
  /** 匹配到的指标列表 */
  matchedMetrics: string[] = [];
  /** 预览加载状态 */
  previewLoading = false;
  /** 是否为预览初始化状态（未进行过预览） */
  isPreviewInit = true;
  /** 预览是否已完成 */
  isPreviewFinished = false;
  /** 输入内容是否已变更（需要重新预览） */
  isInputChanged = false;
  /** 输入框是否已失焦 */
  isInputBlur = false;

  /**
   * 监听数据变化，同步更新正则表达式值
   * @param newVal 新的列表项数据
   */
  @Watch('data', { immediate: true, deep: true })
  onDataChange(newVal: IListItem) {
    this.regexValue = newVal.name;
  }

  /**
   * 处理正则表达式输入事件
   * @param name 输入的正则表达式值
   */
  handleRegexInput(name: string) {
    this.isPreviewFinished = false;
    this.isInputChanged = true;
    this.$emit('regexInput', { id: this.data.id, name });
  }

  handleRegexEnter() {
    this.handleRegexBlur();
    this.$nextTick(() => {
      this.handlePreview();
    });
  }

  /**
   * 处理正则表达式输入框失焦事件
   */
  handleRegexBlur() {
    this.isInputBlur = true;
    this.isInputChanged = false;
  }

  /**
   * 点击预览按钮，调用接口预览正则表达式匹配结果
   */
  async handlePreview() {
    this.previewLoading = true;
    try {
      const params = {
        time_series_group_id: this.timeSeriesGroupId,
        auto_rules: [this.regexValue],
      };
      if (this.isAPM) {
        delete params.time_series_group_id;
        Object.assign(params, {
          app_name: this.appName,
          service_name: this.serviceName,
        });
      }
      const { auto_metrics: autoMetrics } = await this.requestHandlerMap.previewGroupingRule(params);
      this.matchedMetrics = autoMetrics[0]?.metrics || [];
    } finally {
      this.previewLoading = false;
      this.isPreviewFinished = true;
      this.isPreviewInit = false;
    }
  }

  /**
   * 处理删除操作，触发删除事件
   */
  handleDelete() {
    this.$emit('delete', this.data.id);
  }

  /**
   * 生成预览结果展示内容
   * 根据不同的状态（未预览、已变更、无匹配、有匹配）返回不同的展示内容
   * @returns JSX 元素
   */
  generatePreviewResult() {
    if (this.regexValue) {
      if (this.isPreviewInit) {
        if (this.isInputBlur) {
          return (
            <div class='no-preview-regex-main'>
              <bk-exception
                type='empty'
                scene='part'
              >
                <div class='tip-main'>
                  <i class='bk-icon icon-exclamation-circle-shape warning-icon' />
                  <span class='tip-text'>{this.$t('输入表达式后，必须点击预览，方可生效')}</span>
                </div>
              </bk-exception>
            </div>
          );
        }

        return (
          <div class='no-regex-main'>
            <bk-exception
              type='empty'
              scene='part'
            >
              <div class='tip-main'>{this.$t('输入表达式后，必须点击预览，方可生效')}</div>
            </bk-exception>
          </div>
        );
      }

      if (this.isInputChanged) {
        return (
          <div class='input-changed-preview'>
            <i class='bk-icon icon-exclamation-circle-shape warning-icon' />
            <span class='tip-text'>{this.$t('正则表达式已变更，请重新预览。')}</span>
          </div>
        );
      }

      if (!this.matchedMetrics.length) {
        return <div class='no-match-main'>({this.$t('暂无匹配到的指标')})</div>;
      }

      return (
        <div class='list-preview-main'>
          {this.matchedMetrics.map(item => (
            <bk-tag key={item}>{item}</bk-tag>
          ))}
        </div>
      );
    }
    return (
      <div class='no-regex-main'>
        <bk-exception
          type='empty'
          scene='part'
        >
          <div class='tip-main'>{this.$t('输入表达式后，必须点击预览，方可生效')}</div>
        </bk-exception>
      </div>
    );
  }

  /**
   * 渲染组件
   * @returns JSX 元素
   */
  render() {
    return (
      <div class='regex-operate-main'>
        <div class='operate-title'>{this.$t('正则表达式')}</div>
        <div
          class='delete-main'
          onClick={this.handleDelete}
        >
          <i class='icon-monitor icon-mc-delete-line delete-icon' />
        </div>
        <bk-input
          v-model={this.regexValue}
          placeholder={this.$t('支持 JS 正则匹配方式，如子串前匹配go_, 模糊匹配(.*?)_total')}
          onInput={this.handleRegexInput}
          onBlur={this.handleRegexBlur}
          onEnter={this.handleRegexEnter}
        />
        <div class='preview-btn-main'>
          <bk-button
            size='small'
            class='preview-btn'
            theme='primary'
            loading={this.previewLoading}
            disabled={!this.regexValue}
            outline
            onClick={this.handlePreview}
          >
            {this.$t('预览')}
          </bk-button>
          <span class='icon-monitor icon-tishi' />
          <span class='tip-text'>{this.$t('以下指标不会被加入到分组，仅用来规则测试。')}</span>
        </div>
        {this.generatePreviewResult()}
      </div>
    );
  }
}
