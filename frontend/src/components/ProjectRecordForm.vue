<script setup lang="ts">
import { fieldSpec, projectLabel, type FieldValue, type Option, type RecordSchema } from '../types/projects'
const props = defineProps<{ schema: RecordSchema; modelValue: Record<string, FieldValue>; options: Record<string, Option[]>; busy: boolean }>()
const emit = defineEmits<{ 'update:modelValue': [Record<string, FieldValue>]; save: [] }>()
function update(key: string, value: FieldValue) { emit('update:modelValue', { ...props.modelValue, [key]: value }) }
function select(event: Event, key: string, multiple: boolean) {
  const target = event.target as HTMLSelectElement
  update(key, multiple ? Array.from(target.selectedOptions).map(o => Number(o.value)) : target.value ? Number(target.value) : null)
}
</script>
<template>
  <form class="project-form" @submit.prevent="emit('save')">
    <label v-for="(field, key) in schema.properties" :key="key" :class="{ 'full-width': (field.maxLength || 0) > 2000 }">
      <span>{{ field.title || key }} <span v-if="schema.required?.includes(key)" aria-label="필수">*</span></span>
      <input v-if="['project_code', 'wbs_code', 'task_code', 'milestone_code'].includes(key)" :aria-label="field.title || key" :value="modelValue[key] || '저장 시 자동 발급'" readonly />
      <select :aria-label="field.title || key" v-else-if="options[key]" :value="modelValue[key]" :multiple="fieldSpec(field).type === 'array'" :required="schema.required?.includes(key)" :disabled="busy" @change="select($event, key, fieldSpec(field).type === 'array')">
        <option v-if="fieldSpec(field).type !== 'array'" value="">선택 안 함</option><option v-for="option in options[key]" :key="option.id" :value="option.id">{{ option.name }}</option>
      </select>
      <select :aria-label="field.title || key" v-else-if="fieldSpec(field).enum" :value="modelValue[key]" :disabled="busy" @change="update(key, ($event.target as HTMLSelectElement).value)"><option v-for="value in fieldSpec(field).enum" :key="value" :value="value">{{ projectLabel(value) }}</option></select>
      <input :aria-label="field.title || key" v-else-if="fieldSpec(field).type === 'boolean'" type="checkbox" :checked="Boolean(modelValue[key])" :disabled="busy" @change="update(key, ($event.target as HTMLInputElement).checked)" />
      <textarea :aria-label="field.title || key" v-else-if="(field.maxLength || 0) > 2000" :value="String(modelValue[key] || '')" rows="3" :maxlength="field.maxLength" :required="schema.required?.includes(key)" :disabled="busy" @input="update(key, ($event.target as HTMLTextAreaElement).value)" />
      <input :aria-label="field.title || key" v-else :value="modelValue[key]" :type="fieldSpec(field).format === 'date' ? 'date' : ['integer', 'number'].includes(fieldSpec(field).type || '') ? 'number' : 'text'" :step="fieldSpec(field).type === 'integer' ? 1 : 'any'" :min="fieldSpec(field).minimum" :max="fieldSpec(field).maximum" :maxlength="field.maxLength" :required="schema.required?.includes(key)" :disabled="busy" @input="update(key, ($event.target as HTMLInputElement).value || (fieldSpec(field).format === 'date' ? null : ''))" />
    </label>
    <div class="full-width"><button type="submit" class="primary" :disabled="busy">{{ busy ? '저장 중…' : '저장' }}</button></div>
  </form>
</template>
