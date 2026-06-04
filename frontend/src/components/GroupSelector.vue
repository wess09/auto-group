<template>
  <div class="group-selector">
    <div class="group-selector-head">
      <div class="select-all-wrap">
        <el-checkbox
          :model-value="allSelected"
          :indeterminate="partiallySelected"
          :disabled="!groups.length"
          @update:model-value="toggleAll"
          class="custom-checkbox"
        >
          全选目标群
        </el-checkbox>
      </div>
      <div class="group-selector-actions">
        <span class="group-selector-count">已选 <strong class="highlight-count">{{ selectedAvailableCount }}</strong> / {{ groups.length }}</span>
        <el-button size="small" link type="primary" :disabled="!modelValue.length" @click="clear" class="clear-btn">
          清空选择
        </el-button>
      </div>
    </div>
    
    <div class="group-selector-body">
      <div v-if="groups.length" class="group-cards-grid">
        <div 
          v-for="group in groups" 
          :key="group.group_id" 
          class="group-card" 
          :class="{ active: isSelected(group.group_id) }"
          @click="toggleGroup(group.group_id)"
        >
          <el-avatar 
            :size="28" 
            :src="`https://p.qlogo.cn/gh/${group.group_id}/${group.group_id}/100`" 
            class="group-avatar"
          >
            {{ (group.name || '群').charAt(0) }}
          </el-avatar>
          <div class="group-info">
            <span class="group-name" :title="group.name || '未命名群'">{{ group.name || '未命名群' }}</span>
            <span class="group-id">ID: {{ group.group_id }}</span>
          </div>
          <div class="group-check-status">
            <transition name="fade-scale">
              <el-icon v-if="isSelected(group.group_id)" class="check-icon"><Check /></el-icon>
            </transition>
          </div>
        </div>
      </div>
      <el-empty v-else description="无可用群数据" :image-size="60" style="padding: 20px 0" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { Check } from '@element-plus/icons-vue'
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

function isSelected(groupId: number) {
  return props.modelValue.includes(groupId)
}

function toggleGroup(groupId: number) {
  const selected = [...props.modelValue]
  const index = selected.indexOf(groupId)
  if (index > -1) {
    selected.splice(index, 1)
  } else {
    selected.push(groupId)
  }
  emit('update:modelValue', selected)
}

function toggleAll(checked: string | number | boolean) {
  emit('update:modelValue', checked ? [...groupIds.value] : [])
}

function clear() {
  emit('update:modelValue', [])
}
</script>

<style scoped>
.group-selector {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.group-selector-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0 4px;
}

.group-selector-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.group-selector-count {
  font-size: 13px;
  color: var(--geeker-text-secondary);
}

.highlight-count {
  color: var(--md-primary);
  font-weight: 600;
}

.clear-btn {
  font-size: 13px !important;
}

.group-selector-body {
  background-color: #f8fafc;
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 12px;
  padding: 16px;
  max-height: 240px;
  overflow-y: auto;
}

/* 极细滚动条 */
.group-selector-body::-webkit-scrollbar {
  width: 5px;
}
.group-selector-body::-webkit-scrollbar-thumb {
  background: rgba(15, 23, 42, 0.08);
  border-radius: 4px;
}

.group-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 10px;
}

.group-card {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  background: #ffffff;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  cursor: pointer;
  user-select: none;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  position: relative;
  overflow: hidden;
}

.group-card:hover {
  border-color: color-mix(in srgb, var(--md-primary) 35%, #e2e8f0);
  background: color-mix(in srgb, var(--md-primary) 2%, #ffffff);
}

.group-card.active {
  border-color: var(--md-primary);
  background: color-mix(in srgb, var(--md-primary) 6%, #ffffff);
  box-shadow: 0 4px 12px color-mix(in srgb, var(--md-primary) 8%, transparent);
}

.group-avatar {
  border: 1px solid rgba(226, 232, 240, 0.8);
  background-color: #f1f5f9;
  font-weight: 600;
  color: var(--md-primary);
  flex-shrink: 0;
}

.group-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
  flex: 1;
}

.group-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--geeker-text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  line-height: 1.3;
}

.group-id {
  font-size: 11px;
  color: var(--geeker-text-secondary);
  margin-top: 2px;
}

.group-check-status {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.check-icon {
  font-size: 14px;
  color: var(--md-primary);
  font-weight: bold;
}

/* 动效 */
.fade-scale-enter-active,
.fade-scale-leave-active {
  transition: all 0.15s ease;
}
.fade-scale-enter-from,
.fade-scale-leave-to {
  opacity: 0;
  transform: scale(0.7);
}
</style>
