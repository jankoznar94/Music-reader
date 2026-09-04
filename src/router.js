import { createRouter, createWebHistory } from 'vue-router';
import Knihovna from './views/Knihovna.vue';
import Prohlizec from './views/Prohlizec.vue';

const routes = [
  { path: '/', name: 'Knihovna', component: Knihovna },
  { path: '/prohlizec/:id', name: 'Prohlizec', component: Prohlizec, props: true },
  { path: '/:catchAll(.*)', redirect: '/' },
];

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes,
});

export default router;
