<script setup lang="ts">
import AppShell from '@/components/AppShell.vue'
import ConnectionNotice from '@/components/ConnectionNotice.vue'
</script>

<template>
  <ConnectionNotice />
  <AppShell>
    <router-view />
  </AppShell>
</template>
