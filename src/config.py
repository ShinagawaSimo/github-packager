LANGUAGE_IMAGE_MAP = {
    "python": "python:3.11-slim",
    "java": "eclipse-temurin:17-jdk",
    "c/c++": "gcc:13",
    "go": "golang:1.22",
    "javascript": "node:20",
    "rust": "rust:1.75",
}

BATCH_SINGLE_IMAGE_BASE = "ubuntu:22.04"

LANGUAGE_BUILD_PACKAGES = {
    "python": [],
    "java": ["maven", "gradle"],
    "c/c++": ["cmake"],
    "go": [],
    "javascript": ["build-essential"],
    "rust": [],
    "batch": [
        "python3",
        "python3-pip",
        "build-essential",
        "cmake",
        "maven",
        "gradle",
        "nodejs",
        "npm",
        "golang-go",
        "rustc",
        "cargo",
    ],
}

LANGUAGE_BUILD_COMMANDS = {
    "python": [
        "if [ -f requirements.txt ]; then python -m pip install -r requirements.txt; fi",
        "if [ -f pyproject.toml ] || [ -f setup.py ]; then python -m pip install .; fi",
    ],
    "java": [
        "if [ -f pom.xml ]; then mvn -q -DskipTests package; elif [ -f gradlew ]; then chmod +x ./gradlew; ./gradlew assemble -x test; elif ls build.gradle* >/dev/null 2>&1; then gradle assemble -x test; fi",
    ],
    "c/c++": [
        "if [ -f CMakeLists.txt ]; then cmake -S . -B build && cmake --build build; elif [ -f Makefile ] || [ -f makefile ]; then make -k; fi",
    ],
    "go": [
        "if [ -f go.mod ]; then go mod download; go build ./...; fi",
    ],
    "javascript": [
        "if [ -f package.json ]; then if command -v corepack >/dev/null 2>&1; then corepack enable; fi; if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile || pnpm install; elif [ -f yarn.lock ]; then yarn install --frozen-lockfile || yarn install; else npm install; fi; npm run build --if-present; fi",
    ],
    "rust": [
        "if [ -f Cargo.toml ]; then cargo build --workspace --all-targets; fi",
    ],
}

LANGUAGE_TEST_COMMANDS = {
    "python": [
        "if [ -f pyproject.toml ] || [ -f setup.py ] || [ -f requirements.txt ]; then python -m pytest -q; fi",
    ],
    "java": [
        "if [ -f pom.xml ]; then mvn -q test; elif [ -f gradlew ]; then chmod +x ./gradlew; ./gradlew test; elif ls build.gradle* >/dev/null 2>&1; then gradle test; fi",
    ],
    "c/c++": [
        "if [ -d build ]; then ctest --test-dir build; elif [ -f Makefile ] || [ -f makefile ]; then make test; fi",
    ],
    "go": [
        "if [ -f go.mod ]; then go test ./...; fi",
    ],
    "javascript": [
        "if [ -f package.json ]; then npm test --if-present; fi",
    ],
    "rust": [
        "if [ -f Cargo.toml ]; then cargo test --workspace --all-targets; fi",
    ],
}

LANGUAGE_GROUPS = {
    "python": {"Python"},
    "java": {"Java"},
    "c/c++": {"C", "C++"},
    "go": {"Go"},
    "javascript": {"JavaScript", "TypeScript"},
    "rust": {"Rust"},
}

PR_KEYWORDS = {
    "close",
    "closes",
    "closed",
    "fix",
    "fixes",
    "fixed",
    "resolve",
    "resolves",
    "resolved",
}
