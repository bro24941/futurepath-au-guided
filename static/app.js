"use strict";

const $ = id => document.getElementById(id);
const labels = {
  digital_literacy: "Digital literacy", networking: "Networking", linux: "Linux",
  security_basics: "Security basics", python: "Python", incident_response: "Incident response",
  risk_management: "Risk management", postgraduate_coursework: "Postgraduate coursework",
  security_operations: "Security operations", network_security: "Network security", governance: "Governance"
};
const showLabel = value => labels[value] ?? String(value).replaceAll("_", " ");
const skillNames = ["digital_literacy", "networking", "linux", "security_basics", "python", "incident_response", "risk_management"];
const fields = [
  ["age", "Age of the fictitious adult", "number", 18, 120],
  ["citizen", "Australian citizen", "bool"],
  ["year12", "Completed Year 12 or equivalent", "bool"],
  ["it_certificate", "Certificate III or higher in IT", "bool"],
  ["it_experience", "Equivalent IT industry experience", "bool"],
  ["network_os", "Can use networks and the Linux or Windows command line", "bool"],
  ["stem_enrolled", "Studying a STEM degree at an Australian university", "bool"],
  ["study_level", "Study level", ["undergraduate", "postgraduate_coursework", "other"]],
  ["semesters_completed", "Semesters completed when applying", "number", 0, 30],
  ["months_remaining", "Months of study left when the program starts", "number", 0, 120],
  ["credit_average", "Has and expects to maintain a credit average", "bool"],
  ["security_assessment", "Willing to undergo a security assessment", "bool"],
  ["institution", "Institution", ["ANU", "Monash", "Adelaide", "QUT", "other"]],
  ["commencing", "Starting a new course this intake", "bool"],
  ["domestic", "Domestic student", "bool"],
  ["atar", "Fictitious ATAR", "number", 0, 99.95],
  ["commonwealth_supported", "Commonwealth supported place", "bool"],
  ["state", "State or territory", ["NSW", "VIC", "QLD", "TAS", "SA", "WA", "ACT", "NT"]],
  ["digital_literacy", "Comfortable using computers", "bool"]
];
const sourceLabels = {
  verified_against_source: "Checked against provider",
  partially_verified: "Partly checked", unverified: "Source details unconfirmed",
  source_unavailable: "Source unavailable when checked"
};
const criterionLabels = { met: "Meets recorded requirement", not_met: "Doesn’t meet recorded requirement", cannot_tell: "Needs a check" };
const eligibilityLabels = { met: "Meets the recorded criteria", not_met: "Doesn’t meet all recorded criteria", cannot_tell: "Cannot confirm eligibility" };
const deadlineLabels = { open: "Deadline ahead", closing_soon: "Closing soon", rolling: "Rolling applications", closed: "Closed", unknown: "Deadline unclear" };
const statusLabels = { ok: "Done", uncertain: "Needs a check", no_match: "No match", fallback: "Used rules instead" };
const availabilityLabels = { open: "Provider lists applications", closed: "Closed", on_hold: "On hold", unknown: "Intake unconfirmed" };
const aussieDate = new Intl.DateTimeFormat("en-AU", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
const isDate = value => typeof value === "string" && /^\d{4}-\d{2}-\d{2}$/.test(value);
const displayDate = value => isDate(value) ? aussieDate.format(new Date(value)) : value;

// Keep the result and its editable copy in this tab. Reloading the page clears both.
let result = null;
let steps = [];
let decision = "Ready for your review";
let rejected = false;
let editing = false;
let changed = false;
let controller = null;

function element(tag, text, className) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function option(value, text) {
  const node = element("option", text);
  node.value = value;
  return node;
}

// Blank fields stay unknown. An explicit No is sent to the eligibility checks.
for (const [id, title, type, min, max] of fields) {
  const label = element("label", title);
  label.htmlFor = "p-" + id;
  const input = element(type === "number" ? "input" : "select");
  input.id = label.htmlFor;
  if (type === "number") {
    input.type = "number";
    input.min = min;
    input.max = max;
    input.step = id === "atar" ? ".01" : "1";
  } else {
    input.append(option("", "Not sure or not provided"));
    if (type === "bool") input.append(option("true", "Yes"), option("false", "No"));
    else for (const value of type) input.append(option(value, showLabel(value)));
  }
  const box = element("div");
  box.append(label, input);
  $("profile-fields").append(box);
}

for (const skill of skillNames) {
  const label = element("label", undefined, "check");
  const input = element("input");
  input.type = "checkbox";
  input.id = "skill-" + skill;
  input.onchange = () => { if (input.checked) $("skills-known").checked = true; };
  label.append(input, document.createTextNode(showLabel(skill)));
  $("skill-options").append(label);
}

async function checkService() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) throw new Error();
    const info = await response.json();
    $("service-status").textContent = info.llm_mode === "off" ? "Running with rules only." :
      info.api_key_configured ? "Gemini is set up. Check the agent details to see what ran." : "Running with rules only. No Gemini key is set.";
  } catch {
    $("service-status").textContent = "The local service is unavailable. Open Launch_Website.cmd and try again.";
  }
}

