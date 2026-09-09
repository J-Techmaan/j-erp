<script setup lang="ts">
import type { Document } from '../types'
import StatusBadge from './StatusBadge.vue'
defineProps<{ documents: Document[]; empty?: string; actions?: boolean }>()
defineEmits<{ cancel: [document: Document]; recreate: [document: Document] }>()
</script>
<template>
  <div v-if="!documents.length" class="empty-state"><span>▤</span><h3>{{ empty || '표시할 문서가 없습니다.' }}</h3><p>새 문서를 작성하거나 다른 목록을 확인해 보세요.</p></div>
  <div v-else class="table-wrap"><table><thead><tr><th>문서 제목</th><th>작성자</th><th>상태</th><th>작성일</th><th v-if="actions">작업</th></tr></thead><tbody>
    <tr v-for="doc in documents" :key="doc.id"><td><RouterLink :to="`/documents/${doc.id}`" class="document-link">{{ doc.title }}</RouterLink><small class="document-number">{{ doc.document_number }}</small></td><td>{{ doc.author.display_name }}</td><td><StatusBadge :status="doc.status" /></td><td class="muted nowrap">{{ new Date(doc.created_at).toLocaleDateString('ko-KR') }}</td><td v-if="actions" class="table-actions"><button v-if="doc.status === 'IN_PROGRESS'" class="quiet" @click="$emit('cancel', doc)">상신취소</button><button v-else-if="doc.status === 'REJECTED' || doc.status === 'CANCELLED'" class="quiet" @click="$emit('recreate', doc)">재작성</button></td></tr>
  </tbody></table></div>
</template>
