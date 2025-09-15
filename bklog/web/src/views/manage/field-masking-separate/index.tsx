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

import { Component, Ref } from 'vue-property-decorator';
import { Component as tsc } from 'vue-tsx-support';

import { Button } from 'bk-magic-vue';

import $http from '../../../api';
import MaskingField from '../../../components/log-masking/masking-field';

import './index.scss';

interface IProps {
  value: boolean;
}

Component.registerHooks(['beforeRouteEnter']);
@Component
export default class FieldMaskingSeparate extends tsc<IProps> {
  submitLoading = false;

  curCollect = {
    index_set_id: '',
  };

  @Ref('maskingField') private readonly maskingFieldRef: HTMLElement; // 移动到分组实例

  created() {
    this.curCollect = {
      index_set_id: this.$route.params.indexSetId,
    };
  }

  /** 是否不显示 已同步 X 个脱敏结果 */
  get isHiddenSyncNum() {
    return ['bkdata-index-set-masking', 'es-index-set-masking'].includes(this.$route.name);
  }

  /** 进入路由前判断是否是灰度业务 */
  beforeRouteEnter(_from, _to, next) {
    next(vm => {
      const { $store, $router } = vm;
      if (!$store.getters.isShowMaskingTemplate) {
        $router.push({
          name: 'retrieve',
        });
      }
    });
  }

  async submitSelectRule(stepChange = false) {
    const data = (this.maskingFieldRef as any).getQueryConfigParams();
    const isUpdate = (this.maskingFieldRef as any).isUpdate;
    if (!(data.field_configs.length || isUpdate)) {
      this.$router.go(-1);
      return;
    } // 非更新状态且没有任何字段选择规则 直接下一步
    let requestStr = isUpdate ? 'updateDesensitizeConfig' : 'createDesensitizeConfig';
    if (!data.field_configs.length && isUpdate) {
      requestStr = 'deleteDesensitizeConfig';
    } // 无任何字段且是更新时 则删除当前索引集配置
    try {
      this.submitLoading = true;
      const res = await $http.request(`masking/${requestStr}`, {
        params: { index_set_id: this.curCollect?.index_set_id },
        data,
      });
      if (res.result && stepChange) {
        this.$bkMessage({
          theme: 'success',
          message: this.$t('操作成功'),
        });
        this.$router.go(-1);
      }
    } catch {
    } finally {
      this.submitLoading = false;
    }
  }

  cancelSelectRule() {
    this.$router.go(-1);
  }

  render() {
    return (
      <div class='filed-masking-container'>
        <div class='masking-field-box'>
          <MaskingField
            ref='maskingField'
            collect-data={this.curCollect}
            is-hidden-sync-num={this.isHiddenSyncNum}
            is-index-set-masking={false}
            onChangeData={() => this.submitSelectRule()}
          />
        </div>
        <div class='submit-content'>
          <Button
            loading={this.submitLoading}
            theme='primary'
            onClick={() => this.submitSelectRule(true)}
          >
            {this.$t('应用')}
          </Button>
          <Button
            theme='default'
            onClick={() => this.cancelSelectRule()}
          >
            {this.$t('取消')}
          </Button>
        </div>
      </div>
    );
  }
}
