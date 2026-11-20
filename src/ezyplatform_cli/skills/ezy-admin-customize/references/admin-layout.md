# EzyPlatform admin page: what your head and foot code lands in

Every admin page uses one layout (AdminLTE 3 + Bootstrap 4). Read this before writing CSS or JS.

## Where the fragments go

```
<html lang="en|vi|ar|..." dir="ltr|rtl">
<head>
  ...core CSS: Font Awesome 5 (all.min.css), Ionicons, Bootstrap Icons, flag-icons,
     adminlte(.rtl).min.css, DataTables, ezyadmin(.rtl).css...
  <!-- HEAD FRAGMENT HERE (after the core CSS, so your rules win at equal specificity) -->
  ...plugin style files...
  <script>const ezyadmin = { accessibleUris: {} };</script>
</head>
<body class="hold-transition sidebar-mini">
<div class="wrapper">
  <nav class="main-header navbar navbar-expand navbar-white navbar-light">...</nav>
  <aside class="main-sidebar ...">
    <a class="brand-link">...</a>
    <div class="sidebar"><nav><ul class="nav nav-pills nav-sidebar flex-column">
      <li class="nav-item [has-treeview]">
        <a class="nav-link [active]" href="/..."><i class="nav-icon fas fa-..."></i><p>Label <i class="right fas fa-angle-left"></i></p></a>
        <ul class="nav nav-treeview">...children...</ul>
      </li>
      <li class="nav-header">GROUP</li>
    </ul></nav></div>
  </aside>
  <div class="content-wrapper">
    <div class="content-header"> <h1 class="m-0 text-dark">Page title</h1> [#ezyAddNewButton] [#ezyEditButton] ...breadcrumb </div>
    <section class="content"><div id="pageContentBody">...page...</div></section>
  </div>
  <footer class="main-footer">...</footer>
</div>
<div class="right-toolbar">...</div>   (floating tool buttons; .right-toolbar-mini when collapsed)
...modals...
<script> jquery, jquery-ui, bootstrap.bundle, DataTables, moment, daterangepicker, adminlte, ezyclient, socket.js, public.js, ezyadmin.js, plugin scripts...
<!-- FOOT FRAGMENT HERE (everything above is loaded) -->
<script> $(document).ready(...) core init </script>
</body>
```

The fragments are added only to pages of a **signed-in** admin (EzySupport 0.6.1+): the sign-in, 2FA and setup pages are never changed, so a broken customization can always be undone after signing in.

When EzyArticle is active the fragments are rendered by its block renderer instead of raw output. Plain HTML/CSS/JS is kept as is; always run `verify` after `push` to be sure the page contains what you saved.

## Useful selectors

| What | Selector |
|---|---|
| Top bar | `.main-header` (`.navbar-nav` left, `.navbar-nav.ml-auto` right, `.navbar-search-block`) |
| Sidebar / brand | `.main-sidebar`, `.brand-link`, `.nav-sidebar`, `.nav-sidebar .nav-link`, `.nav-link.active`, `.nav-treeview`, `.nav-header`, `.nav-icon` |
| Collapsed sidebar | `body.sidebar-collapse`; mobile open sidebar `body.sidebar-open` |
| Content | `.content-wrapper`, `.content-header h1`, `#pageContentBody` |
| Cards, tables, forms | `.card`, `.card-header`, `.card-body`, `.table`, `.dataTables_wrapper`, `.form-control`, `.btn-primary`, `.badge` |
| Footer, tools | `.main-footer`, `.right-toolbar`, `.right-toolbar-item`, `.right-toolbar-mini` |
| Menu badges | `.nav-sidebar .badge` |

Prefer overriding through your own CSS variables (`:root { --custom-primary: ... }`) and a few strong rules over hundreds of `!important`. Use `!important` only against AdminLTE inline or high-specificity rules (`.main-sidebar`, `.content-wrapper` margins).

## JavaScript available in the foot

