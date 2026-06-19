/* =========================================================================
   D404 实验室值日看板 · 管理后台脚本
   按 body[data-page] 分发到对应页面初始化。
   ========================================================================= */
"use strict";

var $ = function (id) { return document.getElementById(id); };
var WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}

async function api(path, opts) {
  opts = opts || {};
  var res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" } }, opts));
  if (!res.ok) throw new Error(path + " -> HTTP " + res.status);
  return res.json();
}

function toast(msg, type) {
  var area = $("toast");
  if (!area) { alert(msg); return; }
  var el = document.createElement("div");
  el.className = "toast " + (type === "err" ? "err" : "ok");
  el.textContent = msg;
  area.appendChild(el);
  setTimeout(function () { el.classList.add("out"); setTimeout(function () { el.remove(); }, 300); }, 2400);
}

function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(function () { toast("已复制，可粘贴到微信群"); }, function () { fb(text); });
  } else { fb(text); }
}
function fb(text) {
  var ta = document.createElement("textarea"); ta.value = text; document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); toast("已复制"); } catch (e) { toast("复制失败", "err"); }
  document.body.removeChild(ta);
}

/* =========================== 基础设置（首页） =========================== */
var _cfg = null, _duty = null;

async function initHome() {
  _cfg = await api("/api/config");
  _duty = await api("/api/duty");
  $("labName").value = _cfg.lab_name || "";
  $("chatName").value = _cfg.chat_name || "";
  $("skipHolidays").checked = !!_cfg.skip_holidays;
  $("skipCustom").checked = !!_cfg.skip_custom;
  $("baseMonday").value = _duty.base_monday || "";
  $("baseGroup").value = _duty.base_group || "";
  $("orderInput").value = (_duty.order || []).join(",");

  $("btnSaveBasic").addEventListener("click", saveBasic);
  $("btnPreviewDate").addEventListener("click", function () {
    var d = $("previewDate").value;
    if (!d) { toast("请先选择日期", "err"); return; }
    window.open("/?date=" + d, "_blank");
  });
  document.querySelectorAll("button[data-prev]").forEach(function (b) {
    b.addEventListener("click", function () { previewCopy(b.getAttribute("data-prev")); });
  });
  $("btnExport").addEventListener("click", doExport);
  refreshDistLink();
}

async function saveBasic() {
  _cfg.lab_name = $("labName").value.trim();
  _cfg.chat_name = $("chatName").value.trim();
  _cfg.skip_holidays = $("skipHolidays").checked;
  _cfg.skip_custom = $("skipCustom").checked;
  _duty.base_monday = $("baseMonday").value;
  _duty.base_group = parseInt($("baseGroup").value, 10) || 1;
  _duty.order = $("orderInput").value.split(",").map(function (s) { return parseInt(s.trim(), 10); }).filter(function (n) { return !isNaN(n); });
  await api("/api/config", { method: "POST", body: JSON.stringify(_cfg) });
  await api("/api/duty", { method: "POST", body: JSON.stringify(_duty) });
  toast("基础设置已保存");
}

async function previewCopy(kind) {
  var today = $("previewDate").value || new Date().toISOString().slice(0, 10);
  try {
    var v = await api("/api/preview?date=" + today);
    var text = v.copy[kind] || "（无）";
    $("previewText").textContent = text;
    copyText(text);
  } catch (e) { toast("预览失败：" + e.message, "err"); }
}

async function doExport() {
  var btn = $("btnExport"); btn.disabled = true; btn.textContent = "生成中…";
  try {
    var r = await api("/api/export", { method: "POST", body: "{}" });
    var box = $("exportResult");
    box.hidden = false;
    var lines = r.files.map(function (f) { return "  " + f.path + "  (" + f.size + " B)"; });
    box.textContent = "生成完成，共 " + r.count + " 个文件：\n" + lines.join("\n") +
      (r.missing && r.missing.length ? "\n缺失：" + r.missing.join(", ") : "") +
      "\n\ndist 路径：" + r.dist;
    toast(r.ok ? "发布文件已生成" : "已生成，但有缺失文件", r.ok ? "ok" : "err");
    refreshDistLink();
  } catch (e) {
    toast("生成失败：" + e.message, "err");
  } finally {
    btn.disabled = false; btn.textContent = "生成 / 更新发布文件";
  }
}

async function refreshDistLink() {
  try {
    var s = await api("/api/dist_status");
    var link = $("distLink");
    if (link) link.hidden = !s.exists;
  } catch (e) {}
}

/* =========================== 值日人员 =========================== */
async function initDuty() {
  _duty = await api("/api/duty");
  renderGroups();
  $("btnAddGroup").addEventListener("click", addGroup);
}

