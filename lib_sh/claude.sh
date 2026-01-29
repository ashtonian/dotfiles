#!/bin/bash
# Claude Code helper functions for efficient multi-session workflows
# Source this file in your .zshrc: source ~/.dotfiles/lib_sh/claude.sh

#=============================================================================
# SESSION MANAGEMENT
#=============================================================================

# Create git worktree and start Claude session
# Usage: cworktree <branch-name> [base-branch]
cworktree() {
  local branch="${1:-feature-$(date +%s)}"
  local base="${2:-main}"
  local worktree_dir="../worktrees/${branch}"

  if [[ ! -d ".git" ]] && [[ ! -f ".git" ]]; then
    echo "Error: Not in a git repository"
    return 1
  fi

  mkdir -p "../worktrees"
  git worktree add "$worktree_dir" -b "$branch" "$base" || return 1

  echo "Created worktree at $worktree_dir"
  echo "Starting Claude session..."
  cd "$worktree_dir" && claude --session-id "$(uuidgen)"
}

cworktree-list() { git worktree list; }
cworktree-clean() { git worktree prune && echo "Cleaned stale worktrees"; }

# Resume or list Claude sessions
cresume() {
  if [[ -n "$1" ]]; then claude --resume "$1"; else claude --resume; fi
}

ccontinue() { claude --continue; }
cfork() { claude --continue --fork-session; }
copus() { claude --model opus "$@"; }
cplan() { claude --permission-mode plan "$@"; }
cedit() { claude --permission-mode acceptEdits "$@"; }
cadd() { claude --add-dir "$@"; }
cprint() { claude --print "$@"; }
cjson() { claude --print --output-format json "$@"; }

#=============================================================================
# DOCUMENTATION WORKFLOWS
#=============================================================================

# Generate/update CLAUDE.md - AI context file for the repo
# Usage: cdoc [output-file]
cdoc() {
  local output="${1:-CLAUDE.md}"
  claude --print "Analyze this repository thoroughly. Create or update a ${output} file that includes:
1. Project overview and purpose
2. Tech stack and architecture
3. Directory structure explanation
4. Key files and their purposes
5. Build/run/test commands
6. Development workflow
7. Common tasks and how to do them
8. Known issues or gotchas
9. Contributing guidelines summary

Follow any existing documentation conventions in this repo. Be comprehensive but concise."
}

# Update all README files in the repo
# Usage: creadme
creadme() {
  claude --print "Find all README.md files in this repository. For each one:
1. Update outdated information
2. Ensure consistent formatting
3. Add missing sections (installation, usage, API if applicable)
4. Fix broken links
5. Update badges if present

Then identify directories that SHOULD have a README but don't (packages, modules, significant folders).
Create appropriate READMEs for those directories.

Follow existing conventions in this repo. Don't be verbose - be helpful and accurate."
}

# Generate package/module level documentation
# Usage: cpkgdoc [directory]
cpkgdoc() {
  local dir="${1:-.}"
  claude --print "For the directory '${dir}' and its subdirectories:
1. Identify all packages/modules that lack documentation
2. Create concise README.md files for each that explain:
   - What the package does
   - Key exports/APIs
   - Usage examples
   - Dependencies on other internal packages
3. Follow existing documentation patterns in this repo"
}

# Generate API documentation
# Usage: capidoc
capidoc() {
  claude --print "Analyze all API endpoints, exported functions, and public interfaces in this codebase.
Generate comprehensive API documentation including:
1. Endpoint/function signatures
2. Parameters and return types
3. Example usage
4. Error handling
Output in a format consistent with this project's conventions (OpenAPI, JSDoc, GoDoc, etc.)"
}

# Create architecture documentation
# Usage: carch
carch() {
  claude --print "Analyze this codebase and create/update ARCHITECTURE.md covering:
1. High-level system design
2. Component diagram (in mermaid or ASCII)
3. Data flow between components
4. External dependencies and integrations
5. Design patterns used
6. Key architectural decisions and rationale"
}

#=============================================================================
# CODE QUALITY & REVIEW
#=============================================================================

# Review current branch changes
# Usage: creview [base-branch]
creview() {
  local base="${1:-main}"
  claude --print "Review the changes in this branch compared to '${base}':
1. Summarize what changed and why
2. Identify potential bugs or issues
3. Check for security concerns
4. Suggest improvements
5. Note any missing tests
6. Check for style/convention violations

Be constructive and specific. Reference file:line for issues."
}

# Find and document technical debt
# Usage: cdebt
cdebt() {
  claude --print "Analyze this codebase for technical debt:
1. Find TODO/FIXME/HACK comments and categorize them
2. Identify outdated patterns or deprecated usage
3. Find code duplication
4. Identify missing error handling
5. Find hardcoded values that should be config
6. Identify tight coupling or poor abstractions
7. Find missing or inadequate tests

Output as a prioritized list with effort estimates (small/medium/large).
Create or update a TECH_DEBT.md file with findings."
}

