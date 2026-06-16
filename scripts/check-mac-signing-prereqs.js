#!/usr/bin/env node
const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const root = path.resolve(__dirname, '..');
let failed = false;
let warned = false;

function run(cmd, args) {
  return spawnSync(cmd, args, {
    cwd: root,
    encoding: 'utf8',
    shell: false
  });
}

function log(status, message, detail = '') {
  const label = status === 'ok' ? 'OK  ' : status === 'warn' ? 'WARN' : 'FAIL';
  if (status === 'fail') failed = true;
  if (status === 'warn') warned = true;
  console.log(`${label} ${message}${detail ? ` — ${detail}` : ''}`);
}

function hasEnv(name) {
  return typeof process.env[name] === 'string' && process.env[name].trim() !== '';
}

function readJson(file) {
  return JSON.parse(fs.readFileSync(path.join(root, file), 'utf8'));
}

function commandSummary(result) {
  return (result.stdout || result.stderr || '').trim().split('\n').slice(-2).join(' / ');
}

console.log('macOS signing and notarization prerequisite check\n');

if (process.platform === 'darwin') log('ok', 'running on macOS');
else log('fail', 'running on macOS', `current platform: ${process.platform}`);

const xcodeSelect = run('xcode-select', ['-p']);
if (xcodeSelect.status === 0) log('ok', 'Xcode command line tools are installed', xcodeSelect.stdout.trim());
else log('fail', 'Xcode command line tools are installed', commandSummary(xcodeSelect));

const notarytool = run('xcrun', ['notarytool', '--version']);
if (notarytool.status === 0) log('ok', 'notarytool is available', notarytool.stdout.trim());
else log('fail', 'notarytool is available', commandSummary(notarytool));

const identities = run('security', ['find-identity', '-v', '-p', 'codesigning']);
if (identities.status === 0) {
  const lines = identities.stdout.split('\n').filter(Boolean);
  const developerIds = lines.filter(line => /Developer ID Application:/.test(line));
  if (developerIds.length) {
    log('ok', 'Developer ID Application certificate found in keychain', developerIds.map(line => line.replace(/"[^"]+"/, '"Developer ID Application: ..."' )).join('; '));
  } else {
    log('warn', 'Developer ID Application certificate found in keychain', 'not found; use CSC_LINK/CSC_KEY_PASSWORD or install the certificate');
  }
} else {
  log('warn', 'code-signing identities can be listed', commandSummary(identities));
}

const hasCscPair = hasEnv('CSC_LINK') && hasEnv('CSC_KEY_PASSWORD');
if (hasCscPair) log('ok', 'electron-builder certificate env pair is present', 'CSC_LINK + CSC_KEY_PASSWORD');
else log('warn', 'electron-builder certificate env pair is present', 'set CSC_LINK and CSC_KEY_PASSWORD when building outside a prepared keychain');

const hasAppleIdAuth = hasEnv('APPLE_ID') && hasEnv('APPLE_APP_SPECIFIC_PASSWORD') && hasEnv('APPLE_TEAM_ID');
const hasApiKeyAuth = hasEnv('APPLE_API_KEY') && hasEnv('APPLE_API_KEY_ID') && hasEnv('APPLE_API_ISSUER') && hasEnv('APPLE_TEAM_ID');
const hasKeychainProfile = hasEnv('APPLE_KEYCHAIN_PROFILE') && hasEnv('APPLE_TEAM_ID');

if (hasAppleIdAuth) log('ok', 'notarization auth is configured', 'APPLE_ID + APPLE_APP_SPECIFIC_PASSWORD + APPLE_TEAM_ID');
else if (hasApiKeyAuth) log('ok', 'notarization auth is configured', 'APPLE_API_KEY + APPLE_API_KEY_ID + APPLE_API_ISSUER + APPLE_TEAM_ID');
else if (hasKeychainProfile) log('ok', 'notarization auth is configured', 'APPLE_KEYCHAIN_PROFILE + APPLE_TEAM_ID');
else log('warn', 'notarization auth is configured', 'set Apple ID auth, App Store Connect API key auth, or a notarytool keychain profile');

const pkg = readJson('package.json');
const mac = pkg.build && pkg.build.mac ? pkg.build.mac : {};
if (mac.notarize === true) log('ok', 'electron-builder notarize option is enabled');
else log('warn', 'electron-builder notarize option is enabled', 'set build.mac.notarize=true for fully public signed builds');

if (mac.hardenedRuntime === true || mac.hardenedRuntime === undefined) {
  log('ok', 'Hardened Runtime is enabled or using electron-builder default');
} else {
  log('fail', 'Hardened Runtime is enabled', `current value: ${mac.hardenedRuntime}`);
}

const entitlementFiles = [
  mac.entitlements || 'build/entitlements.mac.plist',
  mac.entitlementsInherit || 'build/entitlements.mac.inherit.plist'
];
for (const file of entitlementFiles) {
  if (fs.existsSync(path.join(root, file))) log('ok', `${file} exists`);
  else log('warn', `${file} exists`, 'recommended before enabling notarization');
}

console.log('');
if (failed) {
  console.error('macOS signing prerequisite check failed.');
  process.exit(1);
}

if (warned) {
  console.log('macOS signing prerequisite check passed with warnings.');
  process.exit(0);
}

console.log('macOS signing prerequisite check passed.');
