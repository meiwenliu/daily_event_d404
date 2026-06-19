/* =========================================================================
   D404 实验室值日看板 · 公共展示页脚本（纯静态，镜像 duty_core.py 算法）
   - fetch ./data/{config,duty_groups,skip_days,templates}.json
   - 客户端计算轮换/停提醒/消息/复制文案
   - 时钟、倒计时、复制、浏览器通知、PWA
   ========================================================================= */
"use strict";

/* 用脚本自身位置推导站点根目录，兼容 Flask 预览与子路径部署（如 GitHub Pages /repo/） */
var __scriptSrc = (document.currentScript && document.currentScript.src) || "static/public.js";
var ROOT = new URL("../", new URL(__scriptSrc, location.href)).href;

var WEEKDAY_CN = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"];
var CHECK_ITEMS = ["门窗是否关好", "水电是否关闭", "仪器设备是否正常", "桌面地面是否整洁", "垃圾是否已清理"];

var DATA = null;   // {config, duty, skip, templates}
var VIEW = null;   // 构建出的视图
var NOTIFY_TIMERS = [];

/* ---------------- 工具 ---------------- */
function parseDate(s) { var p = s.split("-").map(Number); return new Date(p[0], p[1] - 1, p[2]); }
function isoDate(d) {
  var y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, "0"), dd = String(d.getDate()).padStart(2, "0");
  return y + "-" + m + "-" + dd;
}
function addDays(d, n) { var x = new Date(d.getTime()); x.setDate(x.getDate() + n); return x; }
function weekMonday(d) { return addDays(d, -((d.getDay() + 6) % 7)); } // 周一=0
function fmtMD(d) { return String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0"); }
function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}
function $(id) { return document.getElementById(id); }

