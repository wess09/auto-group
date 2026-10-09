<template>
  <div
    ref="element"
    style="height: 320px; width: 100%"
    role="img"
    :aria-label="kind === 'trend' ? '近七天群活动趋势' : '加群申请处理结果分布'"
  />
</template>
<script setup lang="ts">
import { onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useTheme } from 'vuetify'
import type { EChartsType } from 'echarts/core'
import type { Trend } from '../api/types'
const props = defineProps<{
  kind: 'trend' | 'breakdown'
  data: Trend[] | { result: string; count: number }[]
}>()
const element = ref<HTMLDivElement | null>(null),
  theme = useTheme()
let chart: EChartsType | undefined,
  observer: ResizeObserver | undefined,
  disposed = false
function update() {
  if (!chart || !element.value) return
  const colors = Object.fromEntries(
    Object.entries(theme.current.value.colors).map(([key, value]) => [key, String(value)]),
  )
  const base = {
    animation: false,
    color: [colors.primary, colors.secondary, colors.tertiary, colors.error],
    backgroundColor: 'transparent',
    textStyle: { color: colors['on-surface'], fontFamily: 'Roboto, Microsoft YaHei, sans-serif' },
    aria: { enabled: true },
    tooltip: { trigger: (props.kind === 'trend' ? 'axis' : 'item') as 'axis' | 'item' },
  }
  if (props.kind === 'trend') {
    const rows = props.data as Trend[]
    chart.setOption(
      {
        ...base,
        legend: { textStyle: { color: colors['on-surface'] }, bottom: 0 },
        grid: { left: 45, right: 20, top: 20, bottom: 70 },
        xAxis: {
          type: 'category',
          data: rows.map((row) => row.date.slice(5)),
          axisLabel: { color: colors['on-surface-variant'] },
        },
        yAxis: {
          type: 'value',
          splitLine: { lineStyle: { color: colors['outline-variant'] } },
          axisLabel: { color: colors['on-surface-variant'] },
        },
        series: (
          [
            ['消息', 'messages'],
            ['入群申请', 'join_requests'],
            ['退群事件', 'leave_events'],
            ['后台操作', 'admin_actions'],
          ] as const
        ).map(([name, key]) => ({
          name,
          type: key === 'messages' ? 'bar' : 'line',
          data: rows.map((row) => row[key]),
          smooth: false,
        })),
      },
      true,
    )
  } else {
    const rows = props.data as { result: string; count: number }[]
    const names: Record<string, string> = {
      approved: '已通过',
      rejected: '已拒绝',
      redirected: '已分流',
      level_rejected: '等级不足',
      level_unknown: '等级获取失败',
      pending: '待处理',
      ignored: '已忽略',
    }
    chart.setOption(
      {
        ...base,
        series: [
          {
            type: 'pie',
            radius: ['45%', '70%'],
            label: { color: colors['on-surface'] },
            data: rows.map((row) => ({ name: names[row.result] || row.result, value: row.count })),
          },
        ],
      },
      true,
    )
  }
}
onMounted(async () => {
  const { echarts } = await import('../charts/engine')
  if (disposed || !element.value) return
  chart = echarts.init(element.value)
  update()
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(element.value)
})
watch([() => props.data, () => theme.name.value], update, { deep: true })
onBeforeUnmount(() => {
  disposed = true
  observer?.disconnect()
  chart?.dispose()
})
</script>
