<template>
  <div class="group-selector">
    <div class="group-selector-head">
      <n-checkbox
        :checked="allSelected"
        :indeterminate="partiallySelected"
        :disabled="!groups.length"
        @update:checked="toggleAll"
      >
        全选目标群
      </n-checkbox>
      <div class="group-selector-actions">
        <span class="group-selector-count">已选 {{ selectedAvailableCount }} / {{ groups.length }}</span>
        <n-button size="tiny" quaternary :disabled="!modelValue.length" @click="clear">
          清空
        </n-button>
      </div>
    </div>
    <n-checkbox-group :value="modelValue" @update:value="updateValue">
      <n-space class="group-selector-options">
        <n-checkbox v-for="group in groups" :key="group.group_id" :value="group.group_id">
          {{ group.name || group.group_id }}
        </n-checkbox>
      </n-space>
    </n-checkbox-group>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ManagedGroup } from '../api/client'

const props = defineProps<{
  groups: ManagedGroup[]
  modelValue: number[]
}>()

const emit = defineEmits<{
  'update:modelValue': [value: number[]]
}>()

const groupIds = computed(() => props.groups.map((group) => group.group_id))
const selectedAvailableCount = computed(() => {
  const selected = new Set(props.modelValue)
  return groupIds.value.filter((groupId) => selected.has(groupId)).length
})
const allSelected = computed(
  () => groupIds.value.length > 0 && selectedAvailableCount.value === groupIds.value.length
)
const partiallySelected = computed(() => selectedAvailableCount.value > 0 && !allSelected.value)

function toggleAll(checked: boolean) {
  emit('update:modelValue', checked ? [...groupIds.value] : [])
}

function clear() {
  emit('update:modelValue', [])
}

function updateValue(value: Array<string | number>) {
  emit('update:modelValue', value.map(Number))
}
</script>
