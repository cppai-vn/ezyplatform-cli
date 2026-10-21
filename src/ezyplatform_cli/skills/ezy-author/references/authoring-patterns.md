# Authoring patterns proven on live EzyPlatform sites

Source: cpp.ai.vn (STANDALONE_PAGE home + `cppai/theme|header|footer` fragments), 2026-10.

## Fragment split for a branded site

| Fragment | Regions used | Holds |
|---|---|---|
| `<ns>/theme` | head, foot | pre-paint theme script, font links, CSS tokens + all shared component CSS; foot = theme toggle behaviour |
| `<ns>/header` | head, content, foot | header CSS; markup with server menu; menu/mobile JS |
| `<ns>/footer` | head, content | footer CSS; markup |

Page `content.html` (STANDALONE_PAGE) includes `theme/header/footer :: head` in `<head>`, `header :: content` first in `<body>`, `footer :: content` last, then `theme :: foot` and `header :: foot` before `</body>`. Use a namespace folder (`cppai/`) so the platform theme's `common/*` fragments stay untouched.

## Light/dark theme

- Light tokens on `:root`; dark overrides the same variable names under `:root[data-theme="dark"]` and `@media (prefers-color-scheme: dark) { :root:not([data-theme]) {...} }`.
- A tiny inline script in `theme :: head` sets `data-theme` from `localStorage` before paint (no flash).
- Separate tokens for accent **fill** (`--bright`) and accent **text** (`--orange`): an orange that works as a fill on light backgrounds usually fails text contrast.
- Always-dark blocks: reuse the dark token set on a class (`.invert`, `.stage`) to give light mode contrast rhythm without a third palette.

## Server menu in a fragment (Thymeleaf)

```html
<nav th:with="headerPost=${ezyfunctions.call('get_post_by_slug', '{slug:&quot;<fragment-slug>&quot;}')}">
  <a th:each="item : ${headerPost.menu.menuItems}"
     th:attr="data-menu-href=${item.customLink}, data-menu-order=${item.orderValue}"
     th:text="${#strings.startsWith(item.linkText, 'cppai_') ? #messages.msg(item.linkText) : item.linkText}"></a>
</nav>
```

The fragment post must stay linked to the menu (`menuId`, gotcha 6). Labels that start with a site prefix are i18n keys resolved by `#messages.msg`.

## Language switch

`?lang=vi|en` selects the language; header JS keeps the parameter on internal links. Default language works without the parameter.

## Data-heavy sections (projects, team, partners)

Generate the VI and EN section HTML from one data structure (script in scratch or `.artifacts/`), then splice into both content files. Keeps the languages structurally identical and makes source-of-truth updates (e.g. a new capability profile) a data edit.

## Motion that reads clearly

- Label every animated vignette with what it depicts ("Automated sales flow"), and use real words in it (step names, field names) instead of abstract blocks.
- Loop short (4–6 s) CSS keyframes; stagger with `animation-delay`.
- No opacity-based scroll reveal on content (gotcha 11).
