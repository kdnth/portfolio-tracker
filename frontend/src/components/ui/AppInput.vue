<script setup lang="ts">
import { computed, useId } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue: string
    label: string
    type?: string
    name?: string
    autocomplete?: string
    placeholder?: string
    error?: string
    hint?: string
    required?: boolean
    disabled?: boolean
    step?: string
    min?: string
  }>(),
  {
    type: 'text',
    name: undefined,
    autocomplete: undefined,
    placeholder: undefined,
    error: undefined,
    hint: undefined,
    required: false,
    disabled: false,
    step: undefined,
    min: undefined,
  },
)

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const generatedId = useId()
const inputId = computed(() => props.name ?? generatedId)
const describedBy = computed(() => {
  if (props.error) return `${inputId.value}-error`
  if (props.hint) return `${inputId.value}-hint`
  return undefined
})
</script>

<template>
  <label class="flex flex-col gap-1.5" :for="inputId">
    <span class="text-sm font-medium text-ink">
      {{ label }}
      <span v-if="required" class="text-danger" aria-hidden="true">*</span>
    </span>

    <input
      :id="inputId"
      :name="name"
      :type="type"
      :value="modelValue"
      :autocomplete="autocomplete"
      :placeholder="placeholder"
      :required="required"
      :disabled="disabled"
      :step="step"
      :min="min"
      :aria-invalid="error ? true : undefined"
      :aria-describedby="describedBy"
      class="w-full rounded-lg border border-border bg-surface px-3 py-2.5 text-sm text-ink outline-none transition placeholder:text-ink-muted/70 focus:border-accent focus:ring-2 focus:ring-accent/20 disabled:cursor-not-allowed disabled:bg-canvas disabled:opacity-70"
      :class="error ? 'border-danger focus:border-danger focus:ring-danger/20' : ''"
      @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />

    <span v-if="error" :id="`${inputId}-error`" class="text-sm text-danger" role="alert">
      {{ error }}
    </span>
    <span v-else-if="hint" :id="`${inputId}-hint`" class="text-sm text-ink-muted">
      {{ hint }}
    </span>
  </label>
</template>
