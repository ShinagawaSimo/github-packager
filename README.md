# github_packager

A small tool that packages a GitHub repository into reproducible test images.

## Structure

- src/
- packager.py
- repositories.txt
- pyproject.toml
- requirements.txt

## Files

- packager.py: module entry loader for running from project root
- src/packager.py: main entry point and CLI routing
- src/config.py: language mappings, build/test commands, image bases
- src/github_api.py: GitHub API access and issue/pull parsing
- src/patches.py: diff extraction and patch split
- src/instances.py: instance assembly and JSONL output
- src/images.py: Dockerfile generation and image build logic
- src/docker_tools.py: Docker build helpers and logging

## Run

```bash
python -m packager --repo_url <URL> --output_dir <PATH>
```

```bash
python -m packager --batch --output_dir <PATH>
```

```bash
python -m packager --batch --single_image --output_dir <PATH>
```

Batch mode reads repositories.txt in the project root. Invalid entries are printed to stderr.

## Compile

During image build, a language-specific compile step is executed when supported. Example triggers:

- Python: requirements.txt or pyproject.toml/setup.py
- Java: pom.xml or gradlew/build.gradle*
- C/C++: CMakeLists.txt or Makefile
- Go: go.mod
- JavaScript/TypeScript: package.json
- Rust: Cargo.toml

## Test

Each image includes /bundle/run_eval.sh, which applies patch.diff and test_patch.diff then runs the build and test commands in test_spec.json.

- Single image: /bundle/run_eval.sh
- Batch image: /bundle/run_eval.sh <instance_id>
