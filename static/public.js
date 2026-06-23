/* D404 值日看板 · 公共页脚本（v3，数据源 = 服务端 /api/public，非 localStorage） */
"use strict";
var $ = function (id) { return document.getElementById(id); };
var WEEKDAYS = ["周一", "周二", "周三", "周四", "周五"];

function esc(s) {
  return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
    return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
  });
}
function fmtMD(ds) { var p = ds.split("-"); return p[1] + "-" + p[2]; }
function toast(msg, type) {
  var area = $("toast"); if (!area) return;
  var el = document.createElement("div");
  el.className = "toast " + (type === "err" ? "err" : "ok");
  el.textContent = msg; area.appendChild(el);
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

function kindMeta(kind) {
  return ({
    duty: { label: "今日值日", cls: "k-duty", icon: "🧹" },
    saturday: { label: "周六大扫除", cls: "k-sat", icon: "🧽" },
    sunday: { label: "今日无固定值日", cls: "k-sun", icon: "☕" },
    skip: { label: "今日暂停值日", cls: "k-skip", icon: "🎉" }
  })[kind] || { label: "", cls: "", icon: "" };
}

function heroHtml(t, checkItems) {
  var m = kindMeta(t.kind);
  var h = '<section class="card hero-card ' + m.cls + (t.skip_kind === "custom" ? " custom" : "") + '">';
  h += '<div class="hero-eyebrow"><span class="hero-ic">' + m.icon + "</span>" + m.label;
  if (t.manual) h += ' <span class="hero-tag">手动设置</span>';
  h += "</div>";
  if (t.kind === "duty") {
    h += '<div class="hero-person">' + esc(t.person) + "</div>";
    h += '<div class="hero-sub">所属组别 <b>' + esc(t.group_name) + '</b> · 本周负责人 <b>' + esc(t.leader) + "</b></div>";
    h += '<ul class="check-list">' + checkItems.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>";
  } else if (t.kind === "saturday") {
    h += '<div class="hero-person">' + esc(t.group_name) + "</div>";
    h += '<div class="hero-sub">负责人 <b>' + esc(t.leader) + "</b> 请组织本组完成大扫除</div>";
    h += '<ul class="check-list">' + checkItems.map(function (c) { return "<li>" + esc(c) + "</li>"; }).join("") + "</ul>";
  } else if (t.kind === "sunday") {
    h += '<div class="hero-sub">周日休息，明天见 👋</div>';
  } else {
    h += '<div class="hero-person">' + esc(t.skip_name) + "</div>";
    if (t.skip_range) h += '<div class="hero-sub">时间范围：<b>' + esc(t.skip_range) + "</b></div>";
    if (t.next_duty) h += '<div class="hero-sub">下一个值日日：<b>' + esc(t.next_duty.date) + " " + esc(t.next_duty.weekday) + " · " + esc(t.next_duty.person) + "</b></div>";
  }
  h += "</section>";
  return h;
}

function copyBtn(label, text, variant) {
  var cls = "btn " + (variant === "primary" ? "btn-primary" : variant === "ghost" ? "btn-ghost" : "");
  return '<button class="' + cls + ' copy-btn" data-text="' + encodeURIComponent(text) + '">' + esc(label) + "</button>";
}

async function render() {
  try {
    var v = await fetch("/api/public", { cache: "no-store" }).then(function (r) { return r.json(); });
  } catch (e) {
    $("view").innerHTML = '<div class="card"><div class="card-title">加载失败</div><div class="muted">' + esc(e.message) + "</div></div>";
    return;
  }
  $("labName").textContent = (v.lab_name || "D404 实验室") + " 值日看板";
  var html = "";
  html += heroHtml(v.today, v.check_items || []);

  // 明日预告
  var tm = v.tomorrow, tmm = kindMeta(tm.kind);
  html += '<section class="card mini-card">';
  html += '<div class="mini-head"><span>明日预告</span><span class="mini-date">' + esc(tm.weekday) + " " + esc(fmtMD(tm.date)) + "</span></div>";
  if (tm.skipped) html += '<div class="mini-body muted">暂停：' + esc(tm.skip_name) + "</div>";
  else if (tm.kind === "saturday") html += '<div class="mini-body">周六大扫除 · <b>' + esc(tm.leader) + "</b></div>";
  else if (tm.kind === "sunday") html += '<div class="mini-body muted">周日，无固定值日</div>';
  else html += '<div class="mini-body">值日：<b>' + esc(tm.person) + "</b> · " + esc(tm.group_name) + "</div>";
  html += "</section>";

  // 本周安排
  html += '<section class="card"><div class="card-title">本周安排</div><div class="week-grid">';
  v.this_week.forEach(function (d) {
    var cls = d.skipped ? "wg-skip" : (d.kind === "saturday" ? "wg-sat" : "wg-duty");
    var main = d.skipped ? ("暂停·" + d.skip_name) : (d.kind === "saturday" ? ("大扫除·" + d.leader) : (d.person || "—"));
    html += '<div class="wg ' + cls + '"><div class="wg-wd">' + esc(d.weekday) + '</div><div class="wg-md">' + esc(fmtMD(d.date)) + '</div><div class="wg-person">' + esc(main) + "</div></div>";
  });
  html += "</div></section>";

  // 下周预告
  var nw = v.next_week;
  html += '<section class="card"><div class="card-title">下周预告</div>';
  html += '<div class="next-info">负责组 <b>' + esc(nw.group_name) + '</b> · 负责人 <b>' + esc(nw.leader) + "</b></div>";
  html += '<div class="next-grid">' + WEEKDAYS.map(function (dn, i) {
    return '<div class="ng"><span class="ng-d">' + dn + "</span><span>" + esc(nw.members[i] || "—") + "</span></div>";
  }).join("") + "</div></section>";

  // 复制区
  html += '<section class="card copy-card"><div class="card-title">一键复制</div><div class="copy-grid">';
  html += copyBtn("复制今日提醒", v.copy.today, "primary");
  html += copyBtn("复制本周安排", v.copy.week, "");
  html += "</div></section>";

  // 公网分享链接（仅公网模式开启且已设置时显示）
  if (v.public_mode_enabled && v.public_url) {
    html += '<section class="card share-card"><div class="card-title">分享链接</div>';
    html += '<div class="share-url">' + esc(v.public_url) + "</div>";
    html += copyBtn("复制分享链接", v.public_url, "primary");
    html += "</section>";
  }

  $("view").innerHTML = html;
  document.querySelectorAll(".copy-btn").forEach(function (b) {
    b.onclick = function () { copyText(decodeURIComponent(b.getAttribute("data-text"))); };
  });
}

function tickClock() {
  var now = new Date();
  $("clockStr").textContent = now.toTimeString().slice(0, 8);
}

async function init() {
  await render();
  setInterval(render, 60000);   // 每分钟刷新，保证看到最新配置
  tickClock(); setInterval(tickClock, 1000);
}
window.addEventListener("DOMContentLoaded", init);
