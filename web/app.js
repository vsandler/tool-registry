// Shared layout and helpers for every page (DECISIONS.md #10 and #12).
//
// The screens only ask the back end and display what it says. There are no approval
// rules here: who may do what comes from the API (for example `my_action` on a tool,
// and `can_open_queue` on a persona). tests/test_web.py guards this.

const PERSONA_KEY = "tool-registry-persona";

const NAV = [
  { href: "./", name: "Catalog", page: "catalog" },
  { href: "submit.html", name: "Submit a tool", page: "submit" },
  // Shown only when the back end says this persona can open the queue.
  { href: "queue.html", name: "Review queue", page: "queue", onlyIfCanOpenQueue: true },
];

let personas = [];

// --- the chosen persona (remembered in this browser only) ---------------------------------

export function currentPersonaId() {
  try {
    return localStorage.getItem(PERSONA_KEY) || "";
  } catch {
    return ""; // private browsing or blocked storage: just ask again
  }
}

function savePersonaId(id) {
  try {
    localStorage.setItem(PERSONA_KEY, id);
  } catch {
    // Nothing to do: the choice lasts until the page is reloaded.
  }
}

export function currentPersona() {
  return personas.find((p) => p.id === currentPersonaId()) || null;
}

// --- talking to the back end ----------------------------------------------------------------

// Calls the API as the chosen persona. On a refusal it throws an Error whose message
// is the back end's own plain-language `detail`, and whose `field` (if any) says which
// form box the message belongs to.
export async function api(path, { method = "GET", body } = {}) {
  const headers = { Accept: "application/json" };
  const personaId = currentPersonaId();
  if (personaId) headers["X-Persona"] = personaId;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  let response;
  try {
    response = await fetch(path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new Error("Can't reach the server. Check it's running, then try again.");
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  if (!response.ok) {
    const error = new Error(messageFrom(data, response.status, personaId));
    error.status = response.status;
    error.field = data && data.field ? data.field : null;
    error.fields = data && Array.isArray(data.fields) ? data.fields : [];
    error.messages = data && data.messages && typeof data.messages === "object" ? data.messages : {};
    throw error;
  }
  return data;
}

function messageFrom(data, status, personaId) {
  if (!personaId && (status === 401 || status === 422)) {
    return "Pick a persona first, using the dropdown at the top of the page.";
  }
  if (data && typeof data.detail === "string") return data.detail;
  return `Something went wrong (the server answered ${status}). Please try again.`;
}

// --- building the page safely ----------------------------------------------------------------

// Creates an element. Text is always set as text, never as HTML, so nothing typed
// into a tool can turn into page code.
export function h(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "className") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key.startsWith("on") && typeof value === "function") {
      node.addEventListener(key.slice(2).toLowerCase(), value);
    } else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

// Shows a message in place of a section's content. Errors are announced to screen
// readers straight away ("alert"); other notes are read politely ("status").
export function showMessage(target, text, kind = "error") {
  const isError = kind === "error";
  target.replaceChildren(
    h("p", { className: `message ${kind}`, role: isError ? "alert" : "status" }, text),
  );
}

// Loads something from the API. If the back end refuses, its message is shown in
// `target` and null is returned, so a page never goes blank or shows a bare code.
export async function loadOrExplain(path, target) {
  try {
    return await api(path);
  } catch (err) {
    showMessage(target, err.message);
    return null;
  }
}

// Marks the form boxes the back end named in a refusal (`fields`) as invalid, and
// points each one at the message explaining it (`messageIdFor(name)` gives that
// message's id). Unnamed boxes are cleared. A box's own hint, if it has one, stays
// linked through `data-hint-id`. Returns the first named box, to move focus to.
export function markInvalid(boxes, fields, messageIdFor) {
  for (const [name, box] of Object.entries(boxes)) {
    const hint = box.dataset.hintId || "";
    if (fields.includes(name)) {
      box.setAttribute("aria-invalid", "true");
      box.setAttribute("aria-describedby", `${messageIdFor(name)} ${hint}`.trim());
    } else {
      box.removeAttribute("aria-invalid");
      if (hint) box.setAttribute("aria-describedby", hint);
      else box.removeAttribute("aria-describedby");
    }
  }
  return fields.map((name) => boxes[name]).find(Boolean) || null;
}

// Saves text the back end produced as a file in the person's downloads, under the
// file name the back end chose. Nothing is sent anywhere or kept in the browser.
export function saveTextFile(filename, text) {
  const url = URL.createObjectURL(new Blob([text], { type: "text/plain;charset=utf-8" }));
  const link = h("a", { href: url, hidden: true });
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

// Sends an approve or reject decision. Every approve/reject button must use this
// (tests/test_web.py checks no page posts a decision any other way).
// - Accepted: clears the messages and returns the updated tool.
// - Refused: shows the back end's plain message next to the buttons (`buttonsArea`),
//   or next to the comment box (`commentArea`) when the back end says the problem is
//   the comment (for example a rejection comment that's too short). Returns null.
export async function decideOrExplain(toolId, decision, { buttonsArea, commentArea } = {}) {
  for (const area of [buttonsArea, commentArea]) if (area) area.replaceChildren();
  try {
    return await api(`/tools/${encodeURIComponent(toolId)}/decisions`, {
      method: "POST",
      body: decision,
    });
  } catch (err) {
    const target = err.field === "comment" && commentArea ? commentArea : buttonsArea;
    if (target) showMessage(target, err.message);
    return null;
  }
}

// --- the shared layout: demo banner, persona dropdown, navigation ------------------------------

export async function renderLayout(activePage) {
  const root = document.getElementById("layout");
  const nav = h("nav", { "aria-label": "Main" });
  const picker = h("div", { className: "persona-picker" });

  root.replaceChildren(
    h(
      "p",
      { className: "demo-banner", role: "note" },
      "Demo: pick a persona, no real sign-in. All people, clients and data are made up.",
    ),
    h(
      "div",
      { className: "topbar" },
      h("a", { className: "brand", href: "./" }, "Tool Registry"),
      picker,
    ),
    nav,
  );

  try {
    personas = await api("/personas");
  } catch (err) {
    showMessage(picker, err.message);
    renderNav(nav, activePage);
    return;
  }

  const select = h(
    "select",
    { id: "persona", name: "persona" },
    h("option", { value: "" }, "Choose a persona…"),
    personas.map((p) => h("option", { value: p.id }, p.label)),
  );
  select.value = currentPersona() ? currentPersonaId() : "";
  select.addEventListener("change", () => {
    savePersonaId(select.value);
    renderNav(nav, activePage);
    window.dispatchEvent(new CustomEvent("personachange"));
  });

  picker.replaceChildren(h("label", { for: "persona" }, "Viewing as"), select);
  renderNav(nav, activePage);
}

function renderNav(nav, activePage) {
  const persona = currentPersona();
  const links = NAV.filter((item) => !item.onlyIfCanOpenQueue || (persona && persona.can_open_queue))
    .map((item) =>
      h(
        "a",
        { href: item.href, "aria-current": item.page === activePage ? "page" : null },
        item.name,
      ),
    );
  nav.replaceChildren(...links);
}

// Runs `load` now, and again whenever a different persona is picked.
export function onPersonaReady(load) {
  window.addEventListener("personachange", load);
  load();
}
