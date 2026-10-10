<template>
  <!-- 混沌海 ChaosSea v1 图标（图形走产品设计流程评审后可迭代） -->
  <img src="@/assets/logo/chaossea-icon.svg" alt="混沌海" :height="height" />
</template>
<script setup lang="ts">
defineOptions({ name: 'LogoIcon' })

defineProps({
  height: {
    type: String,
    default: '36px',
  },
})
</script>
