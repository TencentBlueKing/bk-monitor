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
    <aside class="app-nav">
      <h1 class="app-nav__title">BKLog Vue3</h1>
      <p class="app-nav__hint">v1 已封板，仅落地 Vue3 重设计</p>
      <nav v-for="group in navGroups" :key="group.id" class="app-nav__group">
        <strong>{{ group.title }}</strong>
        <router-link
          v-for="item in group.items"
          :key="item.name"
          :to="{ name: item.name }"
          class="app-nav__link"
        >
          {{ item.meta?.title }}
        </router-link>
      </nav>
    </aside>
    <main class="app-main">
      <router-view />
    </main>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import { routes } from './app-router';

const navGroups = computed(() => {
  const items = routes.filter(route => route.name && route.meta?.title && route.path !== '/:pathMatch(.*)*');
  return [
    { id: 'retrieve', title: '检索', items: items.filter(item => item.meta?.group === 'retrieve') },
    { id: 'manage', title: '管理', items: items.filter(item => item.meta?.group === 'manage') },
    { id: 'other', title: '其他', items: items.filter(item => item.meta?.group === 'other' || item.meta?.group === 'system') },
  ];
});
</script>
