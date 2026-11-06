<script setup>
  const props = defineProps({
    embedded: { type: Boolean, default: false },
    cover: { type: Boolean, default: false },
    fieldWidth: { type: Number, default: -1 },
    railWidth: { type: Number, default: -1 },
    trendHeight: { type: Number, default: -1 },
  });

  const favoriteShown = localStorage.getItem('STORAGE_KEY_FAVORITE_SHOW') === 'true';
  const favoriteWidth = Number(localStorage.getItem('STORAGE_KEY_FAVORITE_WIDTH') || 240);
  const rail = props.railWidth >= 0 ? props.railWidth : favoriteShown ? (Number.isFinite(favoriteWidth) ? favoriteWidth : 240) : 0;
  const side = props.fieldWidth >= 0 ? props.fieldWidth : 200;
  const trend = props.trendHeight >= 0 ? props.trendHeight : 170;
</script>

<template>
  <div
    class="retrieve-page-skeleton"
    :class="{ 'is-embedded': embedded, 'is-cover': cover }"
    :style="{
      '--skeleton-rail': `${rail}px`,
      '--skeleton-side': `${side}px`,
      '--skeleton-trend': `${trend}px`,
    }"
    aria-busy="true"
  >
    <div
      v-if="!embedded && rail > 0"
      class="retrieve-page-skeleton__rail"
    />
    <div class="retrieve-page-skeleton__content">
      <div class="retrieve-page-skeleton__toolbar" />
      <div class="retrieve-page-skeleton__search" />
      <div class="retrieve-page-skeleton__body">
        <div
          v-if="side > 0"
          class="retrieve-page-skeleton__side"
        />
        <div class="retrieve-page-skeleton__main">
          <div class="retrieve-page-skeleton__trend" />
          <div
            v-for="row in 8"
            :key="row"
            class="retrieve-page-skeleton__row"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
  .retrieve-page-skeleton {
    display: flex;
    box-sizing: border-box;
    width: 100%;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    background: #f5f7fa;
  }

  .retrieve-page-skeleton__rail {
    flex: none;
    width: var(--skeleton-rail);
    background: #ebeef5;
  }

  .retrieve-page-skeleton__content {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
    height: 100%;
    padding: 0 8px 8px;
    overflow: hidden;
  }

  .retrieve-page-skeleton__toolbar,
  .retrieve-page-skeleton__search,
  .retrieve-page-skeleton__side,
  .retrieve-page-skeleton__trend,
  .retrieve-page-skeleton__row {
    border-radius: 2px;
    background: linear-gradient(90deg, #eef1f6 25%, #e4e8ef 37%, #eef1f6 63%);
    background-size: 400% 100%;
    animation: retrieve-page-skeleton-shimmer 1.4s ease infinite;
  }

  .retrieve-page-skeleton__toolbar {
    flex: none;
    width: 280px;
    height: 32px;
    margin: 8px 0 8px;
  }

  .retrieve-page-skeleton__search {
    flex: none;
    height: 52px;
    margin-bottom: 8px;
  }

  .retrieve-page-skeleton__body {
    display: flex;
    flex: 1;
    gap: 8px;
    min-height: 0;
  }

  .retrieve-page-skeleton.is-cover {
    position: absolute;
    inset: 0;
    z-index: 30;
  }

  .retrieve-page-skeleton__side {
    flex: none;
    width: var(--skeleton-side);
  }

  .retrieve-page-skeleton__main {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 8px;
    min-width: 0;
  }

  .retrieve-page-skeleton__trend {
    flex: none;
    height: var(--skeleton-trend);
  }

  .retrieve-page-skeleton__row {
    flex: none;
    height: 28px;
  }

  @keyframes retrieve-page-skeleton-shimmer {
    0% {
      background-position: 100% 50%;
    }

    100% {
      background-position: 0 50%;
    }
  }
</style>

<style>
  .retrieve-route-host {
    position: relative;
    width: 100%;
    height: 100%;
    min-height: 0;
    overflow: hidden;
  }
</style>
