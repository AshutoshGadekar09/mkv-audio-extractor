#!/usr/bin/env node

/**
 * MKV Audio Extractor - Node.js CLI Entry Point
 * Part of mkv-audio-extractor npm package
 */

const { spawn, execSync } = require('child_process');
const path = require('path');
const fs = require('fs');

// Check dependencies
function checkDependency(command, installHint) {
  try {
    execSync(`which ${command}`, { stdio: 'ignore' });
    return true;
  } catch {
    console.error(`\x1b[31m[Error]\x1b[0m \x1b[1m${command}\x1b[0m is required but not found.`);
    if (installHint) {
      console.error(`\x1b[33mInstall instructions:\x1b[0m\n  ${installHint}\n`);
    }
    return false;
  }
}

// Ensure python3 and ffmpeg are present
const pythonOk = checkDependency('python3', 'sudo apt install python3 (Debian/Ubuntu) or brew install python (macOS)');
const ffmpegOk = checkDependency('ffmpeg', 'sudo apt install ffmpeg (Debian/Ubuntu) or brew install ffmpeg (macOS)');

if (!pythonOk || !ffmpegOk) {
  process.exit(1);
}

// Find package directory
const packageRoot = path.resolve(__dirname, '..');
const pythonPackageDir = path.join(packageRoot, 'mkv_audio_extractor');

if (!fs.existsSync(pythonPackageDir)) {
  console.error(`\x1b[31m[Error]\x1b[0m Cannot find mkv_audio_extractor modules at ${pythonPackageDir}`);
  process.exit(1);
}

// Prepare environment with PYTHONPATH set to the package root
const env = Object.assign({}, process.env, {
  PYTHONPATH: packageRoot + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : '')
});

// Pass through all CLI arguments
const args = ['-m', 'mkv_audio_extractor', ...process.argv.slice(2)];

// Spawn Python process with full stdio inheritance
const child = spawn('python3', args, {
  env,
  stdio: 'inherit'
});

child.on('error', (err) => {
  console.error('\x1b[31mFailed to start mkv-audio-extractor:\x1b[0m', err.message);
  process.exit(1);
});

child.on('close', (code) => {
  process.exit(code !== null ? code : 0);
});
