<template>
  <QueryError :error="query.error.value" @retry="query.refetch()" />
  <v-progress-linear v-if="query.isFetching.value" indeterminate />
  <MetricChart v-if="section === 'trends' && trends" kind="trend" :data="trends.items" />
  <MetricChart
    v-else-if="section === 'breakdown' && breakdown"
    kind="breakdown"
    :data="breakdown.items"
  />
  <div v-else-if="section === 'rankings' && rankings" class="content-grid">
    <div>
      <h3 class="text-title-medium mb-4">成员规模</h3>
      <v-list bg-color="transparent">
        <v-list-item
          v-for="row in rankings.top_groups"
          :key="row.id"
          :title="String(row.name || row.group_id)"
          :subtitle="`成员 ${row.current_members} · 优先级 ${row.priority}`"
        />
      </v-list>
    </div>
    <div>
      <h3 class="text-title-medium mb-4">近七天活跃群</h3>
      <v-list bg-color="transparent">
        <v-list-item
          v-for="row in rankings.active_groups"
          :key="Number(row.group_id)"
          :title="String(row.name || row.group_id)"
          :subtitle="`消息 ${row.message_count} · 活跃成员 ${row.active_members}`"
        />
      </v-list>
    </div>
    <div>
      <h3 class="text-title-medium mb-4">近七天活跃成员</h3>
      <v-list bg-color="transparent">
        <v-list-item
          v-for="row in rankings.active_members"
          :key="`${row.group_id}:${row.user_id}`"
          :title="String(row.nickname)"
          :subtitle="`群 ${row.group_id} · 消息 ${row.message_count}`"
        />
      </v-list>
    </div>
  </div>
  <div v-else-if="section === 'recent' && recent" class="content-grid">
    <div>
      <h3 class="text-title-medium mb-4">最近退群</h3>
      <v-list bg-color="transparent">
        <v-list-item
          v-for="row in recent.leaves"
          :key="row.id"
          :title="`QQ ${row.user_id}`"
          :subtitle="`群 ${row.group_id} · ${row.sub_type}`"
        />
      </v-list>
      <div v-if="!recent.leaves.length" class="muted">暂无记录</div>
    </div>
    <div>
      <h3 class="text-title-medium mb-4">最近后台操作</h3>
      <v-list bg-color="transparent">
        <v-list-item
          v-for="row in recent.audits"
          :key="row.id"
          :title="String(row.action)"
          :subtitle="String(row.target)"
        />
      </v-list>
      <div v-if="!recent.audits.length" class="muted">暂无记录</div>
    </div>
  </div>
</template>
<script setup lang="ts">
import { computed, defineAsyncComponent } from 'vue'
import { useRpcQuery } from '../api/queries'
import type { ApiMethods } from '../api/types'
import QueryError from './QueryError.vue'
const MetricChart = defineAsyncComponent(() => import('./MetricChart.vue'))
const props = defineProps<{
  section: 'trends' | 'breakdown' | 'rankings' | 'recent'
  active: boolean
}>()
const query = useRpcQuery(
  () => `dashboard.${props.section}` as const,
  {},
  () => `dashboard.${props.section}`,
  () => props.active,
)
const trends = computed(() =>
  props.section === 'trends'
    ? (query.data.value as ApiMethods['dashboard.trends']['result'] | undefined)
    : undefined,
)
const breakdown = computed(() =>
  props.section === 'breakdown'
    ? (query.data.value as ApiMethods['dashboard.breakdown']['result'] | undefined)
    : undefined,
)
const rankings = computed(() =>
  props.section === 'rankings'
    ? (query.data.value as ApiMethods['dashboard.rankings']['result'] | undefined)
    : undefined,
)
const recent = computed(() =>
  props.section === 'recent'
    ? (query.data.value as ApiMethods['dashboard.recent']['result'] | undefined)
    : undefined,
)
</script>
