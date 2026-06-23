const cities = ["Все города", "Москва", "Санкт-Петербург", "Казань", "Омск", "Красноярск", "Владивосток", "Самара", "Нижний Новгород", "Россия", "World"];

const state = {
  route: "world",
  search: "",
  city: "",
  from: "",
  to: ""
};

let content = [];

const sectionMeta = {
  world: {
    label: "Мировые новости",
    title: "Мировые новости о моде, искусстве и дизайне",
    description: "Ежедневная лента из международных источников про моду, искусство, дизайн, архитектуру, технологии и креативные индустрии.",
    heading: "Свежая мировая лента"
  },
  events: {
    label: "Локальные новости",
    title: "Локальные новости культуры и модной индустрии",
    description: "Российские новости, выставки, арт-среда, городские события, музеи, галереи и культурные проекты.",
    heading: "Новости и события в России"
  },
  calls: {
    label: "Конкурсы",
    title: "Конкурсы, открытые заявки и возможности",
    description: "Сначала российские конкурсы и заявки, затем международные открытые заявки, резиденции, гранты и премии.",
    heading: "Конкурсы и возможности"
  },
  scheduled: {
    label: "Подписка",
    title: "Подписка на сводку новостей",
    description: "Выберите периодичность, чтобы получать новости о моде, искусстве и дизайне прямо на почту.",
    heading: "Настройка рассылки"
  }
};

const els = {
  nav: document.querySelector(".nav"),
  navToggle: document.querySelector(".nav-toggle"),
  label: document.getElementById("section-label"),
  title: document.getElementById("page-title"),
  description: document.getElementById("page-description"),
  toolbar: document.getElementById("content-toolbar"),
  contentSection: document.getElementById("content-section"),
  scheduledSection: document.getElementById("scheduled-section"),
  heading: document.getElementById("content-heading"),
  resultMeta: document.getElementById("result-meta"),
  grid: document.getElementById("cards-grid"),
  search: document.getElementById("search-input"),
  city: document.getElementById("city-select"),
  cityField: document.getElementById("city-field"),
  from: document.getElementById("date-from"),
  to: document.getElementById("date-to"),
  resetDates: document.getElementById("reset-dates"),
  form: document.getElementById("subscription-form"),
  formMessage: document.getElementById("form-message"),
  weekdayWrap: document.getElementById("weekday-wrap")
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function formatDate(value) {
  if (!value) return "Дата уточняется";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "long",
    year: "numeric"
  }).format(new Date(`${value}T12:00:00`));
}

function dateInRange(item) {
  if (!state.from && !state.to) return true;
  const start = new Date(`${item.date}T00:00:00`).getTime();
  const end = new Date(`${item.endDate || item.date}T23:59:59`).getTime();
  const from = state.from ? new Date(`${state.from}T00:00:00`).getTime() : -Infinity;
  const to = state.to ? new Date(`${state.to}T23:59:59`).getTime() : Infinity;
  return end >= from && start <= to;
}

function matchesSearch(item) {
  if (!state.search) return true;
  const haystack = [item.title, item.description, item.source, item.category, item.place, item.city]
    .join(" ")
    .toLowerCase();
  return haystack.includes(state.search.toLowerCase());
}

function matchesCity(item) {
  if (!state.city) return true;
  return item.city === state.city || item.place === state.city;
}

function getFilteredItems(route = state.route) {
  return content
    .filter((item) => item.section === route)
    .filter(matchesSearch)
    .filter(dateInRange)
    .filter((item) => (route === "world" ? true : matchesCity(item)))
    .sort((a, b) => new Date(b.date || 0) - new Date(a.date || 0));
}

function renderCard(item) {
  const date = item.endDate && item.endDate !== item.date
    ? `${formatDate(item.date)} - ${formatDate(item.endDate)}`
    : formatDate(item.date);

  const location = item.place && item.place !== "Online" && item.place !== "online" ? item.place : "Online";
  const badge = item.category ? `<span class="badge">${escapeHtml(item.category)}</span>` : "";

  return `
    <article class="card">
      <div class="card-top">
        <span class="source">${escapeHtml(item.source)}</span>
        ${badge}
      </div>
      <h3>${escapeHtml(item.title)}</h3>
      <p>${escapeHtml(item.description)}</p>
      <ul class="meta-list">
        <li><strong>Формат / Локация</strong>${escapeHtml(location)}</li>
        <li><strong>Дата</strong>${escapeHtml(date)}</li>
      </ul>
      <a class="card-action" href="${escapeHtml(item.url)}" target="_blank" rel="noopener noreferrer">Открыть источник</a>
    </article>
  `;
}

