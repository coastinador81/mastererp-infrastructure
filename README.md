# mastererp-infrastructure

Infraestructura de MasterERP. Cada módulo del diagrama es una carpeta con su `template.yaml`, igual que en uonify-capital-infrastructure.

## Foundation

Base compartida del ambiente.

- `templates/foundation/network/template.yaml`
- `templates/foundation/certificates/template.yaml`
- `templates/foundation/internal-dns/template.yaml`
- `templates/foundation/edge/template.yaml`
- `templates/foundation/documents/template.yaml`
- `templates/foundation/queues/template.yaml`
- `templates/foundation/security/template.yaml`
- `templates/foundation/cluster/template.yaml`
- `templates/shared/service/template.yaml`

## Cliente

- `templates/cliente/frontend/template.yaml`
- `templates/cliente/backend/template.yaml`
- `templates/cliente/login/template.yaml`

## Núcleo

- `templates/nucleo/guardias/template.yaml`
- `templates/nucleo/api/template.yaml`
- `templates/nucleo/wiz/gateway/template.yaml`
- `templates/nucleo/wiz/centro-ack/template.yaml`
- `templates/nucleo/motor/artifact-provider/template.yaml`
- `templates/nucleo/motor/argument-resolver/template.yaml`
- `templates/nucleo/motor/coordinador/template.yaml`
- `templates/nucleo/herramientas/registry/template.yaml`
- `templates/nucleo/herramientas/clientes/template.yaml`
- `templates/nucleo/herramientas/inventario/template.yaml`
- `templates/nucleo/herramientas/condiciones/template.yaml`
- `templates/nucleo/herramientas/producto/template.yaml`
- `templates/nucleo/herramientas/datos/template.yaml`
- `templates/nucleo/workers/messaging-gateway/template.yaml`
- `templates/nucleo/workers/rls-policy/template.yaml`
- `templates/nucleo/workers/billing/template.yaml`
- `templates/nucleo/workers/conversation/template.yaml`
- `templates/nucleo/workers/notification/template.yaml`

## Identidad

- `templates/identidad/google-oauth/template.yaml`
- `templates/identidad/vertex/template.yaml`
- `templates/identidad/google-drive/template.yaml`
- `templates/identidad/ses/template.yaml`

## Costos

- `templates/costos/analisis/template.yaml`
- `templates/costos/margen/template.yaml`
- `templates/costos/stripe/template.yaml`

## Datos y redes

- `templates/datos/postgres/template.yaml`
- `templates/datos/redis/template.yaml`
- `templates/datos/red-privada/template.yaml`
- `templates/datos/red-autorizada/template.yaml`

`environments/dev` compone la base que ya existe. Las cajas del diagrama que todavía no tienen servicio propio dejan un parámetro en SSM con valor `pendiente`.
