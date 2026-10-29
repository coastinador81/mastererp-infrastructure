#!/usr/bin/env python3
"""Arma el stack padre de los módulos que solo marcan un parámetro SSM."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "templates"


def ssm_only(path: Path) -> bool:
    types = re.findall(r"^\s+Type:\s+(AWS::\S+)", path.read_text(), re.M)
    return types == ["AWS::SSM::Parameter"]


def logical_id(relative: str) -> str:
    token = re.sub(r"[^A-Za-z0-9]", "", relative)
    return "M" + token


def main() -> None:
    destination = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "build" / "modules.yaml"
    modules = sorted(
        path for path in TEMPLATES.rglob("template.yaml") if ssm_only(path)
    )
    lines = [
        'AWSTemplateFormatVersion: "2010-09-09"',
        'Description: "Marcadores SSM de los modulos. No crea red, base ni servicios."',
        "Parameters:",
        "  Environment:",
        "    Type: String",
        "    Default: dev",
        "    AllowedValues: [dev, qa, prod]",
        "Resources:",
    ]
    for path in modules:
        relative = path.relative_to(TEMPLATES).as_posix()
        parent_to_template = Path("..") / "templates" / relative
        lines.extend(
            [
                f"  {logical_id(relative)}:",
                "    Type: AWS::CloudFormation::Stack",
                "    Properties:",
                f"      TemplateURL: {parent_to_template.as_posix()}",
                "      Parameters:",
                "        Environment: !Ref Environment",
            ]
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text("\n".join(lines) + "\n")
    print(f"{len(modules)} modulos -> {destination}")


if __name__ == "__main__":
    main()
