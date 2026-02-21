# Java 11 to 21 Migration Agent

A CLI-based autonomous coding agent that migrates Java 11 projects to Java 21.
Built with raw Gemini 2.5 Flash API.

---

## What It Does

| Area | What It Migrates |
|------|-----------------|
| A — Build Config | Java version to 21, Spring Boot parent version, Maven compiler/surefire plugins, Gradle toolchain |
| B — Code Modernization | Records, Text Blocks, Pattern Matching instanceof, Switch Expressions, var, List.of(), String.isBlank() |
| C — Dependency Upgrades | Surefire 3.2.5+, Compiler Plugin 3.12.1+, Lombok 1.18.30+, Mockito 5.x, Jackson 2.15+, Byte Buddy 1.14+ |
| D — Spring Boot 2 to 3 | Batch javax.* to jakarta.* migration, Spring Boot parent 3.2.x, Security config updates |
| E — Serialization | java.util.Date to java.time.*, Jackson record support, deprecated ObjectMapper configs |
| F — HTTP Client | RestTemplate to RestClient migration, @Bean definition updates |

After all changes, runs mvn test or ./gradlew test, fixes failures, and retries up to 3 times.
Produces a MIGRATION_REPORT.md with every change logged (category, before/after snippets, how to revert).

---

## Prerequisites

- Docker Desktop — https://www.docker.com/products/docker-desktop
- Gemini API Key (free) — https://aistudio.google.com/apikey
- macOS, Linux, or Windows with WSL2

---

## Installation

```bash
git clone https://github.com/sri123vk/Coding-AI-Agent-for-Java-Migration
cd Coding-AI-Agent-for-Java-Migration
chmod +x run.sh
```

---

## Usage

```bash
export GEMINI_API_KEY=your-key-here
./run.sh https://github.com/any/java11-project
```

The agent will:
1. Build a Docker image with Python 3.11 + Java 21 (Temurin) + Maven + Git
2. Clone the target repository inside Docker
3. Apply all migrations across Areas A to F
4. Run tests and fix failures (up to 3 retries per failure)
5. Print a colour summary table in the terminal
6. Save MIGRATION_REPORT.md to the project root

---

## Example

```bash
export GEMINI_API_KEY=your-key-here
./run.sh https://github.com/spring-projects/spring-petclinic
```

---

## View Results After the Run

```bash
# See every line the agent changed
git -C /tmp/<repo-name> diff HEAD

# List only the changed files
git -C /tmp/<repo-name> diff --name-only HEAD

# Read the full migration report
cat /tmp/<repo-name>/MIGRATION_REPORT.md

# Revert everything back to original
git -C /tmp/<repo-name> checkout .
```

---

## How It Works

The agent runs a standard agentic loop — no framework, raw API calls only:

```
User provides GitHub URL
        |
        v
Gemini 2.5 Flash reads system prompt + conversation history
        |
        v
Gemini decides which tool to call next
        |
        v
Tool executes on the Linux environment inside Docker
        |
        v
Result returned to Gemini as FunctionResponse
        |
        v
Loop repeats up to 80 iterations until migration is complete
```

Six tools available to the agent:

| Tool | Purpose |
|------|---------|
| run_shell | Execute git, mvn, gradlew, python3, sed, grep, find |
| read_file | Read Java, XML, and Gradle source files |
| write_file | Write modernized files (creates .bak backup before overwriting) |
| list_directory | Explore project layout recursively |
| search_in_files | Find migration patterns using grep across all source files |
| log_change | Record every change with category and before/after snippets |

---

## Key Design Decision — Python over sed for pom.xml

pom.xml is always modified using Python one-liners, never rewritten entirely and never using
sed append commands. This was discovered through testing — sed append inserts literal backslash-n
into XML instead of real newlines, always corrupting the file. Python handles it safely:

```bash
python3 -c "
import re, sys
f = sys.argv[1]
c = open(f).read()
c = re.sub(r'<java.version>[^<]*</java.version>', '<java.version>21</java.version>', c)
open(f, 'w').write(c)
" /tmp/repo/pom.xml
```

This also mirrors real production practice — surgically editing only what needs to change
rather than regenerating the whole file and risking dropped dependency tags.

---

## Project Structure

```
Coding-AI-Agent-for-Java-Migration/
├── agent.py          — Main agent (~730 lines — tools, LLM loop, display, report)
├── Dockerfile        — Python 3.11 + Java 21 Temurin + Maven + Git
├── run.sh            — One-command runner with Docker build + run
├── requirements.txt  — google-genai>=0.8.0, rich>=13.7.0
└── README.md         — This file
```

---

## Tested On

| Repository | Tests | Changes |
|---|---|---|
| spring-projects/spring-petclinic | PASSED | 9 changes — Java 21, javax fix, spring-javaformat auto-apply |
| bezkoder/spring-boot-one-to-many | 20 changes | Records, var, Date to Instant, Text Blocks, H2 test override |
| gothinkster/spring-boot-realworld-example-app | 29 changes | Gradle upgrade, javax to jakarta batch, records, var |

---

## Common Migration Patterns Handled

**javax to jakarta batch migration (one command across all files):**
```bash
find /tmp/repo/src -name "*.java" | xargs sed -i \
  's/import javax.persistence./import jakarta.persistence./g'
```

**H2 test database override (when repo needs MySQL but Docker has none):**
```
# src/test/resources/application.properties
spring.datasource.url=jdbc:h2:mem:testdb
spring.datasource.driver-class-name=org.h2.Driver
spring.jpa.hibernate.ddl-auto=create-drop
```

**Record conversion:**
```java
// Before
public class ErrorMessage {
    private int statusCode;
    private Date timestamp;
    public ErrorMessage(int statusCode, Date timestamp) { ... }
    public int getStatusCode() { return statusCode; }
}

// After
public record ErrorMessage(int statusCode, Instant timestamp) {}
```

---

## Motivation

Built from 3 years of experience as an SDE at Barclays, where I manually performed
three Java migration projects — JDK 8 to 11, 11 to 18, and 11 to 21 — each taking
approximately 2 weeks of repetitive work.

The same four types of changes appeared in every migration:
- Updating build files (java.version, plugin versions)
- Modernizing Java syntax (records, var, text blocks)
- Fixing dependency version conflicts (Lombok, Mockito, Surefire)
- Migrating namespaces (javax to jakarta)

This agent automates all four. What took 2 weeks now takes about 10 minutes.

---

CS Coding Agent Assignment — Srimathi Ravisankar, February 2026
