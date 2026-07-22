<script setup lang="ts">
import { ref, watch } from 'vue'

import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'
import { usePortfolioStore, type Portfolio } from '@/stores/portfolio'
import { getApiErrorMessage } from '@/utils/apiError'

const props = defineProps<{
  open: boolean
}>()

const emit = defineEmits<{
  close: []
  created: [portfolio: Portfolio]
}>()

const portfolioStore = usePortfolioStore()

const name = ref('')
const nameError = ref('')
const formError = ref('')
const loading = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      name.value = ''
      nameError.value = ''
      formError.value = ''
      loading.value = false
    }
  },
)

function validate() {
  const trimmed = name.value.trim()
  if (!trimmed) {
    nameError.value = 'Portfolio name is required.'
    return false
  }
  if (trimmed.length > 255) {
    nameError.value = 'Name must be 255 characters or fewer.'
    return false
  }
  nameError.value = ''
  return true
}

async function onSubmit() {
  formError.value = ''
  if (!validate()) return

  loading.value = true
  try {
    const portfolio = await portfolioStore.createPortfolio(name.value.trim())
    emit('created', portfolio)
    emit('close')
  } catch (error) {
    formError.value = getApiErrorMessage(error, 'Unable to create portfolio.')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AppModal :open="open" title="New portfolio" @close="emit('close')">
    <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
      <AppAlert v-if="formError">{{ formError }}</AppAlert>

      <AppInput
        v-model="name"
        label="Name"
        name="portfolioName"
        placeholder="Retirement, taxable, crypto…"
        required
        :error="nameError"
      />

      <div class="flex justify-end gap-2 pt-1">
        <AppButton type="button" variant="secondary" :disabled="loading" @click="emit('close')">
          Cancel
        </AppButton>
        <AppButton type="submit" :loading="loading">Create</AppButton>
      </div>
    </form>
  </AppModal>
</template>
