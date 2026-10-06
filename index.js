/**
 * MKV Audio Extractor - Node.js API
 * (C) 2026 Ashutosh Gadekar
 */

const { spawn, execFile } = require('child_process');
const path = require('path');

const packageRoot = __dirname;

/**
 * Probe an MKV file to inspect audio tracks.
 * @param {string} filePath - Path to MKV file.
 * @returns {Promise<object>} Parsed audio track metadata.
 */
function probe(filePath) {
  return new Promise((resolve, reject) => {
    const pythonScript = `
import json, sys
from mkv_audio_extractor.core.probe import probe_file
from pathlib import Path
try:
    info = probe_file(Path(sys.argv[1]))
    data = {
        "format": info.format_name,
        "duration": info.duration,
        "size": info.size,
        "tracks": [
            {
                "index": t.index,
                "stream_index": t.stream_index,
                "codec": t.codec,
                "language_code": t.language_code,
                "language_name": t.language_name,
                "channels": t.channels,
                "bit_rate": t.bit_rate,
                "title": t.title
            } for t in info.audio_tracks
        ]
    }
    print(json.dumps(data))
except Exception as e:
    print(json.dumps({"error": str(e)}), file=sys.stderr)
    sys.exit(1)
`;

    const proc = spawn('python3', ['-c', pythonScript, filePath], {
      env: Object.assign({}, process.env, { PYTHONPATH: packageRoot })
    });

    let stdout = '';
    let stderr = '';

    proc.stdout.on('data', (d) => { stdout += d; });
    proc.stderr.on('data', (d) => { stderr += d; });

    proc.on('close', (code) => {
      if (code !== 0) {
        return reject(new Error(stderr.trim() || `Probe failed with code ${code}`));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (err) {
        reject(err);
      }
    });
  });
}

/**
 * Run mkv-audio-extractor CLI command with arguments.
 * @param {string[]} args - CLI arguments array.
 * @param {object} [options] - Child process options.
 * @returns {ChildProcess}
 */
function runCli(args = [], options = {}) {
  const cliScript = path.join(__dirname, 'bin', 'mkv-audio-extractor.js');
  return spawn(process.execPath, [cliScript, ...args], Object.assign({ stdio: 'inherit' }, options));
}

module.exports = {
  probe,
  runCli,
  binPath: path.join(__dirname, 'bin', 'mkv-audio-extractor.js')
};
