<!--
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
-->
<template>
  <div class="collector-log">
    <!-- 选择插件 -->
    <div
      v-show="false"
      class="collector-log-item"
    >
      <!-- 插件选择部分优先级提高，故隐藏此处 -->
      <div class="item-label">
        {{ $t('插件') }}
      </div>
      <div class="item-content">
        <bk-input
          v-model="pluginName"
          class="input-width"
          readonly
        />
      </div>
    </div>
    <!-- 日志路径 -->
    <div
      class="collector-log-item"
      style="margin-bottom: 16px"
      :class="{ 'verify-input': rule.logPath }"
    >
      <div class="item-label">
        {{ $t('日志路径') }}
      </div>
      <verify-input
        :show-validate.sync="rule.logPath"
        :validator="{ content: $t('至少填写一条日志路径') }"
      >
        <div class="item-content">
          <div
            v-for="(item, index) in logPath"
            :key="index"
            class="input-group"
          >
            <bk-input
              v-model="item.value"
              class="input-width"
              :placeholder="$t('填写日志路径')"
            />
            <i
              class="icon-monitor icon-jia"
              @click="handleAddRow('path', index)"
            />
            <i
              class="icon-monitor icon-jian"
              @click="handleDelRow('path', index)"
            />
          </div>
          <div class="item-content-tips">
            {{ $t('日志文件为绝对路径，可使用通配符') }}
          </div>
        </div>
      </verify-input>
    </div>
    <!-- 日志字符集 -->
    <div class="collector-log-item">
      <div class="item-label clear-after">
        {{ $t('日志字符集') }}
      </div>
      <div class="item-content">
        <bk-select
          v-model="character"
          class="input-width"
          :clearable="false"
        >
          <bk-option
            v-for="item in characterList"
            :id="item.id"
            :key="item.id"
            :name="item.name"
          />
        </bk-select>
      </div>
    </div>
    <!-- 排除规则 -->
    <div class="collector-log-item">
      <div class="item-label clear-after">
        {{ $t('排除规则') }}
      </div>
      <div class="item-content">
        <div
          v-for="(item, index) in filterRule"
          :key="index"
          class="input-group"
        >
          <bk-input
            v-model="item.value"
            class="input-width"
            :placeholder="$t('填写规则语句')"
          />
          <i
            class="icon-monitor icon-jia"
            @click="handleAddRow('filter', index)"
          />
          <i
            class="icon-monitor icon-jian"
            @click="handleDelRow('filter', index)"
          />
        </div>
      </div>
    </div>
    <!-- 关键字规则 -->
    <div
      class="collector-log-item"
      :class="{ 'verify-input': rule.keywordRule }"
    >
      <div class="item-label">
        {{ $t('关键字规则') }}
      </div>
      <verify-input
        :show-validate.sync="rule.keywordRule"
        :validator="{ content: $t('至少填写一条关键字规则，并填写完整') }"
      >
        <div class="item-content">
          <div
            v-for="(item, index) in keywordRule"
            :key="index"
            class="input-group"
          >
            <bk-input
              v-model="item.name"
              :placeholder="$t('填写规则名')"
              class="fir-input"
            />
            <bk-input
              v-model="item.pattern"
              :placeholder="$t('填写规则语句')"
              class="sec-input"
            />
            <i
              class="icon-monitor icon-jia"
              @click="handleAddRow('rule', index)"
            />
            <i
              class="icon-monitor icon-jian"
              @click="handleDelRow('rule', index)"
            />
          </div>
          <div
            v-if="!isRuleNameRepeat"
            style="color: #f00"
          >
            {{ $t('注意: 名字冲突') }}
          </div>
        </div>
      </verify-input>
    </div>
  </div>
</template>

<script lang="ts">
import { Component, Emit, Prop, Vue, Watch } from 'vue-property-decorator';

import { deepClone } from 'monitor-common/utils/utils';

import VerifyInput from '../../../../components/verify-input/verify-input.vue';

import type { TranslateResult } from 'vue-i18n/types/index';

interface IfilterRules {
  value: string;
}
interface IKeywordRule {
  name: string;
  pattern: string;
}
interface ILogData {
  charset: string;
  filter_patterns: string[];
  log_path: string[];
  rules: IKeywordRule[];
}
interface ILogPath {
  id: number;
  value: string;
}
interface IParams {
  charset: string;
  filter_patterns: string[];
  log_path: string[];
  rules: IKeywordRule[];
}
type TRuleType = 'filter' | 'path' | 'rule';

