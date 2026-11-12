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

<script setup lang="ts">
import {computed, ref} from 'vue';
import NativeTreeContract from './native-tree-contract';
const showTree=ref(false);
import {SearchIcon} from 'tdesign-icons-vue-next';
const iconClicks = ref(0);
import useVisibleInputFocus from '../src/shared/composables/use-visible-input-focus';
import {Button, Checkbox, CheckboxGroup, Radio, RadioGroup, Input, Select, Switch, TagInput} from 'tdesign-vue-next';
const popupOpen = ref(false), popupVisible = ref(false);
const popupInput = ref<{inputRef?: HTMLInputElement}>();
useVisibleInputFocus(popupOpen, computed(() => popupInput.value?.inputRef), '.fixture-popup');
const disabled = ref(false), selected = ref<string[]>([]), mode = ref('ui');
const name = ref(''), entered = ref(''), index = ref(''), refresh = ref(false), tags = ref<string[]>([]);
const options = [{label: '日志', value: 'logs'}, {label: 'Trace', value: 'trace'}];
function reset() {disabled.value = false;selected.value = [];mode.value = 'ui';index.value = '';refresh.value = false;tags.value = [];}
</script>
<template>
  <main>
    <h2>原生 TDesign 交互验证</h2>
    <Button @click="showTree = true">Mount test field tree</Button>
    <NativeTreeContract v-if="showTree" />
    <p>隔离模型契约，不连接业务接口。</p>
    <button type="button" data-testid="clock-icon-button" @click="iconClicks++"><SearchIcon /></button><output data-testid="clock-icon-clicks">{{ iconClicks }}</output>
    <section><Button :disabled="disabled">提交</Button><Checkbox v-model="disabled">禁用提交</Checkbox></section>
    <section>
      <CheckboxGroup v-model="selected"><Checkbox value="a">字段 A</Checkbox><Checkbox value="b">字段 B</Checkbox></CheckboxGroup>
      <output data-testid="selected">已选：{{ selected.join(',') || '无' }}</output>
    </section>
    <section><RadioGroup v-model="mode"><Radio value="ui">UI</Radio><Radio value="sql">SQL</Radio></RadioGroup><output data-testid="query-mode">模式：{{ mode }}</output></section>
    <section><Input v-model.trim="name" placeholder="输入检索名称后按 Enter" @enter="entered = String($event)" /><output>已提交名称：{{ entered || '无' }}</output></section>
    <section><Select v-model="index" :options="options" data-testid="native-select" /><output data-testid="native-selected-index">索引：{{ index || '无' }}</output></section>
    <section><Switch v-model="refresh" data-testid="native-switch" aria-label="启用自动刷新" /><output data-testid="native-refresh">刷新：{{ refresh }}</output></section>
    <section><TagInput v-model="tags" placeholder="新增字段" /><output data-testid="native-tags">字段：{{ tags.join(',') || '无' }}</output></section>
    <Button variant="text" @click="reset">重置</Button>
    <section>
      <Button @click="popupVisible = false; popupOpen = true">挂载隐藏浮层</Button>
      <Button @click="popupVisible = true">显示浮层</Button>
      <Button @click="popupOpen = false">关闭浮层</Button>
    </section>
    <div v-if="popupOpen" class="fixture-popup" :style="{visibility: popupVisible ? 'visible' : 'hidden'}">
      <Input ref="popupInput" placeholder="浮层内聚焦输入" />
    </div>
  </main>
</template>
<style scoped>
main {width: 720px;margin: 24px auto;font: 14px sans-serif;}
section {display: flex;gap: 16px;align-items: center;margin: 20px 0;}
.t-input__wrap,.t-select__wrap,.t-tag-input {max-width: 280px;}
</style>
