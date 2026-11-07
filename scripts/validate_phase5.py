"""Validate resource ownership and authorization gates for phase 4 modules."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULES = (
    "2.3-ecommerce/2.3.4-catalog/2.3.4.1-products",
    "2.3-ecommerce/2.3.4-catalog/2.3.4.2-categories",
    "2.3-ecommerce/2.3.4-catalog/2.3.4.3-attributes",
    "2.3-ecommerce/2.3.4-catalog/2.3.4.4-brands",
    "2.3-ecommerce/2.3.4-catalog/2.3.4.5-suppliers",
    "2.1-inventory/2.1.1-inventory",
    "2.3-ecommerce/2.3.1-orders",
    "2.1-inventory/2.1.3-preparation",
    "2.10-transport/2.10.5-routes",
    "2.1-inventory/2.1.2-nodes",
    "2.3-ecommerce/2.3.2-stores",
    "2.10-transport/2.10.1-drivers",
)


def require(condition, message):
    if not condition:
        raise SystemExit("ERROR: " + message)


def main():
    routes = 0
    for relative in MODULES:
        folder = ROOT / "modules" / relative
        require((folder / "README.md").is_file(), f"README missing: {relative}")
        template = folder / "resources.yml"
        require(template.is_file() and template.stat().st_size, f"resources.yml missing: {relative}")
        require(len(template.read_text().splitlines()) <= 500, f"template exceeds 500 lines: {relative}")
        model = json.loads(template.read_text(encoding="utf-8"))
        resources = model.get("Resources", {})
        functions = [item for item in resources.values() if item.get("Type") == "AWS::Lambda::Function"]
        require(len(functions) == 1, f"one owned Lambda required: {relative}")
        for name, resource in resources.items():
            if resource.get("Type") != "AWS::ApiGatewayV2::Route":
                continue
            routes += 1
            authorization = resource.get("Properties", {}).get("AuthorizationType")
            public_catalog = relative.endswith("2.3.2-stores") and name == "PublicCatalogRoute"
            require(authorization == ("NONE" if public_catalog else "JWT"), f"route authorization mismatch: {relative}/{name}")
        require(not any(folder.glob("lambdas/**/resources.yml")), f"nested Lambda template forbidden: {relative}")
    print(f"OK: Phase 5 Infrastructure gates passed for {len(MODULES)} owners and {routes} routes.")


if __name__ == "__main__":
    main()
