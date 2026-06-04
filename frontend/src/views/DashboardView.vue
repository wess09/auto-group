<template>
  <AdminLayout>
    <div v-loading="!dashboard" element-loading-text="正在读取系统看板数据..." style="min-height: 500px;">
      <div v-if="dashboard">
        <div class="page-head">
          <div>
            <h1 class="page-title">仪表盘</h1>
            <p class="page-subtitle">群审核、运营内容和最近后台动作的概览。</p>
          </div>
          <el-button type="primary" plain @click="load">刷新</el-button>
        </div>

        <!-- 顶部数据大卡片：采用更高端的今日活跃核心与系统资产网格分栏排版，大幅节省高度 -->
        <el-row :gutter="16" class="metric-row-v2" style="margin-bottom: 12px">
          <!-- 左侧今日活跃核心指标 (4个大卡片) -->
          <el-col :xs="24" :sm="24" :md="16" :lg="16" :xl="16" style="margin-bottom: 12px">
            <el-row :gutter="12">
          <el-col v-for="item in coreMetrics" :key="item.label" :xs="12" :sm="12" :md="6" :lg="6" :xl="6">
            <el-card shadow="hover" class="metric-card-v2" :body-style="{ padding: '14px' }">
              <div class="metric-card-header-v2">
                <span class="metric-card-title-v2">{{ item.label }}</span>
                <el-icon class="metric-card-icon-v2" :style="{ color: item.color, backgroundColor: `${item.color}15` }">
                  <component :is="item.icon" />
                </el-icon>
              </div>
              <div class="metric-card-value-v2">
                <el-statistic :value="item.value" />
              </div>
            </el-card>
          </el-col>
        </el-row>
      </el-col>

      <!-- 右侧系统资产与基础指标面板 -->
      <el-col :xs="24" :sm="24" :md="8" :lg="8" :xl="8" style="margin-bottom: 12px">
        <el-card shadow="hover" class="overview-panel-card" :body-style="{ padding: '14px 18px' }">
          <div class="overview-panel-title">群组资产与累积资源</div>
          <div class="overview-grid">
            <div v-for="item in assetMetrics" :key="item.label" class="overview-item">
              <div class="overview-label-wrap">
                <el-icon class="overview-item-icon" :style="{ color: item.color }">
                  <component :is="item.icon" />
                </el-icon>
                <span class="overview-item-label">{{ item.label }}</span>
              </div>
              <span class="overview-item-value">{{ formatNumber(item.value) }}</span>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 中间活跃详情与申请饼图替代进度条 -->
    <div class="dashboard-grid" style="margin-top: 8px">
      <el-card shadow="hover" class="content-band-card">
        <template #header>
          <div class="section-head">
            <h3>今日活跃</h3>
            <span>{{ todayText }}</span>
          </div>
        </template>
        <div class="compact-metrics">
          <div v-for="item in todayMetrics" :key="item.label" class="compact-metric">
            <span>{{ item.label }}</span>
            <strong>{{ item.value }}</strong>
          </div>
        </div>

        <div class="today-insights-box">
          <div class="insights-title-row">
            <el-icon class="insights-icon"><InfoFilled /></el-icon>
            <span class="insights-title">今日核心情报</span>
          </div>
          <div class="insights-content-grid">
            <div class="insight-card">
              <span class="insight-card-label">最活跃群组</span>
              <strong class="insight-card-value text-ellipsis">{{ topGroup }}</strong>
            </div>
            <div class="insight-card">
              <span class="insight-card-label">最活跃成员</span>
              <strong class="insight-card-value text-ellipsis">{{ topMember }}</strong>
            </div>
            <div class="insight-card">
              <span class="insight-card-label">自动入群审核</span>
              <strong class="insight-card-value">{{ approvedCount }} 次通过</strong>
            </div>
            <div class="insight-card">
              <span class="insight-card-label">系统群组资产</span>
              <strong class="insight-card-value">{{ dashboard?.groups ?? 0 }} 个受管群</strong>
            </div>
          </div>
        </div>
      </el-card>

      <el-card shadow="hover" class="content-band-card">
        <template #header>
          <div class="section-head">
            <h3>申请结果分布</h3>
            <span>全部时间统计</span>
          </div>
        </template>
        <!-- ECharts 环形图挂载容器 -->
        <div ref="resultChartRef" style="width: 100%; height: 240px;"></div>
      </el-card>
    </div>

    <!-- 近 7 天活跃趋势：用 ECharts 折线/柱状混合图呈现 -->
    <el-card shadow="hover" class="content-band-card" style="margin-top: 12px">
      <template #header>
        <div class="section-head">
          <h3>近 7 天活跃趋势</h3>
          <span>消息 / 后台操作 / 入群申请 / 退群 趋势统计</span>
        </div>
      </template>
      <!-- ECharts 趋势图挂载容器 -->
      <div ref="trendChartRef" style="width: 100%; height: 320px;"></div>
    </el-card>

    <!-- 下半部分群活跃与成员活跃 -->
    <div class="dashboard-grid" style="margin-top: 12px">
      <el-card shadow="hover" class="content-band-card">
        <template #header>
          <div class="section-head">
            <h3>群人数排行</h3>
            <span>按当前群人数排序</span>
          </div>
        </template>
        <el-table :data="dashboard?.top_groups ?? []" border size="small" style="width: 100%">
          <el-table-column label="排行" width="55" align="center">
            <template #default="{ $index }">
              <span 
                class="rank-badge" 
                :class="{ 
                  'rank-top-1': $index === 0, 
                  'rank-top-2': $index === 1, 
                  'rank-top-3': $index === 2 
                }"
              >
                {{ $index + 1 }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="name" label="群名称" show-overflow-tooltip>
            <template #default="{ row }">
              <div v-if="row.name && row.name !== String(row.group_id)" class="table-group-info">
                <span class="group-table-name">{{ row.name }}</span>
                <span class="group-table-id">{{ row.group_id }}</span>
              </div>
              <div v-else class="table-group-info">
                <span class="group-table-name">{{ row.group_id }}</span>
              </div>
            </template>
          </el-table-column>
          <el-table-column label="满员率" width="110" align="center">
            <template #default="{ row }">
              <div class="table-progress-wrap">
                <el-progress 
                  :percentage="memberPercent(row)" 
                  :stroke-width="6" 
                  :color="getProgressColor(memberPercent(row))"
                />
              </div>
            </template>
          </el-table-column>
          <el-table-column label="群人数" width="105" align="center">
            <template #default="{ row }">
              <span class="group-table-members">{{ row.current_members }}{{ row.max_members ? ` / ${row.max_members}` : '' }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>

      <el-card shadow="hover" class="content-band-card">
        <template #header>
          <div class="section-head">
            <h3>成员活跃排行</h3>
            <span>近 7 天消息发送排行</span>
          </div>
        </template>
        <el-table :data="dashboard?.active_members ?? []" border size="small" style="width: 100%">
          <el-table-column label="排行" width="55" align="center">
            <template #default="{ $index }">
              <span 
                class="rank-badge" 
                :class="{ 
                  'rank-top-1': $index === 0, 
                  'rank-top-2': $index === 1, 
                  'rank-top-3': $index === 2 
                }"
              >
                {{ $index + 1 }}
              </span>
            </template>
          </el-table-column>
          <el-table-column prop="user_id" label="QQ" width="105" />
          <el-table-column prop="nickname" label="昵称" show-overflow-tooltip />
          <el-table-column prop="group_name" label="所在群" show-overflow-tooltip />
          <el-table-column prop="message_count" label="消息数" width="75" align="center" />
          <el-table-column label="最后活跃" width="115" align="center">
            <template #default="{ row }">
              <span class="active-time">{{ formatActiveTime(row.last_active_at) }}</span>
            </template>
          </el-table-column>
        </el-table>
      </el-card>
    </div>

    <!-- 最近退群 -->
    <el-card shadow="hover" class="content-band-card" style="margin-top: 12px">
      <template #header>
        <div class="section-head">
          <h3>最近退群</h3>
          <span>仅受管群事件</span>
        </div>
      </template>
      <el-table :data="dashboard?.recent_leave_events ?? []" border size="small" style="width: 100%">
        <!-- 离开成员 -->
        <el-table-column label="离开成员" width="115">
          <template #default="{ row }">
            <span class="group-table-members">QQ: {{ row.user_id }}</span>
          </template>
        </el-table-column>
        
        <!-- 昵称 -->
        <el-table-column label="昵称" width="120" show-overflow-tooltip>
          <template #default="{ row }">
            <span class="group-table-name">{{ (row.nickname && row.nickname !== String(row.user_id) && row.nickname !== '-') ? row.nickname : '-' }}</span>
          </template>
        </el-table-column>
        
        <!-- 退群群组 -->
        <el-table-column label="退群群组" min-width="150" show-overflow-tooltip>
          <template #default="{ row }">
            <div v-if="row.group_name && row.group_name !== String(row.group_id) && row.group_name !== '-'" class="table-group-info">
              <span class="group-table-name">{{ row.group_name }}</span>
              <span class="group-table-id">{{ row.group_id }}</span>
            </div>
            <div v-else class="table-group-info">
              <span class="group-table-name">{{ row.group_id }}</span>
            </div>
          </template>
        </el-table-column>
        
        <!-- 原因 -->
        <el-table-column label="原因" width="90" align="center">
          <template #default="{ row }">
            <el-tag :type="row.sub_type === 'kick' ? 'danger' : 'info'" size="small">
              {{ row.sub_type === 'kick' ? '被踢' : '主动退群' }}
            </el-tag>
          </template>
        </el-table-column>
        
        <!-- 操作人 -->
        <el-table-column label="操作人" width="140" show-overflow-tooltip>
          <template #default="{ row }">
            <template v-if="row.sub_type === 'kick' && row.operator_id">
              <div v-if="row.operator_nickname && row.operator_nickname !== String(row.operator_id) && row.operator_nickname !== '-'" class="table-group-info">
                <span class="group-table-name">{{ row.operator_nickname }}</span>
                <span class="group-table-id">QQ: {{ row.operator_id }}</span>
              </div>
              <div v-else class="table-group-info">
                <span class="group-table-name">QQ: {{ row.operator_id }}</span>
              </div>
            </template>
            <span v-else class="text-muted">-</span>
          </template>
        </el-table-column>
        
        <!-- 时间 -->
        <el-table-column label="时间" width="115" align="center">
          <template #default="{ row }">
            <span>{{ formatActiveTime(row.created_at) }}</span>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 最近操作 -->
    <el-card shadow="hover" class="content-band-card" style="margin-top: 12px; margin-bottom: 12px;">
      <template #header>
        <div class="section-head">
          <h3>最近操作日志</h3>
          <span>管理后台审计记录</span>
        </div>
      </template>
      <el-table :data="dashboard?.recent_audit_logs ?? []" border size="small" style="width: 100%">
        <el-table-column label="动作" width="150">
          <template #default="{ row }">
            <span>{{ formatAction(row.action) }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="target" label="目标" width="160" />
        <el-table-column label="时间" width="115" align="center">
          <template #default="{ row }">
            <span>{{ formatActiveTime(row.created_at) }}</span>
          </template>
        </el-table-column>
        <el-table-column label="详情" min-width="260">
          <template #default="{ row }">
            <code class="json-cell">{{ JSON.stringify(row.detail) }}</code>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
      </div>
    </div>
  </AdminLayout>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'
import {
  User,
  Select,
  ChatLineRound,
  Checked,
  Notification,
  FolderOpened,
  Star,
  MessageBox,
  CircleClose,
  PieChart,
  InfoFilled
} from '@element-plus/icons-vue'
import AdminLayout from '../components/AdminLayout.vue'
import { api } from '../api/client'

const dashboard = ref<any>(null)

// ECharts 元素引用
const trendChartRef = ref<HTMLDivElement | null>(null)
const resultChartRef = ref<HTMLDivElement | null>(null)

let trendChart: echarts.ECharts | null = null
let resultChart: echarts.ECharts | null = null

// 今日活跃指标大卡片
const coreMetrics = computed(() => [
  { label: '今日消息', value: dashboard.value?.today_messages ?? 0, icon: ChatLineRound, color: '#f59e0b' },
  { label: '活跃成员', value: dashboard.value?.today_active_members ?? 0, icon: User, color: '#8b5cf6' },
  { label: '入群申请', value: dashboard.value?.join_requests ?? 0, icon: Checked, color: '#ec4899' },
  { label: '退群事件', value: dashboard.value?.leave_events ?? 0, icon: CircleClose, color: '#ef4444' }
])

// 系统资产静态数据网格
const assetMetrics = computed(() => [
  { label: '受管群', value: dashboard.value?.groups ?? 0, icon: User, color: '#3b82f6' },
  { label: '启用群', value: dashboard.value?.enabled_groups ?? 0, icon: Select, color: '#10b981' },
  { label: '总人数', value: dashboard.value?.total_members ?? 0, icon: PieChart, color: '#6366f1' },
  { label: '公告数量', value: dashboard.value?.announcements ?? 0, icon: Notification, color: '#14b8a6' },
  { label: '群文件数', value: dashboard.value?.files ?? 0, icon: FolderOpened, color: '#06b6d4' },
  { label: '精华消息', value: dashboard.value?.essence_messages ?? 0, icon: Star, color: '#eab308' }
])

function formatNumber(val: number | undefined) {
  if (val === undefined) return '0'
  return val.toLocaleString('zh-CN')
}

function formatActiveTime(val: string | undefined) {
  if (!val) return '-'
  const cleaned = val.replace('T', ' ')
  if (cleaned.length >= 16) {
    return cleaned.substring(5, 16) // 缩短显示格式为月-日 时:分，避免折行撑高表格
  }
  return cleaned
}

const topGroup = computed(() => {
  const g = dashboard.value?.top_groups?.[0]
  return g ? (g.name || String(g.group_id)) : '暂无数据'
})

const topMember = computed(() => {
  const m = dashboard.value?.active_members?.[0]
  return m ? (m.nickname || String(m.user_id)) : '暂无数据'
})

const approvedCount = computed(() => {
  const item = dashboard.value?.join_result_breakdown?.find((i: any) => i.result === 'approved')
  return item ? item.count : 0
})

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
  blacklisted: '黑名单拒绝',
  pending: '待处理',
  unknown: '未知'
}

const actionLabels: Record<string, string> = {
  'group.create': '创建受管群',
  'group.update': '修改群配置',
  'group.delete': '取消群管理',
  'group.sync_info': '同步群信息',
  'rule.create': '新建答题规则',
  'rule.update': '修改答题规则',
  'rule.delete': '删除答题规则',
  'join_blacklist.create': '新增黑名单',
  'join_blacklist.update': '修改黑名单',
  'join_blacklist.delete': '移除黑名单',
  'message_moderation_rule.create': '创建违规词规则',
  'message_moderation_rule.update': '更新违规词规则',
  'message_moderation_rule.delete': '删除违规词规则',
  'message_moderation_cloud_config.update': '更新腾讯云审查设置',
  'dedupe.whitelist.create': '加去重白名单',
  'dedupe.whitelist.update': '改去重白名单',
  'dedupe.whitelist.delete': '删去重白名单',
  'dedupe.preview.start': '开启去重预览',
  'dedupe.execute.start': '执行去重清理',
  'notice.sync': '同步群公告',
  'notice.send': '发布群公告',
  'notice.delete': '删除群公告',
  'file.sync': '同步群文件',
  'file.distribute': '分发群文件',
  'file.delete': '删除群文件',
  'file.rename': '重命名群文件',
  'file.rename_folder': '重命名文件夹',
  'essence.sync': '同步精华消息',
  'essence.create': '添加精华消息',
  'essence.delete': '移出精华消息'
}

function formatAction(action: string) {
  return actionLabels[action] || action
}

const joinBreakdown = computed(() =>
  (dashboard.value?.join_result_breakdown ?? []).map((item: any) => ({
    label: resultLabels[item.result] ?? item.result,
    count: item.count
  }))
)

// 计算占总申请数的百分比
function calcPercentage(count: number) {
  const total = (dashboard.value?.join_result_breakdown ?? []).reduce((acc: number, curr: any) => acc + curr.count, 0)
  if (!total) return 0
  return Math.round((count / total) * 100)
}

// 动态匹配进度条状态
function getProgressStatus(label: string) {
  if (label.includes('通过')) return 'success'
  if (label.includes('分流')) return 'warning'
  if (label.includes('拒绝') || label.includes('黑名单')) return 'exception'
  return ''
}

// 根据百分比动态决定活跃排行的进度条颜色
function getProgressColor(percent: number) {
  if (percent > 90) return '#ef4444' // 接近满员红色
  if (percent > 70) return '#f59e0b' // 较满黄色
  return 'var(--el-color-primary)'
}

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

function memberPercent(group: any) {
  if (!group.max_members) return 100
  return Math.min(100, Math.round((group.current_members / group.max_members) * 100))
}

// 初始化并渲染 ECharts
function updateTrendChart() {
  if (!trendChartRef.value) return
  if (!trendChart) {
    trendChart = echarts.init(trendChartRef.value)
  }

  const rows = dashboard.value?.activity_trend ?? []
  const dates = rows.map((row: any) => row.date.slice(5))
  const messages = rows.map((row: any) => row.messages)
  const adminActions = rows.map((row: any) => row.admin_actions)
  const joinRequests = rows.map((row: any) => row.join_requests)
  const leaveEvents = rows.map((row: any) => row.leave_events)

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross', label: { backgroundColor: '#64748b' } },
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a' }
    },
    legend: {
      data: ['消息数量', '入群申请', '后台操作', '退群事件'],
      bottom: 0,
      icon: 'circle',
      textStyle: { color: '#64748b', fontSize: 12 }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '10%',
      top: '5%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      boundaryGap: true,
      data: dates,
      axisLine: { lineStyle: { color: '#cbd5e1' } },
      axisLabel: { color: '#64748b' }
    },
    yAxis: {
      type: 'value',
      axisLine: { show: false },
      axisLabel: { color: '#64748b' },
      splitLine: { lineStyle: { color: '#f1f5f9' } }
    },
    series: [
      {
        name: '消息数量',
        type: 'bar',
        barMaxWidth: 14,
        data: messages,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#3b82f6' },
            { offset: 1, color: '#93c5fd' }
          ]),
          borderRadius: [4, 4, 0, 0]
        }
      },
      {
        name: '入群申请',
        type: 'bar',
        barMaxWidth: 14,
        data: joinRequests,
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: '#10b981' },
            { offset: 1, color: '#6ee7b7' }
          ]),
          borderRadius: [4, 4, 0, 0]
        }
      },
      {
        name: '后台操作',
        type: 'line',
        smooth: true,
        data: adminActions,
        lineStyle: { width: 3, color: '#8b5cf6' },
        itemStyle: { color: '#8b5cf6' }
      },
      {
        name: '退群事件',
        type: 'line',
        smooth: true,
        data: leaveEvents,
        lineStyle: { width: 3, color: '#f97316' },
        itemStyle: { color: '#f97316' }
      }
    ]
  }

  trendChart.setOption(option)
}

