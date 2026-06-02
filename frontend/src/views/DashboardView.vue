<template>
  <AdminLayout>
    <div class="page-head">
      <div>
        <h1 class="page-title">仪表盘</h1>
        <p class="page-subtitle">群审核、运营内容和最近后台动作的概览。</p>
      </div>
      <n-button @click="load">刷新</n-button>
    </div>
    <div class="metric-grid">
      <div v-for="item in metrics" :key="item.label" class="metric">
        <div class="metric-label">{{ item.label }}</div>
        <div class="metric-value">{{ item.value }}</div>
      </div>
    </div>
    <div class="dashboard-grid" style="margin-top: 18px">
      <section class="content-band">
        <div class="section-head">
          <h3>今日活跃</h3>
          <span>{{ todayText }}</span>
        </div>
        <div class="compact-metrics">
          <div v-for="item in todayMetrics" :key="item.label" class="compact-metric">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>
      </section>
      <section class="content-band">
        <div class="section-head">
          <h3>申请结果</h3>
          <span>全部时间</span>
        </div>
        <div class="breakdown-list">
          <div v-for="item in joinBreakdown" :key="item.label" class="breakdown-row">
            <span>{{ item.label }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
      </section>
    </div>
    <section class="content-band" style="margin-top: 18px">
      <div class="section-head">
          <h3>近 7 天活跃趋势</h3>
        <span>消息 / 后台操作 / 入群申请 / 退群</span>
      </div>
      <div class="trend-bars">
        <div v-for="day in trendRows" :key="day.date" class="trend-day">
          <div class="trend-stack">
            <span class="trend-bar message" :style="{ height: `${day.messageHeight}%` }"></span>
            <span class="trend-bar admin" :style="{ height: `${day.adminHeight}%` }"></span>
            <span class="trend-bar join" :style="{ height: `${day.joinHeight}%` }"></span>
            <span class="trend-bar leave" :style="{ height: `${day.leaveHeight}%` }"></span>
          </div>
          <div class="trend-label">{{ day.label }}</div>
          <div class="trend-count">{{ day.total }}</div>
        </div>
      </div>
    </section>
    <div class="dashboard-grid" style="margin-top: 18px">
      <section class="content-band">
        <div class="section-head">
          <h3>群活跃排行</h3>
          <span>按当前人数</span>
        </div>
        <div class="group-rank-list">
          <div v-for="group in dashboard?.top_groups ?? []" :key="group.group_id" class="group-rank-row">
            <div>
              <strong>{{ group.name }}</strong>
              <span>{{ group.group_id }} · 优先级 {{ group.priority }}</span>
            </div>
            <div class="rank-meter">
              <div :style="{ width: `${memberPercent(group)}%` }"></div>
            </div>
            <b>{{ group.current_members }}{{ group.max_members ? ` / ${group.max_members}` : '' }}</b>
          </div>
        </div>
      </section>
      <section class="content-band">
        <div class="section-head">
          <h3>成员活跃排行</h3>
          <span>近 7 天</span>
        </div>
        <n-data-table :columns="memberColumns" :data="dashboard?.active_members ?? []" />
      </section>
    </div>
    <section class="content-band" style="margin-top: 18px">
      <div class="section-head">
        <h3>最近退群</h3>
        <span>仅受管群</span>
      </div>
      <n-data-table :columns="leaveColumns" :data="dashboard?.recent_leave_events ?? []" />
    </section>
    <div class="content-band" style="margin-top: 18px">
      <h3>最近操作</h3>
      <n-data-table :columns="logColumns" :data="dashboard?.recent_audit_logs ?? []" />
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, h, onMounted, ref } from 'vue'
import type { DataTableColumns } from 'naive-ui'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const dashboard = ref<any>(null)

const metrics = computed(() => [
  { label: '受管群', value: dashboard.value?.groups ?? 0 },
  { label: '启用群', value: dashboard.value?.enabled_groups ?? 0 },
  { label: '总人数', value: dashboard.value?.total_members ?? 0 },
  { label: '今日消息', value: dashboard.value?.today_messages ?? 0 },
  { label: '今日活跃成员', value: dashboard.value?.today_active_members ?? 0 },
  { label: '入群申请', value: dashboard.value?.join_requests ?? 0 },
  { label: '退群事件', value: dashboard.value?.leave_events ?? 0 },
  { label: '公告', value: dashboard.value?.announcements ?? 0 },
  { label: '群文件', value: dashboard.value?.files ?? 0 },
  { label: '精华消息', value: dashboard.value?.essence_messages ?? 0 }
])

const todayText = computed(() => new Date().toLocaleDateString('zh-CN'))
const todayMetrics = computed(() => [
  { label: '今日消息', value: dashboard.value?.today_messages ?? 0 },
  { label: '活跃成员', value: dashboard.value?.today_active_members ?? 0 },
  { label: '今日申请', value: dashboard.value?.today_join_requests ?? 0 },
  { label: '今日退群', value: dashboard.value?.today_leave_events ?? 0 },
  { label: '今日操作', value: dashboard.value?.today_admin_actions ?? 0 }
])

const resultLabels: Record<string, string> = {
  approved: '已通过',
  rejected: '已拒绝',
  redirected: '已分流',
  pending: '待处理',
  unknown: '未知'
}

const joinBreakdown = computed(() =>
  (dashboard.value?.join_result_breakdown ?? []).map((item: any) => ({
    label: resultLabels[item.result] ?? item.result,
    count: item.count
  }))
)

const trendRows = computed(() => {
  const rows = dashboard.value?.activity_trend ?? []
  const max = Math.max(
    1,
    ...rows.map(
      (row: any) => row.messages + row.admin_actions + row.join_requests + row.leave_events
    )
  )
  return rows.map((row: any) => {
    const total = row.messages + row.admin_actions + row.join_requests + row.leave_events
    return {
      ...row,
      total,
      label: row.date.slice(5),
      messageHeight: Math.max(6, (row.messages / max) * 100),
      adminHeight: Math.max(6, (row.admin_actions / max) * 100),
      joinHeight: Math.max(6, (row.join_requests / max) * 100),
      leaveHeight: Math.max(6, (row.leave_events / max) * 100)
    }
  })
})

const logColumns: DataTableColumns = [
  { title: '动作', key: 'action', width: 160 },
  { title: '目标', key: 'target', width: 180 },
  { title: '时间', key: 'created_at' },
  {
    title: '详情',
    key: 'detail',
    render: (row) => h('code', { class: 'json-cell' }, JSON.stringify(row.detail))
  }
]

const leaveColumns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 130 },
  { title: '群号', key: 'group_id', width: 130 },
  { title: '类型', key: 'sub_type', width: 100 },
  { title: '时间', key: 'created_at' }
]

const memberColumns: DataTableColumns = [
  { title: 'QQ', key: 'user_id', width: 130 },
  { title: '昵称', key: 'nickname' },
  { title: '群', key: 'group_name' },
  { title: '消息数', key: 'message_count', width: 100 },
  { title: '最后活跃', key: 'last_active_at', width: 210 }
]

function memberPercent(group: any) {
  if (!group.max_members) return 100
  return Math.min(100, Math.round((group.current_members / group.max_members) * 100))
}

async function load() {
  const { data } = await api.get('/admin/dashboard')
  dashboard.value = data
}

onMounted(load)
</script>
