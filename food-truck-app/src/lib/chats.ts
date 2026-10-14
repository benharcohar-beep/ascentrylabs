import type { ChatMsg } from './ask'

// Chats live on the device (localStorage), newest first. One is "current" and reopens when you come back to the tab.
export type Chat = { id: string; title: string; created: number; updated: number; msgs: ChatMsg[] }
const KEY = 'eventini-chats', CUR = 'eventini-chat-current'

function read(): Chat[] { try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') } catch { return [] } }
function write(all: Chat[]) { try { localStorage.setItem(KEY, JSON.stringify(all.slice(0, 50))) } catch { /* private mode */ } }

export function listChats(): Chat[] { return read().sort((a, b) => b.updated - a.updated) }
export function getChat(id: string): Chat | undefined { return read().find((c) => c.id === id) }
export function currentId(): string | null { try { return localStorage.getItem(CUR) } catch { return null } }
export function setCurrent(id: string | null) { try { id ? localStorage.setItem(CUR, id) : localStorage.removeItem(CUR) } catch { /* ignore */ } }

export function saveChat(id: string, msgs: ChatMsg[]): Chat {
  const all = read()
  const now = Date.now()
  const first = msgs.find((m) => m.role === 'user')?.content ?? 'New chat'
  const title = first.length > 48 ? first.slice(0, 46).trimEnd() + '…' : first
  const i = all.findIndex((c) => c.id === id)
  const chat: Chat = i >= 0 ? { ...all[i], title, updated: now, msgs } : { id, title, created: now, updated: now, msgs }
  if (i >= 0) all[i] = chat; else all.unshift(chat)
  write(all)
  return chat
}
export function deleteChat(id: string) { write(read().filter((c) => c.id !== id)); if (currentId() === id) setCurrent(null) }
export function newId(): string { return `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}` }

export function whenLabel(ts: number): string {
  const d = new Date(ts), now = new Date()
  const sameDay = d.toDateString() === now.toDateString()
  if (sameDay) return d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' })
  const y = new Date(now); y.setDate(now.getDate() - 1)
  if (d.toDateString() === y.toDateString()) return 'Yesterday'
  return d.toLocaleDateString('en-US', { day: 'numeric', month: 'short' })
}