@Component({
  components: {
    VerifyInput,
  },
})
export default class CollectorLog extends Vue {
  pluginName: TranslateResult; //  插件名称
  logPath: ILogPath[] = [{ id: 0, value: '' }]; // 日志路径
  characterList: { id: string; name: string }[] = [{ id: 'utf-8', name: 'UTF-8' }]; //  日志字符集
  character = 'utf-8'; //  当前字符集
  keywordRule: IKeywordRule[] = [{ name: '', pattern: '' }]; //    关键字规则
  filterRule: IfilterRules[] = [{ value: '' }];
  //  校验提示
  rule: { keywordRule: boolean; logPath: boolean } = {
    logPath: false,
    keywordRule: false,
  };

  ruleItemMap = {
    path: { id: 0, value: '' },
    rule: { name: '', pattern: '' },
    filter: { value: '' },
  };

  get ruleDataMap() {
    return {
      path: this.logPath,
      rule: this.keywordRule,
      filter: this.filterRule,
    };
  }

  //  log回填Data
  @Prop({ default: () => ({}) })
  logData: any;

  //  日志路径校验
  @Watch('logPath', { deep: true })
  onLogPathChange(v: ILogPath[]): void {
    this.rule.logPath = !v.some(item => item.value !== '');
  }

  //  关键字规则校验
  @Watch('keywordRule', { deep: true })
  onKeywordRuleChange(v: IKeywordRule[]): void {
    this.rule.keywordRule = !v.every(item => item.name !== '' && item.pattern !== '');
  }

  //  编辑字段回填
  @Watch('logData', { immediate: true })
  onLogDataChange(v: ILogData): void {
    if (v.charset) {
      this.logPath = v.log_path.map((item, index) => ({ id: index, value: item }));
      this.keywordRule = v.rules;
      this.character = v.charset;
      this.filterRule = v.filter_patterns?.length
        ? v.filter_patterns.map(item => ({ value: `${item}` }))
        : [{ value: '' }];
    }
  }

  //  派发到父组件中控制下一步按钮亮起
  @Watch('canNext', { immediate: true })
  onCanNextChange(v: boolean): void {
    this.logCanSave(v);
  }

  @Emit()
  logCanSave(v: boolean) {
    return v;
  }

  //  能否下一步
  get canNext(): boolean {
    return (
      this.logPath.some(item => item.value !== '') &&
      this.keywordRule.every(item => item.name !== '' && item.pattern !== '') &&
      this.isRuleNameRepeat
    );
  }

  //  规则名字是否重复
  get isRuleNameRepeat(): boolean {
    const nameList = this.keywordRule.map(item => item.name);
    const res = Array.from(new Set(nameList));
    return res.length === nameList.length;
  }

  created() {
    this.pluginName = this.$t('日志关键字采集');
  }

  //  添加行操作
  handleAddRow(type: TRuleType, index: number): void {
    const arr: IfilterRules[] | IKeywordRule[] | ILogPath[] = this.ruleDataMap[type];
    const params: any = deepClone(this.ruleItemMap[type]);
    arr.splice(index + 1, 0, params);
  }

  //  删除行操作
  handleDelRow(type: TRuleType, index: number): void {
    const arr: IfilterRules[] | IKeywordRule[] | ILogPath[] = this.ruleDataMap[type];
    if (arr.length === 1) {
      const params: any = deepClone(this.ruleItemMap[type]);
      arr.splice(index + 1, 0, params);
    }
    arr.splice(index, 1);
  }

  //  获取要上报的数据
  getLogParams(): IParams {
    const logPath: string[] = this.logPath.map(item => item.value).filter(item => item !== '');
    const rules: IKeywordRule[] = this.keywordRule.filter(item => item.name !== '' && item.pattern !== '');
    const params: IParams = {
      log_path: logPath,
      charset: this.character,
      rules,
      filter_patterns: this.filterRule.map(item => item.value).filter(item => item !== ''),
    };
    return params;
  }
}
</script>

<style lang="scss" scoped>
.collector-log {
  &-item {
    display: flex;
    margin-bottom: 20px;

    .item-label {
      position: relative;
      min-width: 75px;
      height: 32px;
      margin-right: 34px;
      line-height: 32px;
      text-align: right;

      &::after {
        position: absolute;
        right: -9px;
        font-size: 12px;
        color: #f00;
        content: '*';
      }
    }

    .item-content {
      .input-width {
        width: 500px;
      }

      .input-group {
        display: flex;
        align-items: center;
        margin-bottom: 7px;

        .fir-input {
          width: 120px;
          margin-right: 8px;
        }

        .sec-input {
          width: 372px;
        }

        i {
          margin-left: 10px;
          font-size: 24px;
          color: #979ba5;
          cursor: pointer;
        }
      }

      &-tips {
        color: #979ba5;
      }
    }

    .clear-after {
      &::after {
        display: none;
      }
    }

    :deep(.bottom-text) {
      padding-top: 8px;
    }
  }

  .verify-input {
    /* stylelint-disable-next-line declaration-no-important */
    margin-bottom: 32px !important;
  }
}
</style>
