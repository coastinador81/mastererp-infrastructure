Ambiente de desarrollo en Oregon (us-west-2), cuenta 277352717693.

`foundation.yaml` conserva la red privada mínima y `platform.yaml` conserva PostgreSQL. Los demás recursos de aplicación se eliminan mediante `.github/workflows/cleanup-dev-to-database.yml`.

Las carpetas siguen el diagrama funcional, de la 1.0 a la 2.10, más las integraciones externas; son estructura documental y no crean recursos por sí solas.
