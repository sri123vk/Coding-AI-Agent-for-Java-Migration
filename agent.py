#!/usr/bin/env python3
"""
Java 11 → 21 Migration Agent  (A + B + C + D)
-----------------------------------------------
A: Build config (Maven/Gradle) + test + fix breaks
B: Code modernization (records, text blocks, pattern matching, switch)
C: Dependency upgrade (plugins, test libs, bytecode tools)
D: Spring Boot 2.x → 3.x migration (javax→jakarta, security, etc.)

Powered by: Gemini 2.5 Flash · Raw API · No frameworks

Usage:  python agent.py <github-repo-url>
"""

import os, sys, json, subprocess, time
from pathlib import Path
from datetime import datetime

import google.genai as genai
from google.genai import types

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.rule import Rule
from rich.syntax import Syntax
from rich import box

console = Console()

# ─────────────────────────────────────────────────────────────
#  TOOL SCHEMAS
# ─────────────────────────────────────────────────────────────

TOOLS = [types.Tool(function_declarations=[
    types.FunctionDeclaration(
        name="run_shell",
        description="Run a shell command. Use for git, mvn, gradle, sed, grep, find, javac.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "command":     types.Schema(type=types.Type.STRING,  description="Shell command"),
                "working_dir": types.Schema(type=types.Type.STRING,  description="Working directory (optional)"),
                "timeout":     types.Schema(type=types.Type.INTEGER, description="Timeout seconds (default 300)"),
            },
            required=["command"]
        )
    ),
    types.FunctionDeclaration(
        name="read_file",
        description="Read a file's contents.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={"path": types.Schema(type=types.Type.STRING, description="File path")},
            required=["path"]
        )
    ),
    types.FunctionDeclaration(
        name="write_file",
        description="Write or overwrite a file. Use for Java source files ONLY, not pom.xml.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "path":    types.Schema(type=types.Type.STRING, description="File path"),
                "content": types.Schema(type=types.Type.STRING, description="New content"),
            },
            required=["path", "content"]
        )
    ),
    types.FunctionDeclaration(
        name="list_directory",
        description="List files recursively.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "path":      types.Schema(type=types.Type.STRING,  description="Directory"),
                "max_depth": types.Schema(type=types.Type.INTEGER, description="Max depth (default 4)"),
            },
            required=["path"]
        )
    ),
    types.FunctionDeclaration(
        name="search_in_files",
        description="Search for a pattern across files.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "directory":      types.Schema(type=types.Type.STRING, description="Directory"),
                "pattern":        types.Schema(type=types.Type.STRING, description="Regex pattern"),
                "file_extension": types.Schema(type=types.Type.STRING, description="e.g. .java"),
            },
            required=["directory", "pattern"]
        )
    ),
    types.FunctionDeclaration(
        name="log_change",
        description="Log every migration change. Call after EVERY file you modify.",
        parameters=types.Schema(
            type=types.Type.OBJECT,
            properties={
                "category":    types.Schema(type=types.Type.STRING, description="BUILD_CONFIG | CODE_MODERNIZATION | DEPENDENCY | SPRING_BOOT | BUG_FIX | TEST_FIX"),
                "file":        types.Schema(type=types.Type.STRING, description="File changed"),
                "change_type": types.Schema(type=types.Type.STRING, description="e.g. Record Class, javax->jakarta"),
                "description": types.Schema(type=types.Type.STRING, description="What changed and why"),
                "before":      types.Schema(type=types.Type.STRING, description="Snippet before"),
                "after":       types.Schema(type=types.Type.STRING, description="Snippet after"),
            },
            required=["category", "file", "change_type", "description"]
        )
    ),
])]

# ─────────────────────────────────────────────────────────────
#  TOOL IMPLEMENTATIONS
# ─────────────────────────────────────────────────────────────

change_log = []

def run_shell(command, working_dir=None, timeout=300):
    try:
        r = subprocess.run(command, shell=True, capture_output=True,
                           text=True, cwd=working_dir, timeout=timeout)
        out = r.stdout[:8000]
        err = r.stderr[:4000]
        return {"stdout": out, "stderr": err, "returncode": r.returncode, "success": r.returncode == 0}
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": f"Timed out after {timeout}s", "returncode": -1, "success": False}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": -1, "success": False}

