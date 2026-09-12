<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { errorMessage } from '../api/client'
import { useGroupStore } from '../stores/groups'
import GroupCodeSelect from '../components/GroupCodeSelect.vue'
const store = useGroupStore(), router = useRouter()
const mode = ref<'create' | 'join' | null>(null), name = ref(''), code = ref(''), busy = ref(false), error = ref(''), notice = ref('')
async function submit() { busy.value = true; error.value = ''; notice.value = ''; try { if (mode.value === 'create') { await store.create(name.value); await router.replace('/') } else { notice.value = (await store.join(code.value)).detail; code.value = '' } } catch (e) { error.value = errorMessage(e) } finally { busy.value = false } }
</script>
<template><div class="group-start"><div class="page-heading"><div><p class="eyebrow">그룹 시작하기</p><h1>함께 일할 그룹을 선택해 주세요.</h1><p class="muted">그룹 안에서 결재를 주고받고 일정을 공유할 수 있습니다.</p></div></div><p v-if="error" class="error">{{ error }}</p><p v-if="notice" class="success">{{ notice }}</p><div v-if="!mode" class="group-choice"><button class="panel choice-card" @click="mode = 'create'"><span>＋</span><strong>그룹 생성하기</strong><small>새 그룹을 만들고 그룹장이 됩니다.</small></button><button class="panel choice-card" @click="mode = 'join'"><span>→</span><strong>그룹 들어가기</strong><small>그룹을 검색하고 선택해 가입을 요청합니다.</small></button></div><form v-else class="panel group-form" @submit.prevent="submit"><button type="button" class="quiet" @click="mode = null">← 이전</button><h2>{{ mode === 'create' ? '새 그룹 만들기' : '그룹 가입 요청' }}</h2><label v-if="mode === 'create'">그룹 이름<input v-model="name" required maxlength="100" /></label><GroupCodeSelect v-else v-model="code" :disabled="busy" /><p v-if="mode === 'create'" class="muted">그룹 코드는 생성 시 영문 대문자와 숫자 8자리로 자동 발급됩니다.</p><button class="primary" :disabled="busy || (mode === 'join' && !code)">{{ busy ? '처리 중…' : mode === 'create' ? '그룹 생성하기' : '가입 요청하기' }}</button></form></div></template>
