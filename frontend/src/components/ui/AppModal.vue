<script setup lang="ts">
import { onMounted, onUnmounted, watch } from 'vue'

const props = defineProps<{
  open: boolean
  title: string
}>()

const emit = defineEmits<{
  close: []
}>()

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && props.open) {
    emit('close')
  }
}

watch(
  () => props.open,
  (isOpen) => {
    document.body.style.overflow = isOpen ? 'hidden' : ''
  },
)

onMounted(() => {
  window.addEventListener('keydown', onKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center"
      role="dialog"
      aria-modal="true"
      :aria-label="title"
    >
      <button
        type="button"
        class="absolute inset-0 bg-ink/40"
        aria-label="Close dialog"
        @click="emit('close')"
      />

      <div
        class="relative z-10 w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-lg"
      >
        <div class="mb-5 flex items-start justify-between gap-4">
          <h2 class="text-lg font-semibold tracking-tight text-ink">{{ title }}</h2>
          <button
            type="button"
            class="rounded-md px-2 py-1 text-sm text-ink-muted transition hover:bg-canvas hover:text-ink"
            @click="emit('close')"
          >
            Close
          </button>
        </div>

        <slot />
      </div>
    </div>
  </Teleport>
</template>