def read_file(path):
    try:
        c = Path(path).read_text(encoding="utf-8", errors="replace")
        lines = c.splitlines()
        if len(c) > 6000:
            c = c[:6000] + f"\n... (truncated, {len(lines)} total lines, showing first 6000 chars)"
        return {"content": c, "lines": len(lines)}
    except Exception as e:
        return {"error": str(e)}

def write_file(path, content):
    try:
        # Save backup before overwriting
        p = Path(path)
        if p.exists():
            backup = Path(str(path) + ".bak")
            backup.write_text(p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "bytes": len(content)}
    except Exception as e:
        return {"error": str(e)}

def list_directory(path, max_depth=4):
    r = subprocess.run(
        f"find {path} -maxdepth {max_depth} "
        "-not -path '*/.git/*' -not -path '*/target/*' "
        "-not -path '*/.gradle/*' -not -path '*/build/*' "
        "| sort | head -300",
        shell=True, capture_output=True, text=True)
    return {"tree": r.stdout}

def search_in_files(directory, pattern, file_extension=".java"):
    r = subprocess.run(
        f'grep -rn --include="*{file_extension}" -E "{pattern}" {directory} 2>/dev/null | head -100',
        shell=True, capture_output=True, text=True)
    return {"matches": r.stdout, "count": len([l for l in r.stdout.splitlines() if l.strip()])}

def log_change(category, file, change_type, description, before="", after=""):
    change_log.append({"category": category, "file": file, "change_type": change_type,
                        "description": description, "before": before, "after": after,
                        "timestamp": datetime.now().strftime("%H:%M:%S")})
    return {"logged": True, "total": len(change_log)}

def execute_tool(name, args):
    if name == "run_shell":        return run_shell(args["command"], args.get("working_dir"), args.get("timeout", 300))
    elif name == "read_file":      return read_file(args["path"])
    elif name == "write_file":     return write_file(args["path"], args["content"])
    elif name == "list_directory": return list_directory(args["path"], args.get("max_depth", 4))
    elif name == "search_in_files":return search_in_files(args["directory"], args["pattern"], args.get("file_extension", ".java"))
    elif name == "log_change":     return log_change(args["category"], args["file"], args["change_type"],
                                                     args["description"], args.get("before",""), args.get("after",""))
    return {"error": f"Unknown tool: {name}"}

# ─────────────────────────────────────────────────────────────
#  DISPLAY
# ─────────────────────────────────────────────────────────────

ICONS  = {"run_shell":"⚡","read_file":"📖","write_file":"✏️ ","list_directory":"📁","search_in_files":"🔍","log_change":"📋"}
COLORS = {"BUILD_CONFIG":"cyan","CODE_MODERNIZATION":"green","DEPENDENCY":"yellow","SPRING_BOOT":"magenta","BUG_FIX":"red","TEST_FIX":"orange3"}

def print_banner():
    console.print()
    console.print(Panel.fit(
        "[bold cyan]☕  Java 11 → 21 Migration Agent[/bold cyan]\n"
        "[dim]  A: Build Config  B: Code Modernization  C: Dependencies  D: Spring Boot 2→3[/dim]\n"
        "[dim]  Powered by Gemini 2.5 Flash · Raw API · No frameworks[/dim]",
        border_style="cyan", padding=(1, 4)))
    console.print()

def print_tool_call(name, args):
    icon = ICONS.get(name, "🔧")
    if name == "run_shell":
        detail = f"[bold yellow]{name}[/bold yellow]  [dim]$ {args.get('command','')[:130]}[/dim]"
    elif name == "write_file":
        detail = f"[bold yellow]{name}[/bold yellow]  [green]{args.get('path','')}[/green]"
    elif name == "read_file":
        detail = f"[bold yellow]{name}[/bold yellow]  [dim]{args.get('path','')}[/dim]"
    elif name == "log_change":
        cat = args.get("category","")
        col = COLORS.get(cat,"white")
        detail = f"[bold yellow]{name}[/bold yellow]  [{col}]{args.get('change_type','')}[/{col}]  [dim]{Path(args.get('file','')).name}[/dim]"
    else:
        detail = f"[bold yellow]{name}[/bold yellow]  [dim]{str(args)[:120]}[/dim]"
    console.print(f"  {icon} {detail}")

