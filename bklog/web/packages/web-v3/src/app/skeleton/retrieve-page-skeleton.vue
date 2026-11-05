<template>
  <div
    class="retrieve-page-skeleton"
    aria-busy="true"
  >
    <div class="retrieve-page-skeleton__toolbar" />
    <div class="retrieve-page-skeleton__search" />
    <div class="retrieve-page-skeleton__body">
      <div class="retrieve-page-skeleton__side" />
      <div class="retrieve-page-skeleton__main">
        <div
          v-for="row in 8"
          :key="row"
          class="retrieve-page-skeleton__row"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
  .retrieve-page-skeleton {
    display: flex;
    flex-direction: column;
    gap: 12px;
    box-sizing: border-box;
    width: 100%;
    min-height: calc(100vh - 52px);
    padding: 16px 16px 24px;
    background: #f5f7fa;
  }

  .retrieve-page-skeleton__toolbar,
  .retrieve-page-skeleton__search,
  .retrieve-page-skeleton__side,
  .retrieve-page-skeleton__row {
    border-radius: 2px;
    background: linear-gradient(90deg, #eef1f6 25%, #e4e8ef 37%, #eef1f6 63%);
    background-size: 400% 100%;
    animation: retrieve-page-skeleton-shimmer 1.4s ease infinite;
  }

  .retrieve-page-skeleton__toolbar {
    height: 32px;
    width: 280px;
  }

  .retrieve-page-skeleton__search {
    height: 48px;
    width: 100%;
  }

  .retrieve-page-skeleton__body {
    display: flex;
    flex: 1;
    gap: 12px;
    min-height: 360px;
  }

  .retrieve-page-skeleton__side {
    width: 240px;
    flex: none;
  }

  .retrieve-page-skeleton__main {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 8px;
  }

  .retrieve-page-skeleton__row {
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
