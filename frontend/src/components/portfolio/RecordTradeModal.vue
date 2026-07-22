<script setup lang="ts">
import { reactive, ref, watch } from 'vue'

import AppAlert from '@/components/ui/AppAlert.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppInput from '@/components/ui/AppInput.vue'
import AppModal from '@/components/ui/AppModal.vue'
import AppSelect from '@/components/ui/AppSelect.vue'
import { usePortfolioStore } from '@/stores/portfolio'
import { getApiErrorMessage } from '@/utils/apiError'
import { dollarsToCents } from '@/utils/money'

const props = defineProps<{
  open: boolean
  portfolioId: number
}>()

const emit = defineEmits<{
  close: []
}>()

const portfolioStore = usePortfolioStore()

const tradeTypeOptions = [
  { label: 'Buy', value: 'buy' },
  { label: 'Sell', value: 'sell' },
]

const form = reactive({
  ticker: '',
  tradeType: 'buy',
  shares: '',
  priceDollars: '',
  executedAt: '',
})

const fieldErrors = reactive({
  ticker: '',
  shares: '',
  priceDollars: '',
  executedAt: '',
})

const formError = ref('')
const loading = ref(false)

function defaultExecutedAt() {
  const now = new Date()
  const offset = now.getTimezoneOffset()
  const local = new Date(now.getTime() - offset * 60_000)
  return local.toISOString().slice(0, 16)
}

function resetForm() {
  form.ticker = ''
  form.tradeType = 'buy'
  form.shares = ''
  form.priceDollars = ''
  form.executedAt = defaultExecutedAt()
  fieldErrors.ticker = ''
  fieldErrors.shares = ''
  fieldErrors.priceDollars = ''
  fieldErrors.executedAt = ''
  formError.value = ''
  loading.value = false
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      resetForm()
    }
  },
)

function validate() {
  const ticker = form.ticker.trim().toUpperCase()
  fieldErrors.ticker =
    ticker.length >= 1 && ticker.length <= 5 ? '' : 'Ticker must be 1–5 characters.'

  const shares = Number(form.shares)
  fieldErrors.shares = Number.isFinite(shares) && shares > 0 ? '' : 'Enter a share quantity greater than 0.'

  const cents = dollarsToCents(form.priceDollars)
  fieldErrors.priceDollars =
    Number.isFinite(cents) && cents > 0 ? '' : 'Enter a price greater than $0.'

  fieldErrors.executedAt = form.executedAt ? '' : 'Execution time is required.'

  return !fieldErrors.ticker && !fieldErrors.shares && !fieldErrors.priceDollars && !fieldErrors.executedAt
}

async function onSubmit() {
  formError.value = ''
  if (!validate()) return

  loading.value = true
  try {
    await portfolioStore.createTrade(props.portfolioId, {
      ticker: form.ticker.trim().toUpperCase(),
      trade_type: form.tradeType as 'buy' | 'sell',
      shares: Number(form.shares),
      price_per_share_cents: dollarsToCents(form.priceDollars),
      executed_at: new Date(form.executedAt).toISOString(),
    })
    emit('close')
  } catch (error) {
    formError.value = getApiErrorMessage(error, 'Unable to record trade.')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AppModal :open="open" title="Record trade" @close="emit('close')">
    <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
      <AppAlert v-if="formError">{{ formError }}</AppAlert>

      <AppInput
        v-model="form.ticker"
        label="Ticker"
        name="ticker"
        placeholder="AAPL"
        required
        :error="fieldErrors.ticker"
      />

      <AppSelect
        v-model="form.tradeType"
        label="Side"
        name="tradeType"
        :options="tradeTypeOptions"
        required
      />

      <AppInput
        v-model="form.shares"
        label="Shares"
        type="number"
        name="shares"
        placeholder="10"
        step="any"
        min="0"
        required
        :error="fieldErrors.shares"
      />

      <AppInput
        v-model="form.priceDollars"
        label="Price per share"
        type="number"
        name="price"
        placeholder="150.00"
        step="0.01"
        min="0"
        hint="Entered in dollars; stored as cents."
        required
        :error="fieldErrors.priceDollars"
      />

      <AppInput
        v-model="form.executedAt"
        label="Executed at"
        type="datetime-local"
        name="executedAt"
        required
        :error="fieldErrors.executedAt"
      />

      <div class="flex justify-end gap-2 pt-1">
        <AppButton type="button" variant="secondary" :disabled="loading" @click="emit('close')">
          Cancel
        </AppButton>
        <AppButton type="submit" :loading="loading">Save trade</AppButton>
      </div>
    </form>
  </AppModal>
</template>