def print_tool_result(name, result):
    if name == "run_shell":
        rc = result.get("returncode", 0)
        mark = "[green]✓[/green]" if rc == 0 else "[red]✗[/red]"
        stdout = result.get("stdout","").strip()
        stderr = result.get("stderr","").strip()
        if stdout:
            lines = stdout.splitlines()[:5]
            console.print(f"    {mark} [dim]{chr(10)+'     '.join(lines)}[/dim]")
        if stderr and rc != 0:
            lines = stderr.splitlines()[:4]
            console.print(f"    [red]  ↳ {chr(10)+'     '.join(lines)}[/red]")
    elif name == "write_file":
        if result.get("success"):
            console.print(f"    [green]✓ Saved ({result.get('bytes',0)} bytes) — backup created[/green]")
        elif result.get("error"):
            console.print(f"    [red]✗ {result['error']}[/red]")
    elif name == "log_change":
        cat = change_log[-1]["category"] if change_log else ""
        col = COLORS.get(cat, "white")
        console.print(f"    [green]✓[/green] [{col}]{cat}[/{col}] change #{result.get('total',0)} logged")

def print_agent_text(text):
    if text and text.strip():
        for line in text.strip().splitlines():
            if line.strip():
                console.print(f"  [cyan]→[/cyan] {line}")

# ─────────────────────────────────────────────────────────────
#  MIGRATION REPORT
# ─────────────────────────────────────────────────────────────

def save_report(repo_url, repo_dir, test_passed):
    lines = [
        "# Java 11 → 21 Migration Report",
        f"\n**Repository:** {repo_url}",
        f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Tests Passed:** {'✅ YES' if test_passed else '❌ NO / Not run'}",
        f"**Total Changes:** {len(change_log)}",
        "\n---\n",
    ]
    titles = {
        "BUILD_CONFIG":       "## 🏗️  A — Build Configuration",
        "CODE_MODERNIZATION": "## ✨  B — Code Modernization",
        "DEPENDENCY":         "## 📦  C — Dependency Upgrades",
        "SPRING_BOOT":        "## 🌱  D — Spring Boot 2→3 Migration",
        "BUG_FIX":            "## 🐛  Bug Fixes",
        "TEST_FIX":           "## 🧪  Test Fixes",
    }
    groups = {}
    for c in change_log:
        groups.setdefault(c["category"], []).append(c)

    for cat, title in titles.items():
        entries = groups.get(cat, [])
        if not entries:
            continue
        lines.append(title + "\n")
        for e in entries:
            lines.append(f"### `{Path(e['file']).name}` — {e['change_type']}")
            lines.append(f"**File:** `{e['file']}`  \n**Time:** {e.get('timestamp','')}\n")
            lines.append(e["description"])
            if e.get("before"): lines.append(f"\n**Before:**\n```java\n{e['before']}\n```")
            if e.get("after"):  lines.append(f"\n**After:**\n```java\n{e['after']}\n```")
            lines.append("")

    lines += [
        "---",
        "\n## 🔄 How to Revert All Changes",
        "```bash",
        "git diff HEAD          # see all changes",
        "git diff HEAD -- file  # see one file",
        "git checkout .         # revert everything",
        "git checkout -- file   # revert one file",
        "```",
        "\n## 📋 Changed Files",
    ]
    changed = sorted(set(e['file'] for e in change_log))
    for f in changed:
        lines.append(f"- `{f}`")

    lines.append("\n_Generated by Java 11→21 Migration Agent (Gemini 2.5 Flash)_")

    path = Path(repo_dir) / "MIGRATION_REPORT.md"
    try:
        path.write_text("\n".join(lines), encoding="utf-8")
    except Exception:
        path = Path("/tmp/MIGRATION_REPORT.md")
        path.write_text("\n".join(lines), encoding="utf-8")
    return str(path)

