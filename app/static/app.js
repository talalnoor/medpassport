"use strict";

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const STATUS_LABEL = {
  prohibited: "Not allowed",
  permit_required: "Permit needed",
  prescription_required: "With prescription",
  caution: "Check first",
  allowed: "Allowed",
  unverified: "Not verified",
};
const CASE_STATUS = {
  awaiting_traveler_review: "Waiting for your review",
  awaiting_doctor: "Waiting for doctor",
  doctor_approved: "Approved by doctor",
  changes_requested: "Doctor asked for changes",
  cancelled: "Cancelled",
};
let countries = [];
let current = null;
let pollTimer = null;

async function api(path, opts = {}) {
  const res = await fetch(path, { headers: opts.body instanceof FormData ? {} : { "Content-Type": "application/json" }, ...opts });
  const raw = await res.text();
  let data = {};
  try { data = JSON.parse(raw); } catch { data = {}; }
  if (!res.ok) {
    if (!data.detail && raw) data.detail = `Server error ${res.status}: ${raw.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ").trim().slice(0, 160)}`;
    let msg = data.detail;
    if (Array.isArray(msg)) msg = msg.map((d) => `${(d.loc || []).slice(1).join(" ")}: ${d.msg}`).join("; ");
    throw new Error(msg || `Request failed (${res.status})`);
  }
  return data;
}

/* ---------- status strip ---------- */
async function loadHealth() {
  try {
    const h = await api("/api/health");
    $("statusStrip").innerHTML =
      `<span class="pill">AI: ${esc(h.ai_provider === "none" ? "offline mode" : h.ai_model)}</span>` +
      `<span class="pill">${h.countries_verified} countries verified</span>` +
      `<span class="pill">Rules reviewed ${esc(h.rules_last_reviewed)}</span>` +
      `<span class="pill">Hosted on Alternate Clouds</span>`;
  } catch { $("statusStrip").innerHTML = `<span class="pill">Server unreachable</span>`; }
}

/* ---------- form rows ---------- */
function countryOptions(selected) {
  const opts = countries.map((c) => `<option value="${c.code}" ${c.code === selected ? "selected" : ""}>${esc(c.name)}</option>`).join("");
  return `<option value="">Choose a country</option>${opts}<option value="OTHER" ${selected === "OTHER" ? "selected" : ""}>Other (not verified)</option>`;
}

function addStop(stop = {}) {
  const idx = $("stops").children.length + 1;
  const row = document.createElement("div");
  row.className = "row stop";
  const isOther = stop.code && !countries.some((c) => c.code === stop.code);
  row.innerHTML = `
    <div><label>Stop ${idx}</label><select class="s-code">${countryOptions(isOther ? "OTHER" : stop.code)}</select></div>
    <div class="s-other-wrap ${isOther ? "" : "hidden"}"><label>Country name</label><input class="s-other" value="${esc(isOther ? stop.code : "")}"></div>
    <label class="check-inline"><input type="checkbox" class="s-transit" ${stop.transit ? "checked" : ""}> Transit only</label>
    <button type="button" class="btn icon" aria-label="Remove stop">Remove</button>`;
  row.querySelector(".s-code").addEventListener("change", (e) => row.querySelector(".s-other-wrap").classList.toggle("hidden", e.target.value !== "OTHER"));
  row.querySelector("button").addEventListener("click", () => row.remove());
  $("stops").appendChild(row);
}

function addMed(med = {}) {
  const row = document.createElement("div");
  row.className = "row med";
  row.innerHTML = `
    <div><label>Medicine name</label><input class="m-name" value="${esc(med.name)}" placeholder="e.g. Panadeine Forte"></div>
    <div><label>Dose</label><input class="m-dose" value="${esc(med.dose)}" placeholder="500 mg"></div>
    <div><label>Days</label><input class="m-days" type="number" min="1" max="365" value="${esc(med.days_supply ?? "")}"></div>
    <div><label>Active ingredient (optional)</label><input class="m-ing" value="${esc((med.ingredients_override || []).join(", "))}" placeholder="${esc(med.hint || "found automatically")}"></div>
    <button type="button" class="btn icon" aria-label="Remove medicine">Remove</button>`;
  row.querySelector("button").addEventListener("click", () => row.remove());
  $("meds").appendChild(row);
}

function fillForm(p) {
  $("tName").value = p.traveler.name || "";
  $("tDate").value = p.traveler.departure_date || "";
  $("tPassport").value = p.traveler.passport || "";
  $("stops").innerHTML = ""; $("meds").innerHTML = "";
  p.route.forEach(addStop);
  p.medicines.forEach(addMed);
}

