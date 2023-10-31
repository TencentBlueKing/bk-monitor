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
import { Component, Prop, Watch } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';
import { Table } from 'bk-magic-vue';

import { frontendCollectConfigDetail } from '../../../../monitor-api/modules/collecting';

import './collector-configuration.scss';

interface IProps {
  id: string | number;
  show: boolean;
}

@Component
export default class CollectorConfiguration extends tsc<IProps> {
  @Prop({ type: [String, Number], default: '' }) id: number | string;
  @Prop({ type: Boolean, default: false }) show: boolean;

  /* 基本信息 */
  basicInfo: any = {};
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
      this.basicInfo = { ...data.basic_info };
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
    });
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
    return (
      <div class='collector-configuration-component'>
        <div class='detail-wrap-item'>
          <div class='wrap-item-title'>{this.$t('基本信息')}</div>
          <div class='wrap-item-content'>
            {[
              formItem('ID', '1111'),
              formItem(this.$t('所属业务'), '1111'),
              formItem(this.$t('采集名称'), '1111'),
              formItem(this.$t('插件'), '1111'),
              formItem(this.$t('采集对象'), '1111'),
              formItem(this.$t('英文名称'), '1111'),
              formItem(this.$t('集群'), '1111')
            ]}
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
