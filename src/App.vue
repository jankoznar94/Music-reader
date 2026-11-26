<template>
  <router-view />
  <!-- Hlášení nové verze je NAD routami: musí se ukázat i v knihovně, i nad
       otevřenou skladbou v prohlížeči. Nic neblokuje, jen se ptá. -->
  <UpdatePrompt />
</template>

<script setup>
import UpdatePrompt from './components/UpdatePrompt.vue';
</script>
