"""Shortcuts for running project checks locally, via invoke.

Usage:
    inv test          # run the test suite
    inv lint           # run ruff
    inv typecheck      # run mypy
    inv build-local    # run lint, typecheck and test, in that order
"""

from invoke import task
from rich.console import Console

console = Console()

PACKAGE = "jiracli_pkg"
TESTS = "tests"


@task
def test(c):
    console.print("\n[bold cyan]=== test ===[/bold cyan]")
    c.run("pytest -q")


@task
def lint(c):
    console.print("\n[bold cyan]=== lint ===[/bold cyan]")
    c.run(f"ruff check {PACKAGE} {TESTS}")


@task
def typecheck(c):
    console.print("\n[bold cyan]=== typecheck ===[/bold cyan]")
    c.run(f"mypy {PACKAGE}")


@task(pre=[lint, typecheck, test])
def build_local(c):
    console.print("\n[bold green]Build passed.[/bold green] :white_check_mark:")