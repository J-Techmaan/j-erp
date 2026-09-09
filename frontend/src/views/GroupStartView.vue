<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { errorMessage } from '../api/client'
import { useGroupStore } from '../stores/groups'
const store = useGroupStore(), router = useRouter()
const mode = ref<'create' | 'join' | null>(null), name = ref(''), code = ref(''), busy = ref(false), error = ref(''), notice = ref('')
async function submit() { busy.value = true; error.value = ''; notice.value = ''; try { if (mode.value === 'create') { await store.create(name.value); await router.replace('/') } else { notice.value = (await store.join(code.value)).detail; code.value = '' } } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
</script>
<template><div class="group-start"><div class="page-heading"><div><p class="eyebrow">그룹 시작하기</p><h1>함께 일할 그룹을 선택해 주세요.</h1><p class="muted">그룹 안에서 결재를 주고받고 일정을 공유할 수 있습니다.</p></div></div><p v-if="error" class="error">{{ error }}</p><p v-if="notice" class="success">{{ notice }}</p><div v-if="!mode" class="group-choice"><button class="panel choice-card" @click="mode = 'create'"><span>＋</span><strong>그룹 생성하기</strong><small>새 그룹을 만들고 그룹장이 됩니다.</small></button><button class="panel choice-card" @click="mode = 'join'"><span>→</span><strong>그룹 들어가기</strong><small>그룹 코드를 입력해 가입을 요청합니다.</small></button></div><form v-else class="panel group-form" @submit.prevent="submit"><button type="button" class="quiet" @click="mode = null">← 이전</button><h2>{{ mode === 'create' ? '새 그룹 만들기' : '그룹 가입 요청' }}</h2><label v-if="mode === 'create'">그룹 이름<input v-model="name" required maxlength="100" /></label><label v-else>그룹 코드<input v-model="code" required minlength="6" maxlength="12" autocomplete="off" /></label><button class="primary" :disabled="busy">{{ busy ? '처리 중…' : mode === 'create' ? '그룹 생성하기' : '가입 요청하기' }}</button></form></div></template>
