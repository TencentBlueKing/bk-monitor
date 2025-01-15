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
import { Component, Emit, Prop } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import SpaceSelect from '../../../components/space-select/space-select';
import { EScopes, EsSpaceScopes } from '../type';
import FormItem from './components/form-item';

import './cluster-more-config.scss';

const defalutTimes = [
  { id: 1, name: window.i18n.tc('1天') },
  { id: 7, name: window.i18n.tc('7天') },
  { id: 30, name: window.i18n.tc('30天') },
];
interface IProps {
  data?: any;
  spaceTypes?: any[];
  onChange?: (v: any) => void;
}
@Component
export default class ClusterMoreConfig extends tsc<IProps> {
  @Prop({ type: String }) selectedType: string;
  @Prop({ type: Object, default: () => null }) data: any;
  @Prop({ type: Array, default: () => [] }) spaceTypes: { id: string; name: string }[];
  localFormData = {
    kafka: {
      is_register_gse: false,
    },
    elasticsearch: {
      scope: EScopes.currentSpace,
      space: [], // 可见范围
      expires: {
        // 过期时间
        default: '',
        max: '',
      },
      replica: {
        // 副本数
        default: 0,
        max: 0,
      },
      cold_warm_phase_settings: {
        hot: '',
        cold: '',
      },
      hotDataTag: '', // 热数据标签
      coldDataTag: '', // 冷数据标签
      capacityAssessmentValue: null, // 容量评估
    },
    hotAndColdDataSwitcherValue: false, // 冷热数据开关值
    logArchivingSwitcherValue: false, // 日志归档开关值
    capacityAssessmentSwitcherValue: false, // 容量评估开关值
  };

  created() {
    if (this.data) {
      this.localFormData = this.data;
      if (this.localFormData.elasticsearch.scope === EScopes.currentSpace) {
        const currentSpace = this.$store.getters.bizId;
        this.localFormData.elasticsearch.space = [currentSpace];
      }
    }
  }

  @Emit('emit-data')
  emitData(field, value) {
    return { field, value };
  }

  @Emit('change')
  handleEmitChange() {
    return this.localFormData;
  }

  handleBizIdsChange(v) {
    this.localFormData.elasticsearch.space = v;
    this.handleEmitChange();
  }

  handleScopeChange(v: EScopes) {
    if (v === EScopes.spaceType) {
      this.localFormData.elasticsearch.space = [];
    } else {
      const currentSpace = this.$store.getters.bizId;
      this.localFormData.elasticsearch.space = [currentSpace];
    }
    this.handleEmitChange();
  }