function renderGroup(title, meta, items) {
  return `
    <div class="group-title">
      <h3>${escapeHtml(title)}</h3>
      <span>${escapeHtml(meta)} · ${items.length}</span>
    </div>
    ${items.map(renderCard).join("")}
  `;
}

function renderContent() {
  const meta = sectionMeta[state.route];
  els.label.textContent = meta.label;
  els.title.textContent = meta.title;
  els.description.textContent = meta.description;
  els.heading.textContent = meta.heading;

  document.querySelectorAll(".nav a").forEach((link) => {
    link.classList.toggle("active", link.dataset.route === state.route);
  });

  const isScheduled = state.route === "scheduled";
  els.toolbar.hidden = isScheduled;
  els.contentSection.hidden = isScheduled;
  els.scheduledSection.hidden = !isScheduled;

  if (isScheduled) {
    cleanupSubscriptionPage();
    return;
  }

  const needsCity = state.route !== "world";
  els.cityField.hidden = !needsCity;
  els.toolbar.classList.toggle("has-city", needsCity);

  const filtered = getFilteredItems();
  els.resultMeta.textContent = "";

  if (!filtered.length) {
    els.grid.innerHTML = `<div class="empty-state">По текущим фильтрам ничего не найдено. Попробуйте расширить период, город или очистить поиск.</div>`;
    return;
  }

  if (state.route === "calls") {
    const russian = filtered.filter((item) => item.region === "russia");
    const global = filtered.filter((item) => item.region !== "russia");
    els.grid.innerHTML = [
      russian.length ? renderGroup("Конкурсы — Россия", "заявки из РФ", russian) : "",
      global.length ? renderGroup("Конкурсы — весь мир", "международные заявки", global) : ""
    ].join("");
    return;
  }

  els.grid.innerHTML = filtered.map(renderCard).join("");
}

function fillCities() {
  const localCities = ["Все города", "Москва", "Санкт-Петербург", "Казань", "Екатеринбург", "Пермь", "Тюмень", "Черноголовка", "Чувашия", "Россия"];
  els.city.innerHTML = localCities
    .map((city, index) => `<option value="${index === 0 ? "" : escapeHtml(city)}">${escapeHtml(city)}</option>`)
    .join("");
}

function setRoute(route) {
  state.route = sectionMeta[route] ? route : "world";
  document.documentElement.dataset.route = state.route;
  document.body.dataset.route = state.route;
  window.history.replaceState(null, "", `#${state.route}`);
  els.nav.classList.remove("open");
  els.navToggle.setAttribute("aria-expanded", "false");
  window.scrollTo(0, 0);
  renderContent();
}

function setQuickRange(range) {
  const now = new Date();
  const to = now.toISOString().slice(0, 10);
  const fromDate = new Date(now);

  if (range === "month") {
    fromDate.setDate(1);
  } else {
    fromDate.setDate(now.getDate() - Number(range));
  }

  state.from = fromDate.toISOString().slice(0, 10);
  state.to = to;
  els.from.value = state.from;
  els.to.value = state.to;
  renderContent();
}

function updateScheduleControls() {
  cleanupSubscriptionPage();
  const frequency = new FormData(els.form).get("frequency");
  els.weekdayWrap.hidden = frequency !== "weekly";
}

function cleanupSubscriptionPage() {
  document
    .querySelectorAll("#scheduled-section input[name='time'], #scheduled-section input[type='time']")
    .forEach((element) => {
      const wrapper = element.closest("label") || element;
      wrapper.remove();
    });

  const oldServerTitle = ["Готово", "к реальному", "серверу"].join(" ");
  document.querySelectorAll("#scheduled-section .subscription-copy article").forEach((article) => {
    if (article.textContent.includes(oldServerTitle)) article.remove();
  });

  document
    .querySelectorAll("#scheduled-section .search-field, #scheduled-section input[type='search'], #scheduled-section #search-input, #scheduled-section #city-field, #scheduled-section #city-select")
    .forEach((element) => {
      const wrapper = element.closest("label") || element;
      wrapper.remove();
    });
}

