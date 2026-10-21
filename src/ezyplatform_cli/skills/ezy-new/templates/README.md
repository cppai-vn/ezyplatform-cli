# User Guide

## Installing EzyPlatform

To use this plugin, you need to install EzyPlatform first.

If you only want to install EzyPlatform in a localhost environment, you can refer to the guide:
[Install EzyPlatform](https://youngmonkeys.org/ezyplatform/guides/install-ezyplatform)

If you want to deploy EzyPlatform on a server with a domain name, you can refer to the guide:
[Deploy EzyPlatform](https://youngmonkeys.org/ezyplatform/guides/deploy-ezyplatform-on-ubuntu)

---

## Environment Setup

First, you need to configure your environment in the `environment.json` file.
The environment being used must have the property `"default": true`.

You need to provide the following values:

* `admin_url`: The URL to your EzyPlatform admin page, for example:
  `https://admin.example.com`
* `admin_access_token`: Your access token for the EzyPlatform admin page.
  You can access your profile page at `<admin_url>/admins/me`, for example:
  `https://admin.example.com/admins/me`
  Then find the `Access Token` field, click to reveal it, enter your password, and copy the access token into the `admin_access_token` property.

If you do not need an environment, you may remove it. However, you must keep at least one environment with the property `"default": true`.

---

## Sync Page Fragments

### Sync All Page Fragments

You can right-click in the Explorer panel and click the `Sync Page Fragment` menu item to sync all page fragments from the server to your local machine.

### Sync a Specific Page Fragment

After syncing all page fragments, you can sync a specific page fragment by right-clicking on the corresponding folder.

For example, if your page fragment folder is:
`page-fragments/common/header`

Right-click the `header` folder. A menu item called `Sync Page Fragment Folder` will appear. Click it to retrieve all content of that page fragment from the server.

### Sync Individual Page Fragment Files

After syncing a page fragment, you can later refresh individual components such as:

* `content.html`
* `foot.html`
* `head.html`
* `meta.json`

Right-click on any of these files, and you will see the `Refresh Page Fragment File` menu item. Click it to fetch the latest content from the server.

---

## Create a Page Fragment

You can create a page fragment by creating the following folder structure:

```
page-fragments
    page_name
        fragment-name
            content.html
            foot.html
            head.html
            meta.json
```

Example:

```
page-fragments
    common
        header
            content.html
            foot.html
            head.html
            meta.json
```

For the `meta.json` file, you need to create it with content similar to the following example:

```json
{
  "title": "Common header fragment",
  "contentType": "HTML",
  "status": "DRAFT"
}
```

If the page fragment already exists on the server, you can sync its content as described above.

To learn more about the purpose of each file, refer to the `AGENTS.md` file.

---

## Create a Page

You can create a page by creating a folder under `pages` and adding the following files:

```
pages
    home
        content.html
        foot.html
        head.html
        meta.json
```

For the `meta.json` file, you need to create it with content similar to the following example:

```json
{
  "slug": "example-page",
  "title": "Example Page",
  "summary": "",
  "featuredImageName": "",
  "pageType": "PAGE",
  "contentType": "HTML",
  "status": "DRAFT",
  "publishedAt": "2026-01-15 09:30:00",
  "password": "",
  "metadata": {}
}
```

`publishedAt` is optional and is written as `yyyy-MM-dd HH:mm:ss` in your local time zone; it is converted to a timestamp when the page is saved or published, and written back in the same format when you sync from the server.

`password` is also optional and protects the page with a password. Syncing brings it back from the server, but a value you already have locally is kept as is. Note that the server stores and returns the password **hashed**, so what you see after a sync is the hash, not your original text: leave it untouched to keep the current password, replace it with plain text to set a new one, and delete the field (or leave it empty) to remove the password on the next save.

To learn more about the purpose of each file, refer to the `AGENTS.md` file.

---

## Sync Page Content

After creating a page, you can right-click on the page folder (for example, `home`).
The `Sync Page Folder` menu item will appear. Click it to sync all page content.

---

## Sync Individual Page Files

After syncing a page, you can refresh individual components:

* `content.html`
* `foot.html`
* `head.html`
* `meta.json`

Right-click on any of these files and click the `Refresh Page File` menu item to fetch the latest content from the server.

---

## Page Types

The available page types include:

1. **PAGE**: A standard page that shares the same header and footer with other pages. Put page body HTML in `content.html`, page-specific head markup or CSS in `head.html`, and page-specific JavaScript in `foot.html`.
2. **STANDALONE_PAGE**: An independent blank page that does not share the header and footer with other pages. You must provide the full HTML, CSS, and JavaScript in `content.html` only. Do not generate code into `head.html` or `foot.html`.
3. **TEMPLATED_PAGE**: A page that shares the header and footer with other pages but allows you to dynamically set the page meta, for example:

```html
<th:block
  th:with="slug=${ezyfunctions.call('get_request_parameter', '{name:'slug'}')}, pageTitle=${ezyfunctions.call('get_post_title_by_slug', '{slug:'' + slug + ''}')}">
  <title>[[${pageTitle}]]</title>
  <meta name="title" th:content="${pageTitle}" />
  <meta property="og:title" th:content="${pageTitle}" />
  <meta property="og:site_name" th:content="${pageTitle}" />
</th:block>
```

---

## Create a Post

You can create a post by creating a folder under `posts` and adding the following files:

```
posts
    hello-world
        content.html
        foot.html
        head.html
        meta.json
```

For the `meta.json` file, you need to create it with content similar to the following example:

```json
{
  "slug": "hello-world",
  "title": "Hello World",
  "summary": "",
  "featuredImageName": "",
  "postType": "POST",
  "contentType": "HTML",
  "status": "DRAFT",
  "publishedAt": "2026-01-15 09:30:00",
  "password": "",
  "metadata": {}
}
```

`publishedAt` and `password` work the same way as for pages: `publishedAt` uses the `yyyy-MM-dd HH:mm:ss` local-time format, and `password` is synced back from the server as a hash unless you already have a local value — keep it untouched to preserve the current password, or clear the field to remove it.

To learn more about the purpose of each file, refer to the `AGENTS.md` file.

## Sync Post Content

After creating a post, you can right-click on the post folder (for example, `hello-world`).
The `Sync Post Folder` menu item will appear. Click it to sync all post content.

## Sync Individual Post Files

After syncing a post, you can refresh individual components:

* `content.html`
* `foot.html`
* `head.html`
* `meta.json`

Right-click on any of these files and click the `Refresh Post File` menu item to fetch the latest content from the server.

---

## Multi-language Content (`<lang>`)

Page fragments, pages, and posts support per-language variants of their files: `content.<lang>.html`, `head.<lang>.html`, `foot.<lang>.html`, `meta.<lang>.json` (for example `content.vi.html`, `meta.en.json`). Add the localized file next to the default one — you don't need to duplicate the whole folder.

* Syncing, publishing, and previewing a localized file uses the `lang` parsed from its own file name.
* `title`/`summary` fall back to the default `meta.json` when missing from `meta.<lang>.json`; `content`/`additionalHead`/`additionalFoot` fall back to the default `.html` file when the localized one is missing.
* Previewing a localized page or post appends `?lang=<lang>` to the preview URL.

---

# Mail Templates

Mail templates live under `mail-templates` and are used by EzyMail to send emails (welcome emails, password reset, notifications, etc.). This requires the EzyMail plugin.

## Create a Mail Template

Create a folder under `mail-templates` and add the following files:

```
mail-templates
    welcome-email
        title.html
        content.html
        meta.json
```

* `title.html`: the mail subject template.
* `content.html`: the mail body template.
* `meta.json`: metadata, for example:

```json
{
  "contentType": "HTML",
  "status": "DRAFT",
  "parameters": {
    "userName": "John",
    "activationLink": "https://example.com/activate/123"
  }
}
```

You may reference variables in `title.html` and `content.html` using `${variableName}` or `{{variableName}}`. Add a sample value for each variable to `meta.json`'s `parameters` field so the preview can render real-looking content; `parameters` is only used locally for preview and is not sent to the server.

If the mail template already exists on the server, sync its content as described below instead of guessing its current values.

## Sync Mail Template Content

Right-click on the mail template folder (for example, `welcome-email`) and click the `Sync Mail Template Folder` menu item to fetch `title.html`, `content.html`, and `meta.json` (`contentType`, `status`) from the server. This overwrites the current local content but keeps your local `parameters`, since the server has no concept of preview parameters.

## Sync Individual Mail Template Files

Right-click on `title.html`, `content.html`, or `meta.json` and click the `Refresh Mail Template File` menu item to fetch just that file from the server.

## Preview Mail Template

Right-click in the editor, on the mail template folder, or on any file within it, and click `Preview`. This saves the mail template files first, then opens the browser preview with the sample values from `meta.json`'s `parameters` field substituted into the placeholder variables.

## Publish Mail Template

Right-click in the editor, on the mail template folder, or on any file within it, and click `Publish Content To Server` to save `title.html`, `content.html`, and the `contentType`/`status` from `meta.json` to the server.

---

# Content Templates

Content templates live under `content-templates/<template_type>/<template_name>` and are used by EzySupport (ticket replies, notifications, canned responses, etc.). This requires the EzySupport plugin.

## Create a Content Template

`template_type` is a free-form folder name you choose to group related templates (for example `ticket-reply`, `notification`, `canned-response`) — the server does not restrict it to a fixed list.

Create a folder under `content-templates/<template_type>` and add the following files:

```
content-templates
    ticket-reply
        welcome-reply
            title.html
            content.html
            meta.json
```

* `title.html`: the template title.
* `content.html`: the template body.
* `meta.json`: metadata, for example:

```json
{
  "contentType": "HTML",
  "status": "DRAFT",
  "parameters": {
    "userName": "John"
  }
}
```

You may reference variables in `title.html` and `content.html` using `${variableName}` or `{{variableName}}`. Add a sample value for each variable to `meta.json`'s `parameters` field so the preview can render real-looking content; `parameters` is only used locally for preview and is not sent to the server.

If the content template already exists on the server, sync its content as described below instead of guessing its current values.

## Sync Content Template Content

Right-click on the content template folder (for example, `welcome-reply`) and click the `Sync Content Template Folder` menu item to fetch `title.html`, `content.html`, and `meta.json` (`contentType`, `status`) from the server. This overwrites the current local content but keeps your local `parameters`, since the server has no concept of preview parameters.

## Sync Individual Content Template Files

Right-click on `title.html`, `content.html`, or `meta.json` and click the `Refresh Content Template File` menu item to fetch just that file from the server.

## Preview Content Template

Right-click in the editor, on the content template folder, or on any file within it, and click `Preview`. This saves the content template files first, then opens the browser preview with the sample values from `meta.json`'s `parameters` field substituted into the placeholder variables.

## Publish Content Template

Right-click in the editor, on the content template folder, or on any file within it, and click `Publish Content To Server` to save `title.html`, `content.html`, and the `contentType`/`status` from `meta.json` to the server.

---

# Terms

Terms live under `terms/<term_type>/<term_slug>` and are used by EzyArticle to classify pages and posts (categories, tags, etc.).

## Create a Term

`term_type` is a free-form folder name you choose to group related terms (for example `category`, `tag`) — the server does not restrict it to a fixed list.

Create a folder under `terms/<term_type>` and add the following files:

```
terms
    category
        announcements
            description.txt
            meta.json
```

* `description.txt`: the term description.
* `meta.json`: metadata, for example:

```json
{
  "name": "Announcements",
  "featuredImageName": "",
  "displayOrder": 0,
  "status": "DRAFT"
}
```

If the term already exists on the server, sync its content as described below instead of guessing its current values.

## Sync Term Content

Right-click on the term folder (for example, `announcements`) and click the `Sync Term Folder` menu item to fetch `description.txt` and `meta.json` (`name`, `featuredImageName`, `displayOrder`, `status`) from the server.

## Sync Individual Term Files

Right-click on `description.txt` or `meta.json` and click the `Refresh Term File` menu item to fetch just that file from the server.

## Publish Term

Right-click in the editor, on the term folder, or on any file within it, and click `Publish Content To Server` to save `description.txt` and the `name`/`featuredImageName`/`displayOrder`/`status` from `meta.json` to the server.

---

# I18n Messages

I18n message files live under `admin/messages` or `web/messages` and are used by EzySupport. This requires the EzySupport plugin.

## Create an I18n Message File

Create a folder named `admin` or `web`, add a `messages` subfolder, and add a `.properties` file:

```
admin
    messages
        messages.properties
        messages_vi.properties
```

* `messages.properties`: the default messages (no language suffix).
* `messages_<lang>.properties`: messages for language `<lang>` (for example `messages_vi.properties`).

Each file is a standard Java `.properties` file:

```properties
common.hello=Hello
common.goodbye=Goodbye
```

Keys and values are trimmed before publishing, so `key = value` (with extra spaces around `=`) works the same as `key=value`.

## Publish I18n Messages

Right-click in the editor or on a `messages.properties` / `messages_<lang>.properties` file and click `Publish Content To Server` to save all the keys in that file to the server for the corresponding `target` (`admin` or `web`) and language.

---

# Media

You need to upload the media to the `/api/v1/media` directory and use the path `/api/v1/media/<media_name>` (for example: `/api/v1/media/hello-world.png`) in your source code.

For CSS and JavaScript files in `/api/v1/media`, use `ezy:mhref` and `ezy:msrc` so EzyArticle can automatically append `?v=<latest_update_time>` and prevent clients from using cached old versions.

```html
<link rel="stylesheet" ezy:mhref="/api/v1/media/style.css" />
<script ezy:msrc="/api/v1/media/app.js"></script>
```

**Note**: The media name should match the expression `^[a-zA-Z0-9_-]+(.[a-zA-Z0-9_-]+)*$`, which means it may only contain English letters, numbers, dots (`.`), hyphens (`-`), or underscores (`_`), example `hello-world.png`. Empty files, files containing only whitespace, or files whose content is exactly `{"token":"invalid"}`, are not uploaded.

## Sync Media

Right-click a media file in `api/v1/media`, or right-click in the editor of an open media file, and choose `Sync Media` to download it from the server and overwrite the current local file. You'll be asked to confirm before the content is overwritten.

## Download Media From a Link

Right-click the `api/v1/media` folder and choose `Download Media From Link`. When your clipboard already holds a link, a dialog shows it and offers `Download` or `Enter another link`; otherwise you are asked to type the link, and pressing Enter starts the download.

Links to this environment (`<admin_url>/api/v1/media/<file_name>` or `<web_url>/api/v1/media/<file_name>`) are fetched with your access token for the admin one and without it for the web one, then saved as `<file_name>`. Since that media is already on the server, nothing is uploaded back.

Any other link is downloaded as an external file. The extension checks that the link really points to a file rather than a web page, works out a name from `Content-Disposition` or from the link itself (asking you to type one when it cannot), saves it, and then uploads it to your server — asking whether to overwrite when the media name already exists there.

In both cases you are asked before an existing local file is overwritten.

This also works without the menu: if a file inside `api/v1/media` contains nothing but a link to this environment's media, saving it downloads the real media instead of uploading the link as a text file, and the leftover file is removed when its name differs.

## Copy Media URL

Right-click a media file in `api/v1/media` and choose `Copy Admin URL` or `Copy Web URL` to copy its full URL to the clipboard, ready to paste into your source code.

## Public / Private Media

Right-click a media file in `api/v1/media` and choose `Toggle Public Media` to switch it between public and private. You'll be shown its current status and asked to confirm before it changes.

# Preview

To preview a page or post, save its content first. Then right-click in the editor, on the page/post folder, or on any file within it. The `Preview Page` menu item will appear.

Click it, and the preview will open in your default browser.

Note:
Saving a page fragment file, a page file, or a post file in the editor only saves it to history and does not affect the currently published content on the server.

---

# Page & Post URLs

Right-click in the editor, on the page/post folder, or on any file within it, and choose `Get Page Admin URL` or `Get Post Admin URL` to save the files and copy `<admin_url>/ezyarticle/pages/{slug}/view[?lang=<language>]` or `<admin_url>/ezyarticle/posts/{slug}/view[?lang=<language>]` to the clipboard.

For pages only, choose `Get Page Web URL` to save the files and copy `<web_url>/{slug}[?lang=<language>]` to the clipboard, where `web_url` is fetched from the server.

---

# Publish

When you are satisfied with the preview result, you can publish the page or post.

For a page fragment: Right-click in the editor, on the page fragment folder, or on any file within the page fragment. The `Publish Content To Server` menu item will appear.

For a page or post: Right-click in the editor, on the page/post folder, or on any file within it. The `Publish Content To Server` menu item will appear.

Click it to publish the content. End users will then see the updated page or post.

---

# Recommendation

You should create a Git repository to manage file versions alongside storing them on your EzyPlatform server. This allows you to leverage the full power of Git for version control.

---

# 📬 Support & Resources

* 🌐 Official Website: [https://ezyplatform.com](https://ezyplatform.com)
* 📘 Documentation: [https://ezyplatform.com/market/items/ezyarticle?tab=docs](https://ezyplatform.com/market/items/ezyarticle?tab=docs)
* 🐛 Issue Tracking: [https://github.com/youngmonkeys/ezyarticle-visual-studio-code-extension](https://github.com/youngmonkeys/ezyarticle-visual-studio-code-extension)
* 💬 Q&A Community: [https://stackask.com/](https://stackask.com/)
* 📧 Support Email: [contact@youngmonkeys.org](mailto:contact@youngmonkeys.org)
