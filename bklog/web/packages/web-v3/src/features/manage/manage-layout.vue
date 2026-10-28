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
  <section class="manage-shell" data-ui="manage-root">
    <aside :class="['manage-nav', { 'is-collapsed': nav.collapsed }]" data-ui="manage-left">
      <nav class="manage-nav__tree" data-ui="manage-nav-tree">
        <section
          v-for="group in groups"
          :key="group.id"
          class="manage-nav__group"
          :data-ui="`manage-nav-group-${group.id}`"
        >
          <button type="button" class="manage-nav__group-title" @click="toggleGroup(group.id)">
            {{ nav.collapsed ? group.keyword : group.title }}
          </button>
          <div v-show="!collapsedGroups.has(group.id)" class="manage-nav__children">
            <router-link
              v-for="item in group.children"
              :key="item.id"
              :to="item.path"
              :class="['manage-nav__item', { 'is-active': activeId === item.id }]"
              :data-ui="`manage-nav-${item.id}`"
            >
              <i :class="['bklog-icon', item.icon]" />
              <span v-if="!nav.collapsed">{{ item.title }}</span>
            </router-link>
          </div>
        </section>
      </nav>
      <button
        type="button"
        class="manage-nav__collapse"
        data-ui="manage-nav-collapse"
        :title="nav.collapsed ? '展开导航' : '收起导航'"
        @click="toggleCollapsed"
      >
        {{ nav.collapsed ? '>' : '<' }}
      </button>
    </aside>
    <section class="manage-outlet">
      <router-view />
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, reactive } from 'vue';
import { useRoute } from 'vue-router';

import { ManageNavController, type ManageNavSnapshot } from './manage-nav';

const route = useRoute();
const controller = new ManageNavController();
const nav = reactive<ManageNavSnapshot>(controller.getState());
const groups = computed(() => controller.getGroups());
const activeId = computed(() => controller.getActiveId(route.path));
const collapsedGroups = computed(() => new Set(nav.collapsedGroups));

const toggleGroup = (id: string) => {
  Object.assign(nav, controller.toggleGroup(id));
};

const toggleCollapsed = () => {
  Object.assign(nav, controller.toggleCollapsed());
};
</script>
