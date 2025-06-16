"""Command that can be run via `invoke <x>`."""

from invoke import task


@task
def run(c):
    """Run the bot."""
    c.run("python main.py")


@task
def venv(c):
    """Activate virtual environment."""
    c.run("source .venv/bin/activate")


@task
def lint(c):
    """Run Ruff to lint the code."""
    c.run("ruff check .")


@task
def format(c):
    """Format code using Ruff."""
    c.run("ruff format .")


@task
def fix(c):
    """Autofix lint errors with Ruff."""
    c.run("ruff check . --fix")


@task
def all(c):
    """Run all code quality tools."""
    lint(c)
    fix(c)
    format(c)
