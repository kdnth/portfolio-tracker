<script setup lang="ts">
defineProps<{
  title: string
  subtitle: string
}>()
</script>

<template>
  <div class="flex min-h-dvh items-center justify-center px-4 py-10">
    <div class="w-full max-w-md">
      <div class="mb-8 text-center">
        <p class="text-sm font-semibold tracking-[0.18em] text-accent uppercase">
          Portfolio Tracker
        </p>
        <h1 class="mt-3 text-3xl font-bold tracking-tight text-ink">{{ title }}</h1>
        <p class="mt-2 text-sm text-ink-muted">{{ subtitle }}</p>
      </div>

      <section class="rounded-2xl border border-border bg-surface p-6 shadow-sm sm:p-8">
        <slot />
      </section>

      <p v-if="$slots.footer" class="mt-6 text-center text-sm text-ink-muted">
        <slot name="footer" />
      </p>
    </div>
  </div>
</template>
