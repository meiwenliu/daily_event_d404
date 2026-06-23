/* D404 值日看板 · 管理后台 + 登录页脚本（v3） */
"use strict";
var $ = function (id) { return document.getElementById(id); };
var WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}
function val(id) { var e = $(id); return e ? e.value : ""; }
function cb(id) { var e = $(id); return e ? e.checked : false; }
function todayIso() { var d = new Date(); return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
function fmtMD(ds) { var p = ds.split("-"); return p[1] + "-" + p[2]; }

function toast(msg, type) {
  var area = $("toast"); if (!area) { alert(msg); return; }
  var el = document.createElement("div");
  el.className = "toast " + (type === "err" ? "err" : "ok");
  el.textContent = msg; area.appendChild(el);
  setTimeout(function () { el.classList.add("out"); setTimeout(function () { el.remove(); }, 300); }, 2400);
}

async function api(path, opts) {
  opts = opts || {};
  var res = await fetch(path, Object.assign({ headers: { "Content-Type": "application/json" }, cache: "no-store" }, opts));
  var data = null;
  try { data = await res.json(); } catch (e) {}
  if (!res.ok) throw new Error((data && (data.error || data.message)) || ("HTTP " + res.status));
  return data;
}

/* ============================ 登录页 ============================ */
function initLogin() {
  var form = $("loginForm");
  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    var pwd = $("pwd").value;
    var err = $("err"); err.hidden = true;
    try {
      await api("/login", { method: "POST", body: JSON.stringify({ password: pwd }) });
      location.href = "/admin";
    } catch (ex) {
      err.textContent = "登录失败：" + ex.message;
      err.hidden = false;
    }
  });
}

/* ============================ 管理后台 ============================ */
var _cfg = null;

async function initAdmin() {
  // 标签切换
  document.querySelectorAll("#adminNav a[data-tab]").forEach(function (a) {
    a.addEventListener("click", function () {
      var tab = a.getAttribute("data-tab");
      document.querySelectorAll("#adminNav a[data-tab]").forEach(function (x) { x.classList.toggle("active", x === a); });
      document.querySelectorAll(".atab").forEach(function (s) { s.hidden = (s.id !== "tab-" + tab); });
    });
  });

  try {
    _cfg = await api("/api/admin/config");
  } catch (ex) {
    if (String(ex.message).indexOf("401") >= 0 || ex.message.indexOf("未登录") >= 0) {
      location.href = "/login"; return;
    }
    toast("加载配置失败：" + ex.message, "err"); return;
  }

  fillBasic();
  renderGroups();
  renderTodayStatus();
  renderOverrides();
  renderSkip();
  fillTemplates();
  renderBackups();
  renderDeploy();
  renderSecurityBanner();

  // 保存按钮（基础/值日/节假日/模板 统一全量保存）
  document.querySelectorAll("button[data-save]").forEach(function (b) {
    b.addEventListener("click", saveAll);
  });
  $("btnAddGroup").addEventListener("click", addGroup);
  $("btnSaveToday").addEventListener("click", applyToday);
  $("btnAddOverride").addEventListener("click", addOverride);
  $("btnAddSkip").addEventListener("click", addSkip);
  $("btnPreviewTpl").addEventListener("click", previewTpl);
  $("btnImportJson").addEventListener("click", importJson);
  $("btnImportCsv").addEventListener("click", importCsv);
  $("btnChangePwd").addEventListener("click", changePwd);
}

function fillBasic() {
  $("labName").value = _cfg.lab_name || "";
  $("chatName").value = _cfg.chat_name || "";
  $("baseMonday").value = (_cfg.rotation || {}).base_monday || "";
  $("baseGroup").value = (_cfg.rotation || {}).base_group || "";
  $("orderInput").value = ((_cfg.rotation || {}).order || []).join(",");
  var st = _cfg.settings || {};
  $("skipHolidays").checked = !!st.skip_holidays;
  $("skipCustom").checked = !!st.skip_custom;
  $("showCountdown").checked = !!st.show_countdown;
  $("saturdayEnabled").checked = !!st.saturday_enabled;
  $("weekdayTimes").value = (st.weekday_times || []).map(function (t) { return t.time; }).join(",");
  $("saturdayTimes").value = (st.saturday_times || []).map(function (t) { return t.time; }).join(",");
  $("tplWeekday").value = (_cfg.templates || {}).tpl_weekday || "";
  $("tplSaturday").value = (_cfg.templates || {}).tpl_saturday || "";
  $("publicMode").checked = !!_cfg.public_mode_enabled;
  $("publicUrl").value = _cfg.public_url || "";
}

function parseTimes(text) {
  return text.split(",").map(function (s) { return s.trim(); }).filter(Boolean)
    .map(function (t) { return { time: t, enabled: true }; });
}