function getWeekdayLabel(value) {
  const labels = {
    monday: "понедельник",
    tuesday: "вторник",
    wednesday: "среду",
    thursday: "четверг",
    friday: "пятницу",
    saturday: "субботу",
    sunday: "воскресенье"
  };
  return labels[value] || "понедельник";
}

function getSectionLabels(values) {
  const labels = {
    world: "Мировые новости",
    events: "Локальные новости",
    calls: "Конкурсы"
  };
  return values.map((value) => labels[value]).filter(Boolean).join(", ") || "Все разделы";
}

function computeNextDigestLabel(payload) {
  if (payload.frequency === "weekly") {
    return `в ближайший ${getWeekdayLabel(payload.weekday)} в 09:00`;
  }
  return "завтра в 09:00";
}

function showSubscriptionSuccess(payload) {
  els.formMessage.className = "form-message success";
  els.formMessage.textContent = `Готово! Все успешно. Новая рассылка отправится ${computeNextDigestLabel(payload)}. В сводке: ${getSectionLabels(payload.sections)}.`;
}

function loadContent() {
  const files = [
    { path: "data/world-news.json", route: "world" },
    { path: "data/local-news.json", route: "events" },
    { path: "data/contests.json", route: "calls" }
  ];

  const allItems = [];
  let loaded = 0;

  files.forEach(({ path, route }) => {
    fetch(path)
      .then((response) => {
        if (!response.ok) throw new Error("Ошибка загрузки");
        return response.json();
      })
      .then((items) => {
        const sectionItems = Array.isArray(items) ? items.map((item) => ({ ...item, section: route })) : [];
        allItems.push(...sectionItems);
      })
      .catch(() => {})
      .finally(() => {
        loaded++;
        if (loaded === files.length) {
          content = allItems;
          renderContent();
        }
      });
  });
}

function submitSubscription(event) {
  event.preventDefault();
  const formData = new FormData(els.form);
  const payload = {
    email: formData.get("email"),
    frequency: formData.get("frequency"),
    weekday: formData.get("frequency") === "weekly" ? formData.get("weekday") : "",
    sections: formData.getAll("sections")
  };

  showSubscriptionSuccess(payload);
  updateScheduleControls();
}

function bindEvents() {
  document.querySelectorAll(".nav a").forEach((link) => {
    link.addEventListener("click", (event) => {
      event.preventDefault();
      setRoute(link.dataset.route);
    });
  });

  els.navToggle.addEventListener("click", () => {
    const open = !els.nav.classList.contains("open");
    els.nav.classList.toggle("open", open);
    els.navToggle.setAttribute("aria-expanded", String(open));
  });

  els.search.addEventListener("input", (event) => {
    state.search = event.target.value.trim();
    renderContent();
  });
  els.city.addEventListener("change", (event) => {
    state.city = event.target.value;
    renderContent();
  });
  els.from.addEventListener("change", (event) => {
    state.from = event.target.value;
    renderContent();
  });
  els.to.addEventListener("change", (event) => {
    state.to = event.target.value;
    renderContent();
  });
  els.resetDates.addEventListener("click", () => {
    state.from = "";
    state.to = "";
    els.from.value = "";
    els.to.value = "";
    renderContent();
  });
  document.querySelectorAll("[data-range]").forEach((button) => {
    button.addEventListener("click", () => setQuickRange(button.dataset.range));
  });
  els.form.addEventListener("change", updateScheduleControls);
  els.form.addEventListener("submit", submitSubscription);
  window.addEventListener("hashchange", () => {
    const route = window.location.hash.replace("#", "");
    if (route !== state.route) setRoute(route);
  });
}

fillCities();
bindEvents();
updateScheduleControls();
setRoute(window.location.hash.replace("#", "") || "world");
loadContent();
cleanupSubscriptionPage();
