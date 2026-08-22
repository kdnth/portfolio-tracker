<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import axios from 'axios'
import DOMPurify from 'dompurify'
import { marked } from 'marked'

import AppAlert from '@/components/ui/AppAlert.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { useDemoStore } from '@/stores/demo'
import { getApiErrorMessage } from '@/utils/apiError'

const props = defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()

const demoStore = useDemoStore()

const loading = ref(false)
const report = ref('')
const error = ref('')

// The report is LLM-generated markdown, not literal user input, but it's still untrusted
// as far as HTML goes -- sanitize before it ever reaches v-html.
const renderedReport = computed(() => DOMPurify.sanitize(marked.parse(report.value, { async: false }) as string))

async function runAnalysis() {
  loading.value = true
  error.value = ''
  report.value = ''
  try {
    report.value = await demoStore.analyzeDemoPortfolio()
  } catch (err) {
    if (axios.isAxiosError(err) && err.response?.status === 429) {
      demoStore.markQuotaExhausted()
    }
    error.value = getApiErrorMessage(err, 'Unable to run the demo analysis right now.')
  } finally {
    loading.value = false
  }
}

// Starts the analysis as soon as the modal opens -- one-shot, no separate "run" click.
watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) runAnalysis()
  },
)
</script>

<template>
  <AppModal :open="open" title="Demo portfolio analysis" size="lg" @close="emit('close')">
    <div class="flex flex-col gap-4">
      <p v-if="loading" class="flex items-center gap-2 py-6 text-sm text-ink-muted">
        <span
          class="size-4 shrink-0 animate-spin rounded-full border-2 border-current border-r-transparent"
          aria-hidden="true"
        />
        Analyzing the demo portfolio. This can take up to 30 seconds…
      </p>

      <AppAlert v-else-if="error">{{ error }}</AppAlert>

      <template v-else>
        <div class="prose prose-sm max-w-none text-ink" v-html="renderedReport" />
        <AppAlert variant="info">
          This is a real analysis from the same agent, run against a demo portfolio of
          fictional companies with synthetically generated price history. It is not financial advice.
        </AppAlert>
      </template>
    </div>
  </AppModal>
</template>