function readForm() {
  const route = [...$("stops").children].map((r) => {
    const code = r.querySelector(".s-code").value;
    const other = r.querySelector(".s-other").value.trim();
    return code === "OTHER" ? { code: other, name: other, transit: r.querySelector(".s-transit").checked }
      : { code, transit: r.querySelector(".s-transit").checked };
  }).filter((s) => s.code);
  const medicines = [...$("meds").children].map((r) => ({
    name: r.querySelector(".m-name").value.trim(),
    dose: r.querySelector(".m-dose").value.trim(),
    days_supply: r.querySelector(".m-days").value ? Number(r.querySelector(".m-days").value) : null,
    ingredients_override: r.querySelector(".m-ing").value.split(",").map((s) => s.trim()).filter(Boolean),
  })).filter((m) => m.name);
  return {
    traveler: { name: $("tName").value.trim(), departure_date: $("tDate").value, passport: $("tPassport").value.trim(), email: "" },
    route, medicines,
  };
}

/* ---------- photo reading (human gate 1) ---------- */
async function readPhoto() {
  const file = $("photo").files[0];
  if (!file) { $("photoNote").innerHTML = `<div class="notice error">Choose a photo first.</div>`; return; }
  $("readPhoto").disabled = true; $("readPhoto").textContent = "Reading…";
  try {
    const fd = new FormData(); fd.append("file", file);
    const data = await api("/api/extract-medicines", { method: "POST", body: fd });
    if (!data.medicines.length) throw new Error("No medicine names could be read. Try a clearer photo or type them.");
    [...$("meds").children].forEach((r) => { if (!r.querySelector(".m-name").value.trim()) r.remove(); });
    data.medicines.forEach((m) => addMed({ name: m.name, dose: m.dose, hint: m.ingredients.length ? `AI read: ${m.ingredients.join(", ")}` : "" }));
    $("photoNote").innerHTML = `<div class="notice">Added ${data.medicines.length} medicine(s) read by AI. Check each name before you continue.</div>`;
  } catch (e) {
    $("photoNote").innerHTML = `<div class="notice error">${esc(e.message)}</div>`;
  } finally { $("readPhoto").disabled = false; $("readPhoto").textContent = "Read photo"; }
}

/* ---------- run the agent ---------- */
async function submitTrip(e) {
  e.preventDefault();
  const payload = readForm();
  const missing = [];
  if (!payload.traveler.name) missing.push("traveller name");
  if (!payload.traveler.departure_date) missing.push("departure date");
  if (!payload.route.length) missing.push("at least one country");
  if (!payload.medicines.length) missing.push("at least one medicine");
  if (missing.length) { $("formMsg").textContent = `Add ${missing.join(", ")}.`; return; }
  $("runBtn").disabled = true; $("formMsg").textContent = "Checking every stop…";
  try {
    const c = await api("/api/cases", { method: "POST", body: JSON.stringify(payload) });
    $("formMsg").textContent = "";
    $("formSection").classList.add("hidden");
    render(c, true);
    loadCases();
  } catch (err) { $("formMsg").textContent = err.message; }
  finally { $("runBtn").disabled = false; }
}

