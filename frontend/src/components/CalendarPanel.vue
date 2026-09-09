<script setup lang="ts">
import { computed, nextTick, onMounted, ref } from 'vue'
import { useScheduleStore } from '../stores/schedules'
import { errorMessage } from '../api/client'
import type { Schedule } from '../types'

const store = useScheduleStore(), today = new Date()
const month = ref(new Date(today.getFullYear(), today.getMonth(), 1))
const error = ref(''), busy = ref(false), loading = ref(false), dialog = ref<HTMLDialogElement | null>(null)
const editId = ref<number>(), title = ref(''), description = ref(''), start = ref(''), end = ref(''), allDay = ref(false), formError = ref('')
const cells = computed(() => {
  const first = new Date(month.value.getFullYear(), month.value.getMonth(), 1)
  const startDay = new Date(first); startDay.setDate(1 - first.getDay())
  return Array.from({ length: 42 }, (_, i) => new Date(startDay.getFullYear(), startDay.getMonth(), startDay.getDate() + i))
})
function dateKey(date: Date) { return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}` }
function localInput(value: string) { const date = new Date(value); return `${dateKey(date)}T${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}` }
function events(day: Date) { const finish = new Date(day); finish.setDate(day.getDate() + 1); return store.items.filter(e => new Date(e.start_at) < finish && new Date(e.end_at) >= day) }
async function load() { loading.value = true; error.value = ''; try { const finish = new Date(cells.value[41]); finish.setDate(finish.getDate() + 1); await store.load(cells.value[0].toISOString(), finish.toISOString()) } catch (e) { error.value = errorMessage(e) } finally { loading.value = false } }
async function changeMonth(delta: number) { month.value = new Date(month.value.getFullYear(), month.value.getMonth() + delta, 1); await load() }
async function goToday() { month.value = new Date(today.getFullYear(), today.getMonth(), 1); await load() }
async function open(day: Date, event?: Schedule) {
  editId.value = event?.id; title.value = event?.title || ''; description.value = event?.description || ''; allDay.value = event?.all_day || false; formError.value = ''
  start.value = event ? localInput(event.start_at) : `${dateKey(day)}T09:00`
  end.value = event ? localInput(event.end_at) : `${dateKey(day)}T10:00`
  await nextTick(); dialog.value?.showModal()
}
function toggleAllDay() { if (allDay.value) { start.value = start.value.slice(0, 10) + 'T00:00'; end.value = end.value.slice(0, 10) + 'T23:59' } }
async function save() {
  busy.value = true; formError.value = ''
  try {
    await store.save({ title: title.value, description: description.value, start_at: new Date(start.value).toISOString(), end_at: new Date(end.value).toISOString(), all_day: allDay.value }, editId.value)
    dialog.value?.close(); await load()
  } catch (e) { formError.value = errorMessage(e) } finally { busy.value = false }
}
async function remove() {
  if (!editId.value || !window.confirm('이 일정을 삭제할까요?')) return
  busy.value = true; formError.value = ''
  try { await store.remove(editId.value); dialog.value?.close(); await load() } catch (e) { formError.value = errorMessage(e) } finally { busy.value = false }
}
onMounted(load)
</script>
<template><section class="panel calendar-panel">
  <div class="calendar-toolbar"><div><p class="eyebrow">MY CALENDAR</p><h2>{{ month.getFullYear() }}년 {{ month.getMonth() + 1 }}월</h2></div><div class="button-row"><button aria-label="이전 달" :disabled="loading" @click="changeMonth(-1)">‹</button><button :disabled="loading" @click="goToday">오늘</button><button aria-label="다음 달" :disabled="loading" @click="changeMonth(1)">›</button><button class="primary" @click="open(today)">＋ 일정</button></div></div>
  <p v-if="error" role="alert" class="error">{{ error }} <button @click="load">다시 시도</button></p><p v-if="loading" role="status" class="calendar-loading">일정을 불러오는 중입니다…</p>
  <div class="calendar-weekdays"><span v-for="day in ['일', '월', '화', '수', '목', '금', '토']" :key="day">{{ day }}</span></div>
  <div class="calendar-grid"><div v-for="day in cells" :key="dateKey(day)" class="calendar-cell" :class="{ outside: day.getMonth() !== month.getMonth(), today: dateKey(day) === dateKey(today), sunday: day.getDay() === 0 }">
    <button class="day-number" :aria-label="`${dateKey(day)} 일정 추가`" @click="open(day)">{{ day.getDate() }}</button>
    <button v-for="event in events(day)" :key="event.id" class="calendar-event" :title="event.title" @click="open(day, event)">{{ event.all_day ? '' : new Date(event.start_at).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', hour12: false }) + ' ' }}{{ event.title }}</button>
  </div></div><div class="calendar-footer"><span class="status-dot"></span> 그룹 일정 <span class="muted">그룹 구성원이 함께 보는 일정입니다.</span></div>
</section>
<dialog ref="dialog" aria-labelledby="schedule-title" @cancel="busy && $event.preventDefault()"><form @submit.prevent="save"><div class="panel-toolbar"><h2 id="schedule-title">{{ editId ? '일정 수정' : '새 일정' }}</h2><button type="button" class="quiet" :disabled="busy" aria-label="닫기" @click="dialog?.close()">✕</button></div><div class="dialog-content"><p v-if="formError" role="alert" class="error">{{ formError }}</p><label>일정 제목<input v-model="title" required maxlength="200" autofocus /></label><label class="check-label"><input v-model="allDay" type="checkbox" @change="toggleAllDay" /> 하루 종일</label><label>시작일<input v-model="start" required type="datetime-local" /></label><label>종료일<input v-model="end" required type="datetime-local" :min="start" /></label><label>메모<textarea v-model="description" rows="3" maxlength="10000"></textarea></label></div><div class="dialog-actions"><button v-if="editId" type="button" class="danger" :disabled="busy" @click="remove">일정 삭제</button><span class="spacer"></span><button type="button" :disabled="busy" @click="dialog?.close()">취소</button><button type="submit" class="primary" :disabled="busy">{{ busy ? '저장 중…' : '일정 저장' }}</button></div></form></dialog>
</template>
