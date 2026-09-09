<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { errorMessage } from '../api/client'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore(), router = useRouter(), route = useRoute()
const signupMode = computed(() => route.path === '/signup')
const name = ref(''), email = ref(''), password = ref(''), passwordConfirm = ref('')
const rememberMe = ref(false), busy = ref(false), error = ref('')

watch(signupMode, () => {
  error.value = ''; password.value = ''; passwordConfirm.value = ''
})

async function submit() {
  error.value = ''
  if (signupMode.value && !name.value.trim()) { error.value = '이름을 입력해 주세요.'; return }
  if (!email.value.trim()) { error.value = '이메일을 입력해 주세요.'; return }
  if (!password.value) { error.value = '비밀번호를 입력해 주세요.'; return }
  if (signupMode.value && (password.value.length < 8 || password.value.length > 128)) {
    error.value = '비밀번호는 8자 이상 128자 이하로 입력해 주세요.'; return
  }
  if (signupMode.value && password.value !== passwordConfirm.value) {
    error.value = '비밀번호가 일치하지 않습니다.'; return
  }
  busy.value = true
  try {
    if (signupMode.value) await auth.signup(name.value, email.value, password.value, passwordConfirm.value)
    else await auth.login(email.value, password.value, rememberMe.value)
    password.value = ''; passwordConfirm.value = ''
    const target = route.query.redirect
    const safeTarget = typeof target === 'string' && target.startsWith('/') &&
      !target.startsWith('//') && !target.includes('\\') && !/^\/(login|signup)([/?#]|$)/.test(target)
    await router.replace(safeTarget ? target : '/')
  } catch (e) { error.value = errorMessage(e) }
  finally { busy.value = false }
}
</script>

<template>
  <main class="login-page">
    <section class="login-intro">
      <div class="brand"><span class="brand-mark">J</span> J-ERP</div>
      <div>
        <p class="eyebrow">우리의 업무 공간</p>
        <h1>함께하는 업무,<br />하나의 공간에서.</h1>
        <p>메모에서 시작하는 결재와<br />놓치지 않는 하루의 일정.</p>
        <div class="intro-flow"><span>기안</span><i>→</i><span>순차 결재</span><i>→</i><span>완결</span></div>
      </div>
      <small>전자결재 · 개인 일정</small>
    </section>
    <section class="login-panel">
      <div class="login-card">
        <p class="eyebrow">{{ signupMode ? '처음 오셨나요?' : '다시 만나 반갑습니다' }}</p>
        <h2>{{ signupMode ? '회원가입' : '로그인' }}</h2>
        <p class="muted">{{ signupMode ? '계정을 만들고 업무를 시작하세요.' : '이메일과 비밀번호로 로그인하세요.' }}</p>
        <p v-if="error || auth.restoreError" class="error" role="alert">{{ error || auth.restoreError }}</p>
        <form class="auth-form" novalidate @submit.prevent="submit">
          <fieldset :disabled="busy">
            <label v-if="signupMode">이름<input v-model="name" autocomplete="name" maxlength="100" required /></label>
            <label>이메일<input v-model="email" type="email" autocomplete="username" maxlength="254" required placeholder="name@example.com" /></label>
            <label>비밀번호<input v-model="password" type="password" :autocomplete="signupMode ? 'new-password' : 'current-password'" maxlength="128" required :aria-describedby="signupMode ? 'password-help' : undefined" /></label>
            <p v-if="signupMode" id="password-help" class="muted">비밀번호는 8자 이상 128자 이하로 입력해 주세요.</p>
            <label v-if="signupMode">비밀번호 확인<input v-model="passwordConfirm" type="password" autocomplete="new-password" maxlength="128" required /></label>
            <label v-else class="check-label"><input v-model="rememberMe" type="checkbox" /> 로그인 상태 유지</label>
            <button class="primary auth-submit" type="submit">{{ busy ? '처리 중…' : signupMode ? '회원가입' : '로그인' }}</button>
          </fieldset>
        </form>
        <p class="login-note">
          {{ signupMode ? '이미 계정이 있으신가요?' : '아직 계정이 없으신가요?' }}
          <RouterLink :to="{ path: signupMode ? '/login' : '/signup', query: route.query }" class="text-link">{{ signupMode ? '로그인' : '회원가입' }}</RouterLink>
        </p>
      </div>
    </section>
  </main>
</template>
