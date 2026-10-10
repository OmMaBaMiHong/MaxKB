<template>
  <!-- 后台上传的自定义登录 logo 优先；默认展示混沌海 ChaosSea v1 字标（图形走产品设计流程评审后可迭代） -->
  <img v-if="theme.themeInfo?.loginLogo" :src="fileURL" alt="" height="45px" class="mr-8" />
  <img v-else src="@/assets/logo/chaossea-full.svg" alt="混沌海 ChaosSea" :height="height" class="mr-8" />
</template>
<script setup lang="ts">
import { computed } from 'vue'
import useStore from '@/stores'
defineOptions({ name: 'LogoFull' })

defineProps({
  height: {
    type: String,
    default: '45px',
  },
})
const { theme } = useStore()
const fileURL = computed(() => {
  if (theme.themeInfo) {
    if (typeof theme.themeInfo?.loginLogo === 'string') {
      return theme.themeInfo?.loginLogo
    } else {
      return URL.createObjectURL(theme.themeInfo?.loginLogo)
    }
  }
  return ''
})
</script>