function collectAll() {
  _cfg.lab_name = val("labName").trim();
  _cfg.chat_name = val("chatName").trim();
  _cfg.rotation = _cfg.rotation || {};
  _cfg.rotation.base_monday = val("baseMonday");
  _cfg.rotation.base_group = parseInt(val("baseGroup"), 10) || 1;
  _cfg.rotation.order = val("orderInput").split(",").map(function (s) { return parseInt(s.trim(), 10); }).filter(function (n) { return !isNaN(n); });
  _cfg.settings = _cfg.settings || {};
  var st = _cfg.settings;
  st.skip_holidays = cb("skipHolidays");
  st.skip_custom = cb("skipCustom");
  st.show_countdown = cb("showCountdown");
  st.saturday_enabled = cb("saturdayEnabled");
  st.show_sunday = st.show_sunday || false;
  st.notify_lead_minutes = st.notify_lead_minutes || 30;
  st.weekday_times = parseTimes(val("weekdayTimes"));
  st.saturday_times = parseTimes(val("saturdayTimes"));
  _cfg.templates = _cfg.templates || {};
  _cfg.templates.tpl_weekday = val("tplWeekday");
  _cfg.templates.tpl_saturday = val("tplSaturday");
  _cfg.groups = collectGroups();
  _cfg.public_mode_enabled = cb("publicMode");
  _cfg.public_url = val("publicUrl").trim();
  // date_overrides / skip_days 已在 _cfg 中由各功能维护
}

function collectGroups() {
  var cards = document.querySelectorAll("#groupsContainer .group-card");
  var groups = [];
  cards.forEach(function (card) {
    var num = parseInt(card.getAttribute("data-num"), 10);
    var name = card.querySelector("input[data-k=name]").value.trim();
    var leader = card.querySelector("input[data-k=leader]").value.trim();
    var members = [];
    card.querySelectorAll("input[data-mem]").forEach(function (inp) { members.push(inp.value.trim()); });
    groups.push({ id: "g-" + num, number: num, name: name, leader: leader, members: members });
  });
  return groups;
}

function renderGroups() {
  var box = $("groupsContainer"); box.innerHTML = "";
  (_cfg.groups || []).forEach(function (g) {
    var members = (g.members && g.members.length === 5) ? g.members : ["", "", "", "", ""];
    var card = document.createElement("div");
    card.className = "group-card"; card.setAttribute("data-num", g.number);
    card.innerHTML =
      '<div class="group-card-head">' +
      '<span class="grp-num">第 ' + g.number + ' 组</span>' +
      '<input type="text" data-k="name" placeholder="组名" value="' + esc(g.name) + '" style="max-width:180px">' +
      '<label class="field" style="flex-direction:row;align-items:center;gap:6px"><span style="margin:0">负责人</span>' +
      '<input type="text" data-k="leader" value="' + esc(g.leader) + '" style="max-width:130px"></label>' +
      '<button class="btn-danger-admin" data-del="' + g.number + '">删除该组</button></div>' +
      '<div class="member-grid">' + WEEKDAYS.map(function (dn, mi) {
        return '<label class="field"><span>' + dn + '</span><input type="text" data-mem="' + mi + '" value="' + esc(members[mi]) + '"></label>';
      }).join("") + "</div>";
    box.appendChild(card);
  });
  box.querySelectorAll("button[data-del]").forEach(function (b) {
    b.addEventListener("click", function () {
      var num = parseInt(b.getAttribute("data-del"), 10);
      if (!confirm("确定删除第 " + num + " 组？")) return;
      _cfg.groups = _cfg.groups.filter(function (g) { return g.number !== num; });
      _cfg.rotation.order = (_cfg.rotation.order || []).filter(function (n) { return n !== num; });
      renderGroups(); toast("已删除，记得点保存");
    });
  });
}
function addGroup() {
  var nums = (_cfg.groups || []).map(function (g) { return g.number; });
  var next = nums.length ? Math.max.apply(null, nums) + 1 : 1;
  _cfg.groups.push({ id: "g-" + next, number: next, name: "第" + next + "组", leader: "", members: ["", "", "", "", ""] });
  _cfg.rotation = _cfg.rotation || {}; _cfg.rotation.order = _cfg.rotation.order || [];
  if (_cfg.rotation.order.indexOf(next) < 0) _cfg.rotation.order.push(next);
  renderGroups(); toast("已新增第 " + next + " 组，记得点保存");
}