# Security audit
# Usage: csecurity
csecurity() {
  claude --print "Perform a security audit of this codebase:
1. Check for hardcoded secrets or credentials
2. Identify SQL injection vulnerabilities
3. Find XSS vulnerabilities
4. Check for insecure dependencies
5. Identify authentication/authorization issues
6. Check for sensitive data exposure
7. Review input validation

Output findings with severity (critical/high/medium/low) and remediation steps."
}

# Find dead/unused code
# Usage: cdead
cdead() {
  claude --print "Analyze this codebase for dead code:
1. Unused functions and methods
2. Unused imports/dependencies
3. Unreachable code paths
4. Unused variables and constants
5. Deprecated code still present
6. Commented-out code blocks

List findings with file:line references. Be conservative - only flag code you're confident is unused."
}

# Dependency audit
# Usage: cdeps
cdeps() {
  claude --print "Audit dependencies in this project:
1. List all direct and indirect dependencies
2. Identify outdated packages (check latest versions)
3. Find deprecated packages
4. Identify packages with known vulnerabilities
5. Find unused dependencies
6. Suggest lighter alternatives where appropriate

Output as actionable recommendations."
}

#=============================================================================
# REFACTORING & MODERNIZATION
#=============================================================================

# Identify refactoring opportunities
# Usage: crefactor [file-or-dir]
crefactor() {
  local target="${1:-.}"
  claude --print "Analyze '${target}' for refactoring opportunities:
1. Long functions that should be split
2. Code duplication to extract
3. Complex conditionals to simplify
4. Poor naming to improve
5. Missing abstractions
6. Violated SOLID principles

Prioritize by impact and provide specific suggestions with before/after examples."
}

# Modernize legacy patterns
# Usage: cmodernize [file-or-dir]
cmodernize() {
  local target="${1:-.}"
  claude --print "Analyze '${target}' for modernization opportunities:
1. Outdated language features (use modern equivalents)
2. Deprecated API usage
3. Old dependency patterns
4. Legacy error handling
5. Callback hell -> async/await (or equivalent)
6. Old testing patterns

Suggest modern alternatives with migration steps."
}

# Add/improve type annotations
# Usage: ctypes [file-or-dir]
ctypes() {
  local target="${1:-.}"
  claude --print "Analyze '${target}' and improve type safety:
1. Add missing type annotations
2. Replace 'any' types with specific types
3. Add interface/type definitions
4. Improve generic type usage
5. Add JSDoc/docstrings where types can't be added

Follow existing type conventions in this project."
}

#=============================================================================
# TESTING
#=============================================================================

# Add missing tests
# Usage: ctests [file-or-dir]
ctests() {
  local target="${1:-.}"
  claude --print "Analyze '${target}' and add missing tests:
1. Identify untested functions/methods
2. Identify untested edge cases
3. Identify untested error paths
4. Create test files following project conventions
5. Use existing test patterns and utilities

Focus on high-value tests that catch real bugs."
}

# Improve test coverage
# Usage: ccoverage
ccoverage() {
  claude --print "Analyze test coverage in this project:
1. Identify files with low or no coverage
2. Find critical paths without tests
3. Identify missing integration tests
4. Find tests that don't actually test anything
5. Suggest specific tests to add

Prioritize by risk - focus on code that handles money, auth, or data."
}

# Generate test fixtures/mocks
# Usage: cfixtures [file-or-dir]
cfixtures() {
  local target="${1:-.}"
  claude --print "For '${target}', generate test fixtures and mocks:
1. Create realistic test data
2. Generate mock implementations for external services
3. Create factory functions for test objects
4. Add helper utilities for common test setups

Follow existing fixture patterns in this project."
}

#=============================================================================
# PROJECT SETUP & ONBOARDING
#=============================================================================

# Generate onboarding documentation
# Usage: conboard
conboard() {
  claude --print "Create comprehensive onboarding documentation for new developers:
1. Prerequisites and system requirements
2. Step-by-step setup guide
3. IDE/editor setup recommendations
4. Development workflow walkthrough
5. Common tasks and commands
6. Where to find things
7. Who to ask for help
8. First issue suggestions

Create or update ONBOARDING.md or CONTRIBUTING.md as appropriate."
}

# Analyze project for a new developer
# Usage: cexplain
cexplain() {
  claude --print "I'm new to this codebase. Help me understand:
1. What does this project do? (2-3 sentences)
2. What's the tech stack?
3. What's the directory structure?
4. Where does execution start?
5. What are the key abstractions I need to understand?
6. What's the typical development workflow?
7. What are the gotchas I should know about?

Be concise but comprehensive."
}