def print_summary(repo_url, repo_dir, test_passed):
    console.print()
    console.print(Rule("[bold cyan]Migration Summary[/bold cyan]", style="cyan"))
    console.print()

    if not change_log:
        console.print("  [yellow]No changes were logged.[/yellow]")
    else:
        labels = {
            "BUILD_CONFIG":       ("🏗  Build Config",   "cyan"),
            "CODE_MODERNIZATION": ("✨ Modernization",    "green"),
            "DEPENDENCY":         ("📦 Dependencies",     "yellow"),
            "SPRING_BOOT":        ("🌱 Spring Boot",      "magenta"),
            "BUG_FIX":            ("🐛 Bug Fixes",        "red"),
            "TEST_FIX":           ("🧪 Test Fixes",       "orange3"),
        }
        table = Table(box=box.ROUNDED, border_style="cyan", header_style="bold cyan", show_lines=True)
        table.add_column("Category",    style="bold",   width=20)
        table.add_column("File",        style="dim",    width=32)
        table.add_column("Change",      style="yellow", width=28)
        table.add_column("Description", style="white")

        groups = {}
        for c in change_log:
            groups.setdefault(c["category"], []).append(c)

        for cat, entries in groups.items():
            label, color = labels.get(cat, (cat, "white"))
            for i, e in enumerate(entries):
                table.add_row(
                    f"[{color}]{label}[/{color}]" if i == 0 else "",
                    Path(e["file"]).name,
                    e["change_type"],
                    e["description"][:65]
                )
        console.print(table)

    console.print()
    test_icon = "[green]✅ PASSED[/green]" if test_passed else "[red]❌ FAILED / Not run[/red]"
    console.print(f"  [bold]Total changes:[/bold]  {len(change_log)}")
    console.print(f"  [bold]Tests:[/bold]          {test_icon}")

    report = save_report(repo_url, repo_dir, test_passed)
    console.print(f"  [bold]Report saved:[/bold]   [cyan]{report}[/cyan]")

    # Show how to view modified files
    console.print()
    console.print(Rule("[bold]View Your Changes[/bold]", style="dim"))
    console.print(f"  [bold]See all changes:[/bold]    [cyan]git -C {repo_dir} diff HEAD[/cyan]")
    console.print(f"  [bold]List changed files:[/bold] [cyan]git -C {repo_dir} diff --name-only HEAD[/cyan]")
    console.print(f"  [bold]View report:[/bold]        [cyan]cat {report}[/cyan]")
    console.print(f"  [bold]Revert all:[/bold]         [cyan]git -C {repo_dir} checkout .[/cyan]")
    console.print()

# ─────────────────────────────────────────────────────────────
#  SYSTEM PROMPT  (A + B + C + D)
# ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert Java migration agent. Migrate a Java 11 project to Java 21.
Cover ALL FOUR areas below. Be thorough and methodical.

═══════════════════════════════════════
AREA A — BUILD CONFIGURATION
═══════════════════════════════════════
CRITICAL: Use sed for ALL pom.xml changes. NEVER rewrite the whole pom.xml with write_file.

For Maven (pom.xml) — use these exact sed patterns (replace REPO with actual path):
  sed -i 's|<java.version>[^<]*</java.version>|<java.version>21</java.version>|g' REPO/pom.xml
  sed -i 's|<maven.compiler.source>[^<]*</maven.compiler.source>|<maven.compiler.source>21</maven.compiler.source>|g' REPO/pom.xml
  sed -i 's|<maven.compiler.target>[^<]*</maven.compiler.target>|<maven.compiler.target>21</maven.compiler.target>|g' REPO/pom.xml

After EVERY pom.xml change: mvn validate -f REPO/pom.xml
If validate fails: fix only the specific broken line with sed.

