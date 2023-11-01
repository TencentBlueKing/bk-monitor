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
import { Component, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Input, Table } from 'bk-magic-vue';

import { frontendCollectConfigDetail, renameCollectConfig } from '../../../../monitor-api/modules/collecting';
import { PLUGIN_MANAGE_AUTH } from '../authority-map';

import './collector-configuration.scss';

interface IProps {
  id: string | number;
  show: boolean;
}

@Component
export default class CollectorConfiguration extends tsc<IProps> {
  @Prop({ type: [String, Number], default: '' }) id: number | string;
  @Prop({ type: Boolean, default: false }) show: boolean;

  @Inject('authority') authority;
  @Inject('handleShowAuthorityDetail') handleShowAuthorityDetail;
  @Inject('authorityMap') authorityMap;

  /* 基本信息 */
  basicInfo: any = {};
  runtimeParams = [];
  basicInfoMap: any = {
    name: window.i18n.t('配置名称'),
    id: 'ID',
    label_info: window.i18n.t('对象'),
    collect_type: window.i18n.t('采集方式'),
    plugin_display_name: window.i18n.t('插件'),
    period: window.i18n.t('采集周期'),
    update_user: window.i18n.t('操作者'),
    update_time: window.i18n.t('最近更新时间'),
    bk_biz_id: window.i18n.t('所属')
  };
  matchType = {
    command: window.i18n.t('命令行匹配'),
    pid: window.i18n.t('PID文件')
  };
  input = {
    show: false,
    copyName: ''
  };
  name = '';
  loading = false;

  @Watch('show', { immediate: true })
  handleShow(v: boolean) {
    if (v) {
      this.getDetailData();
    }
  }

  /**
   * @description 获取详情数据
   */
  getDetailData() {
    frontendCollectConfigDetail({ id: this.id }).then(data => {
      this.basicInfo = { ...data.basic_info, id: this.id };
      if (data.extend_info.log) {
        this.basicInfo = { ...this.basicInfo, ...data.extend_info.log };
        !this.basicInfo.filter_patterns && (this.basicInfo.filter_patterns = []);
        this.basicInfoMap = {
          ...this.basicInfoMap,
          log_path: this.$t('日志路径'),
          filter_patterns: this.$t('排除规则'),
          rules: this.$t('关键字规则'),
          charset: this.$t('日志字符集')
        };
      }
      if (data.extend_info.process) {
        const { process } = data.extend_info;
        this.basicInfoMap = {
          ...this.basicInfoMap,
          match: this.$t('进程匹配'),
          process_name: this.$t('进程名'),
          port_detect: this.$t('端口探测')
        };
        const {
          match_type: matchType,
          process_name: processName,
          port_detect: portDetect,
          match_pattern: matchPattern,
          exclude_pattern: excludePattern,
          pid_path: pidPath
        } = process;
        this.basicInfo = {
          ...this.basicInfo,
          match: matchType,
          match_pattern: matchPattern,
          exclude_pattern: excludePattern,
          pid_path: pidPath,
          process_name: processName || '--',
          port_detect: `${portDetect}`
        };
      }
      this.runtimeParams = data.runtime_params;
    });
  }

  /**
   * @description 更改配置名称
   * @param v
   * @param e
   */
  handleLabelKey(v, e) {
    if (e.code === 'Enter' || e.code === 'NumpadEnter') {
      this.handleTagClickout();
    }
  }
  /**
   * @description 隐藏输入框
   */
  handleTagClickout() {
    console.log('xxxx');
    const data = this.basicInfo;
    const { copyName } = this.input;
    if (copyName.length && copyName !== data.name) {
      this.handleUpdateConfigName(data, copyName);
    } else {
      data.copyName = data.name;
      this.input.show = false;
    }
  }
  /**
   * @description 更改配置名
   * @param data
   * @param copyName
   */
  handleUpdateConfigName(data, copyName) {
    this.loading = true;
    renameCollectConfig({ id: data.id, name: copyName }, { needMessage: false })
      .then(() => {
        this.basicInfo.name = copyName;
        this.name = copyName;
        this.$emit('update-name', data.id, copyName);
        this.$bkMessage({
          theme: 'success',
          message: this.$t('修改成功')
        });
      })
      .catch(err => {
        this.$bkMessage({
          theme: 'error',
          message: err.message || this.$t('发生错误了')
        });
      })
      .finally(() => {
        this.input.show = false;
        this.loading = false;
      });
  }
  /**
   * @description 展示输入框
   * @param key
   */
  handleEditLabel(key) {
    this.input.show = true;
    this.$nextTick().then(() => {
      this.$refs[`input${key}`]?.focus();
    });
  }
  /**
   * @description 跳转到插件编辑
   */
  handleToEditPlugin() {
    if (!this.authority.PLUGIN_MANAGE_AUTH) {
      this.handleShowAuthorityDetail(PLUGIN_MANAGE_AUTH);
    } else {
      this.$router.push({
        name: 'plugin-edit',
        params: {
          title: `${this.$t('编辑插件')} ${this.basicInfo.plugin_id}`,
          pluginId: this.basicInfo.plugin_id
        }
      });
    }
  }

