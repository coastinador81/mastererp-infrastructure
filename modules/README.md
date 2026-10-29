Cada módulo es una plantilla propia. El ambiente solo las compone.

- `network.yaml` — VPC, subredes, NAT y grupos de seguridad.
- `certificates.yaml` — certificados del borde y de las tiendas.
- `internal-dns.yaml` — zona privada del MCP.
- `edge.yaml` — balanceador, reglas por dominio y alias DNS.
- `database.yaml` — PostgreSQL.
- `documents.yaml` — bucket de documentos.
- `queues.yaml` — cola de flujos y su cola de errores.
- `identity.yaml` — roles de ejecución, datos, agentes y MCP.
- `cluster.yaml` — cluster Fargate.
- `service.yaml` — una entrada pública. El ambiente lo usa una vez por pantalla o API.

Los logs de cada servicio van dentro de `service.yaml`.
