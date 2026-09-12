#!/usr/bin/env python3
"""Export a clean public VASP Agent repository.

The private workspace is the source of truth. This script copies only a
small, explicit whitelist of manuscript PDFs, public benchmark data, agent
runtime code, and skills into a separate public repository directory.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path


REPO_URL = "https://github.com/Phoinikas03/VASP_Agent.git"
GIT_REMOTE_URL = "git@github.com:Phoinikas03/VASP_Agent.git"
TITLE = "VASP Agent: An Agentic Framework for Autonomous First-principles Calculations"

MANUSCRIPT_PDFS = [
    "sn-article.pdf",
    "supplementary.pdf",
]

PUBLIC_CODE_FILES = [
    ".env.example",
    "README.md",
    "batch_runner.py",
    "main.py",
    "requirements.txt",
]

PUBLIC_CODE_DIRS = [
    "src",
    "tools",
    "webui",
]

PUBLIC_CODE_EXCLUDES = {
    Path("src/test.py"),
}

PUBLIC_SKILL_DIRS = [
    "incar-builder",
    "incar-dftu-xc",
    "incar-magnetism-soc",
    "incar-performance",
    "incar-smearing-precision",
    "incar-validator",
    "potcar-policy",
    "research-literature",
    "run-vasp",
    "simple-skill-creator",
    "structure-builder",
    "structure-supercell",
    "vasp-error-recovery",
    "workflow-adsorption-energy",
    "workflow-bandgap-legacy-alias",
    "workflow-convergence",
    "workflow-electronic-structure",
    "workflow-eos-lattice-constant",
    "workflow-relax",
]

AUTHOR_GIVEN_FAMILY = [
    ("Zeyu", "Xia"),
    ("Congjie", "Zheng"),
    ("Jinzhe", "Ma"),
    ("Zhongyao", "Wang"),
    ("Shufei", "Zhang"),
    ("Yuqiang", "Li"),
    ("Hang", "Su"),
    ("P.", "Hu"),
    ("Changshui", "Zhang"),
    ("Xingao", "Gong"),
    ("Wanli", "Ouyang"),
    ("Lei", "Bai"),
    ("Dongzhan", "Zhou"),
    ("Mao", "Su"),
]

DENY_NAMES = {
    ".git",
    "__pycache__",
    ".DS_Store",
}

DENY_SUFFIXES = {
    ".aux",
    ".bbl",
    ".blg",
    ".fdb_latexmk",
    ".fls",
    ".log",
    ".out",
    ".synctex.gz",
    ".pyc",
    ".bak",
}

DENY_FILENAMES = {
    ".env",
    "POTCAR",
    "CHG",
    "CHGCAR",
    "WAVECAR",
    "WAVEDER",
    "TMPCAR",
    "PCDAT",
    "PROCAR",
    "DOSCAR",
    "XDATCAR",
    "vasprun.xml",
    "OUTCAR",
    "OSZICAR",
    "REPORT",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    default_workspace = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--workspace-root",
        type=Path,
        default=default_workspace,
        help="Root containing tex/, figshare/, and newvaspagent/.",
    )
    parser.add_argument(
        "--repo-dir",
        type=Path,
        default=default_workspace / "VASP_Agent",
        help="Destination public repository directory.",
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Delete existing destination contents except .git before exporting.",
    )
    parser.add_argument(
        "--init-git",
        action="store_true",
        help="Initialize git metadata and set the public GitHub remote.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned actions without writing files.",
    )
    return parser.parse_args()


def run(cmd: list[str], cwd: Path | None = None, dry_run: bool = False) -> None:
    print("$ " + " ".join(cmd))
    if not dry_run:
        subprocess.run(cmd, cwd=cwd, check=True)


def is_denied(path: Path) -> bool:
    if any(part in DENY_NAMES for part in path.parts):
        return True
    if path.name in DENY_FILENAMES:
        return True
    name = path.name
    return any(name.endswith(suffix) for suffix in DENY_SUFFIXES)


def ensure_clean_destination(repo_dir: Path, clean: bool, dry_run: bool) -> None:
    if not repo_dir.exists():
        if dry_run:
            print(f"mkdir -p {repo_dir}")
        else:
            repo_dir.mkdir(parents=True)
        return

    if not clean:
        return

    for child in repo_dir.iterdir():
        if child.name == ".git":
            continue
        print(f"remove {child}")
        if dry_run:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def copy_file(src: Path, dst: Path, dry_run: bool) -> None:
    if is_denied(src):
        return
    if not src.exists():
        raise FileNotFoundError(src)
    print(f"copy {src} -> {dst}")
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree(
    src: Path,
    dst: Path,
    dry_run: bool,
    excluded_relatives: set[Path] | None = None,
) -> None:
    if not src.exists():
        raise FileNotFoundError(src)
    excluded_relatives = excluded_relatives or set()
    for item in sorted(src.rglob("*")):
        if item.is_dir() or is_denied(item):
            continue
        rel = item.relative_to(src)
        if rel in excluded_relatives:
            print(f"skip {item}")
            continue
        copy_file(item, dst / rel, dry_run)


def write_text(dst: Path, text: str, dry_run: bool) -> None:
    print(f"write {dst}")
    if dry_run:
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text.rstrip() + "\n", encoding="utf-8")


def copy_manuscript(workspace: Path, repo_dir: Path, dry_run: bool) -> None:
    manuscript_src = workspace / "tex" / "main_documents"
    paper_dst = repo_dir / "paper"
    for name in MANUSCRIPT_PDFS:
        copy_file(manuscript_src / name, paper_dst / name, dry_run)


def copy_data_package(workspace: Path, repo_dir: Path, dry_run: bool) -> None:
    figshare = workspace / "figshare"
    data_dst = repo_dir / "data"

    for name in [
        "README.md",
        "DATA_DICTIONARY.md",
        "DATASET_MANIFEST.csv",
        "RAW_FILE_MANIFEST.csv",
    ]:
        copy_file(figshare / name, data_dst / name, dry_run)

    copy_tree(figshare / "datasets", data_dst / "datasets", dry_run)
    copy_tree(figshare / "results" / "summary", data_dst / "results" / "summary", dry_run)


def copy_agent_code(workspace: Path, repo_dir: Path, dry_run: bool) -> None:
    code_src = workspace / "newvaspagent"
    for rel in PUBLIC_CODE_FILES:
        copy_file(code_src / rel, repo_dir / rel, dry_run)

    for dirname in PUBLIC_CODE_DIRS:
        excluded = {
            item.relative_to(dirname)
            for item in PUBLIC_CODE_EXCLUDES
            if item.parts and item.parts[0] == dirname
        }
        copy_tree(code_src / dirname, repo_dir / dirname, dry_run, excluded)


def copy_skills(workspace: Path, repo_dir: Path, dry_run: bool) -> None:
    skills_src = workspace / "newvaspagent" / ".claude" / "skills"
    skills_dst = repo_dir / ".claude" / "skills"
    for skill_name in PUBLIC_SKILL_DIRS:
        copy_tree(skills_src / skill_name, skills_dst / skill_name, dry_run)

    omitted = """# Omitted proprietary PDF skill