For Gradle (build.gradle):
  Add: java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
  Use write_file for gradle files (they're simpler).

log_change(category="BUILD_CONFIG") for each change.

═══════════════════════════════════════
AREA B — CODE MODERNIZATION
═══════════════════════════════════════
For each Java file, use read_file then write_file with modernized version:

1. Text Blocks: multi-line String concatenation -> triple-quote text blocks (triple-quoted strings)
2. Records: simple POJOs (only private fields + getters + equals/hashCode/toString) → record
3. Pattern Matching instanceof:
   Before: if (obj instanceof String) { String s = (String) obj; ... }
   After:  if (obj instanceof String s) { ... }
4. Switch Expressions:
   Before: switch(x) { case A: return 1; case B: return 2; }
   After:  yield switch(x) { case A -> 1; case B -> 2; };
5. var: use for obvious local variable types
6. String.isBlank() instead of .trim().isEmpty()
7. List.of() / Set.of() / Map.of() instead of Arrays.asList() / new ArrayList<>()

log_change(category="CODE_MODERNIZATION") for each file modified.

═══════════════════════════════════════
AREA C — DEPENDENCY UPGRADES
═══════════════════════════════════════
Use sed for pom.xml/build.gradle dependency version changes.
Check and fix:
- Lombok: upgrade to 1.18.30+
- Mockito: upgrade to 5.x
- Maven Surefire: upgrade to 3.2.5+
- Maven Compiler: upgrade to 3.12.1+
- Byte Buddy: upgrade to 1.14+ (needed by Mockito on Java 21)
- Jackson: upgrade to 2.15+ (Java 21 compatibility)
- Remove or update any plugin using ASM < 9.x

Always run mvn validate after dependency changes.
log_change(category="DEPENDENCY") for each version change.

═══════════════════════════════════════
AREA E — SERIALIZATION & JSON CHANGES
═══════════════════════════════════════
Check for Jackson/serialization issues common in Java 21 migrations:

1. Jackson on Records: records need explicit annotations for proper serialization
   - Search: search_in_files(pattern="^public record ", file_extension=".java")
   - If records are used in REST responses, ensure they have @JsonProperty or constructor annotations
   - Fix pattern: add @JsonProperty to record components if needed

2. Deprecated Date types: replace java.util.Date with java.time.*
   - Search: search_in_files(pattern="import java.util.Date", file_extension=".java")
   - Replace with LocalDate, LocalDateTime, or ZonedDateTime
   - Add @JsonFormat(pattern="yyyy-MM-dd") if needed

3. ObjectMapper deprecated configs:
   - Search: search_in_files(pattern="MapperFeature|enable(DeserializationFeature", file_extension=".java")
   - Replace deprecated MapperFeature usages with current equivalents

log_change(category="CODE_MODERNIZATION") for each serialization fix.

═══════════════════════════════════════
AREA F — HTTP CLIENT MIGRATION
═══════════════════════════════════════
Check if RestTemplate is used and migrate to RestClient (Spring Boot 3.2+):

1. Search: search_in_files(pattern="RestTemplate|new RestTemplate", file_extension=".java")
2. If found and project uses Spring Boot 3.x, migrate each usage:
   Before:
     RestTemplate restTemplate = new RestTemplate();
     String result = restTemplate.getForObject(url, String.class);
     ResponseEntity<Foo> r = restTemplate.postForEntity(url, body, Foo.class);
   After:
     RestClient restClient = RestClient.create();
     String result = restClient.get().uri(url).retrieve().body(String.class);
     Foo r = restClient.post().uri(url).body(body).retrieve().body(Foo.class);
3. Update @Bean definitions: replace RestTemplate bean with RestClient.Builder bean
4. If WebFlux is on classpath, suggest WebClient for reactive use cases
5. log_change(category="CODE_MODERNIZATION", change_type="RestTemplate->RestClient") for each file

═══════════════════════════════════════
AREA D — SPRING BOOT 2→3 (if applicable)
═══════════════════════════════════════
First check: grep -r "spring-boot" REPO/pom.xml to detect Spring Boot version.
If Spring Boot 2.x detected:

1. javax.* → jakarta.* migration (MOST IMPORTANT):
   sed -i 's/import javax.persistence./import jakarta.persistence./g' file.java
   sed -i 's/import javax.validation./import jakarta.validation./g' file.java
   sed -i 's/import javax.servlet./import jakarta.servlet./g' file.java
   sed -i 's/import javax.transaction./import jakarta.transaction./g' file.java
   Apply to ALL Java files at once:
   find REPO/src -name "*.java" | xargs sed -i 's/import javax.persistence./import jakarta.persistence./g'
   find REPO/src -name "*.java" | xargs sed -i 's/import javax.validation./import jakarta.validation./g'
   find REPO/src -name "*.java" | xargs sed -i 's/import javax.servlet./import jakarta.servlet./g'
   find REPO/src -name "*.java" | xargs sed -i 's/import javax.transaction./import jakarta.transaction./g'

2. Spring Security config: WebSecurityConfigurerAdapter removed → use SecurityFilterChain bean
3. Update spring-boot-starter-parent version to 3.2.x in pom.xml with sed

log_change(category="SPRING_BOOT") for each change.

═══════════════════════════════════════
TEST & FIX LOOP
═══════════════════════════════════════
After all changes, run: mvn -q test -f REPO/pom.xml (or ./gradlew test)
If FAILS:
  1. Read the full error carefully
  2. Identify the root cause (compilation error? test failure? missing dependency?)
  3. Fix the specific issue
  4. Run tests again
  5. Repeat up to 3 times
  6. log_change(category="BUG_FIX" or "TEST_FIX")

═══════════════════════════════════════
STRICT WORKFLOW
═══════════════════════════════════════
1. git clone into /tmp/<repo-name>
2. list_directory (understand structure)
3. Detect build tool: does pom.xml exist? → Maven. does build.gradle exist? → Gradle.
4. READ the entire build file first before making ANY changes.

IF GRADLE PROJECT:
   a. Read build.gradle carefully — note Spring Boot version, java version, dependencies
   b. Read gradle/wrapper/gradle-wrapper.properties — note Gradle version
   c. Upgrade Gradle wrapper to 8.7: change distributionUrl in gradle-wrapper.properties
   d. Use write_file to update build.gradle with Java 21 toolchain:
      java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }
   e. Run: cd /tmp/<repo-name> && ./gradlew build --no-daemon 2>&1 | head -50
   f. Fix build.gradle errors before proceeding to code changes
   g. Run: cd /tmp/<repo-name> && ./gradlew test --no-daemon

