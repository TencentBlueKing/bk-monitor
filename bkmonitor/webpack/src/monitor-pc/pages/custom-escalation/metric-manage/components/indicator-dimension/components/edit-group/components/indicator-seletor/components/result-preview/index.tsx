import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import _ from 'lodash';

import './index.scss';

/**
 * 列表项接口
 */
export interface IListItem {
  /** 唯一标识 */
  id: string | number;
  /** 显示名称 */
  name: string;
  /** 是否为新增 */
  isAdded?: boolean;
  /** 是否为删除 */
  isDeleted?: boolean;
  /** 是否为变更 */
  isChanged?: boolean;
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
  /** 是否为编辑模式 */
  @Prop({ default: false, type: Boolean }) isEdit: boolean;
  /** 手动分组的指标列表 */
  @Prop({ default: () => [] }) manualList: IListItem[];
  /** 自动分组的表达式列表 */
  @Prop({ default: () => [] }) autoList: IListItem[];
  /** 本地维护的自动分组列表 */
  @Prop({ default: () => [] }) localRawAutoList: IListItem[];
  /** 本地维护的手动分组列表 */
  @Prop({ default: () => [] }) localRawManualList: IListItem[];

  /** 当前展开的折叠面板，默认全部展开 */
  activePanel = ['manul', 'auto'];
  /** 是否仅显示变更项 */
  isOnlyShowChanged = false;

  /** 本地维护的手动分组列表，用于响应式更新 */
  localManualList: IListItem[] = [];
  /** 勾选仅显示变更项前的手动分组列表 */
  localManualListTotalList: IListItem[] = [];
  /** 本地维护的自动分组列表，用于响应式更新 */
  localAutoList: IListItem[] = [];
  /** 勾选仅显示变更项前的自动分组列表 */
  localAutoListTotalList: IListItem[] = [];
  /** 自动分组列表变更统计 */
  localAutoListChangedMap = {
    added: 0,
    deleted: 0,
    changed: 0,
  };
  /** 手动分组列表变更统计 */
  localManualListChangedMap = {
    added: 0,
    deleted: 0,
  };

  /** 自动分组列表变更统计 */
  get localAutoListChangedCount() {
    return (
      this.localAutoListChangedMap.added + this.localAutoListChangedMap.deleted + this.localAutoListChangedMap.changed
    );
  }

  /** 手动分组列表变更统计 */
  get localManualListChangedCount() {
    return this.localManualListChangedMap.added + this.localManualListChangedMap.deleted;
  }

  /** 有效选择的手动分组列表数量 */
  get validSelectedManualListCount() {
    return this.localManualList.filter(item => !item.isDeleted).length;
  }

  /** 有效选择的手动分组列表数量 */
  get validSelectedAutoListCount() {
    return this.localAutoList.filter(item => !item.isDeleted).length;
  }

  /**
   * 监听手动分组列表变化
   * @param newVal 新的手动分组列表
   */
  @Watch('manualList', { immediate: true })
  onManualListChange(newVal: IListItem[]) {
    this.localManualList = [];
    const rawManualListKeys = this.localRawManualList.map(item => item.id);
    const newManualListKeys = newVal.map(item => item.id);
    const addedKeys = _.difference(newManualListKeys, rawManualListKeys);
    const deletedKeys = _.difference(rawManualListKeys, newManualListKeys);
    this.localManualListChangedMap.added = addedKeys.length;
    this.localManualListChangedMap.deleted = deletedKeys.length;
    const oldManualList = newVal.filter(item => ![...addedKeys, ...deletedKeys].includes(item.id));
    if (addedKeys.length > 0) {
      // 逻辑新增并置顶部
      const addedItems = newVal.filter(item => addedKeys.includes(item.id));
      for (const item of addedItems) {
        item.isAdded = true;
      }
      this.localManualList.unshift(...addedItems);
    }
    if (oldManualList.length > 0) {
      // 没变的
      this.localManualList.push(...oldManualList);
    }
    if (deletedKeys.length > 0) {
      // 逻辑删除并置底部
      const deletedItems = this.localRawManualList.filter(item => deletedKeys.includes(item.id));
      for (const item of deletedItems) {
        item.isDeleted = true;
      }
      this.localManualList.push(...deletedItems);
    }
    this.localManualListTotalList = _.cloneDeep(this.localManualList);
    if (this.isOnlyShowChanged) {
      this.handleOnlyShowChangedChange(true);
    }
  }

