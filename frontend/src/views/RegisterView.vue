<script setup lang="ts">
import { reactive, ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'

import AuthShell from '@/components/auth/AuthShell.vue'
import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import { useAuthStore } from '@/stores/auth'
import { getApiErrorMessage } from '@/utils/apiError'

const auth = useAuthStore()
const router = useRouter()

const form = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const fieldErrors = reactive({
  username: '',
  email: '',
  password: '',
  confirmPassword: '',
})

const formError = ref('')
const loading = ref(false)

function validate() {
  fieldErrors.username =
    form.username.trim().length >= 5 ? '' : 'Username must be at least 5 characters.'
  fieldErrors.email = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())
    ? ''
    : 'Enter a valid email address.'
  fieldErrors.password =
    form.password.length >= 8 ? '' : 'Password must be at least 8 characters.'
  fieldErrors.confirmPassword =
    form.confirmPassword === form.password ? '' : 'Passwords do not match.'

  return (
    !fieldErrors.username &&
    !fieldErrors.email &&
    !fieldErrors.password &&
    !fieldErrors.confirmPassword
  )
}

async function onSubmit() {
  formError.value = ''
  if (!validate()) return

  loading.value = true
  try {
    await auth.register(form.username.trim(), form.email.trim(), form.password)
    await router.push({ name: 'portfolios' })
  } catch (error) {
    formError.value = getApiErrorMessage(error, 'Unable to create your account.')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AuthShell
    title="Create your account"
    subtitle="Track portfolios with a clean ledger of holdings and trades."
  >
    <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
      <AppAlert v-if="formError">{{ formError }}</AppAlert>

      <AppInput
        v-model="form.username"
        label="Username"
        name="username"
        autocomplete="username"
        hint="At least 5 characters."
        required
        :error="fieldErrors.username"
      />

      <AppInput
        v-model="form.email"
        label="Email"
        type="email"
        name="email"
        autocomplete="email"
        required
        :error="fieldErrors.email"
      />

      <AppInput
        v-model="form.password"
        label="Password"
        type="password"
        name="password"
        autocomplete="new-password"
        hint="At least 8 characters."
        required
        :error="fieldErrors.password"
      />

      <AppInput
        v-model="form.confirmPassword"
        label="Confirm password"
        type="password"
        name="confirmPassword"
        autocomplete="new-password"
        required
        :error="fieldErrors.confirmPassword"
      />

      <AppButton type="submit" full-width :loading="loading">Create account</AppButton>
    </form>

    <template #footer>
      Already have an account?
      <RouterLink class="font-semibold text-accent hover:text-accent-hover" :to="{ name: 'login' }">
        Sign in
      </RouterLink>
    </template>
  </AuthShell>
</template>