IF MAVEN PROJECT:
   a. Use sed for all pom.xml changes (NEVER rewrite entirely)
   b. Run: mvn validate -f /tmp/<repo>/pom.xml after each change
   c. Run: mvn -q test -f /tmp/<repo>/pom.xml

5. Check Spring Boot version → if 2.x, do Area D (javax→jakarta) FIRST before code changes
6. Area B: modernize Java files one by one
7. Area C: update dependency versions
8. Area E: check serialization/JSON issues
9. Area F: check RestTemplate usage
10. Run tests, read full error output, fix specific issue, retry up to 3 times
11. log_change after EVERY change

CRITICAL FOR GRADLE: Always run gradle commands from the project directory:
  cd /tmp/<repo-name> && ./gradlew test --no-daemon
NOT: ./gradlew test -f build.gradle (this does not work for Gradle)

CRITICAL: Read the FULL error output when tests fail. Fix the ROOT CAUSE.
If build.gradle has a syntax/plugin error, fix that FIRST before running tests.

COMMON ERRORS AND EXACT FIXES:

1. "Override is not a repeatable annotation interface"
   Cause: sed for text block inserted a duplicate @Override annotation.
   Fix: read the file, find the double @Override, remove the duplicate:
     sed -i '0,/@Override/{/@Override/{N;s/@Override\n.*@Override/@Override/}}' FILE.java
   Or simply read the file and use write_file with the corrected content.

2. "package jakarta.cache does not exist"
   Cause: javax.cache has NO jakarta equivalent - it stayed as javax.cache.
   Fix: revert the import back to javax.cache in that file.

3. "class, interface, enum, or record expected at line X"
   Cause: a sed range command deleted too much of the file.
   Fix: read the .bak backup file and restore with write_file.

4. "Non-parseable POM / expected START_TAG"
   Cause: sed inserted literal backslash-n instead of real newlines in XML.
   Fix: read pom.xml, use python3 to insert the plugin block properly:
     run_shell("python3 -c \"import sys; c=open(sys.argv[1]).read(); print(c)\" pom.xml")
   Then use write_file to save the corrected pom.xml.

5. Text block inserts duplicate @Override:
   When converting toString() to text block, use write_file for the WHOLE file,
   not sed, to avoid accidentally duplicating annotations.
