# Frontend build

This directory is the only npm project. Use a current patch release of Node.js
22 (minimum 22.10) or 24 LTS, with npm 10 or 11. `.nvmrc` selects Node 24.

From the repository root:

```sh
npm --prefix theme/static_src ci --include=dev
npm --prefix theme/static_src run build
npm --prefix theme/static_src start
```

`ci --include=dev` installs the committed lockfile, including the Tailwind and
daisyUI build tools declared in `devDependencies`. Keep that flag in production
build stages too: `NODE_ENV=production` or `npm_config_omit=dev` would otherwise
omit the compiler. These build dependencies are not needed to serve collected
CSS from the deployed application.

`build` emits minified production CSS;
`start` watches CSS and template edits, including when launched with closed stdin.
Stop the watcher with Ctrl+C. CSS rebuilding is separate from browser refreshing.

With the Python environment installed, `python manage.py tailwind build` and
`python manage.py tailwind start` run those same npm scripts in this directory.
The Django integration's `tailwind install` uses `npm install`; use `npm ci --include=dev` for
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

Run `npm --prefix theme/static_src test` from the root to compile an isolated
copy, verify the demo components and all three theme palettes, and prove that
the watcher rebuilds both edited and newly created templates.

The scoped npm override keeps `@tailwindcss/cli` on Parcel watcher 2.5.6 until
Tailwind updates its exact 2.5.1 dependency. That patch line removes the
`micromatch` → `braces` chain affected by
[GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm).
It preserves the pinned Tailwind and daisyUI versions. When updating Tailwind,
check whether the override can be removed, regenerate the lockfile, and run
`npm audit`, the CSS build, and the watcher regressions above.