/* ---------------- 核心：镜像 duty_core ---------------- */
function getGroupNumber(d, duty) {
  var order = duty.order || [];
  if (!order.length) return duty.base_group || 1;
  var baseMon = parseDate(duty.base_monday);
  var weeks = Math.floor((weekMonday(d) - baseMon) / 86400000 / 7);
  weeks = ((weeks % order.length) + order.length) % order.length;
  return order[weeks];
}
function getGroup(d, duty) {
  var num = getGroupNumber(d, duty);
  return (duty.groups || []).find(function (g) { return g.number === num; }) || null;
}
function getDutyPerson(d, group) {
  if (!group) return "（未配置）";
  var members = group.members || [];
  var idx = (d.getDay() + 6) % 7; // 周一=0
  if (idx >= 0 && idx < members.length && members[idx]) return members[idx];
  return group.leader || "（未配置）";
}
function isSkipDay(d, skip) {
  var ds = isoDate(d);
  var items = (skip.skip_days || []);
  for (var i = 0; i < items.length; i++) {
    var it = items[i];
    if (!it.start || !it.end) continue;
    if (ds >= it.start && ds <= it.end) return { hit: true, name: it.name || "停提醒", kind: it.kind || "custom", start: it.start, end: it.end };
  }
  return { hit: false, name: "", kind: "", start: "", end: "" };
}
function skipForConfig(d, config, skip) {
  var r = isSkipDay(d, skip);
  if (!r.hit) return { hit: false, name: "", kind: "", start: "", end: "" };
  if (r.kind === "holiday" && !config.skip_holidays) return { hit: false };
  if (r.kind === "custom" && !config.skip_custom) return { hit: false };
  return r;
}
function buildDayInfo(d, config, duty, skip) {
  var group = getGroup(d, duty) || {};
  var r = skipForConfig(d, config, skip);
  var wd = (d.getDay() + 6) % 7;
  var info = {
    date: isoDate(d), weekday: WEEKDAY_CN[wd],
    group_name: group.name || "", leader: group.leader || "",
    skipped: r.hit, skip_name: r.name, skip_kind: r.kind,
    skip_range: r.hit ? (r.start + " ~ " + r.end) : "",
    kind: "", person: ""
  };
  if (r.hit) { info.kind = "skip"; }
  else if (wd < 5) { info.kind = "duty"; info.person = getDutyPerson(d, group); }
  else if (wd === 5) { info.kind = "saturday"; info.person = group.leader || ""; }
  else { info.kind = "sunday"; }
  return info;
}
function nextDutyDay(start, config, duty, skip, maxDays) {
  maxDays = maxDays || 14;
  for (var i = 1; i <= maxDays; i++) {
    var d = addDays(start, i);
    if ((d.getDay() + 6) % 7 >= 5) continue; // 跳过周末
    var info = buildDayInfo(d, config, duty, skip);
    if (!info.skipped) return info;
  }
  return null;
}
function getReminders(d, config) {
  var wd = (d.getDay() + 6) % 7;
  var out = [];
  if (wd < 5) {
    (config.weekday_times || []).forEach(function (t) { if (t.enabled) out.push({ time: t.time, type: "duty" }); });
  } else if (wd === 5) {
    if (config.saturday_enabled) (config.saturday_times || []).forEach(function (t) { if (t.enabled) out.push({ time: t.time, type: "saturday" }); });
  } else if (wd === 6) {
    if (config.show_sunday) (config.weekday_times || []).forEach(function (t) { if (t.enabled) out.push({ time: t.time, type: "duty" }); });
  }
  return out;
}
function renderTpl(tpl, vars) {
  var out = tpl;
  for (var k in vars) { out = out.split("{" + k + "}").join(vars[k]); }
  return out.replace(/^\s+|\s+$/g, "");
}
function buildMessage(d, mtype, config, duty, templates) {
  var group = getGroup(d, duty) || {};
  var vars = {
    date: isoDate(d), weekday: WEEKDAY_CN[(d.getDay() + 6) % 7],
    group_name: group.name || "（未配置）", leader: group.leader || "（未配置）",
    duty_person: getDutyPerson(d, group), chat_name: config.chat_name || ""
  };
  var tpl = mtype === "saturday" ? templates.tpl_saturday : templates.tpl_weekday;
  return renderTpl(tpl, vars);
}
function copyToday(d, DATA) {
  var info = buildDayInfo(d, DATA.config, DATA.duty, DATA.skip);
  return buildMessage(d, info.kind === "saturday" ? "saturday" : "duty", DATA.config, DATA.duty, DATA.templates);
}
function copyWeek(wm, DATA) {
  var cfg = DATA.config;
  var g = getGroup(wm, DATA.duty) || {};
  var lines = ["【" + (cfg.lab_name || "D404 实验室") + "本周值日安排】", "",
    "本周负责组：" + (g.name || "") + "（负责人：" + (g.leader || "") + "）"];
  for (var i = 0; i < 6; i++) {
    var dd = addDays(wm, i);
    var info = buildDayInfo(dd, cfg, DATA.duty, DATA.skip);
    if (info.skipped) lines.push(info.weekday + "（" + fmtMD(dd) + "）暂停（" + info.skip_name + "）");
    else if (info.kind === "saturday") lines.push(info.weekday + "（" + fmtMD(dd) + "）大扫除 · " + info.person);
    else lines.push(info.weekday + "（" + fmtMD(dd) + "）" + info.person);
  }
  var wt = (cfg.weekday_times || []).filter(function (t) { return t.enabled; }).map(function (t) { return t.time; }).join(", ") || "无";
  var st = (cfg.saturday_times || []).filter(function (t) { return t.enabled; }).map(function (t) { return t.time; }).join(", ") || "无";
  lines.push("", "工作日提醒时间：" + wt, "周六大扫除提醒时间：" + st);
  return lines.join("\n");
}
function copyAnnouncement(wm, DATA) {
  var cfg = DATA.config, g = getGroup(wm, DATA.duty) || {}, members = g.members || [];
  var days = ["周一", "周二", "周三", "周四", "周五"];
  var lines = ["【" + (cfg.lab_name || "D404 实验室") + "值日公告】", "",
    "本周负责组：" + (g.name || ""), "负责人：" + (g.leader || ""), ""];
  days.forEach(function (dn, i) { lines.push(dn + "：" + (members[i] || "—")); });
  lines.push("周六：大扫除（负责人：" + (g.leader || "") + "）");
  lines.push("", "请值日同学按时完成值日与安全检查，完成后拍照发群。");
  return lines.join("\n");
}

