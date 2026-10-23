"""Package the firebird-driver-python agent skill for distribution."""

import ast
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile


def driver_version(root: Path) -> str:
    """Read the version without importing the driver or loading a Firebird client."""
    version_file = root / "src" / "firebird" / "driver" / "__init__.py"
    for node in ast.parse(version_file.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "__VERSION__" for target in node.targets
        ):
            version = ast.literal_eval(node.value)
            if isinstance(version, str):
                return version
    raise ValueError(f"No literal __VERSION__ found in {version_file}")


def main() -> None:
    """Write a ZIP with the skill directory at its root."""
    root = Path(__file__).resolve().parent.parent
    skill = root / "skills" / "firebird-driver-python"
    if not (skill / "SKILL.md").is_file():
        raise FileNotFoundError(skill / "SKILL.md")
    archive_path = root / "dist" / f"firebird-driver-{driver_version(root)}-skill.zip"
    archive_path.parent.mkdir(exist_ok=True)

    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED) as archive:
        for path in sorted(skill.rglob("*")):
            if path.is_file():
                archive.write(path, path.relative_to(skill.parent))


if __name__ == "__main__":
    main()
