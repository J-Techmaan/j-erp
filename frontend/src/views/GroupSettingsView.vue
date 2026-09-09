<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { useAuthStore } from '../stores/auth'
import { api, errorMessage } from '../api/client'
import { useGroupStore } from '../stores/groups'
import type { Group } from '../types'
const store = useGroupStore(), group = ref<Group | null>(null), error = ref(''), notice = ref(''), busy = ref(false)
const auth = useAuthStore()
const inviteUrl = ref('')
function legacyCopy(text: string) {
  const input = document.createElement('textarea')
  input.value = text
  input.readOnly = true
  input.style.cssText = 'position:fixed;top:0;left:0;opacity:0;font-size:16px;'
  document.body.appendChild(input)
  try { input.focus(); input.select(); input.setSelectionRange(0, text.length); return document.execCommand('copy') }
  catch { return false } finally { input.remove() }
}
async function copyText(text: string) {
  // Run the fallback synchronously within the tap when Clipboard API is unavailable.
  if (!navigator.clipboard?.writeText) return legacyCopy(text)
  try { await navigator.clipboard.writeText(text); return true } catch { return legacyCopy(text) }
}
async function createInvite() { if (!group.value || busy.value) return; busy.value = true; error.value = ''; try { const { data } = await api.post(`/groups/${group.value.id}/invites`); inviteUrl.value = new URL(`/invite/${data.token}`, window.location.origin).href } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function copyInvite() { notice.value = await copyText(inviteUrl.value) ? '초대 링크를 복사했습니다.' : '초대 링크를 길게 눌러 선택한 뒤 복사해 주세요.' }
const mode = ref<'create' | 'join' | null>(null), name = ref(''), code = ref('')
const isManager = computed(() => isOwner.value || group.value?.members.some(m => m.user.id === auth.user?.id && m.is_admin))
const isOwner = computed(() => group.value?.my_role === 'OWNER')
async function load() { inviteUrl.value = ''; group.value = null; store.pending = []; error.value = ''; if (!store.currentId) return; try { group.value = await store.detail(store.currentId); if (isManager.value) await store.loadPending(store.currentId) } catch (e) { error.value = errorMessage(e) } }
async function copyCode() { if (!group.value) return; notice.value = await copyText(group.value.code) ? '그룹 코드를 복사했습니다.' : '아래 그룹 코드를 길게 눌러 복사해 주세요.' }
async function decide(id: number, action: 'approve' | 'reject') { busy.value = true; try { await store.decide(group.value!.id, id, action); await load() } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function remove(id: number) { if (!confirm('이 그룹원을 내보낼까요?')) return; await store.remove(group.value!.id, id); await load() }
async function deleteGroup() { if (!group.value || !confirm('그룹을 삭제할까요? 이 작업은 되돌릴 수 없습니다.')) return; try { await store.removeGroup(group.value.id); location.href = store.groups.length ? '/' : '/groups/start' } catch (e) { error.value = errorMessage(e) } }
async function submitGroup() { busy.value = true; error.value = ''; try { if (mode.value === 'create') { await store.create(name.value); mode.value = null; name.value = ''; await load() } else { notice.value = (await store.join(code.value)).detail; code.value = ''; mode.value = null } } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
async function setAdmin(id: number, value: boolean) { busy.value = true; error.value = ''; try { await api.put(`/groups/${group.value!.id}/members/${id}/admin`, { is_admin: value }); await load() } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
watch(() => store.currentId, load)
onMounted(async () => { await store.load(); await load() })
</script>
<template><div class="page-heading"><div><p class="eyebrow">그룹 관리</p><h1>{{ group?.name || '그룹' }}</h1><p class="muted">그룹 코드와 구성원을 관리하세요.</p></div><button v-if="group" @click="copyCode">코드 복사: {{ group.code }}</button></div><p v-if="error" class="error">{{ error }}</p><p v-if="notice" class="success">{{ notice }}</p><section class="panel group-section"><h2>내 그룹</h2><label>관리할 그룹<select :value="store.currentId" :disabled="busy" @change="store.select(Number(($event.target as HTMLSelectElement).value))"><option v-for="item in store.groups" :key="item.id" :value="item.id">{{ item.name }}</option></select></label><div class="button-row"><button :disabled="busy" @click="mode = 'create'">새 그룹 만들기</button><button :disabled="busy" @click="mode = 'join'">다른 그룹 가입하기</button></div><form v-if="mode" @submit.prevent="submitGroup"><label v-if="mode === 'create'">그룹 이름<input v-model="name" required maxlength="100" /></label><label v-else>그룹 코드<input v-model="code" required minlength="6" maxlength="12" /></label><div class="button-row"><button type="button" :disabled="busy" @click="mode = null">취소</button><button class="primary" :disabled="busy">{{ mode === 'create' ? '그룹 생성하기' : '가입 요청하기' }}</button></div></form></section><template v-if="group"><section v-if="isManager && store.pending.length" class="panel group-section"><h2>가입 승인 대기</h2><div v-for="request in store.pending" :key="request.id" class="member-row"><span class="avatar">{{ request.user.display_name[0] }}</span><div><strong>{{ request.user.display_name }}</strong><small>가입 요청</small></div><div class="button-row"><button :disabled="busy" @click="decide(request.id, 'reject')">거부</button><button class="primary" :disabled="busy" @click="decide(request.id, 'approve')">승인</button></div></div></section><section class="panel group-section"><h2>그룹 구성원</h2><div v-for="member in group.members" :key="member.id" class="member-row"><span class="avatar">{{ member.user.display_name[0] }}</span><div><strong>{{ member.user.display_name }}</strong><small>{{ member.role === 'OWNER' ? '그룹장' : member.is_admin ? '관리자' : '그룹원' }}</small></div><button v-if="isOwner && member.role !== 'OWNER'" :disabled="busy" @click="setAdmin(member.id, !member.is_admin)">{{ member.is_admin ? '관리자 해제' : '관리자 지정' }}</button><button v-if="isManager && (!member.is_admin || isOwner) && member.role !== 'OWNER'" class="danger" @click="remove(member.id)">내보내기</button></div></section><section class="panel group-section"><h2>초대하기</h2><div v-if="isManager"><button class="primary" :disabled="busy" @click="createInvite">초대 링크 생성</button><p class="muted">링크는 7일간 유효하며, 초대받은 사람은 승인 대기 없이 가입합니다.</p><label v-if="inviteUrl">초대 링크<input :value="inviteUrl" readonly @focus="($event.target as HTMLInputElement).select()" /><button @click="copyInvite">복사</button></label></div><p class="muted">그룹원에게 아래 코드를 전달하세요. 가입 요청은 그룹장 또는 관리자가 승인합니다. 관리자 지정과 그룹 삭제는 그룹장만 가능합니다.</p><div class="group-code">{{ group.code }}</div></section><button v-if="isOwner" class="danger delete-group" @click="deleteGroup">그룹 삭제</button></template></template>