/* ---------------- 视图构建 ---------------- */
function buildView(d) {
  var cfg = DATA.config, duty = DATA.duty, skip = DATA.skip;
  var wm = weekMonday(d);
  var today = buildDayInfo(d, cfg, duty, skip);
  var tomorrow = buildDayInfo(addDays(d, 1), cfg, duty, skip);
  var thisWeek = [];
  for (var i = 0; i < 6; i++) thisWeek.push(buildDayInfo(addDays(wm, i), cfg, duty, skip));
  var nextWm = addDays(wm, 7);
  var nextGroup = getGroup(nextWm, duty) || {};
  var reminders = getReminders(d, cfg);
  if (today.skipped) today.next_duty = nextDutyDay(d, cfg, duty, skip);
  return {
    config: cfg, today: today, tomorrow: tomorrow,
    this_week: thisWeek,
    next_week: { week_monday: isoDate(nextWm), group_name: nextGroup.name || "", leader: nextGroup.leader || "", members: nextGroup.members || [] },
    reminders: reminders, check_items: CHECK_ITEMS,
    copy: {
      today: copyToday(d, DATA),
      tomorrow: copyToday(addDays(d, 1), DATA),
      week: copyWeek(wm, DATA),
      announcement: copyAnnouncement(wm, DATA)
    }
  };
}

/* ---------------- 渲染 ---------------- */
function kindMeta(kind) {
  return ({
    duty: { label: "今日值日", cls: "k-duty", icon: "🧹" },
    saturday: { label: "周六大扫除", cls: "k-sat", icon: "🧽" },
    sunday: { label: "今日无固定值日", cls: "k-sun", icon: "☕" },
    skip: { label: "今日暂停值日提醒", cls: "k-skip", icon: "🎉" }
  })[kind] || { label: "", cls: "", icon: "" };
}

function renderView() {
  var v = VIEW, t = v.today, m = kindMeta(t.kind);
  var html = "";

  // 今日主卡
  html += '<section class="card hero-card ' + m.cls + '">';
  html += '<div class="hero-eyebrow"><span class="hero-ic">' + m.icon + "</span>" + m.label + "</div>";
  if (t.kind === "duty") {
    html += '<div class="hero-person">' + esc(t.person) + "</div>";
    html += '<div class="hero-sub">所属组别 <b>' + esc(t.group_name) + '</b> · 本周负责人 <b>' + esc(t.leader) + "</b></div>";
    html += '<ul class="check-list">' + CHECK_ITEMS.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>";
  } else if (t.kind === "saturday") {
    html += '<div class="hero-person">' + esc(t.group_name) + "</div>";
    html += '<div class="hero-sub">负责人 <b>' + esc(t.leader) + '</b> 请组织本组完成大扫除</div>';
    html += '<ul class="check-list">' + CHECK_ITEMS.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>";
  } else if (t.kind === "sunday") {
    html += '<div class="hero-sub">周日休息，明天见 👋</div>';
  } else if (t.kind === "skip") {
    html += '<div class="hero-person">' + esc(t.skip_name) + "</div>";
    html += '<div class="hero-sub">放假时间：<b>' + esc(t.skip_range) + "</b></div>";
    if (t.next_duty) html += '<div class="hero-sub">下一个值日日：<b>' + esc(t.next_duty.date) + " " + esc(t.next_duty.weekday) + " · " + esc(t.next_duty.person) + "</b></div>";
  }
  html += '<div class="hero-actions">';
  html += copyBtn("复制今日提醒", v.copy.today, t.kind === "skip" ? "ghost" : "primary");
  html += "</div></section>";

  // 明日预告
  var tm = v.tomorrow, tmm = kindMeta(tm.kind);
  html += '<section class="card mini-card">';
  html += '<div class="mini-head"><span>明日预告</span><span class="mini-date">' + esc(tm.weekday) + " " + esc(fmtMD(parseDate(tm.date))) + "</span></div>";
  if (tm.skipped) html += '<div class="mini-body muted">暂停：' + esc(tm.skip_name) + "</div>";
  else if (tm.kind === "saturday") html += '<div class="mini-body">周六大扫除 · <b>' + esc(tm.leader) + "</b></div>";
  else if (tm.kind === "sunday") html += '<div class="mini-body muted">周日，无固定值日</div>';
  else html += '<div class="mini-body">值日：<b>' + esc(tm.person) + "</b> · " + esc(tm.group_name) + "</div>";
  html += copyBtn("复制明日提醒", v.copy.tomorrow, "ghost");
  html += "</section>";

  // 本周安排
  html += '<section class="card"><div class="card-title">本周安排</div><div class="week-grid">';
  v.this_week.forEach(function (d) {
    var cls = d.skipped ? "wg-skip" : (d.kind === "saturday" ? "wg-sat" : "wg-duty");
    var main = d.skipped ? ("暂停·" + d.skip_name) : (d.kind === "saturday" ? ("大扫除·" + d.leader) : (d.person || "—"));
    html += '<div class="wg ' + cls + '"><div class="wg-wd">' + esc(d.weekday) + '</div><div class="wg-md">' + esc(fmtMD(parseDate(d.date))) + '</div><div class="wg-person">' + esc(main) + "</div></div>";
  });
  html += "</div></section>";

  // 下周预告
  var nw = v.next_week;
  html += '<section class="card"><div class="card-title">下周预告</div>';
  html += '<div class="next-info">负责组 <b>' + esc(nw.group_name) + '</b> · 负责人 <b>' + esc(nw.leader) + "</b></div>";
  html += '<div class="next-grid">' + ["周一", "周二", "周三", "周四", "周五"].map(function (dn, i) {
    return '<div class="ng"><span class="ng-d">' + dn + "</span><span>" + esc(nw.members[i] || "—") + "</span></div>";
  }).join("") + "</div></section>";

  // 提醒时间
  var wt = (v.config.weekday_times || []).filter(function (t) { return t.enabled; }).map(function (t) { return t.time; }).join("、") || "无";
  var st = (v.config.saturday_times || []).filter(function (t) { return t.enabled; }).map(function (t) { return t.time; }).join("、") || "无";
  html += '<section class="card"><div class="card-title">提醒时间</div>';
  html += '<div class="rt-row"><span>工作日值日提醒</span><b>' + esc(wt) + "</b></div>";
  html += '<div class="rt-row"><span>周六大扫除提醒</span><b>' + esc(st) + "</b></div>";
  html += '<div class="rt-tip">本网页不会自动发微信群，仅显示提醒并提供一键复制。</div></section>';

  // 复制区
  html += '<section class="card copy-card">';
  html += '<div class="card-title">一键复制（粘贴到微信群）</div>';
  html += '<div class="copy-grid">';
  html += copyBtn("复制今日提醒", v.copy.today, "primary");
  html += copyBtn("复制本周安排", v.copy.week, "");
  html += copyBtn("复制群公告", v.copy.announcement, "");
  html += "</div></section>";

  $("view").innerHTML = html;
  bindCopyButtons();
}

