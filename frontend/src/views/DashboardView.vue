<template>
  <AdminLayout>
    <PageHeader
      title="仪表盘"
      subtitle="当前概况与群活动。今日指标按 UTC 日期统计，数据变化时自动更新。"
    >
      <v-btn variant="tonal" :to="adminPath('jobs')">查看后台任务</v-btn>
    </PageHeader>
    <QueryError :error="summary.error.value" @retry="summary.refetch()" />
    <div class="content-grid mb-6">
      <v-card v-for="metric in metrics" :key="metric.key" class="surface-card pa-6">
        <div class="d-flex align-center justify-space-between muted mb-5">
          <span>{{ metric.title }}</span>
          <v-icon :icon="metric.icon" color="primary" size="24" />
        </div>
        <v-skeleton-loader v-if="summary.isPending.value" type="text" />
        <div v-else class="text-display-small">
          {{ summary.data.value?.[metric.key] ?? 0 }}
        </div>
      </v-card>
    </div>
    <v-card class="surface-card pa-6 mb-6">
      <div class="d-flex flex-wrap ga-6">
        <div v-for="asset in assets" :key="asset.key">
          <div class="text-label-large muted mb-1">{{ asset.title }}</div>
          <div class="text-title-large">{{ summary.data.value?.[asset.key] ?? '—' }}</div>
        </div>
      </div>
    </v-card>
    <LazySection
      v-for="section in sections"
      :key="section.name"
      :title="section.title"
      :name="section.name"
    >
      <template #default="{ active }">
        <DashboardPanel :section="section.name" :active="active" />
      </template>
    </LazySection>
  </AdminLayout>
</template>
<script setup lang="ts">
import {
  mdiMessageOutline,
  mdiAccountOutline,
  mdiAccountPlusOutline,
  mdiAccountMinusOutline,
} from '@mdi/js'
import { useRpcQuery } from '../api/queries'
import { adminPath } from '../adminRoute'
import AdminLayout from '../components/AdminLayout.vue'
import PageHeader from '../components/PageHeader.vue'
import QueryError from '../components/QueryError.vue'
import LazySection from '../components/LazySection.vue'
import DashboardPanel from '../components/DashboardPanel.vue'
const summary = useRpcQuery('dashboard.summary', {}, 'dashboard.summary')
const metrics = [
  { key: 'today_messages', title: '今日消息', icon: mdiMessageOutline },
  { key: 'today_active_members', title: '今日活跃成员', icon: mdiAccountOutline },
  { key: 'today_join_requests', title: '今日入群申请', icon: mdiAccountPlusOutline },
  { key: 'today_leave_events', title: '今日退群', icon: mdiAccountMinusOutline },
] as const
const assets = [
  { key: 'groups', title: '受管群' },
  { key: 'enabled_groups', title: '启用群' },
  { key: 'total_members', title: '总成员' },
  { key: 'announcements', title: '公告' },
  { key: 'files', title: '文件' },
  { key: 'essence_messages', title: '精华' },
] as const
const sections = [
  { name: 'trends', title: '近七天活动' },
  { name: 'breakdown', title: '申请处理结果' },
  { name: 'rankings', title: '规模与活跃排行' },
  { name: 'recent', title: '最近事件' },
] as const
</script>
