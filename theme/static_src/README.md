# Frontend build

This directory is the only npm project. Use a current patch release of Node.js
22 (minimum 22.10) or 24 LTS, with npm 10 or 11. `.nvmrc` selects Node 24.

From the repository root:

```sh
npm --prefix theme/static_src ci
npm --prefix theme/static_src run build
npm --prefix theme/static_src start
```

`ci` installs the committed lockfile. `build` emits minified production CSS;
`start` watches CSS and template edits, including when launched with closed stdin.
Stop the watcher with Ctrl+C. CSS rebuilding is separate from browser refreshing.

With the Python environment installed, `python manage.py tailwind build` and
`python manage.py tailwind start` run those same npm scripts in this directory.
The Django integration's `tailwind install` uses `npm install`; use `npm ci` for
reproducible installs. Set `NPM_BIN_PATH` only when npm is not on your PATH.

Both development and production write `theme/static/css/dist/styles.css`, which
Django discovers as `css/dist/styles.css`. Generated CSS is ignored by Git and
must be built before `collectstatic` for deployment.

Edit `src/styles.css` to configure Tailwind and daisyUI. It explicitly scans root
`templates/`, each top-level application's `templates/`, and application static
JavaScript. Add an `@source` entry when adding a source layout outside those paths.
Use complete utility names in templates; dynamically assembled class fragments
cannot be discovered. The configured themes are `light`, `dark`, and `cupcake`.

Tailwind 4 handles imports, nesting and vendor prefixes. The former PostCSS and
Tailwind 3 JavaScript configuration is no longer used. The old forms, typography,
line-clamp and aspect-ratio plugins were unused in the demo; daisyUI provides the
form components, and line-clamp and aspect-ratio utilities are built into Tailwind.
