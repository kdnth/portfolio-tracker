<script setup lang="ts">
import { onMounted } from 'vue'
import { RouterLink, RouterView, useRouter } from 'vue-router'

import AppButton from '@/components/ui/AppButton.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()

onMounted(async () => {
  if (!auth.username) {
    try {
      await auth.fetchCurrentUser()
    } catch {
      // 401 interceptor handles session expiry
    }
  }
})

async function onLogout() {
  auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="min-h-dvh bg-canvas">
    <header class="border-b border-border bg-surface">
      <div class="mx-auto flex h-14 max-w-5xl items-center justify-between gap-4 px-4">
        <RouterLink
          :to="{ name: 'portfolios' }"
          class="text-sm font-semibold tracking-[0.14em] text-accent uppercase"
        >
          Portfolio Tracker
        </RouterLink>

        <div class="flex items-center gap-3">
          <span v-if="auth.username" class="hidden text-sm text-ink-muted sm:inline">
            {{ auth.username }}
          </span>
          <AppButton variant="ghost" @click="onLogout">Sign out</AppButton>
        </div>
      </div>
    </header>

    <main class="mx-auto max-w-5xl px-4 py-8">
      <RouterView />
    </main>
  </div>
</template>
