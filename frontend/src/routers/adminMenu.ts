import type { Component } from 'vue'
import {
  Bell,
  ChatDotRound,
  CircleClose,
  Connection,
  DataAnalysis,
  DocumentChecked,
  Folder,
  Link,
  List,
  Setting,
  Star,
  User
} from '@element-plus/icons-vue'
import { adminBase, adminPath } from '../adminRoute'

export type AdminMenuItem = {
  path: string
  title: string
  icon: Component
  affix?: boolean
}

export const adminMenuItems: AdminMenuItem[] = [
  { path: adminBase, title: '仪表盘', icon: DataAnalysis, affix: true },
  { path: adminPath('groups'), title: '群配置', icon: User },
  { path: adminPath('rules'), title: '入群规则', icon: DocumentChecked },
  { path: adminPath('join-blacklist'), title: '加群黑名单', icon: CircleClose },
  { path: adminPath('message-moderation'), title: '消息审查', icon: ChatDotRound },
  { path: adminPath('notices'), title: '公告管理', icon: Bell },
  { path: adminPath('files'), title: '群文件', icon: Folder },
  { path: adminPath('essence'), title: '精华管理', icon: Star },
  { path: adminPath('dedupe'), title: '一键去重', icon: Connection },
  { path: adminPath('events'), title: '事件日志', icon: Setting },
  { path: '/join', title: '公开入口', icon: Link }
]

export function titleByPath(path: string) {
  return adminMenuItems.find((item) => item.path === path)?.title ?? 'Auto Group'
}
