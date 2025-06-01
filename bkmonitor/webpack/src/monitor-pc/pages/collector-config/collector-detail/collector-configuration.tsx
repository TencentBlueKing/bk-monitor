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
import { Component, Emit, Inject, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { renameCollectConfig } from 'monitor-api/modules/collecting';
import { copyText } from 'monitor-common/utils/utils.js';

import HistoryDialog from '../../../components/history-dialog/history-dialog';
import { allSpaceRegex, emojiRegex } from '../../../utils/index';
import { PLUGIN_MANAGE_AUTH } from '../authority-map';
import { TabEnum, type TabValue, type TabProperty, type ChangeConfig } from './typings/detail';

import './collector-configuration.scss';

enum ETargetColumn {
  agentStatus = 'agentStatus',
  catetory = 'catetory',
  cloudName = 'cloudName',
  IP = 'IP',
  name = 'name',
  objectType = 'objectType',
}

interface IProps {
  id: number | string;
  show: boolean;
  collectConfigData?: any;
  detailData?: any;
  targetInfo?: any;
  loading: boolean;
  tableLoading: boolean;
  onHandleAllDataChange: <T extends TabEnum, K extends TabProperty<T>>(changeConfig: ChangeConfig<T, K>) => void;
}

@Component
export default class CollectorConfiguration extends tsc<IProps> {
  @Prop({ type: [String, Number], default: '' }) id: number | string;
  @Prop({ type: Boolean, default: false }) show: boolean;
  @Prop({ type: Object, default: () => null }) collectConfigData: any;
  @Prop({ type: Object, default: () => null }) detailData: any;
  @Prop({ type: Object, default: () => null }) targetInfo: any;
  @Prop({ type: Boolean, default: false }) loading: boolean;
  @Prop({ type: Boolean, default: false }) tableLoading: boolean;

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
    bk_biz_id: window.i18n.t('所属'),
  };
  /* 采集目标表格字段 */
  nodeColumns = [
    { id: ETargetColumn.name, name: window.i18n.t('节点名称'), width: 140 },
    { id: ETargetColumn.objectType, name: window.i18n.t('实例数'), width: 100 },
    { id: ETargetColumn.catetory, name: window.i18n.t('分类'), width: 150 },
  ];
  ipColumns = [
    { id: ETargetColumn.IP, name: 'IP', width: 320 },
    { id: ETargetColumn.agentStatus, name: window.i18n.t('Agent状态'), width: 100 },
    { id: ETargetColumn.cloudName, name: window.i18n.t('管控区域'), width: 150 },
  ];
  matchType = {
    command: window.i18n.t('命令行匹配'),
    pid: window.i18n.t('PID文件'),
  };
  input = {
    show: false,
    copyName: '',
  };
  errMsg = {
    name: '',
  };
  name = '';

  get historyList() {
    return [
      { label: this.$t('创建人'), value: this.basicInfo?.create_user || '--' },
      { label: this.$t('创建时间'), value: this.basicInfo?.create_time || '--' },
      { label: this.$t('最近更新人'), value: this.basicInfo?.update_user || '--' },
      { label: this.$t('修改时间'), value: this.basicInfo?.update_time || '--' },
    ];
  }

  @Emit('handleAllDataChange')
  handleAllDataChange<T extends TabEnum, K extends TabProperty<T>>(tab: T, property: K, v: TabValue<T, K>) {
    return { tab, property, data: v };
  }

  @Watch('show', { immediate: true })
  handleShow(v: boolean) {
    if (v) {
      this.getDetailData();
    }
  }

  handleLoadingChange(v: boolean) {
    this.handleAllDataChange(TabEnum.Configuration, 'loading', v);
  }

  /**
   * @description 获取详情数据
   */
  getDetailData() {
    const data = this.detailData;
    this.basicInfo = { ...data.basic_info, id: this.id };
    if (data.extend_info.log) {
      this.basicInfo = { ...this.basicInfo, ...data.extend_info.log };
      !this.basicInfo.filter_patterns && (this.basicInfo.filter_patterns = []);
      this.basicInfoMap = {
        ...this.basicInfoMap,
        log_path: this.$t('日志路径'),
        filter_patterns: this.$t('排除规则'),
        rules: this.$t('关键字规则'),
        charset: this.$t('日志字符集'),
      };
    }
    if (data.extend_info.process) {
      const { process } = data.extend_info;
      this.basicInfoMap = {
        ...this.basicInfoMap,
        match: this.$t('进程匹配'),
        process_name: this.$t('进程名'),
        port_detect: this.$t('端口探测'),
      };
      const {
        match_type: matchType,
        process_name: processName,
        port_detect: portDetect,
        match_pattern: matchPattern,
        exclude_pattern: excludePattern,
        extract_pattern: extractPattern,
        pid_path: pidPath,
      } = process;
      this.basicInfo = {
        ...this.basicInfo,
        match: matchType,
        match_pattern: matchPattern,
        exclude_pattern: excludePattern,
        extract_pattern: extractPattern,
        pid_path: pidPath,
        process_name: processName || '--',
        port_detect: `${portDetect}`,
      };
    }
    this.runtimeParams = data.runtime_params;
  }

  /**
   * @description 更改配置名称
   * @param v
   * @param e
   */
  handleLabelKey(v, e) {
    this.errMsg.name = '';
    if (e.code === 'Enter' || e.code === 'NumpadEnter') {
      this.handleTagClickout();
    }
  }
  /**
   * @description 隐藏输入框
   */
  handleTagClickout() {
    if (allSpaceRegex(this.input.copyName) && !!this.input.copyName) {
      this.errMsg.name = this.$tc('配置名称不能为空');
      return;
    }
    if (emojiRegex(this.input.copyName)) {
      this.errMsg.name = this.$tc('不能输入emoji表情');
      return;
    }
    const data = this.basicInfo;
    const { copyName } = this.input;
    if (copyName.length && copyName !== data.name) {
      this.handleUpdateConfigName(data, copyName);
    } else {
      data.copyName = data.name;
      this.input.show = false;
      this.errMsg.name = '';
    }
  }
  /**
   * @description 更改配置名
   * @param data
   * @param copyName
   */
  handleUpdateConfigName(data, copyName) {
    this.handleLoadingChange(true);
    renameCollectConfig({ id: data.id, name: copyName }, { needMessage: false })
      .then(() => {
        this.basicInfo.name = copyName;
        this.name = copyName;
        this.$emit('update-name', data.id, copyName);
        this.$bkMessage({
          theme: 'success',
          message: this.$t('修改成功'),
        });
      })
      .catch(err => {
        this.$bkMessage({
          theme: 'error',
          message: err.message || this.$t('发生错误了'),
        });
      })
      .finally(() => {
        this.input.show = false;
        this.errMsg.name = '';
        this.handleLoadingChange(false);
      });
  }
  /**
   * @description 展示输入框
   * @param key
   */
  handleEditLabel(key) {
    this.input.copyName = this.basicInfo?.[key] || '';
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
          pluginId: this.basicInfo.plugin_id,
        },
      });
    }
  }

  getBizInfo(id) {
    const item = this.$store.getters.bizList.find(i => i.id === id) || {};
    return item ? `${item.text}(${item.type_name})` : '--';
  }

  handleToEdit() {
    this.$router.push({
      name: 'collect-config-edit',
      params: {
        id: this.id,
        pluginId: this.collectConfigData.plugin_id,
      },
    });
  }

  handleCopyTarget() {
    let copyStr = '';
    if (['TOPO', 'SET_TEMPLATE', 'SERVICE_TEMPLATE', 'DYNAMIC_GROUP'].includes(this.targetInfo.target_node_type)) {
      this.targetInfo.table_data.forEach(item => {
        copyStr += `${item.bk_inst_name}\n`;
      });
    } else if (this.targetInfo.target_node_type === 'INSTANCE') {
      this.targetInfo.table_data.forEach(item => {
        copyStr += `${item.display_name || item.ip}\n`;
      });
    }
    copyText(copyStr, msg => {
      this.$bkMessage({
        message: msg,
        theme: 'error',
      });
      return;
    });
    this.$bkMessage({
      message: this.$t('复制成功'),
      theme: 'success',
    });
  }

  render() {
    function formItem(label, content) {
      return (
        <span class='form-item'>
          <span class='item-label'>{label}:</span>
          <span class='item-content'>{content || '--'}</span>
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
        <div class='header-right-link'>
          <bk-button
            class='width-88 mr-8'
            v-authority={{ active: !this.authority.MANAGE_AUTH && this.collectConfigData?.status !== 'STOPPED' }}
            theme='primary'
            outline
            onClick={() =>
              this.authority.MANAGE_AUTH || this.collectConfigData?.status === 'STOPPED'
                ? this.collectConfigData?.status !== 'STOPPED' && this.handleToEdit()
                : this.handleShowAuthorityDetail()
            }
          >
            {this.$t('编辑')}
          </bk-button>
          <HistoryDialog list={this.historyList} />
        </div>
        <div
          class='detail-wrap-item'
          v-bkloading={{
            isLoading: this.loading,
            zIndex: 0,
          }}
        >
          <div class='wrap-item-title'>{this.$t('基本信息')}</div>
          <div class='wrap-item-content'>
            {Object.keys(this.basicInfoMap).map(key =>
              formItem(
                this.basicInfoMap?.[key],
                (() => {
                  if (key === 'name') {
                    return [
                      <span key={1}>
                        {this.input.show ? (
                          <bk-input
                            ref={`input${key}`}
                            class='edit-input width-150'
                            v-model={this.input.copyName}
                            maxlength={50}
                            onBlur={this.handleTagClickout}
                            onKeydown={this.handleLabelKey}
                          />
                        ) : (
                          <span
                            class='edit-span'
                            onClick={() => this.handleEditLabel(key)}
                          >
                            <span>{this.basicInfo?.[key] || '--'}</span>
                            <span class='icon-monitor icon-bianji' />
                          </span>
                        )}
                      </span>,
                      !!this.errMsg.name && <div class='err-msg'>{this.errMsg.name}</div>,
                    ];
                  }
                  if (key === 'plugin_display_name' && this.basicInfo?.collect_type !== 'Log') {
                    return (
                      <span class='edit-span'>
                        <span>{this.basicInfo?.[key]}</span>
                        <span
                          class='icon-monitor icon-bianji'
                          onClick={this.handleToEditPlugin}
                        />
                      </span>
                    );
                  }
                  if (key === 'period') {
                    return this.basicInfo?.[key] ? `${this.basicInfo?.[key]}s` : '--';
                  }
                  if (key === 'bk_biz_id') {
                    return this.basicInfo?.[key] ? this.getBizInfo(this.basicInfo?.[key]) : '--';
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
                  if (key === 'update_user') {
                    return this.basicInfo?.[key] ? <bk-user-display-name user-id={this.basicInfo?.[key]} /> : '--';
                  }
                  if (this.basicInfo?.collect_type === 'Process' && key === 'match') {
                    return (
                      <span class='detail-item-val process'>
                        {this.basicInfo?.[key] === 'command'
                          ? [
                              <div
                                key={'match-title'}
                                class='match-title'
                              >
                                {this.matchType?.[this.basicInfo?.[key]]}
                              </div>,
                              <ul
                                key={'param-list'}
                                class='param-list'
                              >
                                <li class='param-list-item'>
                                  <span class='item-name'>{this.$t('包含')}</span>
                                  <span class='item-content'>{this.basicInfo?.match_pattern}</span>
                                </li>
                                <li class='param-list-item'>
                                  <span class='item-name'>{this.$t('排除')}</span>
                                  <span class='item-content'>{this.basicInfo?.exclude_pattern}</span>
                                </li>
                                <li class='param-list-item'>
                                  <span class='item-name'>{this.$t('维度提取')}</span>
                                  <span class='item-content'>{this.basicInfo?.extract_pattern}</span>
                                </li>
                              </ul>,
                            ]
                          : [
                              <div
                                key={'match-title'}
                                class='match-title'
                              >
                                {this.matchType?.[this.basicInfo?.[key]]}
                              </div>,
                              <div
                                key={'param-list'}
                              >{`${this.$t('PID的绝对路径')}：${this.basicInfo?.pid_path}`}</div>,
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
                        key={index}
                        class='param-list-item'
                      >
                        <span class='item-name'>
                          <span class={{ 'name-text': true, required: item.required }}>{item.name}</span>
                        </span>
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
        {[
          <div
            key={1}
            class='split-line mt-24'
          />,
          <div
            key={2}
            class='detail-wrap-item'
          >
            <div class='wrap-item-title mt-24'>{this.$t('采集目标')}</div>
            {!!this.targetInfo?.table_data?.length && (
              <bk-button
                class='mt-10'
                size='small'
                theme='primary'
                text
                onClick={() => this.handleCopyTarget()}
              >
                {this.$t('复制目标')}
              </bk-button>
            )}
            <div class='wrap-item-content mt-12'>
              {['TOPO', 'SET_TEMPLATE', 'SERVICE_TEMPLATE', 'DYNAMIC_GROUP'].includes(
                this.targetInfo?.target_node_type
              ) ? (
                <bk-table
                  v-bkloading={{
                    isLoading: this.tableLoading,
                  }}
                  {...{
                    props: {
                      data: this.targetInfo?.table_data || [],
                    },
                  }}
                >
                  {this.nodeColumns.map(column => {
                    const key = `column_${column.id}`;
                    return (
                      <bk-table-column
                        key={key}
                        // width={column.width}
                        formatter={(row: any) => {
                          switch (column.id) {
                            case ETargetColumn.name: {
                              return <span>{row.bk_inst_name}</span>;
                            }
                            case ETargetColumn.objectType: {
                              return <span>{row.count}</span>;
                            }
                            case ETargetColumn.catetory: {
                              if (row.labels?.length) {
                                return row.labels.map((l, lIndex) => (
                                  <span
                                    key={lIndex}
                                    class='classifiy-label'
                                  >
                                    <span class='label-name'>{l.first}</span>
                                    <span class='label-name'>{l.second}</span>
                                  </span>
                                ));
                              }
                              return <span>--</span>;
                            }
                            default: {
                              return <span>--</span>;
                            }
                          }
                        }}
                        label={(() => {
                          if (column.id === ETargetColumn.objectType) {
                            return this.basicInfo?.target_object_type === 'SERVICE'
                              ? this.$t('实例数')
                              : this.$t('主机数');
                          }
                          return column.name;
                        })()}
                        prop={column.id}
                      />
                    );
                  })}
                </bk-table>
              ) : (
                <bk-table
                  v-bkloading={{
                    isLoading: this.tableLoading,
                  }}
                  {...{
                    props: {
                      data: this.targetInfo.table_data,
                    },
                  }}
                >
                  {this.ipColumns.map(column => {
                    const key = `column_${column.id}`;
                    return (
                      <bk-table-column
                        key={key}
                        // width={column.width}
                        formatter={(row: any) => {
                          switch (column.id) {
                            case ETargetColumn.IP: {
                              return <span>{row.display_name}</span>;
                            }
                            case ETargetColumn.agentStatus: {
                              return (
                                <span style={{ color: row.agent_status === 'normal' ? '#2DCB56' : '#EA3636' }}>
                                  {row.agent_status === 'normal' ? this.$t('正常') : this.$t('异常')}
                                </span>
                              );
                            }
                            case ETargetColumn.cloudName: {
                              return <span title={row.bk_cloud_name}>{row.bk_cloud_name || '--'}</span>;
                            }
                            default: {
                              return <span>--</span>;
                            }
                          }
                        }}
                        label={column.name}
                        prop={column.id}
                      />
                    );
                  })}
                </bk-table>
              )}
            </div>
          </div>,
        ]}
      </div>
    );
  }
}