// Opening a folded section lets the browser focus an invalid field inside it.
$("profile-form").addEventListener("invalid", event => {
  for (let parent = event.target.parentElement; parent; parent = parent.parentElement) {
    if (parent.tagName === "DETAILS") parent.open = true;
  }
}, true);

function showResults(visible) {
  $("goal-view").hidden = visible;
  $("results").hidden = !visible;
  $("back-to-plan").hidden = result === null;
  $("error").textContent = "";
  $(visible ? "results-title" : "goal").focus();
}

function finishRequest() {
  controller = null;
  $("generate").disabled = false;
  $("profile-form").removeAttribute("aria-busy");
  $("progress").textContent = "";
}

$("change-goal").onclick = () => showResults(false);
$("back-to-plan").onclick = () => {
  controller?.abort();
  finishRequest();
  showResults(true);
};
$("clear").onclick = () => {
  // Abort first so a delayed response cannot restore information after clearing.
  controller?.abort();
  finishRequest();
  result = null;
  steps = [];
  decision = "Ready for your review";
  editing = changed = rejected = false;
  $("profile-form").reset();
  $("goal").setCustomValidity("");
  for (const id of ["profile-details", "requirements-details", "plan-details", "reject-details", "trace-details"]) $(id).open = false;
  for (const id of ["cards", "trace", "timeline", "notices", "goal-context", "skill-summary", "next-title", "next-detail", "as-of", "plan-summary", "dependency-warning", "decision", "calendar-help"]) $(id).replaceChildren();
  $("reject-reason").value = "";
  $("reject-reason").setCustomValidity("");
  showResults(false);
};

function loadExample(scholarship) {
  // Examples fill the form but still need the tester’s own consent.
  for (const [id] of fields) $("p-" + id).value = "";
  $("identity").value = "prefer_not_to_say";
  for (const skill of skillNames) $("skill-" + skill).checked = !scholarship && skill === "digital_literacy";
  $("skills-known").checked = !scholarship;
  $("goal").value = scholarship ? "Explore cybersecurity scholarships" : "Explore a cybersecurity course";
  $("goal").setCustomValidity("");
  $("goal").focus();
}
$("example-happy").onclick = () => loadExample(false);
$("example-uncertain").onclick = () => loadExample(true);
$("goal").oninput = () => $("goal").setCustomValidity("");