function copyBtn(label, text, variant) {
  var cls = "btn " + (variant === "primary" ? "btn-primary" : variant === "ghost" ? "btn-ghost" : "");
  return '<button class="' + cls + ' copy-btn" data-text="' + encodeURIComponent(text) + '">' + esc(label) + "</button>";
}
function bindCopyButtons() {
  document.querySelectorAll(".copy-btn").forEach(function (b) {
    b.onclick = function () { copyText(decodeURIComponent(b.getAttribute("data-text")), b); };
  });
}

/* ---------------- 复制 ---------------- */
function copyText(text, btn) {
  function done() { toast("已复制，可粘贴到微信群"); if (btn) { var o = btn.textContent; btn.textContent = "✓ 已复制"; setTimeout(function () { btn.textContent = o; }, 1500); } }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text, done); });
  } else { fallbackCopy(text, done); }
}
function fallbackCopy(text, done) {
  var ta = document.createElement("textarea");
  ta.value = text; ta.style.position = "fixed"; ta.style.opacity = "0";
  document.body.appendChild(ta); ta.select();
  try { document.execCommand("copy"); done(); } catch (e) { toast("复制失败，请手动长按选择", "err"); }
  document.body.removeChild(ta);
}

/* ---------------- 时钟 + 倒计时 ---------------- */
function tickClock() {
  var now = new Date();
  $("clockStr").textContent = now.toTimeString().slice(0, 8);
  updateBanner(now);
}
function updateBanner(now) {
  var banner = $("banner");
  if (!VIEW) return;
  var reminders = VIEW.reminders || [];
  var lead = (VIEW.config.notify_lead_minutes || 30);
  if (!reminders.length) { banner.hidden = true; return; }
  var cur = now.getHours() * 60 + now.getMinutes();
  var next = null;
  reminders.forEach(function (r) {
    var p = r.time.split(":"); var m = parseInt(p[0], 10) * 60 + parseInt(p[1], 10);
    if (m >= cur && (next === null || m < next.m)) next = { m: m, time: r.time, type: r.type };
  });
  var past = reminders.filter(function (r) { var p = r.time.split(":"); return (parseInt(p[0], 10) * 60 + parseInt(p[1], 10)) <= cur; });
  if (next) {
    var diff = next.m - cur;
    if (diff <= lead) {
      banner.hidden = false;
      banner.className = "banner warn";
      banner.textContent = "⏰ 距 " + next.time + " 值日提醒还有 " + diff + " 分钟";
    } else { banner.hidden = true; }
  } else if (past.length) {
    banner.hidden = false;
    banner.className = "banner info";
    banner.textContent = "✓ 今日值日提醒时间（" + past.map(function (r) { return r.time; }).join("、") + "）已到";
  } else { banner.hidden = true; }
}

