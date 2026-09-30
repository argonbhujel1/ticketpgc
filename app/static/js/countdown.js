(function () {
  function tick(el) {
    var target = el.getAttribute('data-target');
    if (!target) return;
    var end = new Date(target).getTime();
    if (isNaN(end)) return;
    var now = Date.now();
    var diff = Math.max(0, end - now);
    var s = Math.floor(diff / 1000);
    var d = Math.floor(s / 86400); s -= d * 86400;
    var h = Math.floor(s / 3600); s -= h * 3600;
    var m = Math.floor(s / 60); s -= m * 60;
    var set = function (sel, val) {
      var n = el.querySelector(sel);
      if (n) n.textContent = String(val).padStart(2, '0');
    };
    set('[data-d]', d);
    set('[data-h]', h);
    set('[data-m]', m);
    set('[data-s]', s);
  }
  function run() {
    document.querySelectorAll('.js-countdown').forEach(tick);
  }
  run();
  setInterval(run, 1000);
})();
