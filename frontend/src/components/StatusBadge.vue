<script setup lang="ts">
import { documentLabels, type DocumentStatus } from '../types'
defineProps<{ status: DocumentStatus }>()
</script>
<template><span class="badge" :class="status">{{ documentLabels[status] }}</span></template>