"""

# ─────────────────────────────────────────────────────────────
#  MAIN AGENT LOOP
# ─────────────────────────────────────────────────────────────

def run_agent(repo_url):
    print_banner()
    console.print(f"  [bold]Repository:[/bold] [cyan]{repo_url}[/cyan]")
    console.print(f"  [bold]Migration:[/bold]  Java 11 → Java 21  (A + B + C + D)")
    console.print(f"  [bold]Model:[/bold]      Gemini 2.5 Flash")
    console.print(f"  [bold]Started:[/bold]    {datetime.now().strftime('%H:%M:%S')}")
    console.print()
    console.print(Rule(style="dim"))
    console.print()

    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        tools=TOOLS,
        temperature=0.1,
    )

    first_msg = (
        f"Please fully migrate this Java 11 repository to Java 21: {repo_url}\n\n"
        f"Cover all four areas:\n"
        f"  A) Build config — use sed to update pom.xml java version, validate after\n"
        f"  B) Modernize Java code — records, text blocks, pattern matching, switch expressions\n"
        f"  C) Upgrade dependencies — surefire, compiler plugin, lombok, mockito versions\n"
        f"  D) Spring Boot 2→3 — if detected, migrate javax→jakarta and update Boot version\n\n"
        f"Run mvn test after all changes. Fix any failures. Log every change.\n"
        f"Clone the repo into /tmp/ first."
    )

    test_passed = False
    repo_dir    = "/tmp"
    iteration   = 0
    messages    = [first_msg]

    while iteration < 80:
        iteration += 1

        # Build proper Gemini history (strict turn ordering)
        contents = [types.Content(role="user", parts=[types.Part(text=messages[0])])]
        for msg in messages[1:]:
            if isinstance(msg, dict) and msg["role"] == "model":
                contents.append(types.Content(role="model", parts=msg["parts"]))
            elif isinstance(msg, dict) and msg["role"] == "function_results":
                contents.append(types.Content(role="user", parts=msg["parts"]))
            elif isinstance(msg, str):
                contents.append(types.Content(role="user", parts=[types.Part(text=msg)]))

        with console.status("[cyan]Agent thinking...[/cyan]", spinner="dots"):
            try:
                response = client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=contents,
                    config=config,
                )
            except Exception as e:
                err = str(e)
                console.print(f"  [red]API error: {err[:120]}[/red]")
                if "429" in err:
                    console.print("  [yellow]Rate limited — waiting 30s...[/yellow]")
                    time.sleep(30)
                # Reset to just first message to fix turn ordering issues
                messages = [first_msg, "Please continue the migration from where you left off."]
                continue

        candidate = response.candidates[0]
        if candidate.content is None or not candidate.content.parts:
            console.print("  [yellow]→ Empty response, resetting context...[/yellow]")
            messages = [first_msg, "Please continue the migration. Focus on making mvn test pass."]
            continue

        parts      = candidate.content.parts
        tool_calls = [p for p in parts if p.function_call is not None]
        text_parts = [p for p in parts if hasattr(p, "text") and p.text]

        messages.append({"role": "model", "parts": parts})

        for tp in text_parts:
            print_agent_text(tp.text)

        if not tool_calls:
            console.print()
            console.print(Rule("[bold green]Migration Complete[/bold green]", style="green"))
            break

        console.print()
        func_responses = []

        for part in tool_calls:
            name = part.function_call.name
            args = dict(part.function_call.args)

            print_tool_call(name, args)
            result = execute_tool(name, args)
            print_tool_result(name, result)

            # Track test pass
            if name == "run_shell" and result.get("success"):
                cmd = args.get("command","")
                if ("mvn" in cmd or "gradle" in cmd) and "test" in cmd:
                    test_passed = True

            # Track repo dir
            if name == "run_shell" and "git clone" in args.get("command","") and result.get("success"):
                parts_cmd = args["command"].split()
                repo_dir = parts_cmd[-1] if len(parts_cmd) >= 3 else "/tmp/" + repo_url.rstrip("/").split("/")[-1]

            func_responses.append(types.Part(function_response=types.FunctionResponse(
                name=name, response={"result": result}
            )))

        messages.append({"role": "function_results", "parts": func_responses})

    print_summary(repo_url, repo_dir, test_passed)

# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ("--help", "-h"):
        console.print(Panel(
            "[bold cyan]Usage:[/bold cyan]  python agent.py [bold]<github-repo-url>[/bold]\n\n"
            "[dim]Covers:[/dim]\n"
            "  A) Build config (Maven/Gradle) → Java 21\n"
            "  B) Code modernization (records, text blocks, pattern matching)\n"
            "  C) Dependency upgrades (surefire, lombok, mockito)\n"
            "  D) Spring Boot 2→3 migration (javax→jakarta)\n\n"
            "[bold yellow]Required:[/bold yellow]  export GEMINI_API_KEY=YOUR-FREE-KEY\n"
            "[dim]Free key:[/dim]   https://aistudio.google.com/apikey",
            title="[bold]☕  Java 11→21 Migration Agent[/bold]", border_style="cyan", padding=(1,3)))
        sys.exit(0)

    if not os.environ.get("GEMINI_API_KEY"):
        console.print(Panel(
            "[red]GEMINI_API_KEY is not set.[/red]\n\n"
            "Free key at: [cyan]https://aistudio.google.com/apikey[/cyan]\n\n"
            "Then:  [bold]export GEMINI_API_KEY=YOUR-KEY[/bold]",
            border_style="red", title="Missing API Key"))
        sys.exit(1)

    try:
        run_agent(sys.argv[1])
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Interrupted.[/yellow]")
        print_summary(sys.argv[1], "/tmp", False)
        sys.exit(0)

if __name__ == "__main__":
    main()