  getBizInfo(id) {
    const item = this.$store.getters.bizList.find(i => i.id === id) || {};
    return item ? `${item.text}(${item.type_name})` : '--';
  }

  render() {
    function formItem(label, content) {
      return (
        <span class='form-item'>
          <span class='item-label'>{label}:</span>
          <span class='item-content'>{content}</span>
        </span>
      );
    }
    function stringContent(value) {
      if (typeof value === 'object') {
        return JSON.stringify(value);
      }
      return value;
    }
    return (
      <div class='collector-configuration-component'>
        <div class='detail-wrap-item'>
          <div class='wrap-item-title'>{this.$t('基本信息')}</div>
          <div class='wrap-item-content'>
            {Object.keys(this.basicInfoMap).map(key =>
              formItem(
                this.basicInfoMap?.[key],
                (() => {
                  if (key === 'name') {
                    return (
                      <span>
                        {this.input.show ? (
                          <Input
                            class='edit-input width-150'
                            ref={`input${key}`}
                            maxlength={50}
                            v-model={this.input.copyName}
                            onKeydown={this.handleLabelKey}
                            onBlur={this.handleTagClickout}
                          ></Input>
                        ) : (
                          <span
                            class='edit-span'
                            onClick={() => this.handleEditLabel(key)}
                          >
                            <span>{this.basicInfo?.[key]}</span>
                            <span class='icon-monitor icon-bianji'></span>
                          </span>
                        )}
                      </span>
                    );
                  }
                  if (key === 'plugin_display_name' && this.basicInfo?.collect_type !== 'Log') {
                    return (
                      <span class='edit-span'>
                        <span>{this.basicInfo?.[key]}</span>
                        <span
                          class='icon-monitor icon-bianji'
                          onClick={this.handleToEditPlugin}
                        ></span>
                      </span>
                    );
                  }
                  if (key === 'period') {
                    return `${this.basicInfo?.[key]}s`;
                  }
                  if (key === 'bk_biz_id') {
                    return this.getBizInfo(this.basicInfo?.[key]);
                  }
                  if (key === 'log_path' || key === 'filter_patterns') {
                    if (this.basicInfo?.[key]?.length) {
                      return this.basicInfo[key].map((word, wordIndex) => <span key={wordIndex}>{word}</span>);
                    }
                    return '--';
                  }
                  if (key === 'rules') {
                    return this.basicInfo?.[key]?.map((word, wordIndex) => (
                      <span key={wordIndex}>{`${word.name}=${word.pattern}`}</span>
                    ));
                  }
                  if (this.basicInfo?.collect_type === 'Process' && key === 'match') {
                    return (
                      <span class='detail-item-val process'>
                        {this.basicInfo?.[key] === 'command'
                          ? [
                              <div class='match-title'>{this.matchType?.[this.basicInfo?.[key]]}</div>,
                              <ul class='param-list'>
                                <li class='param-list-item'>
                                  <span class='item-name'>{this.$t('包含')}</span>
                                  <span class='item-content'>{this.basicInfo?.match_pattern}</span>
                                </li>
                                <li class='param-list-item'>
                                  <span class='item-name'>{this.$t('排除')}</span>
                                  <span class='item-content'>{this.basicInfo?.exclude_pattern}</span>
                                </li>
                              </ul>
                            ]
                          : [
                              <div class='match-title'>{this.matchType?.[this.basicInfo?.[key]]}</div>,
                              <div>{`${this.$t('PID的绝对路径')}：${this.basicInfo?.pid_path}`}</div>
                            ]}
                      </span>
                    );
                  }
                  return this.basicInfo?.[key];
                })()
              )
            )}
            {this.runtimeParams.length
              ? formItem(
                  this.$t('运行参数'),
                  <ul class='param-list mt--6'>
                    {this.runtimeParams.map((item, index) => (
                      <li
                        class='param-list-item width-840'
                        key={index}
                      >
                        <span class='item-name'>{item.name}</span>
                        {['password', 'encrypt'].includes(item.type) ? (
                          <span class='item-content'>******</span>
                        ) : (
                          <span class='item-content'>
                            {(item.type === 'file' ? item.value.filename : stringContent(item.value)) || '--'}
                          </span>
                        )}
                      </li>
                    ))}
                  </ul>
                )
              : undefined}
          </div>
        </div>
        <div class='split-line mt-24'></div>
        <div class='detail-wrap-item'>
          <div class='wrap-item-title mt-24'>{this.$t('采集目标')}</div>
          <div class='wrap-item-content mt-12'>
            <Table></Table>
          </div>
        </div>
      </div>
    );
  }
}