/* ---------- rendering ---------- */
function render(c, animate = false) {
  current = c;
  $("results").classList.remove("hidden");
  $("caseMeta").textContent = `Trip ${c.id} for ${c.traveler.name}`;
  $("rulesDate").textContent = c.rules_last_reviewed ? `Rules reviewed ${c.rules_last_reviewed}` : "";

  // trace
  $("trace").innerHTML = "";
  c.trace.forEach((t, i) => {
    const li = document.createElement("li");
    li.className = t.status;
    li.style.animationDelay = animate ? `${i * 120}ms` : "0ms";
    li.innerHTML = `<div><span class="tool">${esc(t.tool.replaceAll("_", " "))}</span><br><span class="small">${esc(t.detail)}</span></div><span class="ms">${t.ms ? t.ms + " ms" : ""}</span>`;
    $("trace").appendChild(li);
  });

  // risk + summary
  $("risk").innerHTML = `<div class="risk ${esc(c.risk.level)}"><strong>${esc(c.risk.headline)}</strong></div>`;
  $("summary").textContent = c.summary;

  // stamp matrix
  const stops = c.route;
  let html = `<thead><tr><th scope="col">Medicine</th>${stops.map((s) => `<th scope="col">${esc(s.name)}${s.transit ? '<span class="transit">transit</span>' : ""}</th>`).join("")}</tr></thead><tbody>`;
  c.medicines.forEach((m) => {
    const ing = m.ingredients.length ? m.ingredients.join(", ") : "ingredient unknown";
    html += `<tr><th scope="row">${esc(m.name)}<span class="ing ${m.ingredient_verified ? "" : "unverified-ing"}">${esc(ing)}${m.ingredient_verified ? "" : " (verify)"}</span></th>`;
    stops.forEach((s) => {
      const f = c.findings.find((x) => x.medicine === m.name && x.country_code === s.code);
      html += `<td>${f ? `<button type="button" class="stamp ${esc(f.status)}" data-m="${esc(m.name)}" data-c="${esc(s.code)}" style="animation-delay:${animate ? 900 + Math.random() * 400 : 0}ms">${esc(STATUS_LABEL[f.status])}</button>` : ""}</td>`;
    });
    html += "</tr>";
  });
  $("matrix").innerHTML = html + "</tbody>";
  $("matrix").querySelectorAll(".stamp").forEach((b) => b.addEventListener("click", () => showFinding(b.dataset.m, b.dataset.c)));
  const firstBad = c.findings.find((f) => f.status === "prohibited") || c.findings.find((f) => f.status === "permit_required");
  if (firstBad) showFinding(firstBad.medicine, firstBad.country_code); else $("findingDetail").classList.add("hidden");

  // plan
  $("plan").innerHTML = c.plan.map((p) => `<li class="${esc(p.kind)} ${p.overdue ? "overdue" : ""}"><div><div class="title">${esc(p.title)}</div><div class="small muted">${esc(p.detail)}</div></div><span class="due">${p.due ? (p.overdue ? "Overdue " : "By ") + esc(p.due) : ""}</span></li>`).join("");
  $("icsLink").href = `/api/cases/${c.id}/calendar.ics`;

  // letter + gate (older cases have no letter_needed field: treat them as needing a letter)
  const letterNeeded = c.letter_needed !== false;
  $("noLetter").classList.toggle("hidden", letterNeeded);
  $("letterBody").classList.toggle("hidden", !letterNeeded);
  $("cancelBtnNoLetter").classList.toggle("hidden", c.status === "cancelled" || c.status === "doctor_approved");
  $("letter").value = c.letter || "";
  $("printLink").href = `/api/cases/${c.id}/letter`;
  $("statusBadge").textContent = !letterNeeded && c.status === "awaiting_traveler_review"
    ? "No letter needed" : (CASE_STATUS[c.status] || c.status);
  $("statusBadge").className = `status-badge ${c.status}`;
  const editable = ["awaiting_traveler_review", "changes_requested"].includes(c.status);
  $("letter").readOnly = !editable;
  $("saveLetter").classList.toggle("hidden", !editable);
  $("gate").classList.toggle("hidden", !editable);
  $("confirm").checked = false; $("approveBtn").disabled = true;
  renderAfter(c);

  // audit
  $("audit").innerHTML = (c.audit || []).map((a) => `<li><span class="muted">${esc(new Date(a.ts).toLocaleString())}</span><strong>${esc(a.actor)}</strong><span>${esc(a.action)}${a.detail ? ` – <span class="muted">${esc(a.detail)}</span>` : ""}</span></li>`).join("");

  document.querySelectorAll(".case-list button").forEach((b) => b.setAttribute("aria-current", b.dataset.id === c.id ? "true" : "false"));
  clearInterval(pollTimer);
  if (c.status === "awaiting_doctor") pollTimer = setInterval(() => openCase(c.id, false), 5000);
}

function showFinding(med, code) {
  const f = current.findings.find((x) => x.medicine === med && x.country_code === code);
  if (!f) return;
  $("findingDetail").classList.remove("hidden");
  $("findingDetail").innerHTML = `<strong>${esc(f.medicine)} in ${esc(f.country)}${f.transit ? " (transit)" : ""}: ${esc(STATUS_LABEL[f.status])}</strong>
    <p style="margin:6px 0">${esc(f.details)}</p>
    ${f.deadline ? `<p class="small" style="margin:0 0 6px"><strong>${f.deadline_passed ? "Deadline passed:" : "Start paperwork by:"}</strong> ${esc(f.deadline)}</p>` : ""}
    ${f.source ? `<a class="small" href="${esc(f.source)}" target="_blank" rel="noopener">Source</a>` : '<span class="small muted">No verified source; contact the embassy.</span>'}`;
}

