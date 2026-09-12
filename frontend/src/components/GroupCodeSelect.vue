<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { api, errorMessage } from '../api/client'

const props = defineProps<{ modelValue: string; disabled?: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [value: string] }>()
const query = ref(''), options = ref<{ id: number; name: string; code: string }[]>([])
const loading = ref(false), error = ref('')
let timer: ReturnType<typeof setTimeout> | undefined
let request = 0
async function load(version: number) {
  try {
    const { data } = await api.get('/groups/search', { params: { q: query.value } })
    if (version === request) options.value = data
  } catch (e) {
    if (version === request) error.value = errorMessage(e)
  } finally {
    if (version === request) loading.value = false
  }
}
watch(query, () => {
  clearTimeout(timer)
  const version = ++request
  emit('update:modelValue', '')
  options.value = []
  error.value = ''
  loading.value = true
  timer = setTimeout(() => load(version), 250)
}, { immediate: true })
watch(() => props.modelValue, (value, previous) => {
  if (!value && previous) options.value = options.value.filter(item => item.code !== previous)
})
onBeforeUnmount(() => { clearTimeout(timer); request++ })
</script>

<template>
  <div>
    <label>그룹 검색<input v-model="query" type="search" maxlength="100" placeholder="그룹 이름 또는 코드로 검색" :disabled="disabled" @keydown.enter.prevent /></label>
    <label>그룹 선택<select :value="modelValue" required :disabled="disabled || loading" @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)">
      <option value="" disabled>{{ loading ? '검색 중…' : '가입할 그룹을 선택해 주세요' }}</option>
      <option v-for="item in options" :key="item.id" :value="item.code">{{ item.name }} · {{ item.code }}</option>
    </select></label>
    <p v-if="error" class="error" role="alert">{{ error }} <button type="button" :disabled="disabled || loading" @click="error = ''; loading = true; load(++request)">다시 시도</button></p>
    <p v-else-if="!loading && !options.length" class="muted" role="status">가입할 수 있는 그룹이 없습니다. 다른 검색어로 찾아보세요.</p>
    <p class="muted">최대 50개가 표시됩니다. 이미 가입했거나 승인 대기 중인 그룹은 제외됩니다.</p>
  </div>
</template>
