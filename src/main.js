import { createApp } from 'vue';
import App from './App.vue';
import router from './router';
import './style.css';
import { resetLibraryState } from './libraryState';

// Při každém (re)startu appky vynulovat stav přehledu not.
// SPA přechod do PDF prohlížeče a zpět stav NEMAŽE (module žije po dobu běhu).
resetLibraryState();

createApp(App).use(router).mount('#app');
