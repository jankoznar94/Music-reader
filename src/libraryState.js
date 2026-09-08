// src/libraryState.js — stav přehledu not, který přežije přechod do PDF prohlížeče
// a zpět v rámci jednoho běhu appky, ale po reloadu / novém otevření se vynuluje.
// (Záměrně NEPOUŽÍVÁME localStorage — výchozí stav má být po každém startu appky.)
const state = {
  tab: 'songs',
  folderFilter: null,
  search: '',
  sortBy: 'name',
  scrollTop: 0,       // pozice scrollu seznamu (v px)
  scrollReady: false, // zda bylo scroll uloženo pro daný "zážitek"
  selectedIds: [],    // označené skladby (hromadný výběr) — pole ID
  openAuthors: [],    // rozbalené záložky autorů — pole klíčů
};

export function saveLibraryState(partial) {
  Object.assign(state, partial);
}

export function resetLibraryState() {
  state.tab = 'songs';
  state.folderFilter = null;
  state.search = '';
  state.sortBy = 'name';
  state.scrollTop = 0;
  state.scrollReady = false;
  state.selectedIds = [];
  state.openAuthors = [];
}

export function getLibraryState() {
  return state;
}