# Bootstrap a greenfield project
# Usage: cinit <project-type>
cinit() {
  local ptype="${1:-}"
  if [[ -z "$ptype" ]]; then
    echo "Usage: cinit <project-type>"
    echo "Types: go, node, python, rust, react, nextjs, cli"
    return 1
  fi
  claude --print "Initialize a new ${ptype} project with best practices:
1. Create appropriate directory structure
2. Initialize package management
3. Set up linting and formatting
4. Configure testing framework
5. Create CI/CD config (GitHub Actions)
6. Add standard documentation (README, LICENSE, CONTRIBUTING)
7. Set up git hooks (pre-commit)
8. Create CLAUDE.md for AI assistance

Follow current best practices for ${ptype} projects."
}

#=============================================================================
# MAINTENANCE & OPERATIONS
#=============================================================================

# Fix all linting issues
# Usage: clint
clint() {
  claude --print "Fix all linting and formatting issues in this codebase:
1. Run the project's linter and fix auto-fixable issues
2. Manually fix remaining issues
3. Ensure consistent code style throughout
4. Don't change logic, only style

Use the project's existing linter configuration."
}

# Update dependencies safely
# Usage: cupdate
cupdate() {
  claude --print "Update dependencies in this project safely:
1. List all outdated dependencies
2. Categorize as patch/minor/major updates
3. Check changelogs for breaking changes
4. Update patch versions automatically
5. Suggest update strategy for minor/major versions
6. Run tests to verify nothing broke

Be conservative - stability over latest versions."
}

# Generate changelog
# Usage: cchangelog [since-tag]
cchangelog() {
  local since="${1:-}"
  local since_arg=""
  [[ -n "$since" ]] && since_arg="since tag '${since}'"
  claude --print "Generate a changelog ${since_arg}:
1. Analyze git commits
2. Group by: Features, Bug Fixes, Breaking Changes, Other
3. Write user-friendly descriptions (not commit messages)
4. Include PR/issue references if available
5. Follow Keep a Changelog format

Output markdown suitable for CHANGELOG.md"
}

# Prepare for PR
# Usage: cpr [base-branch]
cpr() {
  local base="${1:-main}"
  claude --print "Prepare this branch for a pull request to '${base}':
1. Review all changes and summarize them
2. Ensure all tests pass
3. Check for linting issues
4. Verify documentation is updated
5. Draft a PR description with:
   - Summary of changes
   - Testing done
   - Screenshots if UI changes
   - Breaking changes if any
6. Suggest reviewers based on code ownership"
}

#=============================================================================
# LEGACY PROJECT RESCUE
#=============================================================================

# Assess a legacy project
# Usage: clegacy
clegacy() {
  claude --print "Assess this legacy codebase:
1. Determine language versions and framework versions
2. Identify how outdated dependencies are
3. Assess test coverage and quality
4. Identify security vulnerabilities
5. Find deprecated patterns and APIs
6. Estimate modernization effort (small/medium/large/rewrite)
7. Recommend prioritized action plan
8. Identify quick wins for immediate improvement

Create a LEGACY_ASSESSMENT.md with findings."
}

# Create missing documentation for undocumented project
# Usage: cundoc
cundoc() {
  claude --print "This project has little to no documentation. Create:
1. README.md with project overview, setup, usage
2. CLAUDE.md with AI-friendly context
3. ARCHITECTURE.md with system design
4. Package/module READMEs for key directories
5. Inline comments for complex code sections
6. API documentation if applicable

Reverse-engineer understanding from the code."
}

# Identify and fix code rot
# Usage: crot
crot() {
  claude --print "Identify code rot in this project:
1. Find code that hasn't been touched in years
2. Identify features that might be unused
3. Find tests that have been skipped/disabled
4. Identify config for removed features
5. Find orphaned files
6. Check for inconsistent patterns (old vs new style)

Suggest cleanup actions with risk assessment."
}

#=============================================================================
# ALIASES (add these to your .zshrc or source this file)
#=============================================================================
# These are defined as aliases when this file is sourced

# Claude CLI shortcuts - Session Management
alias c='claude'                        # Basic start
alias cc='claude --continue'            # Continue last session
alias cr='claude --resume'              # Resume picker
alias cf='claude --continue --fork-session'  # Fork and continue
alias co='claude --model opus'          # Use Opus model

# Worktree workflow
alias cw='cworktree'                    # Create worktree + session
alias cwl='cworktree-list'              # List worktrees
alias cwc='cworktree-clean'             # Clean stale worktrees

# Documentation (most common)
alias crev='creview'                    # Review branch changes
alias csec='csecurity'                  # Security audit

# Quick Actions
alias cfix='clint'                      # Fix linting issues
alias cupd='cupdate'                    # Update dependencies
alias ctest='ctests'                    # Add missing tests
