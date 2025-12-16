import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './index.scss';

/**
 * 列表项接口
 */
export interface IListItem {
  /** 唯一标识 */
  id: string | number;
  /** 显示名称 */
  name: string;
}

/**
 * 结果预览组件
 * 用于展示手动分组和自动分组的指标列表，支持清空选择和移除单个项
 */
@Component({
  name: 'ResultPreview',
})
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export default class ResultPreview extends tsc<any> {
  /** 手动分组的指标列表 */
  @Prop({ default: () => [] }) manualList: IListItem[];
  /** 自动分组的表达式列表 */
  @Prop({ default: () => [] }) autoList: IListItem[];

  /** 当前展开的折叠面板，默认全部展开 */
  activePanel = ['manul', 'auto'];

  /** 本地维护的手动分组列表，用于响应式更新 */
  localManualList: IListItem[] = [];
  /** 本地维护的自动分组列表，用于响应式更新 */
  localAutoList: IListItem[] = [];

  /**
   * 监听手动分组列表变化
   * @param newVal 新的手动分组列表
   */
  @Watch('manualList', { immediate: true })
  onManualListChange(newVal: IListItem[]) {
    this.localManualList = newVal;
  }

  /**
   * 监听自动分组列表变化
   * @param newVal 新的自动分组列表
   */
  @Watch('autoList', { immediate: true })
  onAutoListChange(newVal: IListItem[]) {
    this.localAutoList = newVal;
  }

  /**
   * 处理清空选择操作
   * 触发 clearSelect 事件通知父组件
   */
  handleClearSelect() {
    this.$emit('clearSelect');
  }

  /**
   * 处理移除手动分组项
   * @param item 要移除的列表项
   */
  handleRemoveManual(item: IListItem) {
    this.localManualList = this.localManualList.filter(row => row.id !== item.id);
    this.$emit('removeManual', item);
  }

  /**
   * 处理移除自动分组项
   * @param item 要移除的列表项
   */
  handleRemoveAuto(item: IListItem) {
    this.localAutoList = this.localAutoList.filter(row => row.id !== item.id);
    this.$emit('removeAuto', item);
  }

  render() {
    return (
      <div class='result-preview-main'>
        <div class='header-main'>
          <div class='title'>{this.$t('结果预览')}</div>
          <bk-button
            type='primary'
            text
            size='small'
            onClick={this.handleClearSelect}
          >
            {this.$t('清空选择')}
          </bk-button>
        </div>
        <div class='list-main'>
          <bk-collapse
            v-model={this.activePanel}
            ext-cls='collapse-main'
          >
            <bk-collapse-item name='manul'>
              <span>{this.$t('手动分组')}：</span>
              <i18n path='{0} 个指标'>
                <span style='font-weight: 700;color: #3A84FF'>{this.localManualList.length}</span>
              </i18n>
              <div slot='content'>
                {this.localManualList.map(item => (
                  <div
                    class='list-item'
                    key={item.id}
                  >
                    <div
                      class='name-display'
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </div>
                    <i
                      class='bk-icon icon-close-line-2 close-icon'
                      onClick={() => this.handleRemoveManual(item)}
                    />
                  </div>
                ))}
              </div>
            </bk-collapse-item>
            <bk-collapse-item
              name='auto'
              style='margin-top: 16px;'
            >
              <span>{this.$t('自动分组')}：</span>
              <i18n path='{0} 个表达式'>
                <span style='font-weight: 700;color: #3A84FF'>{this.localAutoList.length}</span>
              </i18n>
              <div slot='content'>
                {this.localAutoList.map(item => (
                  <div
                    class='list-item'
                    key={item.id}
                  >
                    <div
                      class='name-display'
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </div>
                    <i
                      class='bk-icon icon-close-line-2 close-icon'
                      onClick={() => this.handleRemoveAuto(item)}
                    />
                  </div>
                ))}
              </div>
            </bk-collapse-item>
          </bk-collapse>
        </div>
      </div>
    );
  }
}