The source workspace contains a `pdf` skill that carries a proprietary
third-party license with explicit redistribution restrictions. It is therefore
not exported into this public repository.

All project-owned VASP Agent skills used to describe the manuscript skill
library are exported as sibling directories under `.claude/skills/`.
"""
    write_text(skills_dst / "pdf" / "README.md", omitted, dry_run)


def write_project_files(repo_dir: Path, dry_run: bool) -> None:
    author_lines = "\n".join(
        f"  - family-names: {family}\n    given-names: {given}"
        for given, family in AUTHOR_GIVEN_FAMILY
    )
    citation = f"""cff-version: 1.2.0
message: If you use this repository, please cite the associated manuscript.
title: "{TITLE}"
authors:
{author_lines}
repository-code: "{REPO_URL}"
date-released: "2026-07-03"
"""

    readme = f"""# VASP Agent

This repository is the public companion repository for the manuscript:

**{TITLE}**

It contains the VASP Agent runtime code, public benchmark task definitions,
summary result tables, and the skill library needed to reproduce the reported
calculation workflows. The private development workspace and full raw VASP
outputs are maintained separately.

## Repository Layout

```text
main.py             CLI/Web entry point
batch_runner.py     Batch runner for public benchmark tasks
src/                Agent runtime, tools, scheduler, and LiteLLM bridge
webui/              Local web interface
tools/              Repository maintenance/export helpers
.claude/skills/     Public VASP Agent skill library used by the manuscript
data/datasets/      Public POSCAR inputs and task tables
data/results/       Compact summary result tables for comparison
paper/              Manuscript and supplementary PDFs
```

## Installation

```bash
conda create -n vasp-agent python=3.10 -y
conda activate vasp-agent
pip install -U pip
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` for the model endpoint and local scientific resources. VASP
pseudopotentials are not redistributed; set `PMG_VASP_PSP_DIR` to a local
licensed POTCAR library before running VASP tasks.

## Reproducing Benchmark Runs

List the public relaxation and band-gap tasks:

```bash
python batch_runner.py --data-root data/datasets --tasks relax bandgap --dry-run
```

Run selected tasks after configuring the model endpoint, VASP executable, and
POTCAR path:

```bash
python batch_runner.py --data-root data/datasets --tasks relax --materials Al AlN
python batch_runner.py --data-root data/datasets --tasks bandgap --materials Si GaN
```

