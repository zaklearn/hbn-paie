<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { errorMessage } from '@/shared/services/http'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()
const username = ref('')
const password = ref('')
const error = ref('')
const busy = ref(false)

async function submit() {
  error.value = ''
  busy.value = true
  try {
    await auth.login(username.value, password.value)
    router.push(typeof route.query.suite === 'string' ? route.query.suite : { name: 'dashboard' })
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-fond p-4">
    <form class="carte flex w-full max-w-sm flex-col gap-4 p-6" @submit.prevent="submit">
      <div class="flex items-center gap-2.5">
        <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-menu">HP</div>
        <h1 class="m-0 text-xl font-bold">HBN Paie — connexion</h1>
      </div>
      <label class="etiquette">Identifiant
        <input v-model="username" class="champ" autocomplete="username" required data-testid="login-username">
      </label>
      <label class="etiquette">Mot de passe
        <input v-model="password" type="password" class="champ" autocomplete="current-password" required data-testid="login-password">
      </label>
      <p v-if="error" role="alert" class="m-0 rounded-lg bg-[#FDE7E5] px-3 py-2 text-sm text-[#8E1B12]">{{ error }}</p>
      <button type="submit" class="btn-primaire" :disabled="busy" data-testid="login-submit">Se connecter</button>
    </form>
  </div>
</template>
