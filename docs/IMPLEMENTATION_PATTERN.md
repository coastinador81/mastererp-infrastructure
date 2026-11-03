# Puerta de infraestructura para módulos

Cada capacidad declara sus recursos exclusivos una sola vez en el
`resources.yml` de su raíz funcional. El código Lambda permanece en Platform;
Infrastructure recibe un artefacto versionado mediante parámetros explícitos.

Las rutas administrativas usan el authorizer JWT compartido. Una ruta pública
requiere contrato documentado, respuesta de datos públicos y un permiso Lambda
acotado a su método/ruta. Los recursos compartidos no se duplican. Ninguna
plantilla se aplica como consecuencia de su validación local.

El código y las plantillas mantenidas manualmente tienen un máximo de 500 líneas
por archivo. Validación:

```text
python scripts/validate_phase5.py
python scripts/validate_structure.py
git diff --check
```
