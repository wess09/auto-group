<template>
  <section
    ref="element"
    class="surface-card pa-6 mb-6"
    :data-section="name"
    style="min-height: 320px"
  >
    <h2 class="text-title-large mb-5">{{ title }}</h2>
    <slot v-if="seen" :active="active" />
    <v-skeleton-loader v-else type="article" />
  </section>
</template>
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref } from 'vue'
defineProps<{ title: string; name: string }>()
const element = ref<HTMLElement | null>(null),
  seen = ref(false),
  active = ref(false)
let observer: IntersectionObserver | undefined
onMounted(() => {
  observer = new IntersectionObserver(
    (entries) => {
      active.value = entries[0].isIntersecting
      if (active.value) seen.value = true
    },
    { threshold: 0.05 },
  )
  if (element.value) observer.observe(element.value)
})
onBeforeUnmount(() => observer?.disconnect())
</script>
