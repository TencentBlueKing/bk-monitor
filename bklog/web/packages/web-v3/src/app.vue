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
      <router-link to="/retrieve" class="app-header__brand">
        <span class="app-header__logo" aria-hidden="true" />
        日志平台
      </router-link>
      <nav class="app-header__nav">
        <router-link
          v-for="item in primaryNav"
          :key="item.name"
          :to="{ name: item.name }"
          class="app-header__link"
        >
          {{ item.meta?.title }}
        </router-link>
      </nav>
      <span class="app-header__space">demo (#5000140)</span>
    </header>
    <main class="app-main">
      <router-view />
    </main>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

import { routes } from './app-router';

const primaryNav = computed(() => routes.filter(route => (
  route.name
  && ['retrieve-search', 'manage-collection', 'manage-clean', 'manage-extract', 'dashboard'].includes(String(route.name))
)));
</script>