$("profile-form").addEventListener("submit", async event => {
  event.preventDefault();
  const goal = $("goal").value.trim();
  if (goal.length < 3) {
    $("goal").setCustomValidity("Enter a goal with at least three characters.");
    $("goal").reportValidity();
    return;
  }
  const request = new AbortController();
  controller = request;
  $("error").textContent = "";
  $("progress").textContent = "Looking up options and checking requirements…";
  $("generate").disabled = true;
  $("profile-form").setAttribute("aria-busy", "true");
  const profile = {
    indigenous_identity: $("identity").value,
    skills_known: $("skills-known").checked,
    skills: skillNames.filter(skill => $("skills-known").checked && $("skill-" + skill).checked)
  };
  for (const [id, , type] of fields) {
    const value = $("p-" + id).value;
    if (value !== "") profile[id] = type === "number" ? Number(value) : type === "bool" ? value === "true" : value;
  }
  try {
    // The browser talks only to the local API. The API controls what can go to Gemini.
    const response = await fetch("/api/pathway", {
      method: "POST", headers: { "Content-Type": "application/json" }, signal: request.signal,
      body: JSON.stringify({ goal, profile, adult_tester: $("adult").checked,
        fictitious_profile: $("fiction").checked, privacy_consent: $("privacy").checked })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || "We couldn’t check this goal. Try again.");
    if (controller !== request) return;
    result = data;
    steps = structuredClone(data.plan.steps);
    editing = changed = rejected = false;
    setDecision();
    for (const id of ["plan-details", "reject-details", "trace-details"]) $(id).open = false;
    $("reject-reason").value = "";
    $("reject-reason").setCustomValidity("");
    renderResults();
    showResults(true);
  } catch (error) {
    if (controller === request && error.name !== "AbortError") {
      $("error").textContent = error instanceof TypeError ? "We couldn’t reach the local service. Open Launch_Website.cmd and try again." : error instanceof SyntaxError ? "The service returned an unexpected response. Try again." : error.message;
    }
  } finally {
    if (controller === request) finishRequest();
  }
});

function badge(text, uncertain = false) {
  return element("span", text, uncertain ? "badge uncertain" : "badge");
}

function opportunityCard(record, eligibility, date) {
  // Keep published dates, intake availability and the eligibility decision separate.
  const card = element("article", undefined, "card");
  const tags = element("div", undefined, "badges");
  tags.append(badge(sourceLabels[record.verification_status], record.verification_status !== "verified_against_source"));
  tags.append(badge(deadlineLabels[date.status], date.stale_source || ["unknown", "closed", "closing_soon"].includes(date.status)));
  if (date.stale_source) tags.append(badge("Source needs rechecking", true));
  card.append(element("p", `${record.provider} · ${showLabel(record.category)}`, "meta"), element("h3", record.title), tags,
    element("p", record.description), element("p", record.location, "meta"), element("p", eligibilityLabels[eligibility.status]));
  if (isDate(date.deadline)) {
    const remaining = date.days_remaining === 0 ? " · Today" : date.days_remaining > 0 ? ` · ${date.days_remaining} days left` : "";
    card.append(element("p", `Recorded deadline: ${displayDate(date.deadline)}${remaining}`, "meta"));
  }
  if (record.study_commencement) card.append(element("p", `Study start: ${displayDate(record.study_commencement)}`, "meta"));
  card.append(element("p", `Source checked ${displayDate(record.source_checked_date)}. ${record.evidence_note}`, "meta"));
  const source = element("a", "Open provider page ↗");
  source.href = record.source_url;
  source.target = "_blank";
  source.rel = "noopener noreferrer";
  source.setAttribute("aria-label", `Open provider page for ${record.title} (opens in a new tab)`);
  card.append(source);

  const details = element("details");
  const list = element("ul", undefined, "criteria");
  details.append(element("summary", "See requirements and evidence"));
  for (const criterion of eligibility.criteria) {
    const item = element("li");
    item.append(element("strong", criterion.label), badge(criterionLabels[criterion.status], criterion.status !== "met"), element("small", criterion.evidence_note));
    list.append(item);
  }
  if (list.childElementCount) details.append(list);
  details.append(element("p", `Availability: ${availabilityLabels[record.availability]}.`));
  if (record.notes) details.append(element("p", record.notes, "hint"));
  for (const warning of eligibility.uncertainties) details.append(element("p", warning, "hint"));
  card.append(details);
  return card;
}

function renderResults() {
  const { goal, skills, opportunities, eligibility, deadlines, plan, trace, notices } = result;
  $("goal-context").textContent = goal.track === "general" ? "Cybersecurity pathway" : showLabel(goal.track);
  $("skill-summary").textContent = !goal.in_scope ? "Explore an Australian cybersecurity course, program or career goal." :
    skills.unknown ? "Add the skills you know to get more specific learning suggestions." :
    skills.gaps.length ? `Skills to work on: ${skills.gaps.map(showLabel).join(", ")}.` : "Your selections cover the skills on this shortlist.";
  $("notices").replaceChildren(...notices.map(notice => element("p", notice, "notice")));
  $("as-of").textContent = `Deadlines as at ${displayDate(deadlines.as_of_date)}. Closing soon means within 14 days.`;
  $("cards").replaceChildren();
  for (const record of opportunities) {
    const matchesId = item => item.opportunity_id === record.id;
    $("cards").append(opportunityCard(record, eligibility.find(matchesId), deadlines.items.find(matchesId)));
  }
  if (!opportunities.length) $("cards").append(element("p", "Try a different cybersecurity goal or one of the examples."));
  $("trace").replaceChildren(...trace.map(entry => {
    const item = element("article");
    const method = entry.model ? `Gemini (${entry.model})` : "Rules";
    item.append(element("h3", entry.agent), element("p", entry.task), element("p", entry.result), element("p", entry.source, "meta"),
      element("p", `${method} · ${statusLabels[entry.status]} · ${entry.duration_ms} ms`, "meta"));
    return item;
  }));
  $("plan-summary").textContent = plan.summary;
  $("plan-body").hidden = !plan.steps.length;
  renderSteps();
}

function setDecision(text = "Ready for your review") {
  decision = text;
  $("decision").textContent = decision;
}

function markEdited() {
  changed = true;
  rejected = false;
  $("restore").hidden = false;
  $("reject-reason").value = "";
  $("reject-reason").setCustomValidity("");
  setDecision("Changes ready for your review");
}

// A step must follow every prerequisite, including after a user edit.
function dependencyProblems() {
  const seen = new Set();
  const titles = new Map(result.plan.steps.map(step => [step.id, step.title]));
  const issues = [];
  for (const step of steps) {
    const missing = step.depends_on.filter(id => !seen.has(id));
    if (missing.length) issues.push(`“${step.title}” needs “${titles.get(missing[0])}” earlier in the plan.`);
    seen.add(step.id);
  }
  return issues;
}

function renderSteps(focusId) {
  $("timeline").replaceChildren();
  const titles = new Map(result.plan.steps.map(step => [step.id, step.title]));
  steps.forEach((step, index) => {
    const item = element("li");
    item.id = "step-" + step.id;
    item.tabIndex = -1;
    item.append(element("h3", step.title), element("p", step.detail));
    if (step.depends_on.length) item.append(element("p", "After: " + step.depends_on.map(id => titles.get(id)).join("; "), "meta"));
    if (step.deadline) item.append(element("p", `Recorded deadline: ${displayDate(step.deadline)}`, "meta"));
    const noteDisplay = element("p", step.note ? `Your note: ${step.note}` : "", "meta note-display");
    noteDisplay.classList.toggle("editing", editing);
    item.append(noteDisplay);
    if (editing) {
      const tools = element("div", undefined, "edit-controls");
      const actions = element("div", undefined, "actions");
      for (const [text, action, disabled] of [
        ["Move up", () => moveStep(index, -1), index === 0],
        ["Move down", () => moveStep(index, 1), index === steps.length - 1],
        ["Remove", () => {
          steps.splice(index, 1);
          markEdited();
          renderSteps(steps[Math.min(index, steps.length - 1)]?.id);
          if (!steps.length) $("restore").focus();
        }, false]
      ]) {
        const button = element("button", text, "secondary");
        button.type = "button";
        button.disabled = disabled;
        button.setAttribute("aria-label", `${text}: ${step.title}`);
        button.onclick = action;
        actions.append(button);
      }
      const label = element("label", `Note for step ${index + 1}`);
      const note = element("textarea");
      note.id = label.htmlFor = "note-" + step.id;
      note.maxLength = 300;
      note.rows = 2;
      note.value = step.note || "";
      note.placeholder = "Add a reminder without personal details.";
      note.oninput = () => {
        step.note = note.value;
        noteDisplay.textContent = note.value ? `Your note: ${note.value}` : "";
        markEdited();
      };
      tools.append(actions, label, note);
      item.append(tools);
    }
    $("timeline").append(item);
  });
  const issues = dependencyProblems();
  $("dependency-warning").textContent = issues.length ? issues[0] + (issues.length > 1 ? ` ${issues.length - 1} more steps need attention.` : "") : "";
  $("restore").hidden = !changed;
  $("approve").disabled = issues.length > 0 || !steps.length;
  $("edit-plan").setAttribute("aria-pressed", String(editing));
  $("edit-plan").textContent = editing ? "Finish editing" : "Edit steps";
  const first = steps[0];
  $("next-step").hidden = !first;
  $("next-title").textContent = first?.title || "";
  $("next-detail").textContent = first?.id === "skills-review" && result.skills.gaps.length ?
    "Use the skills above to compare the options below and work out what to learn first." : first?.detail || "";
  const canExportDates = calendarDates().length > 0;
  $("calendar").disabled = !canExportDates;
  $("calendar-help").textContent = canExportDates ? "Only dated deadlines in this plan are included. Check them with the provider." : "There are no dated, current deadlines in this plan to download.";
  if (focusId) $("step-" + focusId)?.focus();
}

function moveStep(index, direction) {
  const [step] = steps.splice(index, 1);
  steps.splice(index + direction, 0, step);
  markEdited();
  renderSteps(step.id);
}

$("open-plan").onclick = () => {
  $("plan-details").open = true;
  $("plan-title").focus();
  $("plan-title").scrollIntoView();
};
$("edit-plan").onclick = () => { editing = !editing; renderSteps(); };
$("restore").onclick = () => {
  steps = structuredClone(result.plan.steps);
  changed = rejected = false;
  $("reject-reason").value = "";
  $("reject-reason").setCustomValidity("");
  setDecision("Suggested steps restored. Ready for your review.");
  renderSteps();
  $("edit-plan").focus();
};
$("approve").onclick = () => {
  if (!steps.length || dependencyProblems().length) return;
  editing = rejected = false;
  $("reject-reason").value = "";
  $("reject-reason").setCustomValidity("");
  $("reject-details").open = false;
  setDecision("Plan approved for this demo. You haven’t applied to a provider.");
  renderSteps();
};
$("reject").onclick = () => {
  const reason = $("reject-reason").value.trim();
  if (!reason) {
    $("reject-reason").setCustomValidity("Enter a short reason before rejecting the plan.");
    $("reject-reason").reportValidity();
    return;
  }
  rejected = true;
  setDecision("Plan rejected. " + reason);
};
$("reject-reason").oninput = () => {
  $("reject-reason").setCustomValidity("");
  if (rejected) {
    rejected = false;
    setDecision();
  }
};

function download(name, type, contents) {
  const url = URL.createObjectURL(new Blob([contents], { type }));
  const link = element("a");
  link.href = url;
  link.download = name;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// Downloads contain the reviewed steps and their sources, without the original profile.
$("export").onclick = () => {
  if (!result) return;
  download("futurepath-plan.json", "application/json", JSON.stringify({
    as_of_date: result.deadlines.as_of_date, decision, steps, dependency_warnings: dependencyProblems(),
    sources: result.opportunities, trace: result.trace,
    notice: "Fictitious adult demonstration. No provider application submitted."
  }, null, 2));
};
$("print").onclick = () => window.print();

function calendarDates() {
  return result.deadlines.items.filter(date => ["open", "closing_soon"].includes(date.status) &&
    !date.stale_source && isDate(date.deadline) && steps.some(step => step.opportunity_id === date.opportunity_id));
}

$("calendar").onclick = () => {
  const dates = calendarDates();
  if (!dates.length) return;
  const lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//FuturePath AU//Pathway demo//EN"];
  const stamp = new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  for (const date of dates) {
    lines.push("BEGIN:VEVENT", `UID:${date.opportunity_id}-${date.deadline}@futurepath.local`, `DTSTAMP:${stamp}`,
      `DTSTART;VALUE=DATE:${date.deadline.replaceAll("-", "")}`, `SUMMARY:Check provider deadline ${date.opportunity_id}`,
      "DESCRIPTION:Confirm the date with the original provider.", "END:VEVENT");
  }
  lines.push("END:VCALENDAR");
  download("futurepath-deadlines.ics", "text/calendar", lines.join("\r\n") + "\r\n");
};

checkService();