/* ---------------- 浏览器通知 ---------------- */
function setupNotify() {
  var btn = $("btnNotify");
  if (!("Notification" in window)) return;
  btn.hidden = false;
  refreshNotifyBtn();
  btn.onclick = function () {
    if (Notification.permission === "granted") {
      scheduleNotifications();
      toast("浏览器提醒已开启（请保持页面打开）");
    } else if (Notification.permission !== "denied") {
      Notification.requestPermission().then(function (p) {
        refreshNotifyBtn();
        if (p === "granted") { scheduleNotifications(); toast("已开启浏览器提醒"); }
        else toast("未授权，无法弹出通知", "err");
      });
    } else { toast("浏览器通知已被禁用，请在浏览器设置中开启", "err"); }
  };
}
function refreshNotifyBtn() {
  var btn = $("btnNotify");
  if (!btn) return;
  btn.textContent = Notification.permission === "granted" ? "✓ 浏览器提醒已开启" : "开启浏览器提醒";
}
function scheduleNotifications() {
  NOTIFY_TIMERS.forEach(clearTimeout); NOTIFY_TIMERS = [];
  if (!VIEW) return;
  var now = new Date();
  VIEW.reminders.forEach(function (r) {
    var p = r.time.split(":");
    var t = new Date(now.getFullYear(), now.getMonth(), now.getDate(), parseInt(p[0], 10), parseInt(p[1], 10), 0, 0);
    var ms = t.getTime() - now.getTime();
    if (ms > 0 && ms < 12 * 3600 * 1000) {
      var to = setTimeout(function () {
        try {
          var n = new Notification("D404 实验室值日提醒", { body: VIEW.copy.today.split("\n").slice(0, 4).join("\n") });
        } catch (e) {}
      }, ms);
      NOTIFY_TIMERS.push(to);
    }
  });
}

/* ---------------- toast ---------------- */
function toast(msg, type) {
  var area = $("toast");
  var el = document.createElement("div");
  el.className = "toast " + (type === "err" ? "err" : "ok");
  el.textContent = msg;
  area.appendChild(el);
  setTimeout(function () { el.classList.add("out"); setTimeout(function () { el.remove(); }, 300); }, 2600);
}

/* ---------------- 启动 ---------------- */
function getQueryDate() {
  var d = new URLSearchParams(location.search).get("date");
  if (d && /^\d{4}-\d{2}-\d{2}$/.test(d)) return parseDate(d);
  return new Date();
}

async function init() {
  try {
    var [config, duty, skip, templates] = await Promise.all([
      fetch(ROOT + "data/config.json").then(function (r) { return r.json(); }),
      fetch(ROOT + "data/duty_groups.json").then(function (r) { return r.json(); }),
      fetch(ROOT + "data/skip_days.json").then(function (r) { return r.json(); }),
      fetch(ROOT + "data/templates.json").then(function (r) { return r.json(); })
    ]);
    DATA = { config: config, duty: duty, skip: skip, templates: templates };
  } catch (e) {
    $("view").innerHTML = '<div class="card"><div class="card-title">加载失败</div><div class="muted">无法读取 data 数据文件：' + esc(e.message) + "</div></div>";
    return;
  }

  $("labName").textContent = (DATA.config.lab_name || "D404 实验室") + " 值日看板";
  refresh();
  setupNotify();
  setInterval(tickClock, 1000); tickClock();
}

function refresh() {
  var d = getQueryDate();
  VIEW = buildView(d);
  $("dateStr").textContent = d.getFullYear() + " 年 " + (d.getMonth() + 1) + " 月 " + d.getDate() + " 日";
  $("weekdayStr").textContent = WEEKDAY_CN[(d.getDay() + 6) % 7];
  renderView();
}

window.addEventListener("DOMContentLoaded", init);