/* ---- 今日状态 ---- */
function renderTodayStatus() {
  var today = todayIso();
  var ov = (_cfg.date_overrides || []).find(function (o) { return o.date === today; });
  $("todayMode").value = ov ? ov.mode : "auto";
  $("todayReason").value = ov ? (ov.reason || "") : "";
  $("todayStatusInfo").innerHTML = ov
    ? '<span class="badge ' + (ov.mode === "paused" ? "badge-rose" : "badge-green") + '">当前：' + (ov.mode === "paused" ? "手动暂停" : "手动正常值日") + "</span> " + esc(ov.reason || "")
    : '<span class="badge badge-gray">当前：自动判断（按星期与放假规则）</span>';
}
function applyToday() {
  var mode = val("todayMode"), reason = val("todayReason").trim();
  var today = todayIso();
  _cfg.date_overrides = (_cfg.date_overrides || []).filter(function (o) { return o.date !== today; });
  if (mode !== "auto") _cfg.date_overrides.push({ id: "today-" + today, date: today, mode: mode, reason: reason });
  saveAll(function () { renderTodayStatus(); renderOverrides(); });
}

/* ---- 指定日期覆盖 ---- */
function renderOverrides() {
  var box = $("overrideList");
  var list = (_cfg.date_overrides || []).slice().sort(function (a, b) { return a.date < b.date ? -1 : 1; });
  if (!list.length) { box.innerHTML = '<div class="hint">暂无日期覆盖</div>'; return; }
  box.innerHTML = list.map(function (o) {
    return '<div class="skip-row"><span><b>' + esc(o.date) + '</b> <span class="badge ' + (o.mode === "paused" ? "badge-rose" : "badge-green") + '">' + (o.mode === "paused" ? "暂停" : "正常") + "</span> " + esc(o.reason || "") + "</span>" +
      '<button class="btn-danger-admin" data-ov-del="' + o.date + '">删除</button></div>';
  }).join("");
  box.querySelectorAll("button[data-ov-del]").forEach(function (b) {
    b.addEventListener("click", function () {
      var d = b.getAttribute("data-ov-del");
      _cfg.date_overrides = _cfg.date_overrides.filter(function (o) { return o.date !== d; });
      saveAll(function () { renderOverrides(); renderTodayStatus(); });
    });
  });
}
function addOverride() {
  var d = val("ovDate"), mode = val("ovMode"), reason = val("ovReason").trim();
  if (!d) { toast("请选择日期", "err"); return; }
  _cfg.date_overrides = (_cfg.date_overrides || []).filter(function (o) { return o.date !== d; });
  _cfg.date_overrides.push({ id: "ov-" + d, date: d, mode: mode, reason: reason });
  $("ovDate").value = ""; $("ovReason").value = "";
  saveAll(function () { renderOverrides(); renderTodayStatus(); });
}

/* ---- 节假日 ---- */
function renderSkip() {
  var box = $("skipList");
  var list = _cfg.skip_days || [];
  if (!list.length) { box.innerHTML = '<div class="hint">暂无节假日/放假</div>'; return; }
  box.innerHTML = list.map(function (s) {
    return '<div class="skip-row"><span><b>' + esc(s.name) + '</b> <span class="badge ' + s.kind + '">' + (s.kind === "holiday" ? "法定节假日" : "课题组放假") + "</span></span>" +
      '<span class="skip-range">' + esc(s.start) + " → " + esc(s.end) + "</span>" +
      '<button class="btn-danger-admin" data-skip-del="' + s.id + '">删除</button></div>';
  }).join("");
  box.querySelectorAll("button[data-skip-del]").forEach(function (b) {
    b.addEventListener("click", function () {
      var id = b.getAttribute("data-skip-del");
      _cfg.skip_days = _cfg.skip_days.filter(function (s) { return s.id !== id; });
      saveAll(renderSkip);
    });
  });
}
function addSkip() {
  var name = val("newSkipName").trim(), kind = val("newSkipKind");
  var start = val("newSkipStart"), end = val("newSkipEnd");
  if (!name || !start || !end) { toast("请填写名称与起止日期", "err"); return; }
  if (start > end) { toast("开始日期不能晚于结束日期", "err"); return; }
  _cfg.skip_days.push({ id: "s-" + Date.now(), name: name, kind: kind, start: start, end: end });
  $("newSkipName").value = ""; $("newSkipStart").value = ""; $("newSkipEnd").value = "";
  saveAll(renderSkip);
}

/* ---- 模板 ---- */
function fillTemplates() { /* fillBasic 已填 */ }
async function previewTpl() {
  collectAll();
  try {
    var v = await api("/api/public");
    $("tplPreview").textContent = "—— 今日值日模板 ——\n" + v.copy.today;
  } catch (ex) { toast("预览失败：" + ex.message, "err"); }
}

