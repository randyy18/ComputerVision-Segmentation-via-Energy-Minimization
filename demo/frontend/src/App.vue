<script setup lang="ts">
import { RouterLink, RouterView } from 'vue-router'
</script>

<template>
  <header class="nav-bar">
    <RouterLink to="/" class="nav-logo">GRABCUT // CHALLENGE</RouterLink>
    <nav class="nav-links">
      <RouterLink to="/">Play</RouterLink>
      <RouterLink to="/leaderboard">Leaderboard</RouterLink>
    </nav>
  </header>
  <RouterView />
</template>
