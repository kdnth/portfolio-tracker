<script setup lang="ts">
import { RouterLink } from 'vue-router'

import logoUrl from '@/assets/logo.png'
import AppButton from '@/components/ui/AppButton.vue'

// Placeholder content only -- the full marketing copy + live analysis demo lands in a
// later task (see docs/BACKLOG.md, Sprint 6). This task is purely about freeing up `/`
// for a public route without changing any existing authenticated URL.
</script>

<template>
  <div class="flex min-h-dvh flex-col items-center justify-center gap-6 bg-canvas px-4 text-center">
    <img :src="logoUrl" alt="" width="48" height="48" class="size-12 rounded-lg" />
    <h1 class="text-3xl font-bold tracking-tight text-ink">Portfolio Tracker</h1>
    <p class="max-w-md text-sm text-ink-muted">
      Track real market performance for your holdings, and get an AI-generated analysis of
      your portfolio on request.
    </p>
    <div class="flex gap-3">
      <RouterLink :to="{ name: 'login' }">
        <AppButton variant="secondary">Log in</AppButton>
      </RouterLink>
      <RouterLink :to="{ name: 'register' }">
        <AppButton>Create an account</AppButton>
      </RouterLink>
    </div>
  </div>
</template>