function renderGroups() {
  var box = $("groupsContainer");
  box.innerHTML = "";
  _duty.groups.forEach(function (g, gi) {
    var members = (g.members && g.members.length === 5) ? g.members : ["", "", "", "", ""];
    var card = document.createElement("div");
    card.className = "group-card";
    card.innerHTML =
      '<div class="group-card-head">' +
      '<span class="grp-num">第 ' + g.number + ' 组</span>' +
      '<input type="text" placeholder="组名" value="' + esc(g.name) + '" data-k="name" style="max-width:180px">' +
      '<label class="field" style="flex-direction:row;align-items:center;gap:6px"><span style="margin:0">负责人</span>' +
      '<input type="text" value="' + esc(g.leader) + '" data-k="leader" style="max-width:130px"></label>' +
      '<button class="btn-danger-admin" data-del="' + gi + '">删除该组</button>' +
      '</div>' +
      '<div class="member-grid">' +
      members.map(function (m, mi) {
        return '<label class="field"><span>' + WEEKDAYS[mi] + '</span><input type="text" value="' + esc(m) + '" data-mem="' + mi + '"></label>';
      }).join("") + '</div>';
    box.appendChild(card);
  });

  box.querySelectorAll("input[data-k]").forEach(function (inp) {
    inp.addEventListener("change", function () { var gi = cardIndexOf(inp); _duty.groups[gi][inp.dataset.k] = inp.value.trim(); saveDuty(); });
  });
  box.querySelectorAll("input[data-mem]").forEach(function (inp) {
    inp.addEventListener("change", function () { var gi = cardIndexOf(inp); _duty.groups[gi].members[parseInt(inp.dataset.mem, 10)] = inp.value.trim(); saveDuty(); });
  });
  box.querySelectorAll("button[data-del]").forEach(function (b) {
    b.addEventListener("click", function () {
      var gi = parseInt(b.dataset.del, 10);
      if (!confirm("确定删除「" + _duty.groups[gi].name + "」？")) return;
      _duty.groups.splice(gi, 1);
      saveDuty().then(renderGroups);
    });
  });
}
function cardIndexOf(el) {
  var cards = document.querySelectorAll("#groupsContainer .group-card");
  for (var i = 0; i < cards.length; i++) if (cards[i].contains(el)) return i;
  return 0;
}
async function saveDuty() { await api("/api/duty", { method: "POST", body: JSON.stringify(_duty) }); }
function addGroup() {
  var next = (_duty.groups.reduce(function (m, g) { return Math.max(m, g.number); }, 0)) + 1;
  _duty.groups.push({ number: next, name: "第" + next + "组", leader: "", members: ["", "", "", "", ""] });
  _duty.order.push(next);
  saveDuty().then(function () { renderGroups(); toast("已新增第" + next + "组"); });
}

/* =========================== 提醒时间 =========================== */
async function initReminders() {
  _cfg = await api("/api/config");
  renderTimes();
  $("btnAddWeekday").addEventListener("click", function () { _cfg.weekday_times.push({ time: "10:00", enabled: true }); renderTimes(); });
  $("btnSaveReminders").addEventListener("click", saveReminders);
}
function renderTimeList(boxId, times) {
  var box = $(boxId);
  if (!times.length) { box.innerHTML = '<div class="hint">暂无提醒时间</div>'; return; }
  box.innerHTML = times.map(function (t, i) {
    return '<div class="time-row">' +
      '<input type="time" value="' + esc(t.time) + '" data-ti="' + i + '">' +
      '<label class="sw-row"><input type="checkbox" class="cb" data-en="' + i + '"' + (t.enabled ? " checked" : "") + '><span class="sw"></span><span>启用</span></label>' +
      '<button class="btn-danger-admin" data-rm="' + i + '">删除</button></div>';
  }).join("");
  box.querySelectorAll("input[data-ti]").forEach(function (inp) {
    inp.addEventListener("change", function () { times[parseInt(inp.dataset.ti, 10)].time = inp.value; });
  });
  box.querySelectorAll("input[data-en]").forEach(function (inp) {
    inp.addEventListener("change", function () { times[parseInt(inp.dataset.en, 10)].enabled = inp.checked; });
  });
  box.querySelectorAll("button[data-rm]").forEach(function (b) {
    b.addEventListener("click", function () { times.splice(parseInt(b.dataset.rm, 10), 1); renderTimes(); });
  });
}
function renderTimes() {
  renderTimeList("weekdayTimes", _cfg.weekday_times);
  renderTimeList("saturdayTimes", _cfg.saturday_times);
  $("saturdayEnabled").checked = !!_cfg.saturday_enabled;
  $("showSunday").checked = !!_cfg.show_sunday;
  $("showCountdown").checked = !!_cfg.show_countdown;
  $("notifyLead").value = _cfg.notify_lead_minutes || 30;
}
async function saveReminders() {
  _cfg.saturday_enabled = $("saturdayEnabled").checked;
  _cfg.show_sunday = $("showSunday").checked;
  _cfg.show_countdown = $("showCountdown").checked;
  _cfg.notify_lead_minutes = parseInt($("notifyLead").value, 10) || 30;
  await api("/api/config", { method: "POST", body: JSON.stringify(_cfg) });
  toast("提醒时间已保存");
}

