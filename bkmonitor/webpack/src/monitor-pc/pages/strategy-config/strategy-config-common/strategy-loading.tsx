import { Component, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import './strategy-loading.scss';

@Component
export class StrategyCellSkeleton extends tsc<{ field?: string; index?: number }> {
  @Prop({ default: '' }) field: string;
  @Prop({ default: 0 }) index: number;

  render() {
    const tag = ['labels', 'noticeGroupList', 'signals', 'levels', 'detectionTypes', 'mealNames'].includes(this.field);
    const toggle = ['enabled', 'needPoll', 'noDataEnabled'].includes(this.field);
    const multiline = ['strategyName', 'itemDescription', 'updator'].includes(this.field);
    return (
      <span
        class={['strategy-cell-skeleton', { 'is-tag': tag, 'is-switch': toggle, 'is-multiline': multiline, 'is-checkbox': this.field === 'selection' }]}
        aria-hidden='true'
      >
        <i style={{ width: toggle || this.field === 'selection' ? undefined : `${[68, 84, 56, 76][this.index % 4]}%` }} />
        {(tag || multiline || this.field === 'operator') && <i />}
      </span>
    );
  }
}

@Component
export default class StrategyFilterSkeleton extends tsc<{ groups?: string[] }> {
  @Prop({ default: () => [] }) groups: string[];

  render() {
    return (
      <div class='strategy-filter-skeleton' role='status' aria-label={this.$t('加载中...')} aria-busy='true'>
        {this.groups.map((id, index) => (
          <div key={id} class='strategy-filter-skeleton__group' aria-hidden='true'>
            <div class='strategy-filter-skeleton__title'><i /><span /></div>
            {['strategy_status', 'data_source_list', 'scenario'].includes(id) &&
              Array.from({ length: id === 'strategy_status' ? 5 : 3 }, (_, row) => (
                <div key={row} class='strategy-filter-skeleton__row'>
                  <i /><span style={{ width: `${[56, 72, 44][(row + index) % 3]}%` }} /><b />
                </div>
              ))}
          </div>
        ))}
      </div>
    );
  }
}
