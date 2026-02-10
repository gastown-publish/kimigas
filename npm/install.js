#!/usr/bin/env node
"use strict";

const { execSync } = require("child_process");
const fs = require("fs");
const path = require("path");
const https = require("https");
const os = require("os");

const VERSION = require("./package.json").version;
const REPO = "gastown-publish/kimigas";

const PLATFORM_MAP = {
  darwin: { arm64: "aarch64-apple-darwin" },
  linux: {
    x64: "x86_64-unknown-linux-gnu",
    arm64: "aarch64-unknown-linux-gnu",
  },
  win32: { x64: "x86_64-pc-windows-msvc" },
};

function getTarget() {
  const platform = os.platform();
  const arch = os.arch();
  const targets = PLATFORM_MAP[platform];
  if (!targets || !targets[arch]) {
    console.error(
      `Unsupported platform: ${platform}-${arch}. Install via pip instead: pip install kimigas`
    );
    process.exit(1);
  }
  return targets[arch];
}

function download(url) {
  return new Promise((resolve, reject) => {
    https
      .get(url, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          return download(res.headers.location).then(resolve, reject);
        }
        if (res.statusCode !== 200) {
          return reject(new Error(`HTTP ${res.statusCode} for ${url}`));
        }
        const chunks = [];
        res.on("data", (chunk) => chunks.push(chunk));
        res.on("end", () => resolve(Buffer.concat(chunks)));
        res.on("error", reject);
      })
      .on("error", reject);
  });
}

async function install() {
  const target = getTarget();
  const isWindows = os.platform() === "win32";
  const ext = isWindows ? "zip" : "tar.gz";
  const url = `https://github.com/${REPO}/releases/download/v${VERSION}/kimigas-${VERSION}-${target}.${ext}`;

  console.log(`Downloading kimigas v${VERSION} for ${target}...`);

  const binDir = path.join(__dirname, "bin");
  fs.mkdirSync(binDir, { recursive: true });

  try {
    const data = await download(url);
    const tmpFile = path.join(os.tmpdir(), `kimigas-download.${ext}`);
    fs.writeFileSync(tmpFile, data);

    if (isWindows) {
      execSync(`powershell -Command "Expand-Archive -Path '${tmpFile}' -DestinationPath '${binDir}' -Force"`, { stdio: "inherit" });
      // Rename kimi.exe to kimigas.exe
      const src = path.join(binDir, "kimi.exe");
      const dst = path.join(binDir, "kimigas.exe");
      if (fs.existsSync(src)) fs.renameSync(src, dst);
    } else {
      execSync(`tar -xzf "${tmpFile}" -C "${binDir}"`, { stdio: "inherit" });
      // Rename kimi to kimigas
      const src = path.join(binDir, "kimi");
      const dst = path.join(binDir, "kimigas");
      if (fs.existsSync(src)) fs.renameSync(src, dst);
      fs.chmodSync(dst, 0o755);
    }

    fs.unlinkSync(tmpFile);
    console.log(`kimigas v${VERSION} installed successfully`);
  } catch (err) {
    console.error(`Failed to download binary: ${err.message}`);
    console.error("Falling back to pip installation...");
    try {
      execSync(`pip install kimigas==${VERSION}`, { stdio: "inherit" });
      // Create a wrapper script
      const wrapper = isWindows
        ? `@echo off\npython -m kimi_cli %*`
        : `#!/bin/sh\nexec python -m kimi_cli "$@"`;
      const wrapperPath = path.join(binDir, isWindows ? "kimigas.cmd" : "kimigas");
      fs.writeFileSync(wrapperPath, wrapper);
      if (!isWindows) fs.chmodSync(wrapperPath, 0o755);
      console.log("kimigas installed via pip fallback");
    } catch {
      console.error("pip fallback also failed. Install manually:");
      console.error("  pip install kimigas");
      process.exit(1);
    }
  }
}

install();
