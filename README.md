# ☕ Java 11 → 21 Migration Agent

A CLI coding agent that **fully migrates Java 11 projects to Java 21** — automatically.  
Covers build config, code modernization, dependency fixes, test runs, and produces a migration report.

---

## What It Does

### Area A — Build Configuration
- Detects Maven (`pom.xml`) or Gradle (`build.gradle`)
- Updates Java version to 21 using `<maven.compiler.release>21</maven.compiler.release>`
- Upgrades `maven-compiler-plugin` to 3.12+, `maven-surefire-plugin` to 3.2.5+
- Adds Gradle Java toolchain block for Gradle projects
- Runs `mvn test` or `./gradlew test` and iterates on failures

### Area B — Code Modernization
| Java Feature | What it replaces |
|---|---|
| **Text Blocks** (Java 15) | Multi-line string concatenation |
| **Records** (Java 16) | Verbose POJOs with only fields + getters |
| **Pattern Matching instanceof** (Java 16) | `if (x instanceof Foo) { Foo f = (Foo) x; }` |
| **Switch Expressions** (Java 14) | Verbose switch statements |
| **`var`** (Java 10) | Redundant type declarations |
| **`String.isBlank()`** (Java 11) | `.trim().isEmpty()` |
| **`List.of()`** (Java 9) | `Arrays.asList(...)` |

### Area C — Dependency & Compatibility
- Detects and migrates `javax.*` → `jakarta.*` (for Spring Boot 3.x / Jakarta EE 9+)
- Updates Lombok, Mockito, Byte Buddy, ASM to Java 21-compatible versions
- Removes deprecated APIs (SecurityManager, Nashorn)
- Adds `--add-opens` JVM flags only when required

### Area D — Spring Boot 2.x → 3.x


-Spring Boot 2.7 → 3.2 migration
-Full javax.* → jakarta.* sweep
-Security config API changes
-Auto-configuration migration
-Integration test support


### Output
-  Migrated source files (in the cloned repo)
- `MIGRATION_REPORT.md` saved to the project root — documents every change with before/after

---

## Quick Start

### 1. Install Docker
Download from: https://www.docker.com/products/docker-desktop/  
(Choose Apple Silicon for M1/M2/M3 Mac, Intel for older Mac)

### 2. Get an Anthropic API Key
Sign up at: https://console.anthropic.com  
Create a key under **API Keys** → starts with `sk-ant-...`

### 3. Set up the project

```bash
# Clone this repo (or unzip the submission)
cd java-migration-agent

# Make the run script executable
chmod +x run.sh
```

### 4. Set your API key

```bash
export ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
```

### 5. Run the agent

```bash
./run.sh https://github.com/your-target/java11-repo
```

That's it! The agent will:
1. Build a Docker image with Python + Java 21 + Maven
2. Clone the target repo
3. Apply all migrations
4. Run tests and fix failures
5. Save `MIGRATION_REPORT.md` to the repo

---

## Manual Docker Commands

```bash
# Build the image
docker build -t java-migration-agent .

# Run migration
docker run --rm \
  -e ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY \
  java-migration-agent https://github.com/user/repo

# Run with help
docker run --rm java-migration-agent --help
```

---

## Without Docker (local Python)

```bash
# Install Python deps
pip install -r requirements.txt

# Set API key
export ANTHROPIC_API_KEY=sk-ant-...

# Run
python agent.py https://github.com/user/java11-repo
```

---

## How It Works (Architecture)

```
user: python agent.py <repo-url>
          │
          ▼
    agent.py — main loop
          │
          ▼
    Anthropic API (claude-sonnet-4-6)
    system prompt: Java migration expert
          │
          ├── tool: run_shell      → git, mvn, javac, grep
          ├── tool: read_file      → read .java, pom.xml, build.gradle
          ├── tool: write_file     → write migrated files back
          ├── tool: list_directory → understand project layout
          ├── tool: search_in_files→ find migration targets
          └── tool: log_change     → track every change for report
          │
          ▼
    Agent iterates until stop_reason == "end_turn"
    (up to 60 iterations)
          │
          ▼
    print_summary() → table of all changes
    save_migration_report() → MIGRATION_REPORT.md
```

**No frameworks used.** Just:
- `anthropic` Python SDK — raw API calls
- `rich` — terminal UI (panels, tables, spinners, colors)

---

## Example Output

```
╭──────────────────────────────────────────────────────╮
│          ☕  Java 11 → 21 Migration Agent            │
│    A: Build Config   B: Code   C: Dependencies       │
╰──────────────────────────────────────────────────────╯

  Repository: https://github.com/example/java11-app
  Migration:  Java 11 → Java 21  (A + B + C)

  → Cloning repository...
  ⚡ run_shell  $ git clone https://github.com/example/java11-app /workspace/java11-app
    ✓ Cloning into '/workspace/java11-app'

  📁 list_directory  /workspace/java11-app
  📖 read_file  pom.xml
  ✏️  write_file  pom.xml
  📋 log_change  Java version bump → pom.xml

  🔍 search_in_files  instanceof
  📖 read_file  src/main/java/com/example/ShapeService.java
  ✏️  write_file  src/main/java/com/example/ShapeService.java
  📋 log_change  Pattern Matching → ShapeService.java

  ⚡ run_shell  $ mvn -q test
    ✓ BUILD SUCCESS

──────────── Migration Summary ────────────────────

  ┌───────────────────┬────────────────┬─────────────────────────┐
  │ Category          │ File           │ Change                  │
  ├───────────────────┼────────────────┼─────────────────────────┤
  │ 🏗️  Build Config  │ pom.xml        │ Java version bump       │
  │ ✨  Modernization │ Person.java    │ Record Class            │
  │ ✨  Modernization │ ShapeService   │ Pattern Matching        │
  │ ✨  Modernization │ Queries.java   │ Text Block              │
  │ 📦  Dependencies  │ pom.xml        │ Surefire 3.2.5          │
  └───────────────────┴────────────────┴─────────────────────────┘

  Total changes:   5
  Tests:           ✅ PASSED
  Report saved:    /workspace/java11-app/MIGRATION_REPORT.md
```

---

## Files

```
java-migration-agent/
├── agent.py           ← Main agent (all logic here)
├── Dockerfile         ← Python 3.11 + Java 21 + Maven 3.9
├── requirements.txt   ← anthropic, rich
├── run.sh             ← Easy one-command runner
├── README.md          ← This file
└── example/
    ├── java11-demo/   ← Sample Java 11 project (before)
    └── java18-migrated/ ← Sample after migration
```

---