/* ---- 导入导出 ---- */
async function importJson() {
  var txt = val("importJsonArea").trim();
  if (!txt) { toast("请粘贴 JSON", "err"); return; }
  var obj;
  try { obj = JSON.parse(txt); } catch (e) { toast("JSON 格式错误：" + e.message, "err"); return; }
  try {
    await api("/api/admin/import/json", { method: "POST", body: JSON.stringify(obj) });
    toast("导入成功"); setTimeout(function () { location.reload(); }, 600);
  } catch (ex) { toast("导入失败：" + ex.message, "err"); }
}
async function importCsv() {
  var txt = val("importCsvArea");
  if (!txt.trim()) { toast("请粘贴 CSV", "err"); return; }
  try {
    var r = await api("/api/admin/import/csv", { method: "POST", body: JSON.stringify({ text: txt }) });
    toast("导入成功，共 " + r.groups + " 组"); setTimeout(function () { location.reload(); }, 600);
  } catch (ex) { toast("导入失败：" + ex.message, "err"); }
}
async function renderBackups() {
  var box = $("backupList");
  try {
    var r = await api("/api/admin/backups");
    var list = r.backups || [];
    if (!list.length) { box.innerHTML = '<div class="hint">暂无备份</div>'; return; }
    box.innerHTML = list.map(function (b) {
      return '<div class="skip-row"><span class="skip-range">' + esc(b.name) + " (" + b.size + " B)</span>" +
        '<button class="btn-ghost-admin" data-restore="' + esc(b.name) + '">恢复</button></div>';
    }).join("");
    box.querySelectorAll("button[data-restore]").forEach(function (bt) {
      bt.addEventListener("click", async function () {
        var name = bt.getAttribute("data-restore");
        if (!confirm("恢复 " + name + "？（当前配置会先自动备份）")) return;
        try { await api("/api/admin/backup/restore", { method: "POST", body: JSON.stringify({ name: name }) }); toast("已恢复"); setTimeout(function () { location.reload(); }, 600); }
        catch (ex) { toast("恢复失败：" + ex.message, "err"); }
      });
    });
  } catch (ex) { box.innerHTML = '<div class="hint">加载失败</div>'; }
}

/* ---- 改密 ---- */
async function changePwd() {
  var o = val("oldPwd"), n = val("newPwd");
  if (n.length < 4) { toast("新密码至少 4 位", "err"); return; }
  try {
    await api("/api/admin/password", { method: "POST", body: JSON.stringify({ old: o, new: n }) });
    toast("密码已修改"); $("oldPwd").value = ""; $("newPwd").value = "";
  } catch (ex) { toast("修改失败：" + ex.message, "err"); }
}

/* ---- 部署 / 安全 信息 ---- */
async function renderDeploy() {
  var box = $("deployInfo");
  try {
    var n = await api("/api/admin/network");
    box.innerHTML =
      '<div class="deploy-row"><span>本机访问</span><b>' + esc(n.local) + "</b></div>" +
      '<div class="deploy-row"><span>局域网访问</span><b>' + esc(n.lan) + '</b> <span class="muted">（手机同 WiFi 打开）</span></div>' +
      '<div class="deploy-row"><span>公网分享链接</span><b>' + (n.public_url ? esc(n.public_url) : '<span class="muted">未设置（在下方填写）</span>') + "</b></div>" +
      '<div class="deploy-row"><span>公网模式</span><b>' + (n.public_mode_enabled ? "已开启" : "未开启") + "</b></div>";
  } catch (e) { box.innerHTML = '<div class="hint">加载失败</div>'; }
}
async function renderSecurityBanner() {
  var warn = $("defaultPwdWarn");
  var info = $("securityInfo");
  try {
    var s = await api("/api/admin/security");
    if (warn) warn.hidden = !s.is_default_password;
    if (info) {
      info.innerHTML =
        '<div class="deploy-row"><span>默认密码</span><b>' + (s.is_default_password ? '<span style="color:#be123c">是（必须修改）</span>' : "已修改 ✓") + "</b></div>" +
        '<div class="deploy-row"><span>最近失败登录次数</span><b>' + s.recent_fail_count + "</b></div>" +
        (s.recent_fails && s.recent_fails.length ? '<div class="hint">最近失败：' + s.recent_fails.map(function (f) { return esc(f.ts + " " + (f.ip || "")); }).join("；") + "</div>" : "");
    }
  } catch (e) { /* 忽略 */ }
}

/* ---- 统一保存 ---- */
async function saveAll(after) {
  collectAll();
  try {
    await api("/api/admin/config", { method: "POST", body: JSON.stringify(_cfg) });
    toast("已保存（已自动备份旧配置）");
    if (after) after();
  } catch (ex) {
    toast("保存失败：" + ex.message, "err");
  }
}

/* ============================ 入口 ============================ */
window.addEventListener("DOMContentLoaded", function () {
  if (window.__loginPage) { initLogin(); return; }
  initAdmin();
});
