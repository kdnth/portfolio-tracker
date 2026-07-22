<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/apiError'

const auth = useAuthStore()
const router = useRouter()
const loadError = ref('')

onMounted(async () => {
  if (!auth.username) {
    try {
      await auth.fetchCurrentUser()
    } catch (error) {
      loadError.value = getApiErrorMessage(error, 'Could not load your profile.')
    }
  }
})

async function onLogout() {
  auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <div class="mx-auto flex min-h-dvh w-full max-w-3xl flex-col justify-center px-4 py-10">
    <p class="text-sm font-semibold tracking-[0.18em] text-accent uppercase">Portfolio Tracker</p>
    <h1 class="mt-3 text-3xl font-bold tracking-tight text-ink">You're signed in</h1>
    <p class="mt-2 text-ink-muted">
      Welcome{{ auth.username ? `, ${auth.username}` : '' }}.
    </p>

    <AppAlert v-if="loadError" class="mt-6">{{ loadError }}</AppAlert>

    <div class="mt-8">
      <AppButton variant="secondary" @click="onLogout">Sign out</AppButton>
    </div>
  </div>
</template>