  /**
   * 监听自动分组列表变化
   * @param newVal 新的自动分组列表
   */
  @Watch('autoList', { immediate: true, deep: true })
  onAutoListChange(newVal: IListItem[]) {
    this.localAutoList = [];
    const localRawAutoListMap = this.localRawAutoList.reduce<Record<string, IListItem>>((acc, item) => {
      acc[item.id] = item;
      return acc;
    }, {});
    const rawAutoListKeys = this.localRawAutoList.map(item => item.id);
    const newAutoListKeys = newVal.map(item => item.id);
    const addedKeys = _.difference(newAutoListKeys, rawAutoListKeys);
    const deletedKeys = _.difference(rawAutoListKeys, newAutoListKeys);
    this.localAutoListChangedMap.added = addedKeys.length;
    this.localAutoListChangedMap.deleted = deletedKeys.length;
    const oldAutoList = newVal.filter(item => ![...addedKeys, ...deletedKeys].includes(item.id));
    if (addedKeys.length > 0) {
      // 逻辑新增并置顶部
      const addedItems = newVal.filter(item => addedKeys.includes(item.id));
      for (const item of addedItems) {
        item.isAdded = true;
      }
      this.localAutoList.unshift(...addedItems);
    }
    if (oldAutoList.length > 0) {
      // 没变的
      this.localAutoListChangedMap.changed = 0;
      for (const item of oldAutoList) {
        if (localRawAutoListMap[item.id].name !== item.name) {
          this.localAutoListChangedMap.changed++;
          item.isChanged = true;
        }
      }
      this.localAutoList.push(...oldAutoList);
    }
    if (deletedKeys.length > 0) {
      // 逻辑删除并置底部
      const deletedItems = this.localRawAutoList.filter(item => deletedKeys.includes(item.id));
      for (const item of deletedItems) {
        item.isDeleted = true;
      }
      this.localAutoList.push(...deletedItems);
    }
    this.localAutoListTotalList = _.cloneDeep(this.localAutoList);
  }

  /**
   * 处理清空选择操作
   */
  handleClearAll(e: MouseEvent) {
    if (e.x === 0 && e.y === 0) {
      // 不触发清空操作
      return;
    }

    this.$emit('clearSelect');
  }