Interactive runs can be launched with:

```bash
python main.py --mode web
```

Summary tables used for result comparison are in `data/results/summary/`.
Column definitions are documented in `data/DATA_DICTIONARY.md`.

## What Is Intentionally Excluded

The repository does not include VASP pseudopotentials, API credentials,
scheduler state, agent session logs, full run directories, LaTeX manuscript
sources, paper figure assets, plotting-only scripts, documentation drafts, or
large restart and density files such as `WAVECAR`, `CHGCAR`, `CHG`, and
`POTCAR`.

The proprietary third-party `pdf` skill is represented only by an omission note
because its license restricts redistribution. Filtered raw calculation evidence
is indexed by `data/RAW_FILE_MANIFEST.csv` when available, but large raw
calculation archives should be distributed through an external data repository
rather than GitHub.

## Manuscript PDFs

The compiled manuscript and supplementary PDFs are kept in `paper/` for
reference. LaTeX sources and figure assets are deliberately not included in
this code-focused public export.

## Regenerating This Repository

This repository is generated from the private workspace by:

```bash
python newvaspagent/tools/export_public_repo.py --clean --init-git
```

Only the export whitelist is copied. Do not manually mirror the private
workspace into this public repository.
"""

    gitignore = """# Python
__pycache__/
*.py[cod]

# Local environments and secrets
.env
.venv/
venv/
.litellm_autostart/
litellm_autostart_config.yaml
litellm_autostart.log

# LaTeX build outputs
*.aux
*.bbl
*.blg
*.fdb_latexmk
*.fls
*.log
*.out
*.synctex.gz
*.toc

# VASP restricted or heavy outputs
POTCAR
POTCAR_dir/
runs/
workspace/
logs/
CHG
CHGCAR
WAVECAR
WAVEDER
TMPCAR
PCDAT
PROCAR
DOSCAR
XDATCAR
vasprun.xml
OUTCAR
OSZICAR
REPORT

# Local backups
*.bak
*.bak_*
"""

    gitattributes = """*.tex text
*.bib text
*.md text
*.csv text
*.py text
*.svg text
*.png binary
*.jpg binary
*.jpeg binary
*.pdf binary
"""

    environment = """name: vasp-agent
channels:
  - conda-forge
dependencies:
  - python=3.10
  - pip
  - pip:
      - -r requirements.txt
"""

    license_text = """Copyright (c) 2026 VASP Agent authors.

No open-source license has been selected for this public companion repository
yet. Unless otherwise stated in a future LICENSE update, all rights are
reserved by the authors.
"""

    write_text(repo_dir / "README.md", readme, dry_run)
    write_text(repo_dir / "CITATION.cff", citation, dry_run)
    write_text(repo_dir / ".gitignore", gitignore, dry_run)
    write_text(repo_dir / ".gitattributes", gitattributes, dry_run)
    write_text(repo_dir / "environment.yml", environment, dry_run)
    write_text(repo_dir / "LICENSE", license_text, dry_run)


def initialize_git(repo_dir: Path, dry_run: bool) -> None:
    if not (repo_dir / ".git").exists():
        run(["git", "init"], cwd=repo_dir, dry_run=dry_run)
        run(["git", "checkout", "-B", "main"], cwd=repo_dir, dry_run=dry_run)
    existing = subprocess.run(
        ["git", "remote"],
        cwd=repo_dir,
        text=True,
        capture_output=True,
        check=False,
    )
    remotes = set(existing.stdout.split())
    if "origin" in remotes:
        run(["git", "remote", "set-url", "origin", GIT_REMOTE_URL], cwd=repo_dir, dry_run=dry_run)
    else:
        run(["git", "remote", "add", "origin", GIT_REMOTE_URL], cwd=repo_dir, dry_run=dry_run)


def main() -> None:
    args = parse_args()
    workspace = args.workspace_root.resolve()
    repo_dir = args.repo_dir.resolve()

    if not workspace.exists():
        raise FileNotFoundError(workspace)
    if workspace == repo_dir or repo_dir in workspace.parents:
        raise ValueError("Destination repository must not be the workspace root or its parent.")

    ensure_clean_destination(repo_dir, clean=args.clean, dry_run=args.dry_run)
    copy_manuscript(workspace, repo_dir, args.dry_run)
    copy_data_package(workspace, repo_dir, args.dry_run)
    copy_agent_code(workspace, repo_dir, args.dry_run)
    copy_skills(workspace, repo_dir, args.dry_run)
    write_project_files(repo_dir, args.dry_run)

    if args.init_git:
        initialize_git(repo_dir, args.dry_run)

    print(f"Export complete: {repo_dir}")


if __name__ == "__main__":
    main()