function renderAfter(c) {
  const box = $("afterApprove");
  if (c.status === "awaiting_doctor") {
    box.innerHTML = `<div class="notice">Waiting for your doctor. ${esc(c.notification || "")}
      <div class="linkbox"><input readonly value="${esc(c.doctor_link)}" aria-label="Doctor review link"><button class="btn ghost" type="button" id="copyLink">Copy link</button></div></div>`;
    $("copyLink").addEventListener("click", () => { navigator.clipboard.writeText(c.doctor_link); $("copyLink").textContent = "Copied"; });
  } else if (c.status === "doctor_approved") {
    const r = c.doctor_review;
    box.innerHTML = `<div class="notice good">Approved by ${esc(r.doctor_name)} (registration ${esc(r.registration_no)}). ${r.note ? esc(r.note) + " " : ""}Print the letter, then have it signed and stamped.</div>`;
  } else if (c.status === "changes_requested") {
    box.innerHTML = `<div class="notice error">Your doctor asked for changes: ${esc(c.doctor_review?.note || "no note")}. Edit the letter and send it again.</div>`;
  } else if (c.status === "cancelled") {
    box.innerHTML = `<div class="notice error">This trip was cancelled.</div>`;
  } else box.innerHTML = "";
}

/* ---------- actions ---------- */
async function saveLetter() {
  try { render(await api(`/api/cases/${current.id}/letter`, { method: "PUT", body: JSON.stringify({ letter: $("letter").value }) })); flash("Letter saved"); }
  catch (e) { alert(e.message); }
}

async function approve() {
  if (!$("confirm").checked) return;
  $("approveBtn").disabled = true;
  try {
    if ($("letter").value !== current.letter) await api(`/api/cases/${current.id}/letter`, { method: "PUT", body: JSON.stringify({ letter: $("letter").value }) });
    render(await api(`/api/cases/${current.id}/approve`, { method: "POST", body: JSON.stringify({ doctor_email: $("docEmail").value.trim(), confirm: true }) }));
    loadCases();
  } catch (e) { alert(e.message); $("approveBtn").disabled = false; }
}

async function cancelCase() {
  if (!confirm("Cancel this trip? The doctor link will stop working.")) return;
  try { render(await api(`/api/cases/${current.id}/cancel`, { method: "POST" })); loadCases(); } catch (e) { alert(e.message); }
}

function flash(text) { $("caseMeta").textContent = text; setTimeout(() => current && ($("caseMeta").textContent = `Trip ${current.id} for ${current.traveler.name}`), 1500); }

async function openCase(id, scroll = true) {
  try {
    const c = await api(`/api/cases/${id}`);
    if (current && current.id === id && current.status === c.status && !scroll) return;
    $("formSection").classList.add("hidden");
    render(c);
    if (scroll) $("results").scrollIntoView({ behavior: "smooth" });
  } catch (e) { alert(e.message); }
}

async function loadCases() {
  const { cases } = await api("/api/cases");
  $("caseList").innerHTML = cases.length ? cases.map((c) => `<li><button type="button" data-id="${esc(c.id)}" aria-current="${current && current.id === c.id}"><span class="who">${esc(c.traveler)}</span><span class="meta">${esc(c.route.join(" → "))}<br>${esc(CASE_STATUS[c.status] || c.status)}</span></button></li>`).join("")
    : `<li class="muted small">No trips yet. Check your first trip.</li>`;
  $("caseList").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => openCase(b.dataset.id)));
}

function newTrip() {
  clearInterval(pollTimer);
  current = null;
  $("results").classList.add("hidden");
  $("formSection").classList.remove("hidden");
  $("tripForm").reset(); $("stops").innerHTML = ""; $("meds").innerHTML = ""; $("photoNote").innerHTML = "";
  addStop(); addMed();
  loadCases();
  $("formSection").scrollIntoView({ behavior: "smooth" });
}

async function init() {
  try { countries = (await api("/api/countries")).countries; } catch { countries = []; }
  addStop(); addMed();
  $("addStop").addEventListener("click", () => addStop());
  $("addMed").addEventListener("click", () => addMed());
  $("demoBtn").addEventListener("click", async () => fillForm(await api("/api/demo")));
  $("readPhoto").addEventListener("click", readPhoto);
  $("tripForm").addEventListener("submit", submitTrip);
  $("saveLetter").addEventListener("click", saveLetter);
  $("confirm").addEventListener("change", (e) => ($("approveBtn").disabled = !e.target.checked));
  $("approveBtn").addEventListener("click", approve);
  $("cancelBtn").addEventListener("click", cancelCase);
  $("cancelBtnNoLetter").addEventListener("click", cancelCase);
  $("newTripBtn").addEventListener("click", newTrip);
  loadCases();
}
init();