  render() {
    return (
      <div class='cluster-config-cluster-more-config'>
        {(() => {
          switch (this.selectedType) {
            case 'kafka':
              return (
                <FormItem title={this.$tc('是否向GSE注册配置')}>
                  <bk-switcher
                    v-model={this.localFormData.kafka.is_register_gse}
                    theme='primary'
                    onChange={this.handleBizIdsChange}
                  />
                </FormItem>
              );
            case 'elasticsearch':
              return (
                <div>
                  <FormItem title={this.$tc('可见范围')}>
                    <bk-radio-group
                      class='mb15'
                      v-model={this.localFormData.elasticsearch.scope}
                      onChange={this.handleScopeChange}
                    >
                      {EsSpaceScopes.map(item => (
                        <bk-radio
                          key={item.id}
                          class='cluster-form-item-radio'
                          value={item.id}
                        >
                          {item.name}
                        </bk-radio>
                      ))}
                    </bk-radio-group>
                    {this.localFormData.elasticsearch.scope === EScopes.spaceType ? (
                      <bk-select
                        v-model={this.localFormData.elasticsearch.space}
                        multiple
                        onChange={this.handleEmitChange}
                      >
                        {this.spaceTypes.map(item => (
                          <bk-option
                            id={item.id}
                            key={item.id}
                            name={item.name}
                          />
                        ))}
                      </bk-select>
                    ) : (
                      <SpaceSelect
                        disabled={this.localFormData.elasticsearch.scope !== EScopes.multiSpace}
                        needAlarmOption={false}
                        needAuthorityOption={false}
                        spaceList={this.$store.getters.bizList}
                        value={this.localFormData.elasticsearch.space}
                        onChange={this.handleBizIdsChange}
                      />
                    )}
                  </FormItem>
                  <div class='horizontal'>
                    <FormItem
                      width={272}
                      title={this.$tc('过期时间')}
                    >
                      <div class='time-select-wrap'>
                        <div class='left-wrap'>{this.$tc('默认')}</div>
                        <bk-select
                          v-model={this.localFormData.elasticsearch.expires.default}
                          allow-create
                          onChange={this.handleEmitChange}
                        >
                          {defalutTimes.map(item => (
                            <bk-option
                              id={item.id}
                              key={item.id}
                              name={item.name}
                            />
                          ))}
                        </bk-select>
                      </div>
                    </FormItem>
                    <FormItem
                      width={272}
                      title={''}
                    >
                      <div class='time-select-wrap'>
                        <div class='left-wrap'>{this.$tc('最大')}</div>
                        <bk-select
                          v-model={this.localFormData.elasticsearch.expires.max}
                          allow-create
                          onChange={this.handleEmitChange}
                        >
                          {defalutTimes.map(item => (
                            <bk-option
                              id={item.id}
                              key={item.id}
                              name={item.name}
                            />
                          ))}
                        </bk-select>
                      </div>
                    </FormItem>
                  </div>
                  <div class='horizontal'>
                    <FormItem
                      width={272}
                      title={this.$tc('副本数')}
                    >
                      <div class='time-select-wrap'>
                        <div class='left-wrap'>{this.$tc('默认')}</div>
                        <bk-input
                          style={{ flex: 1 }}
                          v-model={this.localFormData.elasticsearch.replica.default}
                          type='number'
                          onChange={this.handleEmitChange}
                        />
                      </div>
                    </FormItem>
                    <FormItem
                      width={272}
                      title={''}
                    >
                      <div class='time-select-wrap'>
                        <div class='left-wrap'>{this.$tc('默认')}</div>
                        <bk-input
                          style={{ flex: 1 }}
                          v-model={this.localFormData.elasticsearch.replica.max}
                          type='number'
                          onChange={this.handleEmitChange}
                        />
                      </div>
                    </FormItem>
                  </div>
                  <FormItem title={this.$tc('冷热数据')}>
                    <div class='hint-switcher'>
                      <bk-switcher
                        v-model={this.localFormData.hotAndColdDataSwitcherValue}
                        theme='primary'
                        onChange={this.handleBizIdsChange}
                      />
                      {this.localFormData.hotAndColdDataSwitcherValue && (
                        <div class='get-hint'>
                          <i class='icon-monitor icon-hint hint-icon' />
                          <i18n path='没有获取到任何标签，具体可到{0}查看'>
                            <div class='button-text'>{this.$tc(' 配置方法 ')}</div>
                          </i18n>
                        </div>
                      )}
                    </div>
                    {this.localFormData.hotAndColdDataSwitcherValue && (
                      <div class='horizontal'>
                        <FormItem width={270}>
                          <div
                            class='hint-lable-title'
                            slot='title'
                          >
                            <div class='lable'>{this.$tc('热数据标签')}</div>
                            <div class='link'>
                              <i class='icon-monitor icon-mc-visual' />
                              <span class='text'>{this.$tc('查看实例列表')}</span>
                            </div>
                          </div>
                          <bk-select
                            v-model={this.localFormData.elasticsearch.cold_warm_phase_settings.hot}
                            onChange={this.handleEmitChange}
                          >
                            {[].map(option => (
                              <bk-option
                                id={option}
                                key={option}
                                name={option}
                              />
                            ))}
                          </bk-select>
                        </FormItem>
                        <FormItem width={270}>
                          <div
                            class='hint-lable-title'
                            slot='title'
                          >
                            <div class='lable'>{this.$tc('冷数据标签')}</div>
                            <div class='link'>
                              <i class='icon-monitor icon-mc-visual' />
                              <span class='text'>{this.$tc('查看实例列表')}</span>
                            </div>
                          </div>
                          <bk-select
                            v-model={this.localFormData.elasticsearch.cold_warm_phase_settings.cold}
                            onChange={this.handleEmitChange}
                          >
                            {[].map(option => (
                              <bk-option
                                id={option}
                                key={option}
                                name={option}
                              />
                            ))}
                          </bk-select>
                        </FormItem>
                      </div>
                    )}
                  </FormItem>
                  <div class='cluster-form-item mb24'>
                    <div class='flex-item'>
                      {/* 暂时不需要日志归档和容量评估 */}
                      {/* <div>*/}
                      {/*  <div class="cluster-form-item-content column-direction mb6">{this.$tc('日志归档')}</div>*/}
                      {/*  <div class={['hint-switcher']}>*/}
                      {/*    <bk-switcher*/}
                      {/*      theme="primary"*/}
                      {/*      v-model={this.logArchivingSwitcherValue}*/}
                      {/*      onChange={val => this.emitData('log_archiving', val)}>*/}
                      {/*    </bk-switcher>*/}
                      {/*    {*/}
                      {/*      this.logArchivingSwitcherValue && (*/}
                      {/*        <div class="clickable-area get-hint">*/}
                      {/*          <i class={['icon-monitor', 'icon-mc-detail']}/>*/}
                      {/*          <div class="ml5">{this.$tc('查看文档说明')}</div>*/}
                      {/*        </div>*/}
                      {/*      )*/}
                      {/*    }*/}
                      {/*  </div>*/}
                      {/* </div>*/}
                      {/* <div class="ml70">*/}
                      {/*  <div class="cluster-form-item-content mb6">{this.$tc('容量评估')}</div>*/}
                      {/*  <div class={['hint-switcher']}>*/}
                      {/*    <bk-switcher theme="primary" v-model={this.capacityAssessmentSwitcherValue}/>*/}
                      {/*    {*/}
                      {/*      this.capacityAssessmentSwitcherValue && (*/}
                      {/*        <div class="get-hint ml24">*/}
                      {/*          {this.$tc('采集主机达到')}*/}
                      {/*          <bk-input*/}
                      {/*            v-model={this.localFormData.elasticsearch.capacityAssessmentValue}*/}
                      {/*            class="ml2 mr2"*/}
                      {/*            type="number"*/}
                      {/*            behavior="simplicity"*/}
                      {/*            style={{ width: '80px' }}*/}
                      {/*            onInput={val => this.emitData('capacity_assessment_nums', Number(val))}>*/}
                      {/*          </bk-input>*/}
                      {/*          {this.$tc('台，必须进行容量评估')}*/}
                      {/*        </div>*/}
                      {/*      )*/}
                      {/*    }*/}
                      {/*  </div>*/}
                      {/* </div>*/}
                    </div>
                  </div>
                </div>
              );
          }
        })()}
      </div>
    );
  }
}