function updateResultChart() {
  if (!resultChartRef.value) return
  if (!resultChart) {
    resultChart = echarts.init(resultChartRef.value)
  }

  const rawData = joinBreakdown.value
  const data = rawData.map((item: any) => ({
    name: item.label,
    value: item.count
  }))

  const colorPalette = {
    '已通过': '#10b981',
    '已分流': '#f59e0b',
    '已拒绝': '#ef4444',
    '黑名单拒绝': '#64748b',
    '待处理': '#3b82f6',
    '未知': '#cbd5e1'
  }

  const option = {
    tooltip: {
      trigger: 'item',
      formatter: '{b}: {c} 次 ({d}%)',
      backgroundColor: 'rgba(255, 255, 255, 0.95)',
      borderColor: '#e2e8f0',
      borderWidth: 1,
      textStyle: { color: '#0f172a' }
    },
    legend: {
      orient: 'horizontal',
      bottom: 5,
      icon: 'circle',
      textStyle: { color: '#64748b', fontSize: 11 },
      formatter: (name: string) => {
        const item = data.find((d: any) => d.name === name)
        return item ? `${name} (${item.value}次)` : name
      }
    },
    series: [
      {
        name: '申请结果',
        type: 'pie',
        radius: ['45%', '70%'],
        center: ['50%', '42%'], // 向上稍微偏移，为底部的 legend 留出空间
        avoidLabelOverlap: true,
        itemStyle: {
          borderRadius: 8,
          borderColor: '#ffffff',
          borderWidth: 2
        },
        label: {
          show: false
        },
        labelLine: {
          show: false // 彻底隐藏多余的引导线线段
        },
        emphasis: {
          label: {
            show: false // 移除高亮时圆环中心的重叠文本，完全由 Tooltip 承载完整数据展示
          }
        },
        data: data,
        color: rawData.map((item: any) => (colorPalette as any)[item.label] || '#6366f1')
      }
    ]
  }

  resultChart.setOption(option)
}

