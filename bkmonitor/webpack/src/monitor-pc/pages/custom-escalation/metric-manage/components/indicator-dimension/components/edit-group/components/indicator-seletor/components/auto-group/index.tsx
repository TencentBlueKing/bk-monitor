import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import RegexOperation from './components/regex-operation';
import type { IListItem } from '../../components/result-preview';

import { random } from 'monitor-common/utils/utils';

import './index.scss';

/**
 * 自动分组组件
 * 根据分组规则（正则表达式）自动发现并分组指标
 */
@Component({
  name: 'AutoGroup',
})
export default class AutoGroup extends tsc<any> {
  /** 自动分组列表数据 */
  @Prop({ default: () => [] }) autoList: IListItem[];

  /** 正则表达式列表 */
  regexList: IListItem[] = [];

  /**
   * 监听自动分组列表变化，同步更新正则表达式列表
   * @param newVal 新的自动分组列表数据
   */
  @Watch('autoList', { immediate: true })
  onAutoListChange(newVal: IListItem[]) {
    this.regexList = newVal;
  }

  /**
   * 添加新的正则表达式项
   */
  handleAddItem() {
    const newItem = {
      id: random(8),
      name: '',
    };
    this.regexList.push(newItem);
  }

  /**
   * 删除指定的正则表达式项
   * @param id 要删除的项的唯一标识
   */
  handleDeleteItem(id: string) {
    this.regexList = this.regexList.filter(item => item.id !== id);
    this.$emit('deleteItem', id);
  }

  /**
   * 处理正则表达式输入事件
   * @param data 输入的正则表达式数据
   */
  handleRegexInput(data: IListItem) {
    this.$emit('regexInput', data);
  }

  /**
   * 清空所有选择的正则表达式
   */
  clearSelect() {
    this.regexList = [];
  }

  render() {
    return (
      <div class='auto-group-main'>
        <bk-alert
          type='info'
          style='margin-bottom: 12px;'
          title={this.$t('根据规则自动发现未来新指标，存量指标不生效。')}
        />
        <div class='regex-list-main'>
          {this.regexList.map(item => (
            <RegexOperation
              key={item.id}
              data={item}
              onDelete={this.handleDeleteItem}
              onRegexInput={this.handleRegexInput}
            />
          ))}
          <bk-button
            text
            theme='primary'
            class='add-item-btn'
            onClick={this.handleAddItem}
          >
            <i class='icon-monitor icon-mc-add add-icon' />
            {this.$t('正则表达式')}
          </bk-button>
        </div>
      </div>
    );
  }
}
