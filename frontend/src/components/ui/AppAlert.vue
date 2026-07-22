<script setup lang="ts">
withDefaults(
  defineProps<{
    variant?: 'error' | 'success' | 'info'
    title?: string
  }>(),
  {
    variant: 'error',
    title: undefined,
  },
)
</script>

<template>
  <div
    class="rounded-lg border px-3.5 py-3 text-sm"
    :class="{
      'border-danger-border bg-danger-soft text-danger': variant === 'error',
      'border-accent/30 bg-accent-soft text-accent-hover': variant === 'success',
      'border-border bg-canvas text-ink': variant === 'info',
    }"
    :role="variant === 'error' ? 'alert' : 'status'"
  >
    <p v-if="title" class="font-semibold">{{ title }}</p>
    <p :class="title ? 'mt-0.5' : ''">
      <slot />
    </p>
  </div>
</template>
