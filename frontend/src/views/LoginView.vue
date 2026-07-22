<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import AuthShell from '@/components/auth/AuthShell.vue'
import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/apiError'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const form = reactive({
  identifier: '',
  password: '',
})

const fieldErrors = reactive({
  identifier: '',
  password: '',
})

const formError = ref('')
const loading = ref(false)

function validate() {
  fieldErrors.identifier = form.identifier.trim() ? '' : 'Email or username is required.'
  fieldErrors.password = form.password ? '' : 'Password is required.'
  return !fieldErrors.identifier && !fieldErrors.password
}

async function onSubmit() {
  formError.value = ''
  if (!validate()) return

  loading.value = true
  try {
    await auth.login(form.identifier.trim(), form.password)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : '/'
    await router.push(redirect)
  } catch (error) {
    formError.value = getApiErrorMessage(error, 'Unable to sign in. Check your credentials.')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell title="Welcome back" subtitle="Sign in to review holdings, trades, and performance.">
    <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
      <AppAlert v-if="formError">{{ formError }}</AppAlert>

      <AppInput
        v-model="form.identifier"
        label="Email or username"
        name="identifier"
        autocomplete="username"
        placeholder="you@example.com"
        required
        :error="fieldErrors.identifier"
      />

      <AppInput
        v-model="form.password"
        label="Password"
        type="password"
        name="password"
        autocomplete="current-password"
        required
        :error="fieldErrors.password"
      />

      <AppButton type="submit" full-width :loading="loading">Sign in</AppButton>
    </form>

    <template #footer>
      New here?
      <RouterLink class="font-semibold text-accent hover:text-accent-hover" :to="{ name: 'register' }">
        Create an account
      </RouterLink>
    </template>
  </AuthShell>
</template>