/* =========================== 节假日 =========================== */
var _skip = null;
async function initHolidays() {
  _cfg = await api("/api/config");
  _skip = await api("/api/skip");
  renderSkip();
  $("btnAddSkip").addEventListener("click", addSkip);
}
function renderSkip() {
  var box = $("skipList");
  if (!_skip.skip_days || !_skip.skip_days.length) { box.innerHTML = '<div class="hint">暂无停提醒日期</div>'; return; }
  box.innerHTML = _skip.skip_days.map(function (s) {
    return '<div class="skip-row">' +
      '<span><b>' + esc(s.name) + '</b> <span class="badge ' + s.kind + '">' + (s.kind === "holiday" ? "法定节假日" : "课题组放假") + '</span></span>' +
      '<span class="skip-range">' + esc(s.start) + " → " + esc(s.end) + '</span>' +
      '<button class="btn-ghost-admin" data-edit="' + s.id + '">编辑</button>' +
      '<button class="btn-danger-admin" data-del="' + s.id + '">删除</button></div>';
  }).join("");
  box.querySelectorAll("button[data-del]").forEach(function (b) {
    b.addEventListener("click", function () {
      _skip.skip_days = _skip.skip_days.filter(function (s) { return s.id !== b.dataset.del; });
      saveSkip();
    });
  });
  box.querySelectorAll("button[data-edit]").forEach(function (b) {
    b.addEventListener("click", function () {
      var s = _skip.skip_days.find(function (x) { return x.id === b.dataset.edit; });
      $("newName").value = s.name; $("newKind").value = s.kind;
      $("newStart").value = s.start; $("newEnd").value = s.end;
      s._editing = true; $("editHint").hidden = false;
      toast("已载入，修改后点添加即更新");
    });
  });
}
async function addSkip() {
  var name = $("newName").value.trim(), kind = $("newKind").value;
  var start = $("newStart").value, end = $("newEnd").value;
  if (!name || !start || !end) { toast("请填写名称与起止日期", "err"); return; }
  if (start > end) { toast("开始日期不能晚于结束日期", "err"); return; }
  var editing = _skip.skip_days.find(function (s) { return s._editing; });
  if (editing) { editing.name = name; editing.kind = kind; editing.start = start; editing.end = end; delete editing._editing; $("editHint").hidden = true; }
  else { _skip.skip_days.push({ id: "s-" + Date.now(), name: name, kind: kind, start: start, end: end }); }
  $("newName").value = ""; $("newStart").value = ""; $("newEnd").value = "";
  await saveSkip();
}
async function saveSkip() { await api("/api/skip", { method: "POST", body: JSON.stringify(_skip) }); renderSkip(); toast("已保存"); }

/* =========================== 消息模板 =========================== */
var _tpl = null;
async function initTemplates() {
  _tpl = await api("/api/templates");
  $("tplWeekday").value = _tpl.tpl_weekday || "";
  $("tplSaturday").value = _tpl.tpl_saturday || "";
  $("btnSaveTpl").addEventListener("click", saveTpl);
  $("btnPreviewTpl").addEventListener("click", previewTpl);
}
async function saveTpl() {
  _tpl.tpl_weekday = $("tplWeekday").value;
  _tpl.tpl_saturday = $("tplSaturday").value;
  await api("/api/templates", { method: "POST", body: JSON.stringify(_tpl) });
  toast("模板已保存");
}
async function previewTpl() {
  _tpl.tpl_weekday = $("tplWeekday").value;
  _tpl.tpl_saturday = $("tplSaturday").value;
  await api("/api/templates", { method: "POST", body: JSON.stringify(_tpl) });
  var today = new Date().toISOString().slice(0, 10);
  var v = await api("/api/preview?date=" + today);
  $("tplPreview").textContent =
    "──── 周一到周五模板（按今天渲染）────\n" + (v.copy_preview.weekday || "") +
    "\n\n──── 周六大扫除模板（按本周六渲染）────\n" + (v.copy_preview.saturday || "");
}

/* =========================== 入口 =========================== */
document.addEventListener("DOMContentLoaded", function () {
  var page = document.body.dataset.page;
  try {
    if (page === "home") initHome();
    else if (page === "duty") initDuty();
    else if (page === "reminders") initReminders();
    else if (page === "holidays") initHolidays();
    else if (page === "templates") initTemplates();
  } catch (e) { toast("页面初始化失败：" + e.message, "err"); }
});
