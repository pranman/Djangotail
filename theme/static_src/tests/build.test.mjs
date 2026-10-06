import assert from "node:assert/strict";
import { spawn, spawnSync } from "node:child_process";
import { once } from "node:events";
import {
  cpSync, existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync,
  symlinkSync, writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import { fileURLToPath } from "node:url";
import test from "node:test";

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repository = resolve(frontend, "../..");
const npmCli = process.env.npm_execpath;
assert.ok(npmCli, "Run these regressions through npm test");

function createFixture(t) {
  // Compile real configuration and templates in isolation. Unique classes below
  // cannot leak in through the test source: automatic scanning is disabled.
  const root = mkdtempSync(join(tmpdir(), "django-tailwind-build-"));
  const cwd = join(root, "theme/static_src");
  mkdirSync(join(cwd, "src"), { recursive: true });
  cpSync(join(frontend, "src/styles.css"), join(cwd, "src/styles.css"));
  cpSync(join(frontend, "package.json"), join(cwd, "package.json"));
  symlinkSync(join(frontend, "node_modules"), join(cwd, "node_modules"),
    process.platform === "win32" ? "junction" : "dir");
  for (const directory of ["MainApp/templates", "theme/templates", "templates"]) {
    if (existsSync(join(repository, directory))) {
      cpSync(join(repository, directory), join(root, directory), { recursive: true });
    }
  }
  mkdirSync(join(root, "templates"), { recursive: true });
  mkdirSync(join(root, "ExampleApp/templates"), { recursive: true });
  mkdirSync(join(root, "ExampleApp/static"), { recursive: true });
  writeFileSync(join(root, "templates/source-probe.html"),
    '<div class="w-[137px] dark:opacity-[0.37]"></div>');
  writeFileSync(join(root, "ExampleApp/templates/source-probe.html"),
    '<div class="min-h-[139px]"></div>');
  writeFileSync(join(root, "ExampleApp/static/source-probe.js"),
    'element.classList.add("max-w-[141px]");');
  t.after(() => rmSync(root, { recursive: true, force: true }));
  return { root, cwd, output: join(root, "theme/static/css/dist/styles.css") };
}

function runBuild(cwd) {
  const result = spawnSync(process.execPath, [npmCli, "run", "build"], {
    cwd, encoding: "utf8", timeout: 30_000,
  });
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
}

test("production build emits template utilities, components and distinct themes", (t) => {
  const { cwd, output } = createFixture(t);
  runBuild(cwd);
  const css = readFileSync(output, "utf8");

  for (const declaration of ["width:137px", "min-height:139px", "max-width:141px"]) {
    assert.ok(css.includes(declaration), `Missing source-discovered utility: ${declaration}`);
  }
  assert.match(css, /dark\\:opacity-\\\[0\\\.37\\\]/);
  assert.match(css, /:where\(\[data-theme=dark\],\[data-theme=dark\] \*\)/);
  for (const component of ["btn", "card", "input"]) {
    assert.match(css, new RegExp(`\\.${component}\\{[^}]*;`),
      `Missing daisyUI ${component} component from the demo`);
  }

  const primaryColors = new Set();
  const backgrounds = new Set();
  for (const theme of ["light", "dark", "cupcake"]) {
    const block = css.match(new RegExp(`\\[data-theme=${theme}\\][^{]*\\{([^}]+)}`));
    assert.ok(block, `Missing ${theme} theme selector`);
    const primary = block[1].match(/--color-primary:([^;]+);/);
    const background = block[1].match(/--color-base-100:([^;]+);/);
    assert.ok(primary, `${theme} needs a primary color`);
    assert.ok(background, `${theme} needs a background color`);
    primaryColors.add(primary[1]);
    backgrounds.add(background[1]);
  }
  assert.equal(primaryColors.size, 3, "Each advertised theme needs its own palette");
  assert.equal(backgrounds.size, 3, "Each advertised theme needs its own background");
});

async function waitForBuild(child, output, pattern, getLog) {
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    assert.equal(child.exitCode, null, `Watcher exited early: ${getLog()}`);
    if (existsSync(output) && pattern.test(readFileSync(output, "utf8"))) return;
    await delay(100);
  }
  assert.fail(`Watcher did not emit ${pattern}: ${getLog()}`);
}

async function stopWatcher(child) {
  if (child.exitCode !== null) return;
  const exited = once(child, "exit");
  if (process.platform === "win32") {
    const result = spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], {
      encoding: "utf8", timeout: 10_000,
    });
    assert.equal(result.status, 0, result.stdout + result.stderr);
  } else {
    // npm creates descendants; stop the isolated process group, not only npm.
    process.kill(-child.pid, "SIGTERM");
  }
  await Promise.race([
    exited,
    delay(5_000, undefined, { ref: false }).then(() => { throw new Error("Watcher did not stop"); }),
  ]);
}

test("npm start stays alive without stdin and rebuilds new template classes", async (t) => {
  const { root, cwd, output } = createFixture(t);
  const watcher = spawn(process.execPath, [npmCli, "start"], {
    cwd, stdio: ["ignore", "pipe", "pipe"], detached: process.platform !== "win32",
  });
  let log = "";
  watcher.stdout.on("data", (chunk) => { log += chunk; });
  watcher.stderr.on("data", (chunk) => { log += chunk; });
  try {
    await waitForBuild(watcher, output, /width:\s*137px/, () => log);
    writeFileSync(join(root, "ExampleApp/templates/source-probe.html"),
      '<div class="min-h-[139px] w-[143px]"></div>');
    await waitForBuild(watcher, output, /width:\s*143px/, () => log);
    writeFileSync(join(root, "templates/added-after-watch.html"),
      '<div class="h-[149px]"></div>');
    await waitForBuild(watcher, output, /height:\s*149px/, () => log);
  } finally {
    await stopWatcher(watcher);
  }
});
