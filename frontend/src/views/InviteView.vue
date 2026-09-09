<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api, errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'
import { useGroupStore } from '../stores/groups'
const route = useRoute(), router = useRouter(), auth = useAuthStore(), groups = useGroupStore()
const invite = ref<{ group_name: string; inviter: string | null; member_count: number } | null>(null)
const error = ref(''), notice = ref(''), loading = ref(true), busy = ref(false), joinedId = ref<number | null>(null)
const endpoint = `/invites/${encodeURIComponent(String(route.params.token))}`
onMounted(async () => { try { invite.value = (await api.get(endpoint)).data } catch (e) { error.value = errorMessage(e) } finally { loading.value = false } })
async function accept() {
  if (busy.value) return
  busy.value = true; error.value = ''
  try { const { data } = await api.post(endpoint + '/accept'); joinedId.value = data.group_id; notice.value = data.detail; await groups.load() }
  catch (e) { error.value = errorMessage(e) } finally { busy.value = false }
}
async function openGroup() { if (joinedId.value) { groups.select(joinedId.value); await router.push('/') } }
</script>
<template><main class="invite-page"><section class="panel form-panel invite-card"><p class="eyebrow">J-ERP · 그룹 초대</p><p v-if="loading" role="status">초대를 확인하는 중입니다…</p><p v-if="error" class="error" role="alert">{{ error }}</p><template v-if="invite"><h1>{{ invite.group_name }} 그룹에 가입하시겠습니까?</h1><p class="muted">{{ invite.inviter ? `${invite.inviter}님의 초대` : '그룹 초대' }} · 그룹원 {{ invite.member_count }}명</p><p v-if="notice" class="success" role="status">{{ notice }}</p><button v-if="joinedId" class="primary" @click="openGroup">그룹으로 이동</button><div v-else-if="!auth.user" class="button-row"><RouterLink class="button primary" :to="{ path: '/login', query: { redirect: route.fullPath } }">로그인</RouterLink><RouterLink class="button" :to="{ path: '/signup', query: { redirect: route.fullPath } }">회원가입</RouterLink></div><button v-else class="primary" :disabled="busy" @click="accept">{{ busy ? '가입 중…' : '가입하기' }}</button><p class="muted">초대를 수락하면 바로 가입됩니다. 기존 그룹 소속은 유지됩니다.</p></template></section></main></template>
