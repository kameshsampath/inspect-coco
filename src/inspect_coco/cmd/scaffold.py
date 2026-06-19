"""inspect-coco scaffold — generate eval suites from plugin structure."""

from __future__ import annotations

import sys
from pathlib import Path

import click

from inspect_coco.idd import score_instruction


@click.command()
@click.option(
    "--plugin-dir",
    type=click.Path(exists=True),
    help="Skills directory to scan (default: auto-detect from .cortex-plugin/plugin.json).",
)
@click.option(
    "--output-dir",
    type=click.Path(),
    default="evals",
    help="Output directory for generated eval suites.",
)
@click.option(
    "--skill",
    "only_skills",
    multiple=True,
    help="Only scaffold these skills (repeatable).",
)
@click.option(
    "--ignore",
    "extra_ignores",
    multiple=True,
    help="Extra ignore patterns (repeatable).",
)
@click.option("--dry-run", is_flag=True, help="Show what would be generated without writing.")
def scaffold(
    plugin_dir: str | None,
    output_dir: str,
    only_skills: tuple[str, ...],
    extra_ignores: tuple[str, ...],
    dry_run: bool,
) -> None:
    """Generate eval suites from CoCo plugin/skill structure.

    Scans the current project for CoCo skills, filters out routers
    and ignored paths, and generates IDD-structured eval tasks.
    """
    from inspect_coco.scaffold import detect_plugin, filter_skills, generate_suite

    root = Path.cwd()
    plugin_path = Path(plugin_dir) if plugin_dir else None
    out = Path(output_dir)

    # Detect skills
    skills = detect_plugin(root, plugin_dir=plugin_path)
    if not skills:
        click.echo(
            "No skills found. Ensure .cortex-plugin/plugin.json exists or use --plugin-dir.",
            err=True,
        )
        sys.exit(1)

    click.echo(f"Detected {len(skills)} skill(s)")

    # Filter
    filtered = filter_skills(
        skills,
        project_root=root,
        extra_ignores=list(extra_ignores) if extra_ignores else None,
        only_skills=list(only_skills) if only_skills else None,
    )

    if not filtered:
        click.echo("No leaf skills remain after filtering (all routers or ignored).", err=True)
        sys.exit(1)

    click.echo(f"Generating evals for {len(filtered)} leaf skill(s):")
    for s in filtered:
        click.echo(f"  - {s.name}")

    # Generate
    all_files: list[Path] = []
    for skill in filtered:
        files = generate_suite(skill, output_dir=out, dry_run=dry_run)
        all_files.extend(files)

    if dry_run:
        click.echo(f"\n[DRY-RUN] Would create {len(all_files)} files:")
        for f in all_files:
            click.echo(f"  {f}")
        return

    click.echo(f"\nGenerated {len(all_files)} files in {out}/")

    # Run IDD check on generated instructions
    click.echo("\nIDD score check on generated instructions:")
    for skill in filtered:
        inst_path = out / skill.name / "basic-prompt" / "instruction.md"
        if inst_path.exists():
            score = score_instruction(inst_path.read_text())
            status = (
                click.style("PASS", fg="green")
                if score.total >= 0.6
                else click.style("WARN", fg="yellow")
            )
            click.echo(f"  {status} {skill.name}: {score.total:.2f}")

    click.echo("\nDone. Next steps:")
    click.echo("  1. Edit tests/test.sh in each task to add verification logic")
    click.echo("  2. Refine instruction.md Output section with specific success criteria")
    click.echo(f"  3. Run: inspect-coco idd-check {out}/")
    click.echo(f"  4. Run: inspect-coco run {out}/ --dry-run")