function handleResize() {
  trendChart?.resize()
  resultChart?.resize()
}

watch(dashboard, () => {
  if (dashboard.value) {
    setTimeout(() => {
      updateTrendChart()
      updateResultChart()
    }, 50)
  }
})

let timerId: any = null

async function load() {
  const { data } = await api.get('/admin/dashboard')
  dashboard.value = data
}

onMounted(() => {
  window.addEventListener('resize', handleResize)
  load()
  // 每 15 秒自动刷新一次数据
  timerId = setInterval(load, 15000)
})

onUnmounted(() => {
  window.removeEventListener('resize', handleResize)
  trendChart?.dispose()
  resultChart?.dispose()
  if (timerId) {
    clearInterval(timerId)
  }
})
</script>

<style scoped>
.today-insights-box {
  margin-top: 14px;
  padding: 12px 14px;
  background: linear-gradient(180deg, #f8fafc 0%, #f1f5f9 100%);
  border: 1px solid rgba(226, 232, 240, 0.8);
  border-radius: 10px;
}
.insights-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  color: var(--md-primary);
}
.insights-icon {
  font-size: 14px;
}
.insights-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.5px;
  text-transform: uppercase;
}
.insights-content-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px 12px;
}
.insight-card {
  display: flex;
  flex-direction: column;
  gap: 2px;
  background: #ffffff;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid rgba(226, 232, 240, 0.5);
}
.insight-card-label {
  font-size: 10.5px;
  color: var(--geeker-text-secondary);
  font-weight: 500;
}
.insight-card-value {
  font-size: 13px;
  color: var(--geeker-text);
  font-weight: 700;
}
.text-ellipsis {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