- `window.jQuery` / `$` (3.x), Bootstrap 4 JS (`$('#id').modal('show')`, tooltips), AdminLTE (`$('[data-widget="pushmenu"]').PushMenu('toggle')`).
- `ezyadmin`: `ezyadmin.escapeHtml(value)` (returns `''` for falsy values, pass `String(value)` for numbers), `ezyadmin.isRtl()`, `ezyadmin.messages` (translated texts of the page), `ezyadmin.shortToast('bg-success', text)`, `ezyadmin.formatTimeStamp(ms, format)`. Do not declare your own HTML escape helper.
- Current language: `document.documentElement.lang`; direction: `document.documentElement.dir` or `getComputedStyle(document.documentElement).direction`.
- The admin uses session cookies: `fetch('/api/v1/...', {credentials: 'same-origin'})` calls admin APIs as the signed-in admin. Do not call write APIs from customization code unless the user asked for that feature.

## Rules that avoid broken admins

1. Wrap everything in an IIFE, guard every element lookup, never throw at top level. A failing script must leave the default admin usable.
2. Scope big changes under a body class you add (`document.body.classList.add('custom-x')`) so CSS only applies when your script ran.
3. Hide original elements (`display: none`) instead of removing them: core scripts still look for them.
4. Pages can be shown inside iframes (other customizations, previews). Detect `window.self !== window.top` before building a whole new chrome.
5. `localStorage` / `sessionStorage` can throw: wrap in try/catch, prefix keys (`customAdmin...`).
6. Right-to-left: use logical properties (`margin-inline-start`, `padding-inline-end`, `inset-inline-start`, `text-align: start`). For values that cannot be logical (transforms, background positions, absolute offsets) add `[dir="rtl"] ...` overrides. JS that positions popups must read the direction. Text the admin types (inputs, table cells) keeps `unicode-bidi: plaintext`.
7. Mobile (≤ 767.98 px): the sidebar becomes an overlay. Test it; turn off desktop-like experiences on small screens (`matchMedia('(max-width: 767.98px)')`).
8. Texts you add: keep a small dictionary per language (`en`, `vi`, ...) chosen from `document.documentElement.lang`, English as fallback.
9. Fonts: add a font that covers every admin language (for example `Be Vietnam Pro` + `Noto Sans Arabic`) and keep the default stack as fallback.
10. Keep dark/light consistent: if you change backgrounds, also change text, borders, inputs, dropdowns, modals, tables and DataTables paging.
11. Icons: Font Awesome 5 (`fas fa-...`, `far`, `fab`) and Bootstrap Icons (`bi bi-...`) are already loaded.

## Small recipes

Brand color and font (head):

```html
<!-- admin-customization: brand -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Be+Vietnam+Pro:wght@400;500;600;700&family=Noto+Sans+Arabic:wght@400;600&display=swap">
<style id="customAdminBrand">
:root { --custom-primary: #7c3aed; --custom-primary-hover: #6d28d9; --custom-sidebar-bg: #2e1065; }
body, .btn, .form-control, .nav-sidebar .nav-link { font-family: 'Be Vietnam Pro', 'Noto Sans Arabic', 'Source Sans Pro', sans-serif; }
.btn-primary { background: var(--custom-primary); border-color: var(--custom-primary); }
.btn-primary:hover { background: var(--custom-primary-hover); border-color: var(--custom-primary-hover); }
.main-sidebar { background: var(--custom-sidebar-bg) !important; }
.nav-sidebar .nav-link.active { background: var(--custom-primary) !important; }
</style>
```

A note in the header (foot):

```html
<!-- admin-customization: header note -->
<script id="customAdminHeaderNote">
(function () {
    var nav = document.querySelector('.main-header .navbar-nav');
    if (!nav) { return; }
    var texts = { en: 'Staging site', vi: 'Trang thử nghiệm' };
    var lang = (document.documentElement.lang || 'en').split('-')[0];
    var li = document.createElement('li');
    li.className = 'nav-item d-none d-sm-inline-block';
    li.innerHTML = '<span class="nav-link text-danger font-weight-bold">'
        + ezyadmin.escapeHtml(texts[lang] || texts.en) + '</span>';
    nav.appendChild(li);
})();
</script>
```

The complete desktop experience in `examples/desktop/` shows the patterns for large changes.
