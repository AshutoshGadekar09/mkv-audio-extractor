# Contributing to MKV Audio Extractor

Thank you for your interest in contributing to **MKV Audio Extractor**! We welcome contributions from developers, testers, translators, and documentation writers of all experience levels.

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code.

## Ways to Contribute

- **Report Bugs**: Submit detailed bug reports with sample file information and reproduction steps.
- **Suggest Features**: Propose new formats, UI improvements, or CLI flags.
- **Improve Documentation**: Enhance instructions, add tutorials, or fix typos.
- **Submit Pull Requests**: Fix bugs, add new features, or add language codes to the ISO map.

---

## Development Setup

### 1. Prerequisites

- Python 3.10+
- `ffmpeg` and `ffprobe`
- `git`

### 2. Fork & Clone

```bash
git clone https://github.com/<your-username>/mkv-audio-extractor.git
cd mkv-audio-extractor
```

### 3. Create a Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[gui,dev]"
```

### 4. Running Tests

Run the full test suite with:

```bash
pytest tests/ -v
```

Unit tests only (without ffmpeg generation):

```bash
pytest tests/test_core.py -v -k "not TestWithRealMKV"
```

---

## Making Changes

1. **Create a branch** for your work:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bug-fix
   ```

2. **Follow Code Guidelines**:
   - Write clean, readable Python code with type annotations (`typing`).
   - Match PEP 8 formatting conventions.
   - Use `subprocess` safely: always pass argument lists, never construct shell strings.
   - Ensure all public functions, classes, and methods have descriptive docstrings.

3. **Add Tests**:
   - If adding a new feature or fixing a bug, write corresponding tests in `tests/`.
   - Make sure all existing tests pass before submitting your PR.

4. **Test the GUI**:
   - Ensure the GUI works properly:
     ```bash
     python3 -m mkv_audio_extractor
     ```

5. **Test the Debian package**:
   ```bash
   ./build-deb.sh
   ```

---

## Submitting a Pull Request

1. Push your branch to your GitHub fork:
   ```bash
   git push origin feature/your-feature-name
   ```
2. Open a Pull Request on GitHub against the `main` branch.
3. Fill out the PR template describing your changes, why they are needed, and how you tested them.
4. A maintainer will review your pull request shortly!
