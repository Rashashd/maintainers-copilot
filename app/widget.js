(function () {
  var me = document.currentScript;
  var widgetId = me.getAttribute('data-widget-id');
  var widgetHost = me.getAttribute('data-widget-host') || 'http://localhost:3000';
  var apiUrl = new URL(me.src).origin;

  if (!widgetId) {
    console.error('[widget.js] data-widget-id attribute is required');
    return;
  }

  // Offset each widget so multiple instances don't overlap.
  // Each closed bubble is 72px wide + 8px gap = 80px step.
  window.__widgetSlot = (window.__widgetSlot || 0);
  var slot = window.__widgetSlot++;
  var rightPx = slot * 80;

  var iframe = document.createElement('iframe');
  iframe.src =
    apiUrl +
    '/widget/embed/' +
    encodeURIComponent(widgetId) +
    '?widget_host=' +
    encodeURIComponent(widgetHost) +
    '&api=' +
    encodeURIComponent(apiUrl) +
    '&slot=' + slot;
  iframe.title = 'Chat widget';
  iframe.allow = 'microphone';

  iframe.style.cssText =
    'position:fixed;bottom:0;right:' + rightPx + 'px;width:72px;height:72px;' +
    'border:none;z-index:2147483647;transition:width 0.2s,height 0.2s;';
  iframe.dataset.widgetSlot = slot;
  document.body.appendChild(iframe);

  window.addEventListener('message', function (e) {
    if (!e.data || e.data.type !== 'widget-resize') return;
    // Match by slot so only the correct iframe resizes.
    if (e.data.slot !== undefined && e.data.slot !== slot) return;
    iframe.style.height = (e.data.height || 72) + 'px';
    iframe.style.width = e.data.expanded ? '380px' : '72px';
  });
})();
