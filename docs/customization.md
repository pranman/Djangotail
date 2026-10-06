# Customize the starter

## Pages and layout

The home view renders `MainApp/templates/MainApp/home.html`, which extends
`templates/base.html`. Change the home content first, then adapt the shared
header, navigation and footer. The layout provides `title`, `extra_head`,
`content` and `scripts` blocks. New application templates should use a namespace
such as `your_app/page.html`; connect their views in `Project/urls.py`.

The demonstration form only updates text in the current browser. It does not
send or store the entered name. Replace it with your own Django form/view when
adding application behavior, including CSRF protection for POST requests.

## Tailwind CSS 4

The stylesheet is `theme/static_src/src/styles.css`. Its `@source` directives
scan the root `templates/` directory, top-level apps' `templates/` directories
and application static JavaScript. Add a source when introducing a different
directory layout. Source paths are relative to the stylesheet.

Use complete utility class names, for example `bg-red-500`, in scanned source.
Do not assemble fragments such as `bg-{{ color }}-500`; a static CSS scan cannot
infer the resulting class. Map variants to complete names or explicitly include
the needed classes.

Tailwind 4 uses CSS configuration. There is no active `tailwind.config.js` or
PostCSS configuration file. Follow the [Tailwind documentation](https://tailwindcss.com/docs)
when adding tokens, utilities or plugins, and retain the committed npm lockfile.

## daisyUI 5 themes

The CSS plugin config enables all three advertised themes:

```css
@plugin "daisyui" {
  themes: light --default, cupcake;
}

@plugin "daisyui/theme" {
  name: "dark";
  prefersdark: true;
  --color-primary-content: #fff;
}
```

The demo deliberately starts in light mode when there is no saved choice. Its
selector changes the root `data-theme` attribute and stores the choice locally
under `starter-theme`. It continues to work when browser storage is unavailable.
The JavaScript allowlist and selector options live in
`MainApp/static/MainApp/js/demo.js` and `MainApp/templates/MainApp/home.html`.

When adding a theme, update the CSS, selector and JavaScript allowlist together,
then add a browser assertion proving that its computed palette changes.
Theme configuration alone does not prove a working UI. The dark theme includes
a primary-text contrast override in the stylesheet; preserve or recheck it
when changing colors. See the [daisyUI theme reference](https://daisyui.com/docs/themes/).

Tailwind `dark:` utilities follow the selected dark theme via the explicit
custom variant in the stylesheet. The demo's daisyUI classes must target version
5; older classes such as `form-control` are not part of this configuration.

## Validate a change

Keep `python bootstrap.py dev` running while editing. Check desktop and narrow
layouts, keyboard navigation and all themes. Run the frontend/compiler and
[browser checks](browser-checks.md) before updating the
[README preview](images/README.md). Assets are local and deterministic; avoid
making the initial demo depend on remote image services or CDN scripts.
