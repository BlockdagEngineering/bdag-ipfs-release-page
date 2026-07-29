import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";


class FakeClassList {
  constructor() {
    this.values = new Set();
  }

  add(...names) {
    names.forEach((name) => this.values.add(name));
  }

  remove(...names) {
    names.forEach((name) => this.values.delete(name));
  }

  toggle(name, force) {
    const enabled = force === undefined ? !this.values.has(name) : Boolean(force);
    if (enabled) {
      this.values.add(name);
    } else {
      this.values.delete(name);
    }
    return enabled;
  }

  contains(name) {
    return this.values.has(name);
  }
}


class FakeElement {
  constructor({ dataset = {}, value = "", disabled = false } = {}) {
    this.attributes = new Map();
    this.classList = new FakeClassList();
    this.dataset = { ...dataset };
    this.disabled = disabled;
    this.hidden = false;
    this.innerHTML = "";
    this.listeners = new Map();
    this.parentElement = null;
    this.queries = new Map();
    this.textContent = "";
    this.value = value;
  }

  addEventListener(type, listener) {
    this.listeners.set(type, listener);
  }

  bind(selector, element) {
    this.queries.set(selector, element);
    return element;
  }

  querySelector(selector) {
    return this.queries.get(selector) ?? null;
  }

  removeAttribute(name) {
    this.attributes.delete(name);
    if (name === "href") {
      delete this.href;
    }
  }

  setAttribute(name, value) {
    this.attributes.set(name, String(value));
  }
}


class FakeDocument {
  constructor() {
    this.ids = new Map();
    this.lists = new Map();
    this.singles = new Map();
  }

  addId(id, element = new FakeElement()) {
    this.ids.set(id, element);
    return element;
  }

  addList(selector, elements) {
    this.lists.set(selector, elements);
  }

  addSingle(selector, element) {
    this.singles.set(selector, element);
  }

  getElementById(id) {
    return this.ids.get(id) ?? null;
  }

  querySelector(selector) {
    if (selector.startsWith("#")) {
      return this.getElementById(selector.slice(1));
    }
    return this.singles.get(selector) ?? null;
  }

  querySelectorAll(selector) {
    return this.lists.get(selector) ?? [];
  }
}


function releasePageDom() {
  const document = new FakeDocument();
  for (const id of [
    "releaseBadge",
    "releaseStatus",
    "releaseStatusDetail",
    "softwareStatus",
    "softwareStatusDetail",
    "datasetStatus",
    "datasetStatusDetail",
    "releaseDot",
    "softwareDot",
    "datasetDot",
    "draftNotice",
    "installCommand",
    "copyCommand",
    "walletLabel",
    "datasetField",
    "retentionField",
    "selectionSummary",
    "inputNotice",
    "toast",
  ]) {
    document.addId(id);
  }
  document.getElementById("copyCommand").disabled = true;
  document.addId("dataDir", new FakeElement({ value: "/srv/blockdag/node-data" }));
  document.addId("downloadDir", new FakeElement({ value: "/srv/blockdag/downloads" }));
  document.addId("wallet", new FakeElement({ value: "0x1111111111111111111111111111111111111111" }));

  const actions = [];
  for (const key of ["linux-amd64", "linux-arm64", "portable", "full_archive"]) {
    const card = new FakeElement();
    for (const field of ["status", "filename", "size", "sha256", "cid"]) {
      card.bind(`[data-field="${field}"]`, new FakeElement());
    }
    if (key === "portable" || key === "full_archive") {
      card.bind('[data-field="unpacked-size"]', new FakeElement());
    }
    const download = card.bind('[data-action="download"]', new FakeElement());
    actions.push(download);
    if (key === "portable" || key === "full_archive") {
      actions.push(card.bind('[data-action="manifest"]', new FakeElement()));
    }
    document.addSingle(`[data-artifact="${key}"]`, card);
  }

  const recordLinks = [];
  for (const key of [
    "release-auth",
    "release-key",
    "release-notes",
    "dataset-key",
    "dataset-verifier",
    "portable-manifest",
    "archive-manifest",
  ]) {
    const parent = new FakeElement();
    parent.bind("code", new FakeElement());
    const link = new FakeElement();
    link.parentElement = parent;
    recordLinks.push(link);
    document.addSingle(`[data-record="${key}"]`, link);
  }

  const profileButtons = [
    new FakeElement({ dataset: { profile: "mining" } }),
    new FakeElement({ dataset: { profile: "public-rpc" } }),
    new FakeElement({ dataset: { profile: "non-mining" } }),
  ];
  const presetButton = new FakeElement({ dataset: { preset: "full-archive-rpc" }, disabled: true });
  const datasetButtons = [
    new FakeElement({ dataset: { dataset: "none" } }),
    new FakeElement({ dataset: { dataset: "portable" }, disabled: true }),
    new FakeElement({ dataset: { dataset: "full_archive" }, disabled: true }),
  ];
  const retentionButtons = [
    new FakeElement({ dataset: { retention: "current" } }),
    new FakeElement({ dataset: { retention: "archive" } }),
  ];

  document.addList("[data-profile]", profileButtons);
  document.addList("[data-preset]", [presetButton]);
  document.addList("[data-dataset]", datasetButtons);
  document.addList("[data-retention]", retentionButtons);
  document.addList('[data-action="download"], [data-action="manifest"]', actions);
  document.addList("[data-record]", recordLinks);
  document.addList(
    '[data-dataset="portable"], [data-dataset="full_archive"], [data-preset="full-archive-rpc"]',
    [datasetButtons[1], datasetButtons[2], presetButton],
  );

  document.addSingle('[data-preset="full-archive-rpc"]', presetButton);
  document.addSingle('[data-dataset="portable"]', datasetButtons[1]);
  document.addSingle('[data-dataset="full_archive"]', datasetButtons[2]);
  return document;
}