  /**
   * 处理移除手动分组项
   * @param item 要移除的列表项
   */
  handleRemoveManual(item: IListItem) {
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

  /**
   * 处理仅显示变更项操作
   */
  handleOnlyShowChangedChange(value: boolean) {
    if (value) {
      this.localManualList = this.localManualListTotalList.filter(item => item.isDeleted || item.isAdded);
      this.localAutoList = this.localAutoListTotalList.filter(item => item.isDeleted || item.isAdded || item.isChanged);
    } else {
      this.localManualList = this.localManualListTotalList;
      this.localAutoList = this.localAutoListTotalList;
    }
  }

  /**
   * 处理恢复手动分组项
   * @param item 要恢复的列表项
   */
  handleRecoverManual(item: IListItem) {
    this.$emit('recoverManualItem', item);
  }

  /**
   * 处理恢复自动分组项
   * @param item 要恢复的列表项
   */
  handleRecoverAuto(item: IListItem) {
    this.$emit('recoverAutoItem', item);
  }

  render() {
    return (
      <div class='result-preview-main'>
        <div class='header-main'>
          <div class='title'>{this.$t('结果预览')}</div>
          {this.isEdit && <div class='separator' />}
          {this.isEdit && (
            <bk-checkbox
              class='only-show-changed'
              v-model={this.isOnlyShowChanged}
              onChange={this.handleOnlyShowChangedChange}
            >
              {this.$t('仅显示变更项')}
            </bk-checkbox>
          )}
          <bk-button
            type='primary'
            text
            class='clear-btn'
            size='small'
            onClick={this.handleClearAll}
          >
            {this.$t('清空选择')}
          </bk-button>
        </div>
        <div class='list-main'>
          <bk-collapse
            v-model={this.activePanel}
            ext-cls='collapse-main'
          >
            <bk-collapse-item name='auto'>
              <span>{this.$t('自动发现规则')}：</span>
              <i18n path='{0} 个表达式'>
                <span style='font-weight: 700;color: #3A84FF'>{this.validSelectedAutoListCount}</span>
              </i18n>
              {this.isEdit && (
                <span
                  style='margin-left: 6px;'
                  class={this.localAutoListChangedCount > 0 ? 'auto-changed-count' : ''}
                >
                  <span>(</span>
                  {this.localAutoListChangedCount > 0 ? (
                    <span>
                      <i18n path='{0} 变更'>
                        <span style='font-weight: 700;color: #E38B02'>{this.localAutoListChangedMap.changed}</span>
                      </i18n>
                      <span>、</span>
                      <i18n path='{0} 新增'>
                        <span style='font-weight: 700;color: #2CAF5E'>{this.localAutoListChangedMap.added}</span>
                      </i18n>
                      <span>、</span>
                      <i18n path='{0} 移除'>
                        <span style='font-weight: 700;color: #EA3636'>{this.localAutoListChangedMap.deleted}</span>
                      </i18n>
                    </span>
                  ) : (
                    <span>{this.$t('暂无变更')}</span>
                  )}
                  <span>)</span>
                </span>
              )}
              <div slot='content'>
                {this.localAutoList.map(item => (
                  <div
                    class='content-list-item'
                    key={item.id}
                  >
                    {this.isEdit && (
                      <span>
                        {item.isAdded && <div class='icon-main added-icon'>{this.$t('新增')}</div>}
                        {item.isDeleted && <div class='icon-main deleted-icon'>{this.$t('移除')}</div>}
                        {item.isChanged && <div class='icon-main changed-icon'>{this.$t('变更')}</div>}
                      </span>
                    )}

                    <div
                      class={['name-display', item.isDeleted ? 'is-deleted' : '']}
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </div>
                    {!item.isDeleted ? (
                      <i
                        class='bk-icon icon-close-line-2 close-icon'
                        onClick={() => this.handleRemoveAuto(item)}
                      />
                    ) : (
                      <bk-button
                        text
                        class='recover-btn'
                        theme='primary'
                        size='small'
                        onClick={() => this.handleRecoverAuto(item)}
                      >
                        {this.$t('恢复')}
                      </bk-button>
                    )}
                  </div>
                ))}
              </div>
            </bk-collapse-item>
            <bk-collapse-item
              name='manul'
              style='margin-top: 16px;'
            >
              <span>{this.$t('已选择')}：</span>
              <i18n path='{0} 个指标'>
                <span style='font-weight: 700;color: #3A84FF'>{this.validSelectedManualListCount}</span>
              </i18n>
              {this.isEdit && (
                <span>
                  <span style='margin-left: 6px;'>(</span>
                  {this.localManualListChangedCount > 0 ? (
                    <span>
                      <i18n path='{0} 新增'>
                        <span style='font-weight: 700;color: #2CAF5E'>{this.localManualListChangedMap.added}</span>
                      </i18n>
                      <span>、</span>
                      <i18n path='{0} 移除'>
                        <span style='font-weight: 700;color: #EA3636'>{this.localManualListChangedMap.deleted}</span>
                      </i18n>
                    </span>
                  ) : (
                    <span>{this.$t('暂无变更')}</span>
                  )}
                  <span>)</span>
                </span>
              )}
              <div slot='content'>
                {this.localManualList.map(item => (
                  <div
                    class='content-list-item'
                    key={item.id}
                  >
                    {this.isEdit && (
                      <span>
                        {item.isAdded && <div class='icon-main added-icon'>{this.$t('新增')}</div>}
                        {item.isDeleted && <div class='icon-main deleted-icon'>{this.$t('移除')}</div>}
                      </span>
                    )}

                    <div
                      class={['name-display', item.isDeleted ? 'is-deleted' : '']}
                      v-bk-overflow-tips
                    >
                      {item.name}
                    </div>
                    {!item.isDeleted ? (
                      <i
                        class='bk-icon icon-close-line-2 close-icon'
                        onClick={() => this.handleRemoveManual(item)}
                      />
                    ) : (
                      <bk-button
                        text
                        class='recover-btn'
                        theme='primary'
                        size='small'
                        onClick={() => this.handleRecoverManual(item)}
                      >
                        {this.$t('恢复')}
                      </bk-button>
                    )}
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
