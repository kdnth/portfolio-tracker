<script setup lang="ts">
import { computed, useId } from 'vue'

export interface SelectOption {
  label: string
  value: string
}

const props = withDefaults(
  defineProps<{
    modelValue: string
    label: string
    options: SelectOption[]
    name?: string
    error?: string
    hint?: string
    required?: boolean
    disabled?: boolean
  }>(),
  {
    name: undefined,
    error: undefined,
    hint: undefined,
    required: false,
    disabled: false,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const generatedId = useId()
const selectId = computed(() => props.name ?? generatedId)
const describedBy = computed(() => {
  if (props.error) return `${selectId.value}-error`
  if (props.hint) return `${selectId.value}-hint`
  return undefined
})
</script>

<template>
  <label class="flex flex-col gap-1.5" :for="selectId">
    <span class="text-sm font-medium text-ink">
      {{ label }}
      <span v-if="required" class="text-danger" aria-hidden="true">*</span>
    </span>

    <select
      :id="selectId"
      :name="name"
      :value="modelValue"
      :required="required"
      :disabled="disabled"
      :aria-invalid="error ? true : undefined"
      :aria-describedby="describedBy"
      class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-ink outline-none transition focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:cursor-not-allowed disabled:bg-canvas disabled:opacity-70"
      :class="error ? 'border-danger focus:border-danger focus:ring-danger/20' : ''"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="option in options" :key="option.value" :value="option.value">
        {{ option.label }}
      </option>
    </select>

    <span v-if="error" :id="`${selectId}-error`" class="text-sm text-danger" role="alert">
      {{ error }}
    </span>
    <span v-else-if="hint" :id="`${selectId}-hint`" class="text-sm text-ink-muted">
      {{ hint }}
    </span>
  </label>
</template>
