<!--
  Tencent is pleased to support the open source community by making
  蓝鲸智云PaaS平台 (BlueKing PaaS) available.

  Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.

  蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.

  License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
    ---------------------------------------------------
  Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
  documentation files (the "Software"), to deal in the Software without restriction, including without limitation
  the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
  to permit persons to whom the Software is furnished to do so, subject to the following conditions:
  The above copyright notice and this permission notice shall be included in all copies or substantial portions of
  the Software.
  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
  THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
  CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
  IN THE SOFTWARE.
-->
<template>
  <section class="app-shell">
    <header class="app-header" data-ui="app-header">
      <router-link to="/retrieve" class="app-header__brand" data-ui="nav-brand">
        <span class="app-header__logo" aria-hidden="true" />
        <span class="app-header__brand-text">日志平台</span>
      </router-link>
      <nav class="app-header__nav" data-ui="nav-primary">
        <router-link
          v-for="item in primaryNav"
          :key="item.id"
          :to="item.to"
          :class="['app-header__link', { 'is-active': isActive(item.id) }]"
          :data-ui="`nav-${item.id}`"
        >
          {{ item.title }}
        </router-link>
      </nav>
      <button type="button" class="app-header__space" data-ui="space-select">
        <i class="bklog-icon bklog-mc-business" />
        <span>demo</span>
        <small>#5000140</small>
        <i class="bklog-icon bklog-arrow-down" />
      </button>
      <span class="app-header__actions">
        <i class="bklog-icon bklog-help" title="帮助" />
        <i class="bklog-icon bklog-shezhi" title="设置" />
        <span class="app-header__user" data-ui="nav-user">demo</span>
      </span>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </section>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router';

const route = useRoute();
const primaryNav = [
  { id: 'retrieve', title: '检索', to: '/retrieve' },
  { id: 'dashboard', title: '仪表盘', to: '/dashboard' },
  { id: 'manage', title: '管理', to: '/manage/collection' },
];
const isActive = (id: string) => {
  const path = route.path;
  if (id === 'retrieve') return path.startsWith('/retrieve');
  if (id === 'dashboard') return path.startsWith('/dashboard');
  return path.startsWith('/manage');
};
</script>