test("the actual RC62 DOMContentLoaded path uses the finalized default identity and unlocks", async () => {
  const moduleUrl = new URL(
    "../releases/2.0.0-community-rescue-rc.62/assets/release-page.mjs",
    import.meta.url,
  );
  const manifestUrl = new URL(
    "../releases/2.0.0-community-rescue-rc.62/release-manifest.json",
    import.meta.url,
  );
  const source = await readFile(moduleUrl, "utf8");
  const manifest = JSON.parse(await readFile(manifestUrl, "utf8"));
  const functionHeader = [
    "export function buildInstallCommand(",
    "  manifest,",
    "  options = {},",
    "  expectedIdentity = EXPECTED_RELEASE_IDENTITY,",
    ") {",
    "",
  ].join("\n");
  assert.ok(source.includes(functionHeader), "buildInstallCommand signature changed");
  const instrumented = source.replace(
    functionHeader,
    `${functionHeader}  globalThis.__rc62BuildInstallCommandArgumentCount = arguments.length;\n`,
  );

  const previous = {
    document: globalThis.document,
    fetch: globalThis.fetch,
    window: globalThis.window,
  };
  const listeners = new Map();
  const document = releasePageDom();
  let fetchedResource = null;

  try {
    globalThis.document = document;
    globalThis.window = {
      addEventListener(type, listener) {
        listeners.set(type, listener);
      },
      location: { href: "https://release.invalid/releases/rc62/" },
      setTimeout() {
        return 0;
      },
    };
    globalThis.fetch = async (resource) => {
      fetchedResource = resource;
      return {
        ok: true,
        async json() {
          return structuredClone(manifest);
        },
      };
    };

    const dataUrl = `data:text/javascript;base64,${Buffer.from(instrumented).toString("base64")}`;
    await import(dataUrl);
    const domContentLoaded = listeners.get("DOMContentLoaded");
    assert.equal(typeof domContentLoaded, "function");
    domContentLoaded();

    for (let attempt = 0; attempt < 10; attempt += 1) {
      if (document.getElementById("installCommand").textContent.includes('bash "$PACKAGE_ROOT/install.sh"')) {
        break;
      }
      await new Promise((resolve) => setImmediate(resolve));
    }

    assert.equal(fetchedResource, "release-manifest.json");
    assert.equal(globalThis.__rc62BuildInstallCommandArgumentCount, 2);
    assert.equal(document.getElementById("releaseBadge").textContent, "Published");
    assert.equal(document.getElementById("copyCommand").disabled, false);
    assert.match(
      document.getElementById("installCommand").textContent,
      /bash "\$PACKAGE_ROOT\/install\.sh"/,
    );
    assert.doesNotMatch(
      document.getElementById("installCommand").textContent,
      /2\.0\.0-community-rescue-rc\.62 is not publication-ready/,
    );
  } finally {
    if (previous.document === undefined) {
      delete globalThis.document;
    } else {
      globalThis.document = previous.document;
    }
    if (previous.fetch === undefined) {
      delete globalThis.fetch;
    } else {
      globalThis.fetch = previous.fetch;
    }
    if (previous.window === undefined) {
      delete globalThis.window;
    } else {
      globalThis.window = previous.window;
    }
    delete globalThis.__rc62BuildInstallCommandArgumentCount;
  }
});
